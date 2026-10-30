#!/usr/bin/env python3
from datetime import datetime
from config import html_style, MERCHANT_NAMES, HTML_OUTPUT, WINDOW_MINUTES, TS_MINUTES, RUN_FOREVER, TOP_N_ISSUERS, recipients, directory_path, report_path, recipients_adm, APP_BASE_URL, TZ_DISPLAY
from db_helpers import pg_connect, fetch_overall_metrics, fetch_worst_issuers, fetch_timeseries, fetch_daily_currency_totals, fetch_daily_metrics, fetch_schema_data, fetch_acq_data
from charts import plot_timeseries, plot_worst
from html_templates import build_html, build_html_mail, build_html_mail_client, build_schemas_html
from utils import send_email_mutt, parse_clients_file, slugify, send_email_mail
from core.alert_config import AlertConfigStore
from core.alert_engine import AlertStateStore, build_critical_drop_email, evaluate_critical_drop, filter_issuer_alerts, is_within_schedule
from pandas.plotting import register_matplotlib_converters

import os
import sys
import time as time_module
import logging
import traceback
import pandas as pd

register_matplotlib_converters()

alert_config_store = AlertConfigStore(legacy_window_minutes=WINDOW_MINUTES)
alert_state_store = AlertStateStore()

# ---------- Runner ----------
def run_once():
    conn = pg_connect()
    try:
        if not os.path.exists(directory_path):
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {directory_path} not exist! ")
            return
        log_file = f"{directory_path}/wplreport.log"
        logging.basicConfig(filename=log_file,
                format='%(asctime)s [%(process)d] - %(levelname)s - %(message)s',
                filemode='a',
                level=logging.INFO)
        if not os.path.exists(report_path):
            logging.info(f"report_path: {report_path} does not exits!")
            return

        
        clients_file = f"{directory_path}/clientsT1.txt"
        clients = parse_clients_file(clients_file)
        if not clients:
            logging.info(f"No clients found in {clients_file}")
            return
        
        
        overall_clients = []

        for aliases in clients:
            if conn.closed != 0:
                conn = pg_connect()

            logging.debug(f"{aliases} ")
            MERCHANT_NAMES = aliases
            overall = fetch_overall_metrics(conn, MERCHANT_NAMES, WINDOW_MINUTES,0)
            overall_d7 = fetch_overall_metrics(conn, MERCHANT_NAMES, WINDOW_MINUTES,7)
            df_worst = fetch_worst_issuers(conn, MERCHANT_NAMES, WINDOW_MINUTES, TOP_N_ISSUERS)
            df_ts    = fetch_timeseries(conn, MERCHANT_NAMES, TS_MINUTES)

  
            #2 worst issuers
            df_worst_t2 = df_worst.head(2)
            decliners = ""
