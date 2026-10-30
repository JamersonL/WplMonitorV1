#!/usr/bin/env python3
"""Create/update config/auth.json without putting passwords in shell history."""
import getpass
import hashlib
import json
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = Path(os.getenv("WPL_ADMIN_AUTH_FILE") or ROOT / "config" / "auth.json")


def main():
    username = input("Admin username: ").strip()
    if not username or len(username) > 100:
        raise SystemExit("Username must contain 1 to 100 characters.")
    password = getpass.getpass("Admin password (minimum 14 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if len(password) < 14:
        raise SystemExit("Password must contain at least 14 characters.")
    if password != confirm:
        raise SystemExit("Passwords do not match.")

    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1, dklen=64)
    record = {"username": username, "salt": salt.hex(), "password_hash": digest.hex(),
              "scrypt": {"n": 16384, "r": 8, "p": 1}}
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    temp = TARGET.with_suffix(TARGET.suffix + ".tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp, 0o600)
    os.replace(temp, TARGET)
    print(f"Administrator credentials saved to {TARGET}")


if __name__ == "__main__":
    main()
