import psycopg2
import psycopg2.extras
import pandas as pd
from config import PG_CONN_OPTS, TZ_DISPLAY
import time
import functools
from psycopg2 import extensions
import logging

# Retry settings (you can also move these to config/env)
RETRY_MAX_ATTEMPTS = 20          # total attempts
RETRY_BASE_SLEEP_S = 5           # first backoff wait, then exponential
RETRY_BACKOFF_FACTOR = 2.0       # 5s, 10s, 20s, ...

def retry_on_recovery_conflict(func):
    """
    Retries a DB-read function on standby conflicts or broken connections.
    Recreates the connection when it is no longer usable.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        attempt = 0
        conn = args[0]

        while True:
            try:
                # Rollback only if connection still looks alive
                if isinstance(conn, psycopg2.extensions.connection) and conn.closed == 0:
                    try:
                        conn.rollback()
                    except psycopg2.Error:
                        # rollback itself failed → force reconnect
                        raise psycopg2.InterfaceError("rollback failed")

                return func(conn, *args[1:], **kwargs)

            except (
                psycopg2.extensions.TransactionRollbackError,
                psycopg2.InterfaceError,
                psycopg2.OperationalError,
            ) as e:
                attempt += 1
                if attempt >= RETRY_MAX_ATTEMPTS:
                    raise

                logging.error(
                    "[retry_on_recovery_conflict] %s attempt %d/%d: %s",
                    func.__name__, attempt, RETRY_MAX_ATTEMPTS, e
                )

                # Always dispose the broken connection
                try:
                    if conn and conn.closed == 0:
                        conn.close()
                except Exception:
                    pass

                sleep_s = RETRY_BASE_SLEEP_S * (RETRY_BACKOFF_FACTOR ** (attempt - 1))
                time.sleep(sleep_s)

                # ✅ recreate connection
                conn = pg_connect()

    return wrapper

def retry_on_recovery_conflict_old(func):
    """
    Retries a DB-read function if it fails with TransactionRollbackError
    such as: 'canceling statement due to conflict with recovery'.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        attempt = 0
        while True:
            try:
                if isinstance(args[0], psycopg2.extensions.connection):
                    try:
                        conn = args[0]
                        if conn.closed == 0:
                            conn.rollback()
                    except Exception:
                        pass
                return func(*args, **kwargs)
            except extensions.TransactionRollbackError as e:
                attempt += 1
                if attempt >= RETRY_MAX_ATTEMPTS:
                    # re-raise on final failure
                    raise

                if isinstance(args[0], psycopg2.extensions.connection):
                    conn = args[0]
                    try:
                        if conn and conn.closed == 0:
                            conn.close()
                    except Exception:
                        pass

                sleep_s = RETRY_BASE_SLEEP_S * (RETRY_BACKOFF_FACTOR ** (attempt - 1))
                # Optional: log/print for observability
                logging.error(f"[retry_on_recovery_conflict] {func.__name__} attempt {attempt}/{RETRY_MAX_ATTEMPTS} ")
                logging.error(f"after TransactionRollbackError: {e}. Sleeping {sleep_s:.1f}s...")
                time.sleep(sleep_s)
    return wrapper

def pg_connect():
    conn = psycopg2.connect(**PG_CONN_OPTS)
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE %s;", (TZ_DISPLAY,))
    return conn

@retry_on_recovery_conflict
def fetch_overall_metrics(conn, merchants, win_minutes,days_ago):
    sql = """
    WITH clientes_filtrados AS (
      SELECT codigo_cliente FROM clientes WHERE nome_loja_resumido = ANY(%s)
    )
    SELECT
      COUNT(*) AS total_transacoes,
      COUNT(*) FILTER (WHERE status_autorizacao = '00') AS transacoes_aprovadas
    FROM transacoes_aprova_facil
    WHERE data_hora_recebimento >= date_trunc('minute', (now() - INTERVAL '%s days') - (%s)::interval)
      AND data_hora_recebimento <  date_trunc('minute', (now() - INTERVAL '%s days'))
      AND codigo_cliente IN (SELECT codigo_cliente FROM clientes_filtrados);
    """
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, (merchants, days_ago, f"{win_minutes} minutes", days_ago))
        row = cur.fetchone()
    total = (row["total_transacoes"] or 0)
    aprov = (row["transacoes_aprovadas"] or 0)
    rate = round((aprov / total * 100.0), 2) if total else 0.0
    return dict(total=total, aprovadas=aprov, taxa=rate)

