# WplMonitorV1 — Scope, Architecture & AI Agent Developer Guidelines

> **Purpose:** This document is the technical contract for contributors and AI coding agents working on **WplMonitorV1**. Read it before changing source code, database access, monitoring rules, report generation, alerting, configuration, or runtime behavior.

---

## Table of Contents

1. Core Mission & Architectural Principles
2. Absolute Project Constraints
3. Domain Knowledge & Payment Terminology
4. Monitored Database Schema Reference
5. Configuration Reference
6. Component Architecture & Execution Flow
7. Detailed Module & Function Reference
8. Monitoring, Comparison & Alert Logic
9. Reporting & Visualization Rules
10. Runtime, Operations & Deployment
11. AI Agent Extension Recipes
12. Testing, Verification & Gotchas
13. Security & Hardening Priorities

---

# 1. Core Mission & Architectural Principles

## 1.1 Mission

WplMonitorV1 is a Python-based operational monitoring solution for payment transaction processing.

Its main purpose is to provide near-real-time operational visibility for Tier-1 merchants across LATAM by:

- reading merchant aliases from `clientsT1.txt`;
- querying PostgreSQL transaction data;
- calculating approval, decline, recurring and volume metrics;
- identifying issuer-level degradation;
- comparing the current monitoring window with the equivalent period seven days earlier;
- collecting schema and acquisition performance;
- generating HTML dashboards with embedded Matplotlib charts;
- sending alert e-mails when configured issuer-level conditions are met.

The application is an **operational monitoring daemon**, not a general-purpose web application and not a persistent data-management system.

## 1.2 Architectural principles

### Read-oriented monitoring

The application consumes operational transaction data from PostgreSQL. Monitoring logic must remain read-oriented.

### File-based operational configuration

Merchant lists, database parameters, report paths, recipients and HTML styling are primarily defined in source/configuration files and environment variables rather than persisted application metadata.

### Continuous execution

The normal mode uses `RUN_FOREVER = 1` and executes approximately once per minute.

### HTML-first reporting

The current reporting mechanism is server-side HTML generation. Charts are rendered by Matplotlib and embedded as Base64 PNG images.

### Minimal architectural footprint

The V1 architecture is intentionally simple:

```text
clientsT1.txt
      |
      v
   main.py
      |
      +------------------+
      |                  |
      v                  v
db_helpers.py        charts.py
      |                  |
      v                  |
 PostgreSQL              |
      |                  |
      +--------+----------+
               |
               v
      html_templates.py
               |
               v
       HTML report files
               |
               +--> e-mail alerts
```

Do not introduce a new framework, persistence layer, service layer or deployment architecture merely for code style. New architecture must solve a documented operational problem.

---

# 2. Absolute Project Constraints

These rules are non-negotiable unless the project owner explicitly requests a change.

## 2.1 Do not mutate the monitored database

All monitoring SQL must be read-only.

Agents must not:

- create or alter tables;
- create indexes, sequences or schemas;
- insert, update or delete monitoring metadata;
- store application sessions or configuration in PostgreSQL;
- add database-side objects solely to support the monitor.

When introducing SQL, prefer explicit read-only semantics and preserve the existing schema.

## 2.2 Preserve the current monitoring model

Do not change the meaning of:

- approval status;
- issuer identification;
- recurring-transaction detection;
- D-7 comparison;
- Tier-1 merchant alias matching;
- country/acquisition technology mapping;

unless the requested change explicitly concerns business logic.

## 2.3 Preserve the continuous runner

The normal execution model is:

```text
run_once()
    -> process all configured clients
    -> produce merchant reports
    -> evaluate alarms
    -> build consolidated schema dashboard
    -> wait until next minute
    -> repeat
```

Avoid introducing multiple independent infinite loops.

## 2.4 Do not silently disable alerting

Alert e-mail delivery is a functional part of V1.

Changes to alert conditions, recipients, delivery mechanism or cooldown behavior must be explicit and documented.

## 2.5 Preserve operational file paths unless requested

The following runtime locations are operationally significant:

- `/data/wpl_reports/`
- `/var/www/html/tier1/byissuer/reports/`
- `wplreport.log`

Do not replace absolute paths with arbitrary new locations without considering the production runtime.

## 2.6 Avoid committing secrets

Do not add new credentials, API keys, tokens, private keys or passwords to source control.

