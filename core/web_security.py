"""CSRF helpers for the administrative forms."""
import hmac
import secrets
from flask import abort, session


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validate_csrf(provided):
    expected = session.get("_csrf_token", "")
    if not expected or not provided or not hmac.compare_digest(expected, provided):
        abort(400, description="Invalid or missing CSRF token.")