@retry_on_recovery_conflict
def fetch_worst_issuers(conn, merchants, win_minutes, top_n):
    sql = """
    WITH clientes_filtrados AS (
      SELECT codigo_cliente FROM clientes WHERE nome_loja_resumido = ANY(%s)
    )
    SELECT
      INITCAP(COALESCE(COALESCE(NULLIF(js.dados->>'BinTable_BancoEmissor', ''), NULLIF(js.dados->>'IssuerName','')), 'Unknown')) AS issuer_bank,
   --   COALESCE(NULLIF(js.dados->>'BinTable_BancoEmissor',''), 'Unknown') AS issuer_bank,
      COUNT(*) AS total_tx,
      COUNT(*) FILTER (WHERE t.status_autorizacao = '00') AS approved,
      COUNT(*) FILTER (WHERE t.status_autorizacao <> '00') AS declined,
      ROUND(
        CASE WHEN COUNT(*) > 0 THEN
          (COUNT(*) FILTER (WHERE t.status_autorizacao = '00'))::decimal / COUNT(*) * 100
        ELSE 0 END, 2
      ) AS approval_rate,
      ROUND(
        CASE WHEN COUNT(*) > 0 THEN
            (COUNT(*) FILTER (WHERE dados->>'storedCredentials_merchantInitiatedReason' = 'RECURRING'))::decimal / COUNT(*) * 100
        ELSE 0 END, 2
      ) AS recurring_percentage
    FROM transacoes_aprova_facil t
    JOIN campos_transacoes_json js ON t.numero_transacao = js.numero_transacao
    WHERE t.data_hora_recebimento >= date_trunc('minute', now() - (%s)::interval)
      AND t.data_hora_recebimento <  date_trunc('minute', now())
      AND t.codigo_cliente IN (SELECT codigo_cliente FROM clientes_filtrados)
    GROUP BY 1
    ORDER BY declined DESC, approval_rate ASC
    LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (merchants, f"{win_minutes} minutes", top_n))
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["issuer_bank","total_tx","approved","declined","approval_rate", "recurring_percentage"])

@retry_on_recovery_conflict
def fetch_timeseries(conn, merchants, lookback_minutes):
    sql = """
    WITH clientes_filtrados AS (
      SELECT codigo_cliente FROM clientes WHERE nome_loja_resumido = ANY(%s)
    )
    SELECT
      date_trunc('minute', data_hora_recebimento) AS minute,
      COUNT(*) AS total,
      COUNT(*) FILTER (WHERE status_autorizacao = '00') AS approved
    FROM transacoes_aprova_facil
    WHERE data_hora_recebimento >= now() - (%s)::interval
      AND codigo_cliente IN (SELECT codigo_cliente FROM clientes_filtrados)
    GROUP BY 1
    ORDER BY 1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (merchants, f"{lookback_minutes} minutes"))
        rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["minute","total","approved"])
    if not df.empty:
        df["minute"] = pd.to_datetime(df["minute"])
        df["rate"]   = (df["approved"] / df["total"] * 100).round(2)
    else:
        df["rate"] = pd.Series(dtype=float)
    return df

import psycopg2.extras
from decimal import Decimal

