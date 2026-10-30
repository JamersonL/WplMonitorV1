"""Authenticated administrative pages for merchant alert configuration."""
from __future__ import annotations

from functools import wraps
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for

from config import WINDOW_MINUTES, directory_path
from core.alert_config import AlertConfigStore
from core.auth import verify_admin
from core.web_security import csrf_token, validate_csrf
from utils import parse_clients_file, slugify

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _config_store():
    return AlertConfigStore(legacy_window_minutes=WINDOW_MINUTES)


def _merchant_registry():
    clients_path = Path(directory_path) / "clientsT1.txt"
    if not clients_path.is_file():
        current_app.logger.error("Merchant list not found: %s", clients_path)
        return []
    merchants, seen = [], set()
    for aliases in parse_clients_file(str(clients_path)):
        if not aliases:
            continue
        name = aliases[0]
        key = slugify(name.lower())
        if key and key not in seen:
            seen.add(key)
            merchants.append({"key": key, "name": name, "aliases": aliases})
    return merchants


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@admin_bp.context_processor
def inject_template_helpers():
    return {"csrf_token": csrf_token}


@admin_bp.get("")
def admin_home():
    return redirect(url_for("admin.alerts"))


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_authenticated"):
        return redirect(url_for("admin.alerts"))
    if request.method == "POST":
        validate_csrf(request.form.get("csrf_token"))
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if verify_admin(username, password):
            session.clear()
            session["admin_authenticated"] = True
            session["admin_username"] = username
            session.permanent = True
            target = request.args.get("next", "")
            if not target.startswith("/admin/") or target.startswith("//"):
                target = url_for("admin.alerts")
            return redirect(target)
        flash("Invalid username or password.", "error")
    return render_template("manager/login.html")


@admin_bp.post("/logout")
@_login_required
def logout():
    validate_csrf(request.form.get("csrf_token"))
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("admin.login"))


@admin_bp.route("/alerts", methods=["GET", "POST"])
@_login_required
def alerts():
    merchants = _merchant_registry()
    if not merchants:
        return render_template("manager/alerts.html", merchants=[], selected=None, settings=None,
            error="No merchants were found in clientsT1.txt. Check the configured directory."), 503

    merchant_key = request.args.get("merchant") or request.form.get("merchant") or merchants[0]["key"]
    selected = next((item for item in merchants if item["key"] == merchant_key), None)
    if selected is None:
        abort(404)

    store = _config_store()
    error = None
    try:
        settings = store.get_merchant(selected["key"])
    except (OSError, ValueError) as exc:
        current_app.logger.exception("Unable to read alert configuration")
        settings, error = None, f"Unable to load alert configuration: {exc}"

    if request.method == "POST":
        validate_csrf(request.form.get("csrf_token"))
        if settings is None:
            abort(503, description=error or "Alert configuration is unavailable.")
        payload = {
            "schedule": {
                "start": request.form.get("schedule_start", ""),
                "end": request.form.get("schedule_end", ""),
            },
            "issuer": {
                "enabled": request.form.get("issuer_enabled") == "on",
                "min_transactions": request.form.get("issuer_min_transactions", ""),
                "max_approval_rate": request.form.get("issuer_max_approval_rate", ""),
                "max_recurring_percentage": request.form.get("issuer_max_recurring_percentage", ""),
                "cooldown_minutes": request.form.get("issuer_cooldown_minutes", ""),
            },
            "critical_drop": {
                "enabled": request.form.get("critical_drop_enabled") == "on",
                "threshold_percent": request.form.get("critical_drop_threshold", ""),
                "minimum_baseline_transactions": request.form.get("critical_drop_minimum_baseline", ""),
                "cooldown_minutes": request.form.get("critical_drop_cooldown_minutes", ""),
            },
        }
        try:
            store.save_merchant(selected["key"], payload)
            flash(f"Alert rules for {selected['name']} were saved successfully.", "success")
            return redirect(url_for("admin.alerts", merchant=selected["key"]))
        except ValueError as exc:
            error, settings = str(exc), payload

    return render_template("manager/alerts.html", merchants=merchants, selected=selected,
                           settings=settings, error=error)