#            for _, r in df_worst_t2.iterrows():
#                issuer_bank = r['issuer_bank'].split()
#                if len(issuer_bank) > 3 and issuer_bank[2][0:2] == "La":
#                    decliners += " ".join(issuer_bank[:4]) + ",<br>"
#                else:
#                    decliners += " ".join(issuer_bank[:2 if ((len(issuer_bank[0])+len(issuer_bank[1])) > 10 and len(issuer_bank) <= 3 ) else 3]) + ",<br>"

            for _, r in df_worst_t2.iterrows():
                issuer_bank = r['issuer_bank'].split()

                if len(issuer_bank) >= 3 and issuer_bank[2] == "La":
                    decliners += " ".join(issuer_bank[:4]) + ",<br>"

                elif len(issuer_bank) >= 2:
                    # safe length calculation
                    name_len = len(issuer_bank[0]) + len(issuer_bank[1])

                    if name_len > 10 and len(issuer_bank) >= 3:
                        decliners += " ".join(issuer_bank[:2]) + ",<br>"
                    else:
                        decliners += " ".join(issuer_bank[:min(3, len(issuer_bank))]) + ",<br>"

                elif len(issuer_bank) == 1:
                    decliners += issuer_bank[0] + ",<br>"

            overall_clients.append({
                    "client": aliases,
                    "now": overall,
                    "d7": overall_d7,
                    "decliners": decliners[0:-5] if len(decliners) > 4 else None })
                    #"decliners": decliners[0:-5]})

            daily        = fetch_daily_metrics(conn, MERCHANT_NAMES)
            daily_curr   = fetch_daily_currency_totals(conn, MERCHANT_NAMES)

            img_ts   = plot_timeseries(df_ts, MERCHANT_NAMES, TS_MINUTES)
            img_w    = plot_worst(df_worst, WINDOW_MINUTES)

            now_disp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            html = build_html(
                now_disp, MERCHANT_NAMES, overall, df_worst, img_ts, img_w,
                daily_curr=daily_curr
            )
            merchant_slug = slugify(MERCHANT_NAMES[0].lower())
            HTML_OUTPUT = f"{report_path}/{merchant_slug}_issuers.html"
            with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
                f.write(html)
            logging.info(f"Wrote {HTML_OUTPUT} — total={overall['total']} approved={overall['aprovadas']} rate={overall['taxa']:.2f}% | daily_total={daily['total']}")


            alert_settings = alert_config_store.get_merchant(merchant_slug)
            alert_schedule = is_within_schedule(
                datetime.now().time(), alert_settings["schedule"]
            )

            # Existing issuer alert: preserve the original conditions as merchant-level rules.
            alert_issuers = filter_issuer_alerts(df_worst, alert_settings["issuer"])
            if alert_schedule and not alert_issuers.empty:
                remaining = alert_state_store.cooldown_remaining(
                    merchant_slug, "issuer", alert_settings["issuer"]["cooldown_minutes"]
                )
                if remaining is None:
                    html_mail = build_html_mail(
                        now_disp, MERCHANT_NAMES, overall, alert_issuers, daily_curr, APP_BASE_URL
                    )
                    subject = (
                        f"[ALERT] {MERCHANT_NAMES[0]} Low Approval Rate for Issuer(s): "
                        f"{', '.join(alert_issuers['issuer_bank'])}"
                    )
                    send_email_mail(html_mail, subject, recipients_adm, HTML_OUTPUT)
                    html_mail_client = build_html_mail_client(
                        now_disp, MERCHANT_NAMES, overall, df_worst, daily_curr, APP_BASE_URL
                    )
                    send_email_mail(html_mail_client, subject, recipients, None)
                    alert_state_store.mark_sent(merchant_slug, "issuer")
                    logging.info("Issuer alarm sent for %s", aliases)
                else:
                    logging.info(
                        "Issuer alert suppressed for %s. Cooldown active (%d min left).",
                        aliases, int(remaining.total_seconds() // 60)
                    )

            # New merchant-level Critical Drop: current window versus equivalent D-7 window.
            critical_drop = evaluate_critical_drop(
                overall["total"], overall_d7["total"], alert_settings["critical_drop"]
            )
            if alert_schedule and critical_drop:
                remaining = alert_state_store.cooldown_remaining(
                    merchant_slug, "critical_drop",
                    alert_settings["critical_drop"]["cooldown_minutes"]
                )
                if remaining is None:
                    html_drop = build_critical_drop_email(
                        merchant_name=MERCHANT_NAMES[0],
                        current_total=critical_drop["current_total"],
                        baseline_total=critical_drop["baseline_total"],
                        drop_percent=critical_drop["drop_percent"],
                        threshold_percent=critical_drop["threshold_percent"],
                        window_minutes=WINDOW_MINUTES,
                        app_base_url=APP_BASE_URL,
                        merchant_slug=merchant_slug,
                    )
                    subject = (
                        f"[CRITICAL DROP] {MERCHANT_NAMES[0]} - "
                        f"volume down {critical_drop['drop_percent']:.2f}%"
                    )
                    send_email_mail(html_drop, subject, recipients_adm, None)
                    send_email_mail(html_drop, subject, recipients, None)
                    alert_state_store.mark_sent(merchant_slug, "critical_drop")
                    logging.warning(
                        "Critical Drop alert sent for %s: current=%s baseline_d7=%s drop=%.2f%%",
                        aliases, critical_drop["current_total"], critical_drop["baseline_total"],
                        critical_drop["drop_percent"]
                    )
                else:
                    logging.info(
                        "Critical Drop alert suppressed for %s. Cooldown active (%d min left).",
                        aliases, int(remaining.total_seconds() // 60)
                    )
        #END LOOP
        
        #Get Schemas
        schema_d0 = fetch_schema_data(conn, WINDOW_MINUTES, TOP_N_ISSUERS, 0)
        schema_d7 = fetch_schema_data(conn, WINDOW_MINUTES, TOP_N_ISSUERS, 7)

        # Rename columns to avoid collisions
        schema_d0 = schema_d0.rename(columns=lambda c: f"{c}_now" if c != "schema" else c)
        schema_d7 = schema_d7.rename(columns=lambda c: f"{c}_7d" if c != "schema" else c)

        # Merge
        schema_df = pd.merge(schema_d0, schema_d7, on="schema", how="outer").fillna(0)

        # Deltas
        schema_df["approval_rate_delta"] = schema_df["approval_rate_now"] - schema_df["approval_rate_7d"]
        schema_df["declined_delta"] = schema_df["declined_now"] - schema_df["declined_7d"]
        schema_df["total_tx_delta"] = schema_df["total_tx_now"] - schema_df["total_tx_7d"]
        schema_df["recurring_delta"] = (
            schema_df["recurring_percentage_now"] - schema_df["recurring_percentage_7d"]
        )

        # Logging header
        logging.info(
            "Schema comparison | window=%sm | now vs 7 days ago",
            WINDOW_MINUTES,
        )

        # Log per schema (sorted by worst approval drop)
        schema_df = schema_df.sort_values("total_tx_now")

        for _, r in schema_df.iterrows():
            logging.info(
                (
                    "schema=%s | tx=%d→%d (Δ %+d) | "
                    "declined=%d→%d (Δ %+d) | "
                    "approval=%.2f%%→%.2f%% (Δ %+0.2f%%) | "
                    "recurring=%.2f%%→%.2f%% (Δ %+0.2f%%)"
                ),
                r["schema"],
                r["total_tx_7d"],
                r["total_tx_now"],
                r["total_tx_delta"],
                r["declined_7d"],
                r["declined_now"],
                r["declined_delta"],
                r["approval_rate_7d"],
                r["approval_rate_now"],
                r["approval_rate_delta"],
                r["recurring_percentage_7d"],
                r["recurring_percentage_now"],
                r["recurring_delta"],
            )


        COUNTRIES = ["AR", "BR", "CO", "MX"]
        DAYS = [0, 7]

        acq_data = []

        if conn.closed != 0:
            conn = pg_connect()

        for country in COUNTRIES:
            for days_ago in DAYS:
                df = fetch_acq_data(conn, WINDOW_MINUTES, country, days_ago)
                df["country"] = country
                df["days_ago"] = days_ago
                acq_data.append(df)

                if df.empty:
                    logging.warning(
                      "ACQ data EMPTY | country=%s days_ago=%s window=%sm",
                        country, days_ago, WINDOW_MINUTES
                    )
                else:
                    logging.info(
                        "ACQ summary | country=%s days_ago=%s rows=%s total_tx=%s approved=%s declined=%s avg_approval_rate=%.2f",
                        country,
                        days_ago,
                        len(df),
                        int(df["total_tx"].sum()),
                        int(df["approved"].sum()),
                        int(df["declined"].sum()),
                        df["approval_rate"].mean(),
                    )


        HTML_OUTPUT = f"{report_path}/schemas_full.html"
        html = build_schemas_html(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), schema_df,acq_data,overall_clients)
        with open(HTML_OUTPUT, "w", encoding="utf-8") as f:
            f.write(html)
        logging.info(f"Wrote {HTML_OUTPUT} ")

    finally:
        conn.close()

def sleep_to_next_minute(pad=0.2):
    now = datetime.now()
    secs = 60 - now.second - now.microsecond/1_000_000
    time_module.sleep(max(0.0, secs + pad))

def main():
    if RUN_FOREVER:
        while True:
            try:
                run_once()
            except Exception as e:
                logging.error(f"ERROR:{e}")
                tb = traceback.extract_tb(sys.exc_info()[2])[-1]
                logging.error(
                    "Error at %s:%s (%s): %s",
                    tb.filename,
                    tb.lineno,
                    tb.name,
                    e,
                    exc_info=True,
                )

                traceback.print_exc()
            sleep_to_next_minute()
    else:
        run_once()

if __name__ == "__main__":
    main()