@retry_on_recovery_conflict
def fetch_daily_metrics(conn, merchants):
    """
    Daily totals since midnight (server TZ already set by SET TIME ZONE).
    Returns: total tx, approved tx, approval rate %, approved amount (all currencies combined).
    """
    sql = """
    WITH clientes_filtrados AS (
      SELECT codigo_cliente FROM clientes WHERE nome_loja_resumido = ANY(%s)
    )
    SELECT
      COUNT(*) AS total_tx,
      COUNT(*) FILTER (WHERE status_autorizacao = '00') AS approved_tx,
      ROUND(
        CASE WHEN COUNT(*) > 0 THEN
          (COUNT(*) FILTER (WHERE status_autorizacao = '00'))::decimal / COUNT(*) * 100
        ELSE 0 END, 2
      ) AS approval_rate,
      COALESCE(SUM(valor_transacao) FILTER (WHERE status_autorizacao = '00'), 0) AS approved_amount
    FROM transacoes_aprova_facil
    WHERE data_hora_recebimento >= date_trunc('day', now())
      AND codigo_cliente IN (SELECT codigo_cliente FROM clientes_filtrados);
    """
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, (merchants,))
        row = cur.fetchone() or {}
    return dict(
        total=int(row.get("total_tx") or 0),
        approved=int(row.get("approved_tx") or 0),
        rate=float(row.get("approval_rate") or 0.0),
        amount=float(row.get("approved_amount") or 0.0)  # combined, regardless of currency
    )

@retry_on_recovery_conflict
def fetch_daily_currency_totals(conn, merchants):
    """
    Per-currency totals for today:
      - approved_tx: count(status='00')
      - approved_amount: sum(valor_transacao) where status='00'
    Returns a list of dicts: [{moeda:'BRL', approved_tx:..., approved_amount:...}, ...]
    """
    sql = """
    WITH clientes_filtrados AS (
      SELECT codigo_cliente FROM clientes WHERE nome_loja_resumido = ANY(%s)
    )
    SELECT
      COALESCE(NULLIF(moeda, ''), 'UNK') AS moeda,
      COUNT(*) FILTER (WHERE status_autorizacao = '00') AS approved_tx,
      COALESCE(SUM(valor_transacao) FILTER (WHERE status_autorizacao = '00'), 0) AS approved_amount
    FROM transacoes_aprova_facil
    WHERE data_hora_recebimento >= date_trunc('day', now())
      AND codigo_cliente IN (SELECT codigo_cliente FROM clientes_filtrados)
    GROUP BY 1
    ORDER BY 1;
    """
    out = []
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(sql, (merchants,))
        for r in cur.fetchall():
            out.append({
                "moeda": r["moeda"],
                "approved_tx": int(r["approved_tx"] or 0),
                "approved_amount": float(r["approved_amount"] or 0.0),
            })
    return out