If an existing deployment contains infrastructure-specific credentials, do not copy or expose them in documentation, examples, tests or new source files.

---

# 3. Domain Knowledge & Payment Terminology

## 3.1 Merchant / client identification

Tier-1 clients are represented as one or more aliases on each line of `clientsT1.txt`.

Example:

```text
'PedidosYa','PEDIDOS YA'
'JETSMART','Jetsmart Argentina'
'Tam Linhas Aereas','Tam Linhas Aéreas','TAM LINHAS AEREAS SA'
```

Aliases are matched against:

```text
clientes.nome_loja_resumido
```

Multiple aliases on one line represent the same logical merchant grouping.

Lines beginning with `#` are disabled/commented and must not be treated as active clients.

## 3.2 Authorization status

Current transaction approval semantics:

- `status_autorizacao = '00'` → approved;
- other values → not approved / declined for reporting purposes.

The distinction between business declines and technical failures must not be invented unless the underlying source data or existing code supports it.

## 3.3 Issuer bank

Issuer identification is derived from JSON data in `campos_transacoes_json.dados`.

Preferred source:

```text
BinTable_BancoEmissor
```

Fallback:

```text
IssuerName
```

Unknown issuer values are normalized to `Unknown` by the current query logic.

## 3.4 Recurring transactions

Recurring percentage is calculated from:

```text
dados->>'storedCredentials_merchantInitiatedReason' = 'RECURRING'
```

Do not redefine recurring traffic using a different field unless the data model is explicitly updated.

## 3.5 Schema / administradora

Schema performance is grouped using:

```text
transacoes_aprova_facil.administradora
```

The consolidated dashboard compares current activity with the equivalent seven-day-earlier window.

## 3.6 Acquisition / technology mapping

The current country mapping is:

| Country | Technology codes |
| --- | --- |
| Argentina | `AR` |
| Brazil | `RB`, `WL` |
| Colombia | `RC` |
| Mexico | `RM`, `PS` |

Do not change these mappings without verifying the payment-routing meaning with the project owner.

---

# 4. Monitored Database Schema Reference

The V1 monitor relies on the following PostgreSQL tables.

## 4.1 CLIENTES

Primary logical role: merchant lookup.

Relevant column:

```text
codigo_cliente
nome_loja_resumido
```

## 4.2 TRANSACOES_APROVA_FACIL

Primary logical role: transaction facts.

Relevant columns include:

```text
numero_transacao
codigo_cliente
administradora
tipo_tecnologia
status_autorizacao
valor_transacao
moeda
data_hora_recebimento
data_hora_processamento
```

## 4.3 CAMPOS_TRANSACOES_JSON

Primary logical role: JSON transaction attributes.

Join key:

```text
numero_transacao
```

JSON field:

```text
dados
```

Known attributes used by V1:

- `BinTable_BancoEmissor`
- `IssuerName`
- `storedCredentials_merchantInitiatedReason`
- other JSON attributes may be consumed by specialized queries when required.

## 4.4 Database session timezone

`pg_connect()` sets the PostgreSQL session timezone from:

```text
TZ_DISPLAY
```

Default:

```text
America/Sao_Paulo
```

Changes to date/time SQL must preserve this timezone behavior.

---

# 5. Configuration Reference

## 5.1 Environment-supported parameters

| Variable | Default / role |
| --- | --- |
| `MERCHANT_NAMES` | `PedidosYa,PEDIDOS YA` |
| `HTML_OUTPUT` | Legacy/default merchant report path |
| `WINDOW_MINUTES` | `15` |
| `TS_MINUTES` | `120` |
| `TOP_N_ISSUERS` | `10` |
| `REFRESH_SECONDS` | `60` |
| `TZ_DISPLAY` | `America/Sao_Paulo` |

## 5.2 Code-defined operational settings

The current V1 configuration also contains:

- `PG_CONN_OPTS`
- `directory_path`
- `recipients_adm`
- `recipients`
- `report_path`
- `RUN_FOREVER`
- `html_style`

These values are operationally significant.

## 5.3 HTML styling

Shared report styling is stored in `config.py` as `html_style`.

The current theme uses:

- dark/deep blue;
- Worldpay-oriented blue/cyan accents;
- KPI cards;
- responsive grid layout;
- approval badges;
- warning/error indicators;
- embedded chart presentation;
- print styling.

A visual redesign should preferably be isolated to:

- `config.py` CSS;
- `html_templates.py` markup;
- `charts.py` chart palette/formatting.

