# WplMonitorV1

WplMonitorV1 is a Python-based operational monitoring application for payment transaction activity. It connects to PostgreSQL, calculates approval/decline metrics, identifies issuer-level degradation, generates HTML reports with charts, and sends alert e-mails when configured low-approval conditions are detected.

## What the application does

The application is designed to run continuously (or as a single execution) and refresh monitoring information approximately once per minute.

For each configured Tier-1 client, it:

1. Reads client/merchant aliases from `clientsT1.txt`.
2. Queries PostgreSQL for transaction activity in a configurable time window.
3. Calculates total transactions, approved transactions, approval rate, declining issuers, and recurring-transaction percentage.
4. Retrieves daily totals and approved amounts, including per-currency totals.
5. Builds a minute-by-minute time series and generates an approval-rate/transaction-volume chart.
6. Generates a chart of issuers with the highest number of declines.
7. Writes an HTML report for each merchant.
8. Compares schema performance with the equivalent period seven days earlier.
9. Collects acquisition/technology data for Argentina, Brazil, Colombia, and Mexico.
10. Generates a consolidated `schemas_full.html` dashboard.
11. Sends e-mail alerts when issuer-level approval conditions meet the configured thresholds.

## Architecture

| File | Responsibility |
| --- | --- |
| `main.py` | Application orchestration, monitoring loop, report generation, comparisons, and alert decisions. |
| `config.py` | Database settings, monitoring parameters, recipients, report paths, and shared HTML/CSS styling. |
| `db_helpers.py` | PostgreSQL connection handling, SQL queries, metric aggregation, and retry/reconnect logic. |
| `charts.py` | Matplotlib chart generation and Base64 PNG conversion. |
| `html_templates.py` | HTML report and dashboard templates. |
| `utils.py` | Client-file parsing, formatting helpers, slug generation, and e-mail delivery. |
| `clientsT1.txt` | Tier-1 client names and database aliases. |
| `restart.sh` | Helper script to stop the running process and restart it with `nohup`. |
| `nohup.out` | Runtime output from a background execution; not required by the application logic. |

### Runtime flow

```text
clientsT1.txt
     |
     v
main.py ---> db_helpers.py ---> PostgreSQL
  |                 |
  |                 +--> retry/reconnect on DB failures
  |
  +--> charts.py ------------+
  |                          |
  +--> html_templates.py ----+--> HTML reports/dashboard
  |
  +--> alert conditions --> sendmail --> e-mail recipients
```

## Monitoring windows

The main monitoring window is controlled by `WINDOW_MINUTES` and defaults to **15 minutes**.

The time-series lookback is controlled by `TS_MINUTES` and defaults to **120 minutes**.

Several metrics are also queried for the equivalent period **7 days earlier**, allowing the dashboard to show current-vs-D-7 deltas.

The PostgreSQL session timezone is set from `TZ_DISPLAY`, which defaults to `America/Sao_Paulo`.

## Client monitoring

Each line in `clientsT1.txt` can contain multiple aliases representing the same merchant. Lines beginning with `#` are ignored.

Example:

```text
'PedidosYa','PEDIDOS YA'
'JETSMART','Jetsmart Argentina'
```

The aliases are matched against `clientes.nome_loja_resumido` in PostgreSQL.

## Issuer analysis and alerting

Issuer metrics are obtained by joining transaction data with JSON information in `campos_transacoes_json`.

The monitor calculates:

- total transactions;
- approved transactions;
- declined transactions;
- approval rate;
- recurring-transaction percentage.

The current alert condition in `main.py` requires all of the following:

```text
total_tx > 150
approval_rate < 10%
recurring_percentage < 70%
```

Alerts are only sent between **08:00 and 23:00**.

An in-memory cooldown prevents repeated alerts for the same client during the configured monitoring window.

## Schema and acquisition monitoring

Schema performance is grouped by the `administradora` field and compared between the current window and the equivalent window seven days earlier.

The comparison includes:

- approval-rate delta;
- declined-transaction delta;
- total-transaction delta;
- recurring-percentage delta.

Acquisition data is currently mapped as follows:

| Country | Technologies |
| --- | --- |
| Argentina | `AR` |
| Brazil | `RB`, `WL` |
| Colombia | `RC` |
| Mexico | `RM`, `PS` |

## Reporting

Reports are generated as HTML and use shared styling defined in `config.py`.

Charts are generated with Matplotlib and embedded directly into the HTML as Base64-encoded PNG data.

The application produces:

- an issuer report for each configured client;
- `schemas_full.html`, containing consolidated acquisition, schema, and client information.

The dashboard uses an HTML auto-refresh interval controlled by `REFRESH_SECONDS`, which defaults to **60 seconds**.

## Database reliability

Database read functions use the `retry_on_recovery_conflict` decorator.

When PostgreSQL reports a recovery conflict or the connection becomes unusable, the application:

1. Attempts to roll back the connection.
2. Closes the broken connection.
3. Waits using exponential backoff.
4. Creates a new PostgreSQL connection.
5. Retries the operation.

Current retry configuration:

- maximum attempts: `20`;
- initial wait: `5` seconds;
- backoff factor: `2.0`.

## Running the monitor

The main entry point is:

```bash
python3 main.py
```

The current configuration enables continuous execution through `RUN_FOREVER = 1`.

For background execution, `restart.sh` runs:

```bash
nohup /data/wpl_reports/main.py &
```

The application writes its operational log to `wplreport.log` under the configured data directory.

## Configuration

The following values can be supplied through environment variables:

| Variable | Default |
| --- | --- |
| `MERCHANT_NAMES` | `PedidosYa,PEDIDOS YA` |
| `HTML_OUTPUT` | configured path in `config.py` |
| `WINDOW_MINUTES` | `15` |
| `TS_MINUTES` | `120` |
| `TOP_N_ISSUERS` | `10` |
| `REFRESH_SECONDS` | `60` |
| `TZ_DISPLAY` | `America/Sao_Paulo` |

Other operational values, including database connection configuration, report paths, and e-mail recipients, are currently defined directly in `config.py`.

## Dependencies

The main external Python dependencies are:

- `psycopg2` / `psycopg2.extras` — PostgreSQL connectivity;
- `pandas` — tabular data processing;
- `matplotlib` — chart generation.

The application also relies on Python standard-library modules for logging, file parsing, e-mail construction, process management, and time handling.

The host requires the local `sendmail` command for the primary e-mail implementation. `mutt` is also supported by an alternate helper in `utils.py`.

## Operational considerations

- Alert cooldown state is stored in process memory and is therefore reset when the application restarts.
- `clientsT1.txt` is runtime configuration: changing aliases changes which database transactions are included in client metrics.
- Report directories must exist and be writable by the process.
- Several paths and operational settings are environment-specific, so the repository currently behaves more like an operational application/script than a fully packaged portable application.
- `nohup.out` is a runtime artifact and is not required for the application's source-code operation.

## Security note

The repository configuration contains infrastructure-specific connection and recipient settings. For broader distribution or production hardening, credentials and other environment-specific secrets should be supplied through environment variables or a dedicated secrets-management solution rather than committed to source control.

## Current purpose

Based on the implementation, WplMonitorV1 is an operational payment-monitoring solution focused on near-real-time visibility into transaction approval performance across LATAM processing.

Its main responsibilities are monitoring client performance, identifying issuer and schema degradation, comparing current activity with the same period seven days earlier, producing operational dashboards, and notifying support/operations teams when configured approval-rate conditions are detected.