@retry_on_recovery_conflict
def fetch_schema_data(conn, win_minutes, top_n, days_ago):
    sql = """
    SELECT
      administradora AS schema,
      COUNT(*) AS total_tx,
      COUNT(*) FILTER (WHERE t.status_autorizacao = '00') AS approved,
      COUNT(*) FILTER (WHERE t.status_autorizacao <> '00') AS declined,
      ROUND(
        CASE WHEN COUNT(*) > 0 THEN
          (COUNT(*) FILTER (WHERE t.status_autorizacao = '00'))::decimal / COUNT(*) * 100
        ELSE 0 END, 2
      ) AS approval_rate,
      ROUND(
        CASE WHEN COUNT(*) > 0 THEN
            (COUNT(*) FILTER (WHERE dados->>'storedCredentials_merchantInitiatedReason' = 'RECURRING'))::decimal / COUNT(*) * 100
        ELSE 0 END, 2
      ) AS recurring_percentage
    FROM transacoes_aprova_facil t
    JOIN campos_transacoes_json js ON t.numero_transacao = js.numero_transacao
    WHERE t.data_hora_recebimento >= date_trunc('minute', (now() - INTERVAL '%s days') - (%s)::interval)
      AND t.data_hora_recebimento <  date_trunc('minute', (now() - INTERVAL '%s days'))
      AND t.tipo_tecnologia in ('PS','WL','AR','RB','RM','RC')
    GROUP BY 1
    ORDER BY declined DESC, approval_rate ASC
    LIMIT %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (days_ago, f"{win_minutes} minutes", days_ago, top_n))
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["schema","total_tx","approved","declined","approval_rate", "recurring_percentage"])


@retry_on_recovery_conflict
def fetch_acq_data(conn, win_minutes, country, days_ago):


    if country == "BR":
        techs = ["RB", "WL"]
    elif country == "AR":
        techs = ["AR"]
    elif country == "CO":
        techs = ["RC"]
    elif country == "MX":
        techs = ["RM", "PS"]
    else:
        techs = ["PS", "WL", "AR", "RB", "RM", "RC"]

    sql = """
    SELECT
      t.tipo_tecnologia AS schema,
      COUNT(*) AS total_tx,
      COUNT(*) FILTER (WHERE t.status_autorizacao = '00') AS approved,
      COUNT(*) FILTER (WHERE t.status_autorizacao <> '00') AS declined,
      ROUND(
        CASE WHEN COUNT(*) > 0 THEN
          COUNT(*) FILTER (WHERE t.status_autorizacao = '00')::decimal / COUNT(*) * 100
        ELSE 0 END, 2
      ) AS approval_rate,
      ROUND(
        CASE WHEN COUNT(*) > 0 THEN
          COUNT(*) FILTER (
            WHERE js.dados->>'storedCredentials_merchantInitiatedReason' = 'RECURRING'
          )::decimal / COUNT(*) * 100
        ELSE 0 END, 2
      ) AS recurring_percentage
    FROM transacoes_aprova_facil t
    JOIN campos_transacoes_json js
      ON t.numero_transacao = js.numero_transacao
    WHERE t.data_hora_recebimento >=
          date_trunc('minute',
            now()
            - (%s * INTERVAL '1 day')
            - (%s * INTERVAL '1 minute')
          )
      AND t.data_hora_recebimento <
          date_trunc('minute',
            now()
            - (%s * INTERVAL '1 day')
          )
      AND t.tipo_tecnologia = ANY(%s)
    GROUP BY 1
    ORDER BY declined DESC, approval_rate ASC
    """

    with conn.cursor() as cur:
        cur.execute(sql, (days_ago, win_minutes, days_ago, techs))
        rows = cur.fetchall()

    return pd.DataFrame(
        rows,
        columns=[
            "schema",
            "total_tx",
            "approved",
            "declined",
            "approval_rate",
            "recurring_percentage",
        ],
    )
    
def fetch_acq_datai_old(conn, win_minutes, country, days_ago):

    if country == "BR":
        sql_c = "'RB,'WL'"
    elif country == "AR":
        sql_c = "'AR'"
    elif country == "CO":
        sql_c = "'RC'"
    elif country == "MX":
        sql_c = "'RM','PS'"
    else:
        sql_c ="'PS','WL','AR','RB','RM','RC'"

    sql = """
    SELECT
      t.tipo_tecnologia AS tipo_tecnologia,
      COUNT(*) AS total_tx,
      COUNT(*) FILTER (WHERE t.status_autorizacao = '00') AS approved,
      COUNT(*) FILTER (WHERE t.status_autorizacao <> '00') AS declined,
      ROUND(
        CASE WHEN COUNT(*) > 0 THEN
          (COUNT(*) FILTER (WHERE t.status_autorizacao = '00'))::decimal / COUNT(*) * 100
        ELSE 0 END, 2
      ) AS approval_rate,
      ROUND(
        CASE WHEN COUNT(*) > 0 THEN
            (COUNT(*) FILTER (WHERE dados->>'storedCredentials_merchantInitiatedReason' = 'RECURRING'))::decimal / COUNT(*) * 100
        ELSE 0 END, 2
      ) AS recurring_percentage
    FROM transacoes_aprova_facil t
    JOIN campos_transacoes_json js ON t.numero_transacao = js.numero_transacao
    WHERE t.data_hora_recebimento >= date_trunc('minute', (now() - INTERVAL '%s days') - (%s)::interval)
      AND t.data_hora_recebimento <  date_trunc('minute', (now() - INTERVAL '%s days'))
      AND t.tipo_tecnologia in (%s)
    GROUP BY 1
    ORDER BY declined DESC, approval_rate ASC

    """
    with conn.cursor() as cur:
        cur.execute(sql, (days_ago, f"{win_minutes} minutes", days_ago, sql_c))
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=["schema","total_tx","approved","declined","approval_rate", "recurring_percentage"])