Do not couple a purely visual change to SQL logic.

---

# 6. Component Architecture & Execution Flow

## 6.1 main.py

`main.py` is the application orchestrator.

Responsibilities:

1. Open/reopen PostgreSQL connection.
2. Validate report and working directories.
3. Parse `clientsT1.txt`.
4. Process each merchant alias group.
5. Calculate current and D-7 metrics.
6. Retrieve worst issuers.
7. Retrieve the time series.
8. Generate merchant charts.
9. Render merchant HTML report.
10. Write report files.
11. Evaluate issuer alert conditions.
12. Send configured alert e-mails.
13. Query schema performance.
14. Query acquisition data for AR/BR/CO/MX.
15. Build `schemas_full.html`.
16. Log execution.
17. Sleep until the next minute.

## 6.2 db_helpers.py

Responsible for:

- PostgreSQL connections;
- session timezone setup;
- monitoring SQL;
- metric aggregation;
- schema/acquisition queries;
- retry/reconnect behavior;
- conversion of selected results into pandas DataFrames.

## 6.3 charts.py

Responsible for:

- Matplotlib figure creation;
- approval-rate/time-series visualization;
- issuer-decline visualization;
- Base64 PNG conversion.

Charts are embedded into HTML rather than served as separate static image files.

## 6.4 html_templates.py

Responsible for:

- merchant dashboard HTML;
- internal alert e-mail HTML;
- client e-mail HTML;
- consolidated schema/acquisition dashboard HTML.

This module currently contains a large amount of inline HTML/CSS.

## 6.5 utils.py

Responsible for:

- e-mail delivery through local `sendmail`;
- alternate `mutt` delivery;
- integer/currency formatting;
- parsing `clientsT1.txt`;
- slug generation for report filenames.

## 6.6 clientsT1.txt

Runtime merchant configuration.

It is not merely documentation. Changing it changes which merchants are monitored.

## 6.7 restart.sh

Operational helper that stops the current process based on the log and starts:

```bash
nohup /data/wpl_reports/main.py &
```

Changes to this script must consider production process management and permissions.

---

# 7. Detailed Module & Function Reference

## 7.1 db_helpers.py

### `pg_connect()`

Creates a PostgreSQL connection using `PG_CONN_OPTS` and applies `TZ_DISPLAY`.

### `retry_on_recovery_conflict`

Decorator used by read functions.

Current recovery strategy:

1. rollback when possible;
2. execute the wrapped function;
3. catch recovery/interface/operational failures;
4. close the unusable connection;
5. wait using exponential backoff;
6. recreate the connection;
7. retry.

Current settings:

- maximum attempts: `20`;
- base sleep: `5` seconds;
- backoff factor: `2.0`.

Do not increase retry counts or sleeps without considering the effect on the one-minute monitoring cycle.

### `fetch_overall_metrics()`

Returns current aggregate transaction volume and approval statistics.

### `fetch_worst_issuers()`

Returns issuer-level transaction, approval, decline and recurring metrics, ordered by operational degradation indicators.

### `fetch_timeseries()`

Builds minute-level time-series data used by the approval/volume chart.

### Daily metrics functions

Functions including:

- `fetch_daily_metrics()`
- `fetch_daily_currency_totals()`

provide day-level operational summaries and currency breakdowns.

### Schema and acquisition functions

Functions including:

- `fetch_schema_data()`
- `fetch_acq_data()`

feed the consolidated dashboard.

## 7.2 charts.py

### `fig_to_b64(fig)`

Converts a Matplotlib figure to Base64-encoded PNG.

### `plot_timeseries(...)`

Creates a dual-axis visualization:

- transaction volume as bars;
- approval rate as a line;
- configurable lookback in minutes.

### `plot_worst(...)`

Creates a horizontal bar chart of declining issuers.

## 7.3 html_templates.py

Important builders include:

- `build_html()`
- `build_html_mail()`
- `build_html_mail_client()`
- `build_schemas_html()`

Any template modification must preserve the data keys expected by `main.py`.

## 7.4 utils.py

Important helpers:

- `send_email_mail()`
- `send_email_mutt()`
- `fmt_int()`
- `fmt_money()`
- `parse_clients_file()`
- `slugify()`

---

# 8. Monitoring, Comparison & Alert Logic

## 8.1 Current monitoring window

Default:

```text
WINDOW_MINUTES = 15
```

