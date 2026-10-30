"""Alert evaluations and persistent per-merchant/per-alert cooldown state."""

import html
import json
import os
import tempfile
from datetime import datetime, time, timedelta
from pathlib import Path
from urllib.parse import quote

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = BASE_DIR / "config" / "alert_state.json"


def _parse_clock(value):
    hour, minute = (int(part) for part in value.split(":"))
    return time(hour, minute)


def is_within_schedule(now_time, schedule):
    start = _parse_clock(schedule["start"])
    end = _parse_clock(schedule["end"])
    if start < end:
        return start <= now_time <= end
    return now_time >= start or now_time <= end


def filter_issuer_alerts(df, rules):
    if df is None:
        return df
    if not rules.get("enabled", True) or df.empty:
        return df.iloc[0:0].copy()
    return df[
        (df["total_tx"] > int(rules["min_transactions"])) &
        (df["approval_rate"] < float(rules["max_approval_rate"])) &
        (df["recurring_percentage"] < float(rules["max_recurring_percentage"]))
    ]


def evaluate_critical_drop(current_total, baseline_total, rules):
    if not rules.get("enabled", False):
        return None
    current = max(0, int(current_total or 0))
    baseline = max(0, int(baseline_total or 0))
    minimum = int(rules["minimum_baseline_transactions"])
    threshold = float(rules["threshold_percent"])
    if baseline < minimum or baseline <= 0:
        return None
    drop_percent = ((baseline - current) / baseline) * 100.0
    if drop_percent < threshold:
        return None
    return {"current_total": current, "baseline_total": baseline,
            "drop_percent": round(drop_percent, 2), "threshold_percent": threshold}


class AlertStateStore:
    """Persist alert timestamps to prevent cooldown resets after service restarts."""
    def __init__(self, path=None):
        self.path = Path(os.getenv("WPL_ALERT_STATE_FILE") or path or DEFAULT_STATE_PATH)

    def _read(self):
        if not self.path.exists():
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def cooldown_remaining(self, merchant_key, alert_type, cooldown_minutes, now=None):
        now = now or datetime.now()
        raw = self._read().get(f"{merchant_key}:{alert_type}")
        if not raw:
            return None
        try:
            last_sent = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")
        except (TypeError, ValueError):
            return None
        remaining = timedelta(minutes=int(cooldown_minutes)) - (now - last_sent)
        return remaining if remaining.total_seconds() > 0 else None

    def mark_sent(self, merchant_key, alert_type, now=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._read()
        payload[f"{merchant_key}:{alert_type}"] = (now or datetime.now()).isoformat(timespec="seconds")
        fd, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
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


def build_critical_drop_email(merchant_name, current_total, baseline_total, drop_percent,
                              threshold_percent, window_minutes, app_base_url="", merchant_slug=""):
    name = html.escape(str(merchant_name))
    safe_url = ""
    if app_base_url and merchant_slug:
        safe_url = f"{app_base_url.rstrip('/')}/reports/{quote(merchant_slug)}_issuers.html"
    link_html = f'<p><a href="{html.escape(safe_url, quote=True)}">Open merchant dashboard</a></p>' if safe_url else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Critical Drop Alert - {name}</title>
<style>body{{margin:0;padding:24px;background:#f5f7fa;color:#20262e;font:15px/1.5 Arial,sans-serif}}.container{{max-width:720px;margin:auto;background:#fff;border-radius:12px;padding:24px;border-top:5px solid #d93d3d}}h2{{color:#003a70;margin-top:0}}.metric{{font-size:28px;font-weight:bold;color:#003a70}}.muted{{color:#5a6b7b;font-size:12px}}</style>
</head><body><div class="container">
<h2>Critical Transaction Volume Drop</h2><p><strong>Merchant:</strong> {name}</p>
<p>Transaction volume in the last {int(window_minutes)} minutes dropped by:</p>
<p class="metric">{float(drop_percent):.2f}%</p>
<p><strong>Current window:</strong> {int(current_total):,} transactions</p>
<p><strong>Equivalent D-7 window:</strong> {int(baseline_total):,} transactions</p>
<p><strong>Configured threshold:</strong> {float(threshold_percent):.2f}%</p>
{link_html}<p class="muted">WPL LatAm TSO Monitoring • Automated alert</p>
</div></body></html>"""
