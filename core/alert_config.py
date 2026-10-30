"""Atomic, validated JSON storage for merchant alert rules."""
from __future__ import annotations

import copy
import json
import math
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "alerts.json"

DEFAULT_SETTINGS = {
    "schedule": {"start": "08:00", "end": "23:00"},
    "issuer": {
        "enabled": True,
        "min_transactions": 150,
        "max_approval_rate": 10.0,
        "max_recurring_percentage": 70.0,
        "cooldown_minutes": None,
    },
    "critical_drop": {
        "enabled": False,
        "threshold_percent": 30.0,
        "minimum_baseline_transactions": 150,
        "cooldown_minutes": 30,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def default_document():
    return {"version": 1, "defaults": copy.deepcopy(DEFAULT_SETTINGS), "merchants": {}}


def _number(value, field, minimum, maximum, integer=False):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        parsed = int(value) if integer else float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be {'an integer' if integer else 'numeric'}") from None
    if not math.isfinite(float(parsed)) or not minimum <= parsed <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return parsed


def _time_value(value, field):
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value):
        raise ValueError(f"{field} must use HH:MM format")
    hour, minute = (int(part) for part in value.split(":"))
    if hour > 23 or minute > 59:
        raise ValueError(f"{field} is not a valid time")
    return value


def validate_merchant_settings(settings):
    if not isinstance(settings, dict):
        raise ValueError("Merchant settings must be an object")
    schedule = settings.get("schedule", {})
    issuer = settings.get("issuer", {})
    critical = settings.get("critical_drop", {})
    if not all(isinstance(item, dict) for item in (schedule, issuer, critical)):
        raise ValueError("Schedule, issuer and critical_drop must be objects")
    start = _time_value(schedule.get("start"), "Schedule start")
    end = _time_value(schedule.get("end"), "Schedule end")
    if start == end:
        raise ValueError("Schedule start and end cannot be equal")

    def enabled(section, name):
        value = section.get("enabled")
        if not isinstance(value, bool):
            raise ValueError(f"{name}.enabled must be true or false")
        return value

    return {
        "schedule": {"start": start, "end": end},
        "issuer": {
            "enabled": enabled(issuer, "issuer"),
            "min_transactions": _number(issuer.get("min_transactions"), "Issuer minimum transactions", 0, 10000000, True),
            "max_approval_rate": _number(issuer.get("max_approval_rate"), "Issuer maximum approval rate", 0, 100),
            "max_recurring_percentage": _number(issuer.get("max_recurring_percentage"), "Issuer maximum recurring percentage", 0, 100),
            "cooldown_minutes": _number(issuer.get("cooldown_minutes"), "Issuer cooldown", 1, 10080, True),
        },
        "critical_drop": {
            "enabled": enabled(critical, "critical_drop"),
            "threshold_percent": _number(critical.get("threshold_percent"), "Critical Drop threshold", 0.1, 100),
            "minimum_baseline_transactions": _number(critical.get("minimum_baseline_transactions"), "Critical Drop minimum baseline transactions", 1, 10000000, True),
            "cooldown_minutes": _number(critical.get("cooldown_minutes"), "Critical Drop cooldown", 1, 10080, True),
        },
    }


class AlertConfigStore:
    """Reads the policy file on each call; changes apply on the next monitor cycle."""
    def __init__(self, path=None, legacy_window_minutes=15):
        configured_path = os.getenv("WPL_ALERTS_CONFIG")
        self.path = Path(configured_path or path or DEFAULT_CONFIG_PATH)
        self.legacy_window_minutes = max(1, int(legacy_window_minutes))

    @contextmanager
    def _exclusive_lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path.with_suffix(self.path.suffix + ".lock"), "a", encoding="utf-8") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_document(self):
        if not self.path.exists():
            return default_document()
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                document = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Alert configuration JSON is invalid: {exc}") from exc
        if not isinstance(document, dict) or not isinstance(document.get("merchants", {}), dict):
            raise ValueError("Alert configuration has an invalid structure")
        merged = _deep_merge(default_document(), document)
        merged["version"] = 1
        return merged

    def load(self):
        return self._read_document()

    def get_merchant(self, merchant_key):
        document = self._read_document()
        override = document["merchants"].get(merchant_key, {})
        if not isinstance(override, dict):
            raise ValueError(f"Configuration for merchant '{merchant_key}' must be an object")
        resolved = _deep_merge(document["defaults"], override)
        if resolved["issuer"].get("cooldown_minutes") is None:
            resolved["issuer"]["cooldown_minutes"] = self.legacy_window_minutes
        return resolved

    def save_merchant(self, merchant_key, settings):
        if not re.fullmatch(r"[a-z0-9_-]{1,100}", merchant_key or ""):
            raise ValueError("Invalid merchant key")
        validated = validate_merchant_settings(settings)
        with self._exclusive_lock():
            document = self._read_document()
            document["merchants"][merchant_key] = validated
            self._atomic_write(document)

    def _atomic_write(self, document):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            backup_dir = self.path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup_path = backup_dir / f"{self.path.stem}_{stamp}{self.path.suffix}"
            backup_path.write_bytes(self.path.read_bytes())
            try:
                os.chmod(backup_path, 0o600)
            except OSError:
                pass
        fd, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(document, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