This controls the main near-real-time operational window.

## 8.2 Time-series lookback

Default:

```text
TS_MINUTES = 120
```

This controls chart history.

## 8.3 D-7 comparison

The application calculates many current metrics twice:

- `days_ago = 0`
- `days_ago = 7`

For schema comparisons, it calculates deltas such as:

```text
approval_rate_delta
declined_delta
total_tx_delta
recurring_delta
```

Do not silently switch the baseline to a different period.

## 8.4 Issuer alert condition

Current issuer alert condition:

```text
total_tx > 150
AND approval_rate < 10%
AND recurring_percentage < 70%
```

All conditions must be true before an issuer enters the alert set.

## 8.5 Alert hours

Current e-mail alerting is restricted to:

```text
08:00 through 23:00
```

This is business/operational behavior, not presentation logic.

## 8.6 Cooldown

`main.py` stores the last alert timestamp in:

```python
last_alarm_time
```

The cooldown is based on:

```text
ALARM_COOLDOWN = WINDOW_MINUTES
```

State is process-local and is reset whenever the daemon restarts.

## 8.7 Alert recipients

There are two recipient groups:

- administrative/internal recipients;
- client/operational recipients.

The exact lists are configured in `config.py`.

Do not copy real recipient addresses into tests or examples.

---

# 9. Reporting & Visualization Rules

## 9.1 Merchant reports

Each active client group produces a merchant-specific HTML report.

The filename is derived from the first alias using `slugify()` and written under `report_path`.

## 9.2 Consolidated dashboard

The application writes:

```text
schemas_full.html
```

It consolidates:

- acquisition information;
- schema comparison;
- client-level status cards.

## 9.3 Refresh

Generated dashboards use an HTML refresh interval based on:

```text
REFRESH_SECONDS
```

Default: 60 seconds.

## 9.4 Chart data format

Charts are embedded as:

```text
data:image/png;base64,...
```

Do not introduce external image dependencies unless explicitly requested.

## 9.5 Status semantics

Keep the existing visual relationship between:

- healthy / positive;
- warning;
- error / degradation.

When changing thresholds used for styling, verify whether they are also used by alerting or only presentation.

---

# 10. Runtime, Operations & Deployment

## 10.1 Standard execution

Primary command:

```bash
python3 main.py
```

## 10.2 Continuous execution

Current production mode:

```text
RUN_FOREVER = 1
```

The main loop runs approximately once per minute.

## 10.3 Background execution

The existing helper uses:

```bash
nohup /data/wpl_reports/main.py &
```

## 10.4 Runtime directories

The process expects the configured directory and report destination to exist and be writable.

## 10.5 Logging

The application writes operational messages to:

```text
wplreport.log
```

The log captures:

- processing status;
- report generation;
- schema/acquisition summaries;
- retry conditions;
- alert dispatch;
- exceptions.

Do not remove logging from critical operational paths merely to reduce output.

## 10.6 Host dependencies

The current e-mail implementation expects local OS tooling:

- `/usr/sbin/sendmail`;
- optionally `mutt`.

Any containerization effort must explicitly account for this dependency.

---

# 11. AI Agent Extension Recipes

## 11.1 Add a new monitored merchant

1. Add the merchant or aliases to `clientsT1.txt`.
2. Preserve one logical merchant grouping per line.
3. Use exact aliases that match `clientes.nome_loja_resumido`.
4. Run one monitoring cycle.
5. Verify the merchant report was generated.
6. Verify the consolidated dashboard includes the merchant.
7. Verify alert logic remains correct.

## 11.2 Change monitoring window

Update:

```text
WINDOW_MINUTES
```

Then verify:

- SQL date window;
- D-7 comparison;
- alert cooldown;
- report labels;
- chart titles.

These behaviors are coupled.

## 11.3 Change chart appearance

Modify `charts.py` and, where needed, `config.py`.

Verify both:

- time-series chart;
- worst-issuer chart.

Do not change query output shape for a purely visual change.

## 11.4 Change dashboard appearance

Modify `html_templates.py` and/or `config.py::html_style`.

Preserve the data contract from `main.py`.

After modification, render:

- at least one merchant report;
- `schemas_full.html`;
- internal alert e-mail HTML;
- client alert e-mail HTML when applicable.

## 11.5 Change alert thresholds

Update the condition in `main.py` and document:

- new threshold;
- operational rationale;
- expected effect;
- cooldown implications.

