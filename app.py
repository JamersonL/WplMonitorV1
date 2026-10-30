"""Flask application for the WplMonitorV1 administrative console."""
import os
from datetime import timedelta
from pathlib import Path

from flask import Flask, redirect, url_for
from blueprints.admin import admin_bp

BASE_DIR = Path(__file__).resolve().parent


def create_app(test_config=None):
    secret_key = os.getenv("WPL_ADMIN_SECRET_KEY")
    if not secret_key and not (test_config and test_config.get("TESTING")):
        raise RuntimeError("WPL_ADMIN_SECRET_KEY must be set before starting the WPL admin application.")

    app = Flask(__name__, template_folder=str(BASE_DIR / "templates"),
                 static_folder=str(BASE_DIR / "static_admin"),
                 static_url_path="/admin/static")
    app.config.update(
        SECRET_KEY=secret_key or "test-only-secret",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("WPL_ADMIN_COOKIE_SECURE", "true").lower() in ("1", "true", "yes"),
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=int(os.getenv("WPL_ADMIN_SESSION_MINUTES", "30"))),
        MAX_CONTENT_LENGTH=32 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    app.register_blueprint(admin_bp)

    @app.route("/", methods=["GET"])
    def root():
        return redirect(url_for("admin.alerts"))

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; "
            "frame-ancestors 'none'; base-uri 'self'")
        return response
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host=os.getenv("WPL_ADMIN_HOST", "127.0.0.1"),
            port=int(os.getenv("WPL_ADMIN_PORT", "8010")), debug=False)
