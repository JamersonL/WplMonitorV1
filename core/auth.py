"""Scrypt-based administrator credential verification."""
import hashlib
import hmac
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


def auth_file_path():
    return Path(os.getenv("WPL_ADMIN_AUTH_FILE") or BASE_DIR / "config" / "auth.json")


def verify_admin(username: str, password: str) -> bool:
    try:
        with open(auth_file_path(), "r", encoding="utf-8") as handle:
            record = json.load(handle)
        if not hmac.compare_digest(str(record.get("username", "")), str(username or "")):
            return False
        salt = bytes.fromhex(record["salt"])
        expected = bytes.fromhex(record["password_hash"])
        params = record.get("scrypt", {})
        actual = hashlib.scrypt(str(password or "").encode("utf-8"), salt=salt,
            n=int(params.get("n", 16384)), r=int(params.get("r", 8)),
            p=int(params.get("p", 1)), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return False
