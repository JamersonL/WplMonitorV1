# WplMonitorV1 — Merchant Alert Administration

This feature adds an authenticated Flask administration console at the URL path /admin/alerts. It does not replace the existing monitoring dashboard or remove existing issuer alerts.

## Alert behavior

### Existing issuer alert

The original issuer conditions remain the defaults and can be configured per merchant:

- Issuer transaction count must be greater than min_transactions.
- Issuer approval rate must be less than max_approval_rate.
- Issuer recurring percentage must be less than max_recurring_percentage.

Default thresholds remain 150 transactions, 10% approval rate and 70% recurring percentage. The default issuer cooldown follows the existing WINDOW_MINUTES setting unless a merchant override is saved.

### New Critical Drop alert

For each merchant, compare the transaction count in the current WINDOW_MINUTES interval with the equivalent interval exactly seven days earlier:

    drop_percent = ((D7_total - current_total) / D7_total) * 100

Trigger when all of the following are true:

- critical_drop.enabled is true;
- D-7 baseline is at least minimum_baseline_transactions;
- calculated drop is greater than or equal to threshold_percent;
- merchant is inside its configured alert schedule; and
- that merchant's Critical Drop cooldown has expired.

A merchant without a qualifying D-7 baseline will not trigger a Critical Drop alert. Volume growth will not trigger. Issuer and Critical Drop cooldowns are tracked independently and persisted. Critical Drop is disabled by default until explicitly enabled.

## Runtime files

The following files are generated locally and must not be committed:

- config/alerts.json: active alert policy.
- config/auth.json: scrypt administrator credential hash.
- config/alert_state.json: last successful alert timestamps.
- config/backups/: automatic timestamped backups before policy updates.

The active files are excluded by .gitignore. The monitor and admin web process must both be able to read/write the active configuration and state files. Easiest secure deployment is to run both under the same dedicated, non-root service account. Do not change the existing production service account without checking the operational impact first.

Environment variables:

- WPL_ADMIN_SECRET_KEY: required, long random Flask session secret.
- WPL_ADMIN_AUTH_FILE: optional alternate path to administrator credentials.
- WPL_ALERTS_CONFIG: optional alternate alert configuration path.
- WPL_ALERT_STATE_FILE: optional alternate alert cooldown-state path.
- WPL_ADMIN_HOST: optional bind host; defaults to 127.0.0.1.
- WPL_ADMIN_PORT: optional bind port; defaults to 8010.
- WPL_ADMIN_COOKIE_SECURE: defaults to true; set false only for local HTTP development.
- WPL_ADMIN_SESSION_MINUTES: administrator session lifetime; defaults to 30.

## Install and initialize

Use the same Python environment as WplMonitorV1:

    python3 -m pip install -r requirements-admin.txt
    mkdir -p config/backups
    python3 scripts/create_admin_auth.py

The credential helper prompts interactively and stores only a salted scrypt hash. It does not put the password in shell history.

Generate a session secret:

    python3 -c 'import secrets; print(secrets.token_urlsafe(48))'

Store the value as WPL_ADMIN_SECRET_KEY in a protected environment file or systemd EnvironmentFile. Do not commit it.

Optionally seed config/alerts.json from config/alerts.example.json:

    cp config/alerts.example.json config/alerts.json
    chmod 600 config/alerts.json

Replace the example merchant_slug key with the real merchant key. Keys are generated from the first alias in clientsT1.txt using the existing slugify helper. If the active JSON file is absent, built-in defaults are used and the file is created on the first save.

## Run locally

    WPL_ADMIN_COOKIE_SECURE=false WPL_ADMIN_SECRET_KEY='local-development-only-secret' python3 app.py

Open http://127.0.0.1:8010/admin/alerts.

For production, run behind Apache/Nginx over HTTPS and bind Flask to localhost:

    gunicorn --workers 2 --bind 127.0.0.1:8010 --timeout 30 wsgi:app

Example Apache reverse-proxy mapping (merge with the existing virtual host; do not replace dashboard mappings):

    ProxyPreserveHost On
    ProxyPass        /admin/ http://127.0.0.1:8010/admin/
    ProxyPassReverse /admin/ http://127.0.0.1:8010/admin/

The administrative app uses a secure session cookie, scrypt authentication, CSRF validation, standard security headers and no public link from the dashboard. Restrict /admin/ further at the network layer, VPN or Apache access-control layer where appropriate.

## Operational behavior

- main.py reads alert rules for each merchant on every monitoring cycle. Saved changes take effect on the next cycle; the monitor does not need a restart.
- Configuration changes are validated and written atomically. Previous versions are copied to config/backups/.
- Alert timestamps are stored separately by merchant and alert type, so a process restart does not reset cooldown.
- The admin process and monitoring process must use the same WPL_ALERTS_CONFIG and WPL_ALERT_STATE_FILE values.
- The admin process reads the same clientsT1.txt file under directory_path.
- Do not run multiple monitor instances against the same alert-state file unless a shared locking policy is added.

## Tests

    python3 -m pip install -r requirements-admin.txt
    python3 -m unittest discover -s tests -v

## Deployment note

This feature adds a separate Flask/Gunicorn web process. It does not convert main.py into a Flask request handler. Deploy the web process as a separate systemd service and add the reverse-proxy mapping only after staging verification. The existing WPL monitor service remains the alert sender.