Never alter alert criteria as a side effect of a refactor.

## 11.6 Add a new metric

Preferred sequence:

1. identify source table/field;
2. add a read-only query in `db_helpers.py`;
3. return a stable field name;
4. consume it in `main.py`;
5. expose it in the appropriate HTML builder;
6. add focused verification.

Avoid embedding new SQL directly inside HTML-generation code.

---

# 12. Testing, Verification & Gotchas

## 12.1 Minimum verification after source changes

At minimum:

```bash
python3 -m py_compile main.py db_helpers.py charts.py html_templates.py utils.py config.py
```

Then run a controlled application cycle when database access is available.

## 12.2 HTML verification

Verify generated HTML is:

- syntactically complete;
- readable in a browser;
- free from broken Base64 images;
- compatible with the configured refresh interval;
- populated with the expected client and issuer values.

## 12.3 Alert verification

When changing alert logic, test cases should cover:

1. threshold not met;
2. threshold met;
3. outside alert hours;
4. cooldown active;
5. cooldown expired;
6. empty issuer result;
7. database failure/reconnect.

## 12.4 Database failure behavior

The retry decorator is a critical availability feature.

Do not remove:

- rollback handling;
- connection close/recreate;
- exponential backoff;
- logging.

Be careful with any change that can cause a long blocking retry sequence because it may delay the next monitoring cycle.

## 12.5 Timezone gotchas

The code uses both:

- PostgreSQL session time zone via `SET TIME ZONE`;
- Python `datetime.now()`.

When changing date/time handling, verify that the two remain operationally aligned with `TZ_DISPLAY`.

## 12.6 Process-local cooldown

Alert cooldown is not persisted.

After restart, the monitor can alert again immediately if conditions are still met and the alert window is open.

Do not describe the cooldown as durable state.

## 12.7 Client file parsing

`parse_clients_file()` supports:

- single client names;
- comma-separated aliases using single quotes;
- commented lines beginning with `#`.

Do not replace it with a parser that breaks existing client syntax.

## 12.8 Legacy/unused variables

Some configuration values and functions are historical or compatibility-oriented.

Before deleting anything, verify references across:

- `main.py`;
- `db_helpers.py`;
- `charts.py`;
- `html_templates.py`;
- `utils.py`;
- operational scripts.

## 12.9 Runtime artifact

`nohup.out` is a runtime artifact and is not required for core source-code behavior.

Avoid treating it as application configuration.

---

# 13. Security & Hardening Priorities

## 13.1 Credential management

Database configuration is currently represented in `config.py`.

For hardened deployments, credentials should come from:

- environment variables;
- a secrets manager;
- another secure runtime injection mechanism.

Never add new hard-coded secrets.

## 13.2 E-mail recipient management

Recipient lists are operational configuration. Keep them outside tests and sample documentation.

## 13.3 Database access minimization

The database account should have only the read permissions needed by the monitor.

## 13.4 File-system permissions

The process must be able to:

- write the operational log;
- write generated HTML reports;

but should not receive broader permissions than necessary.

## 13.5 External command execution

`utils.py` invokes local binaries such as `sendmail` and `mutt`.

Changes involving subprocess execution must:

- avoid shell interpolation;
- preserve argument boundaries;
- fail explicitly when delivery cannot be performed;
- log actionable diagnostics.

## 13.6 Refactoring priority

For future hardening, prioritize:

1. secret externalization;
2. least-privilege database access;
3. predictable runtime directories;
4. safer process management;
5. test coverage around monitoring and alerts;
6. separation of configuration from source code.

Do not combine security hardening with unrelated visual or business-rule changes unless explicitly requested.

---

# Final Rule for AI Agents

Before making a change, identify whether it affects:

- database access;
- monitoring windows;
- D-7 comparison;
- merchant matching;
- alert thresholds;
- alert recipients;
- report output;
- chart semantics;
- runtime/restart behavior.

For every change:

1. Inspect the existing implementation first.
2. Preserve unrelated behavior.
3. Prefer the smallest change that satisfies the request.
4. Keep SQL read-only.
5. Do not expose or add credentials.
6. Verify syntax and affected report/alert paths.
7. Document material behavioral changes.

**WplMonitorV1 is an operational monitoring system. Reliability, continuity of monitoring, correctness of metrics, and predictable alert behavior take precedence over unnecessary architectural or stylistic refactoring.**
