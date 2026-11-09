from datetime import datetime
from config import html_style,html_style_m, REFRESH_SECONDS, WINDOW_MINUTES, TZ_DISPLAY, logos, APP_BASE_URL

GLOBALPAYMENTS_LOGO_URL = 'https://www.globalpayments.com/-/media/project/global-payments/corporate/corporate/global/site-logos/logoprimary-with-wordmark.svg?rev=09622a20277c45bbba231663e06267fb'
from utils import fmt_int, fmt_money, slugify
from collections import defaultdict
import base64_lib

# ---------- HTML (Your WP-styled template with minimal adaptations) ----------
def build_html(now_display, merchants, overall, df_worst, img_ts_b64, img_ts_diff_b64, img_worst_b64,img_by_adm, df_cli, *, daily_curr):
    # issuer table logic stays the same...

    merchants_str = ", ".join(merchants)
    
    window_min = overall['win_minutes']
    
    if merchants[0] == "Uber Eats":
        tit_cli = "Uber"
    elif merchants[0] == "WPGPFBRTIKTOKADSECOM":
        tit_cli = "TikTok (Ebanx)"
    elif merchants[0] == "Hillside Pasteko":
        tit_cli = "Bet365"
    elif merchants[0] == "WPGPEYAARSUPERCVV":
        tit_cli = "PedidosYa"
    else :
        tit_cli = merchants_str
    
    cli = df_cli["rows"]

    all_clients = ", ".join(
        f"{row['codigo_cliente']} ({row['percentual'] or 0}%) [Expected {row['percentual_d7']}% ] "
        for row in cli
    )

    all_clients_table = "".join(
        f"""<tr>
              <td style='text-align: left; '><small>{row['codigo_cliente']}</small></td>
              <td class={'' if row['percentual'] >= (row['percentual_d7']/2)  else 'warn' } ><small>{row['percentual'] or 0}% (Expected {row['percentual_d7']}%)</small></td>
              <td class={'' if row['transacoes_aprovadas'] >= (row['transacoes_aprovadas_d7']/2) else 'warn' } ><small>{row['transacoes_aprovadas'] or 0} (Expected {row['transacoes_aprovadas_d7']})</small><td>
            </tr>"""
        for row in cli
    )
    

    # Build currency chips
    if daily_curr:
        chips = []
        for row in daily_curr:
            chips.append(
                #f"<span class='chip'><span class='country-chip'>{row['moeda']}</span>"
                f"<span ><h2>"
                f" {fmt_money(row['moeda'], row['approved_amount'])}"
                f" </h2><span class='note'>({fmt_int(row['approved_tx'])} tx)</span></span>"
            )
        currency_chips_html = " ".join(chips)
    else:
        currency_chips_html = "<span class='note'>No approved amounts today</span>"

    # Build issuer table HTML
    if df_worst is None or df_worst.empty:
        table_html = "<tbody><tr><td colspan='5'>No transactions in the current window.</td></tr></tbody>"
    else:
        df_fmt = df_worst.copy()
        df_fmt["approval_rate"] = df_fmt["approval_rate"].map(lambda v: f"{v:.2f}%")
        rows = []
        for _, r in df_fmt.iterrows():
            rate_val = float(str(r["approval_rate"]).replace("%", "")) if isinstance(r["approval_rate"], str) else float(r["approval_rate"])
            status_class = "ok" if rate_val >= 80 else ("warn" if rate_val >= 50 else "err")
            
            schema_logo = ""

            if r['administradora'] == "VISA" and str(r['cred_deb'])[0] == "D" :
                schema_logo = base64_lib.visaelectron_logo 
            elif r['administradora'] == "VISA" and str(r['cred_deb'])[0] == "C" :
                schema_logo = base64_lib.visa_generic_logo
            elif r['administradora'] == "MASTERCARD" and str(r['cred_deb'])[0] == "C" :
                schema_logo = base64_lib.mastercard_logo 
            elif r['administradora'] == "MASTERCARD" and str(r['cred_deb'])[0] == "D" :
                schema_logo = base64_lib.maestro_logo 
            elif r['administradora'] == "ELO" :
                schema_logo = base64_lib.elo_logo 

            rows.append(
                f"<tr>"
                f"<td style='text-align: left;'><small>{r['codigo_cliente']}</small></td>"
                f"<td><a style='color: inherit; text-decoration: none;' target='_blank' href='https://latam-dashboards.fnfis.com/graphs/d/ff9y4ahy9dfcwb/app-rate-by-issuer?orgId=1&from=now-15m&to=now&timezone=browser&var-query0={r['issuer_bank']}'>{r['issuer_bank']}</a></td>"
                f"<td><img width='40' alt='{str(r['administradora']).capitalize()} - {r['cred_deb']}' src=\"{schema_logo}\"/>"
                #f"&nbsp;<small><span class='badge prod'>{r['cred_deb']}</span></small></td>"
                f"<td>{int(r['total_tx']):,}</td>"
                f"<td>{int(r['approved']):,}</td>"
                f"<td>{int(r['declined']):,}</td>"
                f"<td><span class=' {'' if r['avg_latency_sec'] is None or r['avg_latency_sec'] < 2.5 else ('warn' if r['avg_latency_sec'] < 3.5 else 'err')}'>{str(r['avg_latency_sec'])}</span></td>"
                f"<td><span class=' {'' if int(r['err'])/int(r['total_tx']) < 0.3 else 'err' }'><small>{int((int(r['err']))/int(r['total_tx']))*100}%</small></span></td>"
                f"<td><small>{int(r['recurring_percentage']):,}%</small></td>"
                f"<td><span class='badge {status_class}'>{rate_val:.2f}%</span></td>"
                f"</tr>"
            )
        table_html = "<tbody>" + "\n".join(rows) + "</tbody>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta http-equiv="refresh" content="{REFRESH_SECONDS}">
<title>Merchant Approval Performance — {merchants_str}</title>
<style>
  {html_style}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>Merchant Approval Performance — {tit_cli}</h1>
    <div class="sub">Generated at <strong>{now_display}</strong> ({TZ_DISPLAY}) • Auto-refresh {REFRESH_SECONDS}s</div>
  </div>
</header>

<main class="wrap">

  <!-- Window KPIs -->
  <section class="kpi">
    <div class="card">
      <h3>Total Transactions ({window_min} min)</h3>
      <div class="value">{overall['total']:,}</div>
      <div class="delta"><b>Avg. Latency: <span class='badge {'ok' if overall['avg_latency_sec'] < 2.5 else ('warn' if overall['avg_latency_sec'] < 3.5 else 'err')}'>{overall['avg_latency_sec']}s<span></td></b></div>
    </div>
    <div class="card">
      <h3>Approved ({window_min} min)</h3>
      <div class="value">{overall['aprovadas']:,}</div>
      <div class="delta">Status: {'Good' if overall['taxa']>=90 else ('Watch' if overall['taxa']>=80 else 'Alert')}</div>
    </div>
    <div class="card">
      <h3>Approval Rate ({window_min} min)</h3>
      <div class="value">{overall['taxa']:.2f}%</div>
      <div class="delta">Target ≥ 90%</div>
    </div>
    <div class="card">
      <h3><b>Total</b> Approved Today</h3>
      <div class="delta">{currency_chips_html}</div>
    </div>
  </section>

  <!-- Charts Row -->
  <section class="flex">
    <div class="card half">
      <h2>Approval Rate & Volume by Minute</h2>
      <img class="chart" alt="Top Declining Issuers" src="data:image/png;base64,{img_ts_b64}"/>
	  <div class="legend">
		<span class="chip"><span class="dot" style="background:#005aa3"></span>Approval %</span>
		<span class="chip"><span class="dot" style="background:#00b3b3"></span>Volume</span>
      </div>
    </div>
    <div class="card half">
      <h2>Top Declining Issuers</h2>
      <img class="chart" alt="Top Declining Issuers" src="data:image/png;base64,{img_worst_b64}"/>
    </div>
  </section>

  <!-- Charts Row -->
  <section class="flex">
  <br>
      <img class="chart" alt="Top Declining Issuers" src="data:image/png;base64,{img_ts_diff_b64}"/>
    </div>
  </section>

  <!-- Issuer Table -->
  <section class="section card">
    <h2>Issuer Details — last {WINDOW_MINUTES} minutes</h2>
    <table>
      <thead>
        <tr>
          <th style='text-align: left;'>User ID</th>
          <th>Issuer Bank</th>
          <th>Scheme (Prod)</th>
          <th>Total</th>
          <th>Approved</th>
          <th>Declined</th>
          <th>Latency (Avg)</th>
          <th alt="RespCode 91,96,30,06">Errors</th>
          <th>Recurring</th>
          <th>Approval Rate</th>
        </tr>
      </thead>
      {table_html}
    </table>
  </section>
  <section class="flex">
  <div class="card half">
    <h2>Clients / User list</h2>
    <table>
    <thead>
    <tr>
        <th style='text-align: left;'>User ID</th>
        <th>% of total <br> <small>Expected 4w based</small></th>
        <th>Volume Approv.<br> <small>Expected 4w based</small></th>
        <th></th>
    </tr>
    {all_clients_table}
    </table>
    <!--div class="card">{all_clients}</div-->
  </div>
  <div class="card half">
    <h2>Schemes/Brand</h2>
    <table>
    <thead>
    <tr>
        <th style='text-align: left;'><small>Last 15min percentage by Scheme</small></th>
    </tr>  
    </thead>  
    <tr>
        <td><img alt="Top Schemas brand" src="data:image/png;base64,{img_by_adm}"/></td>
    </tr>  
    </table>  
  </div>
  </section>

  <footer>WP Confidential • Merchants: {merchants_str} </footer>
</main>
</body>
</html>
"""

def _build_email_issuer_table(alert_issuers):
    """Render the complete issuer detail table used in alert emails."""
    from html import escape

    if alert_issuers is None or alert_issuers.empty:
        return "<p>No issuers triggered the alert condition.</p>"

    rows = []
    for _, r in alert_issuers.iterrows():
        issuer = escape(str(r.get("issuer_bank", "N/A")))
        total = fmt_int(r.get("total_tx", 0))
        approved = fmt_int(r.get("approved", 0)) if "approved" in r.index else "N/A"
        declined = fmt_int(r.get("declined", 0)) if "declined" in r.index else "N/A"
        recurring_value = r.get("recurring_percentage", 0)
        approval_value = r.get("approval_rate", 0)
        try:
            recurring = f"{float(recurring_value):.1f}%"
        except (TypeError, ValueError):
            recurring = escape(str(recurring_value))
        try:
            approval = f"{float(approval_value):.2f}%"
        except (TypeError, ValueError):
            approval = escape(str(approval_value))
        rows.append(
            "<tr>"
            f"<td>{issuer}</td><td>{total}</td><td>{approved}</td><td>{declined}</td>"
            f"<td>{recurring}</td><td>{approval}</td>"
            "</tr>"
        )

    return (
        "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;width:100%;'>"
        "<thead><tr><th>Issuer</th><th>Total Tx</th><th>Approved</th><th>Declined</th>"
        "<th>Recurring</th><th>Approval Rate</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _build_dashboard_link(app_url):
    from html import escape

    if not app_url:
        app_url = "https://ukdc1-pc-nag101.fnfis.com/tier1/byissuer/"
    safe_url = escape(str(app_url).strip(), quote=True)
    return (
        f'<p><a href="{safe_url}" style="display:inline-block;background:#005aa3;color:#fff;'
        'padding:10px 16px;text-decoration:none;border-radius:4px;">'
        'Open WPL LatAm TSO Dashboard</a></p>'
        f'<p style="font-size:12px;color:#666;">Direct link: <a href="{safe_url}">{safe_url}</a></p>'
    )



def _build_email_clients_table(client_rows):
    """Render the Clients / User list table for email clients that may block CSS."""
    from html import escape

    if isinstance(client_rows, dict):
        client_rows = client_rows.get("rows", [])
    if not client_rows:
        return "<p>No client/user-list data available.</p>"

    def _number(value, digits=0):
        try:
            number = float(value or 0)
            return f"{number:,.{digits}f}"
        except (TypeError, ValueError):
            return escape(str(value if value is not None else "N/A"))

    rows_html = []
    for row in client_rows:
        user_id = escape(str(row.get("codigo_cliente", "N/A")))
        current_pct = _number(row.get("percentual", 0), 2)
        expected_pct = _number(row.get("percentual_d7", 0), 2)
        current_approved = _number(row.get("transacoes_aprovadas", 0))
        expected_approved = _number(row.get("transacoes_aprovadas_d7", 0))
        rows_html.append(
            "<tr>"
            f"<td style='border:1px solid #d8e0e8;padding:6px;text-align:left'>{user_id}</td>"
            f"<td style='border:1px solid #d8e0e8;padding:6px'>{current_pct}% "
            f"<small>(Expected {expected_pct}%)</small></td>"
            f"<td style='border:1px solid #d8e0e8;padding:6px'>{current_approved} "
            f"<small>(Expected {expected_approved})</small></td>"
            "</tr>"
        )

    return (
        "<table role='presentation' border='0' cellpadding='0' cellspacing='0' "
        "style='border-collapse:collapse;width:100%;font-size:12px'>"
        "<thead><tr>"
        "<th style='border:1px solid #d8e0e8;padding:6px;background:#0a4d86;color:#fff;text-align:left'>User ID</th>"
        "<th style='border:1px solid #d8e0e8;padding:6px;background:#0a4d86;color:#fff;text-align:left'>% of total <small>(Expected 4w based)</small></th>"
        "<th style='border:1px solid #d8e0e8;padding:6px;background:#0a4d86;color:#fff;text-align:left'>Volume Approv. <small>(Expected 4w based)</small></th>"
        "</tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table>"
    )


def build_html_mail(now_display, merchants, overall, alert_issuers, daily_curr, app_url="", df_cli=None):
    from html import escape

    merchants_str = escape(", ".join(str(m) for m in merchants))
    generated_at = escape(str(now_display))

    if daily_curr:
        currency_html = "<ul>" + "".join(
            f"<li>{escape(str(fmt_money(row['moeda'], row['approved_amount'])))} "
            f"({fmt_int(row['approved_tx'])} tx)</li>"
            for row in daily_curr
        ) + "</ul>"
    else:
        currency_html = "<p>No approved amounts today</p>"

    issuers_html = _build_email_issuer_table(alert_issuers)
    dashboard_link_html = _build_dashboard_link(app_url)
    clients_table_html = _build_email_clients_table(df_cli)

    return f"""
    <html>
    <body style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#333;">
      <style>{html_style}
        table {{ width:100%; border-collapse:collapse; }}
        th, td {{ border:1px solid #d8e0e8; padding:8px; text-align:left; }}
        th {{ background:#0a4d86; color:#fff; }}
        tr:nth-child(even) {{ background:#f5f8fb; }}
      </style>
      <div style="margin-bottom:12px;"><img alt="Global Payments" width="220" style="display:block;max-width:100%;height:auto;background:#fff;padding:8px;border-radius:4px;" src="{GLOBALPAYMENTS_LOGO_URL}" /></div>
      <h2>Merchant Approval Alert</h2>
      <h2>{merchants_str}</h2>
      <p><strong>Generated:</strong> {generated_at}</p>
      <h3>Alert Issuers (Tx &gt; 150 &amp; Approval &lt; 10% &amp; Recurring &lt; 70%)</h3>
      <div class="card">{issuers_html}</div>
      <div class="card">
        <h3>Window KPIs (last {WINDOW_MINUTES} min)</h3>
        <ul>
          <li>Total Transactions: {overall['total']:,}</li>
          <li>Approved: {overall['aprovadas']:,}</li>
          <li>Approval Rate: {overall['taxa']:.2f}%</li>
        </ul>
      </div>
      <div class="card">
        <h3>Approved Amounts by Currency (Today)</h3>
        {currency_html}
      </div>
      <div class="card"><h3>Clients / User list</h3>{clients_table_html}</div>
      <div class="card">
        <h3>Monitoring Dashboard</h3>
        {dashboard_link_html}
      </div>
      <p style="color:#888;font-size:12px;">WP Confidential</p>
    </body>
    </html>
    """


def build_html_mail_client(now_display, merchants, overall, alert_issuers, daily_curr, app_url="", df_cli=None):
    """Build the merchant-facing alert email with issuer details and dashboard link."""
    from html import escape

    merchants_str = escape(", ".join(str(m) for m in merchants))
    generated_at = escape(str(now_display))

    if daily_curr:
        currency_html = "<ul>" + "".join(
            f"<li>{escape(str(fmt_money(row['moeda'], row['approved_amount'])))} "
            f"({fmt_int(row['approved_tx'])} tx)</li>"
            for row in daily_curr
        ) + "</ul>"
    else:
        currency_html = "<p>No approved amounts today</p>"

    issuers_html = _build_email_issuer_table(alert_issuers)
    dashboard_link_html = _build_dashboard_link(app_url)
    clients_table_html = _build_email_clients_table(df_cli)

    return f"""
    <html>
    <body style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#333;">
      <style>
        body {{ font-family:Segoe UI,Arial,sans-serif; color:#333; }}
        .header {{ background:#0A2A3F; color:#fff; padding:16px; }}
        .card {{ background:#fff; border:1px solid #e2e6ea; border-radius:6px; padding:12px; margin:12px 0; }}
        table {{ width:100%; border-collapse:collapse; }}
        th, td {{ border:1px solid #d8e0e8; padding:8px; text-align:left; }}
        th {{ background:#0a4d86; color:#fff; }}
        tr:nth-child(even) {{ background:#f5f8fb; }}
      </style>
      <div class="header"><div style="margin-bottom:12px;"><img alt="Global Payments" width="220" style="display:block;max-width:100%;height:auto;background:#fff;padding:8px;border-radius:4px;" src="{GLOBALPAYMENTS_LOGO_URL}" /></div><h2>Merchant Approval Alert</h2><h3>{merchants_str}</h3></div>
      <p><strong>Generated:</strong> {generated_at}</p>
      <div class="card">
        <h3>Alert Issuers (Tx &gt; 150 &amp; Approval &lt; 10% &amp; Recurring &lt; 70%)</h3>
        {issuers_html}
      </div>
      <div class="card">
        <h3>Window KPIs (last {WINDOW_MINUTES} min)</h3>
        <ul>
          <li>Total Transactions: {overall['total']:,}</li>
          <li>Approved: {overall['aprovadas']:,}</li>
          <li>Approval Rate: {overall['taxa']:.2f}%</li>
        </ul>
      </div>
      <div class="card"><h3>Approved Amounts by Currency (Today)</h3>{currency_html}</div>
      <div class="card"><h3>Clients / User list</h3>{clients_table_html}</div>
      <div class="card"><h3>Monitoring Dashboard</h3>{dashboard_link_html}</div>
      <p style="color:#888;font-size:12px;">WP Confidential</p>
    </body>
    </html>
    """


def build_schemas_html(
    now_display,
    df_cmp,           # comparison dataframe (now vs 7d)
    acq_data,
    overall_clients
):
    if overall_clients is None:
        table_clients_html  = (
            "<tbody><tr>"
            "<td colspan='8'>No schema data available.</td>"
            "</tr></tbody>"
        )
    else:
        overall_clients.sort(
            key=lambda x: (x["now"]["win_minutes"], -x["now"]["total"])
        )

        rows_c = []
        warn_c = []
        for client_data in overall_clients:
            
            if (int(client_data['now']['total']) + int(client_data['d7']['total'])) == 0:
                continue
                
                    
            diff_rate_now_d7 = client_data['now']['taxa'] - client_data['d7']['taxa']
            delta_arrow = "+" if diff_rate_now_d7 >= 0 else ""
            delta_class = "ok" if diff_rate_now_d7 >= 0 else ("err" if diff_rate_now_d7 < -20 else "warn")
            
            if client_data['d7']['total'] > 0 :
                vol_rate = ((client_data['now']['total'] / client_data['d7']['total'])-1)*100
            else :
                vol_rate = client_data['now']['total']*100 if client_data['now']['total'] > 10 else 9999
            
            vol_arrow = "▲" if vol_rate >= 0 else "▼"
            vol_class = "ok" if vol_rate >= 0 else ("err" if vol_rate < -50 else "warn")
            
            rate_now = client_data['now']['taxa']
            status_class = (
                "ok" if rate_now >= 70 else
                ("warn" if rate_now >= 40 else "err")
            )
            
                
            merchant_slug = slugify(client_data['client'][0].lower())
            m_link = f"{merchant_slug}_issuers.html"
            
            if client_data['client'][0] == "Uber Eats":
                client_data['client'][0] = "Uber"
            elif client_data['client'][0] == "WPGPFBRTIKTOKADSECOM":
                client_data['client'][0] = "TikTok (Ebanx)"
            elif client_data['client'][0] == "Hillside Pasteko":
                client_data['client'][0] = "Bet365"
            elif client_data['client'][0] == "WPGPEYAARSUPERCVV":
                client_data['client'][0] = "PedidosYa"

            win_span = f"""<span class="note">{"("+str(int(client_data['now']['win_minutes']/60))+"h)" if client_data['now']['win_minutes'] > 60 else "("+str(int(client_data['now']['win_minutes']))+"m)"}</span>"""
            
            rows_c.append(
                f"""
                    <a href="{m_link}" style="color: inherit; text-decoration: none;">
                    <div class="{client_data['div_class']} card">
                      <h3>{client_data['client'][0]} {win_span}</h3>
                      <div class="value">{int(client_data['now']['total']):,}<span class="badge {status_class}">
                      {rate_now:.2f}%
                    </span> 
                      </div>
                      <div><span class="{vol_class}">{vol_arrow} {vol_rate:.2f}% </span><span style="font-size: 0.7em;">  | ({delta_arrow}{diff_rate_now_d7:.1f})</span></div>
                      <div class="legend"><b>Decliners:</b> {client_data['decliners']}</div>
                    </div>
                    </a>
                """)

            if client_data['alert_msg'] != "":
                warn_c.append(
                    f"""
                        <div class="legend"><b>{client_data['alert_msg']}</b></div>
                    """)


        table_clients_html = "\n".join(rows_c)
        table_warns_html = "\n".join(warn_c)

    if df_cmp is None or df_cmp.empty:
        table_html = (
            "<tbody><tr>"
            "<td colspan='8'>No schema data available.</td>"
            "</tr></tbody>"
        )
    else:
        rows = []

        # sort by worst approval degradation
        df_cmp = df_cmp.sort_values("total_tx_now", ascending=False)


        for _, r in df_cmp.iterrows():

            if r['schema'] == "CARNET":
                continue

            delta = r["approval_rate_delta"]
            delta_class = "ok" if delta >= 0 else "err"
            delta_arrow = "▲" if delta >= 0 else "▼"
               
            if int(r['total_tx_7d']) > 0 :
                delta_total_p =  ((int(r['total_tx_now']) / int(r['total_tx_7d'])) - 1 ) * 100
            else:
                delta_total_p = int(r['total_tx_now'])*100

            delta_class_total = "ok" if delta_total_p >= 0 else "err"
            delta_arrow_total = "▲" if delta_total_p >= 0 else "▼"
            
            rate_now = r["approval_rate_now"]

            status_class = (
                "ok" if rate_now >= 80 else
                ("warn" if rate_now >= 50 else "err")
            )

            rows.append(
                f"""
                <div class="card">
                <table>
                  <tbody>
                            <tr>
                              <td><h2>{r['schema']}</h2></td>

                              <td>
                                            <div >
                                      <div class="value">{int(r['total_tx_now']):,} <span class="badge">
                                      {r['approval_rate_now']:.2f}%
                                    </span> 
                                      </div>
                                      <div><span class="{delta_class_total}">{delta_arrow_total} {delta_total_p:+.2f}% </span><span style="font-size: 0.7em;">  | ({delta:+.2f})</span></div>
                                  </div>
                              </td>  
                            </tr>
                    </tbody>
                </table>
                </div>
                """
            )
        table_html =  "\n".join(rows)


    # ---- regroup acq_data ----
    grouped = defaultdict(dict)

    for df in acq_data:
        if df.empty:
            continue
        country = df["country"].iloc[0]
        days_ago = int(df["days_ago"].iloc[0])
        grouped[country][days_ago] = df

    # ---- ACQ INFO ----
    html_acq_r = []

    for country, data in grouped.items():
        if 0 not in data or 7 not in data:
            continue

        df_now = data[0]
        df_d7  = data[7]

        # ---- summarize NOW ----
        total_now = int(df_now["total_tx"].sum())
        approved_now = int(df_now["approved"].sum())
        rate_now = round((approved_now / total_now * 100) if total_now else 0, 2)

        # ---- summarize D-7 ----
        total_d7 = int(df_d7["total_tx"].sum())
        approved_d7 = int(df_d7["approved"].sum())
        rate_d7 = round((approved_d7 / total_d7 * 100) if total_d7 else 0, 2)

        # ---- delta ----
        delta = round(rate_now - rate_d7, 2)
        delta_symbol = "▲" if delta >= 0 else "▼"
        delta_class = "ok" if delta >= 0 else "err"

        # ---- rate_class ----
        rate_class = "ok" if rate_now >= 50 else ("err" if rate_now < 25 else "warn")

        if total_d7 > 0 :
            delta_total_p =  ((int(total_now) / int(total_d7)) - 1 ) * 100
        else:
            delta_total_p = int(total_now)*100

        delta_class_total = "ok" if delta_total_p >= 0 else "err"
        delta_arrow_total = "▲" if delta_total_p >= 0 else "▼"

        if country == "AR":
            country_name = f"""<img alt="ARG" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAOBAMAAAA23ZrAAAAAHlBMVEV0rN////+iyOr+9N3/+vH/+vD86b7yz3vxzXjnpBty6toBAAAAKElEQVQI12MgByghgAKDIAiYGYJIATBHtLMEwRGpbIVxEMpQDSADAAASAwihg8yZPwAAAABJRU5ErkJggg=="/> WP Argentina"""
        elif country == "BR":
            country_name = f"""<img alt="BRA" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAPCAMAAADXs89aAAAAclBMVEUAmzr93wAAJ3YInTcVO34ILnsToDUopjFArCu1qiLLuhjNuxe4zQ/r2gQhR4AQNoAaOmp+n7RTZFVetCVvuSF/vR2QwhmYxBepyRPBzw7U1Ara1giHp7hulKlafqZmjqVFapKLnJCBkYNWb38wTXssRmKdGTTHAAAAe0lEQVQY04VQVw6FMAx7CS2jLS3wFntz/ytShFBAINVflmXZTl5OeN6TGpZVeBP9PwgBuX9V33GUICZR/DmJgQLJOFoIKIKj6gsAQ9ekaYuZpb+9WoHFggaxr6eNK3JnmjOGbNzdlM0NN1pT9mnJTEtot5R2t/tK+okLK49+BVPNPvMpAAAAAElFTkSuQmCC"/> WP Brasil"""
        elif country == "MX":
            country_name = f"""<img alt="MEX" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAANCAMAAAB1uQVvAAAAaVBMVEUAZ0XODyT///+rTFZYnIbgZ3X3+/v48O2/wcBEeGfPEyjk3tXM2MeMaE/++/nw9O3u7+LMvpVIfGzZ2cvM2MaYvbfjza++xay8sqSTsqKCp5Rxk4i0d36njXygcHa2WGKyhmCLc1t8TDAitl7UAAAAaElEQVQY033PRw6AIBRFUf0WpKnYe9v/IkUgxgh6w+jkDfieKQRd5KvWDw9ujxWnLkcIkMObjVOwPRP8mO09LcXOO2p5xuqhZ3pPHg551bIcpJP3f1IAex//3GX25PICY/nwmOimQLWcfAIE0viIgjsAAAAASUVORK5CYII="/> WP Mexico"""
        elif country == "CO":
            country_name = f"""<img alt="COL" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPBAMAAAD9gUllAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAElBMVEX80RZ+hFUAOJObG0HOESYAAAD8bLiPAAAAAWJLR0QF+G/pxwAAAAd0SU1FB+QCGQ0CB7Ja3DMAAAAWSURBVAjXY2JAAkzU5QgigAAqh6p6ANs1A0sZ94y0AAAAJXRFWHRkYXRlOmNyZWF0ZQAyMDIwLTAyLTI1VDEzOjAyOjA3KzAwOjAwN9pO2QAAACV0RVh0ZGF0ZTptb2RpZnkAMjAyMC0wMi0yNVQxMzowMjowNiswMDowMODw/dEAAAAASUVORK5CYII="/>WP Colombia"""
        else:
            country_name = country

        # ---- HTML ----
        html_acq_r.append(f"""
<div class="flex">
  <table class="acq-card card">
    <thead>
      <tr>
        <th colspan="2">{country_name}</th>
      </tr>
    </thead>
    <tbody ><!--class="{delta_class}"-->
      <tr>
        <th>
          <div>
            <div class="value">
              <h1>
                {total_now:,}
                <span class="badge {rate_class}">
                  {rate_now:.2f}%
                </span>
              </h1>
            </div>
            <div>
              <span class="{delta_class_total}">
                {delta_arrow_total} {abs(delta_total_p):.2f}%
              </span>
              <span style="font-size: 0.7em;">
                | ({(rate_now - rate_d7):.2f})
              </span>
            </div>
          </div>
        </th>
      </tr>
    </tbody>
  </table>
</div>""")

    html_acq =  "\n".join(html_acq_r)

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta http-equiv="refresh" content="{REFRESH_SECONDS}">
<title>Schema Approval Comparison</title>

<style>
{html_style}
.delta.ok {{ color: #0a7f3f; }}
.delta.err {{ color: #b00020; }}
</style>
</head>

<body>
<!--header>
  <div class="wrap">
    <h1>Schema Approval Comparison</h1>
    <div class="sub">
      Generated at <strong>{now_display}</strong> ({TZ_DISPLAY})
      • Now vs 7 days ago
    </div>
  </div>
</header-->

<main class="wrap">
    <section class="err">
        {table_warns_html}
    </section>
  <section class="section flex">
    {html_acq}
  </section>

  <section class="section flex">
    <!--h2>Schema Performance — Window {WINDOW_MINUTES} min</h2-->
    {table_html}
  </section>
<section class="kpi flex">
    {table_clients_html}
</section>
<section>
                    <div class="note"><span>* </span><span class="badge card">Healthy (< 25%)</span> <span class="badge warn"> Attention (> 26% < 50%)</span> <span class="badge err">Critical (> 50%) </span></div>
                    <div class="note">
                        <div class="kpi">
                            <div class=" card" style="background:#f0f0f0; max-width: max-content;border-style: solid;border-color: #a9a7a7;border-width: 0.5px; padding: 8px;" >		
                              <h3>Merchant Name <span class="note">(Time frame [15m / 24h]) </span></h3>
                              <div class="value" style="font-size: 1.2rem;">Current Volume <span class="badge ok" style="font-size: 0.6rem;">
                              Current App Rate
                            </span> 
                              </div>
                              <div><span class="ok">▼▲ (%) Volume compared to 4 weeks avg.</span><span style="font-size: 0.7em;">  | (App Rate compared 4 weeks avg.)</span></div>
                              <div class="legend"><b>Decliners:</b> Top declined issuers</div>
                            </div>
                        </div>
                    </div>
</section>

  <footer>
    WP Confidential 
  </footer>

</main>
</body>
</html>
"""

def build_schemas_html_email(
    now_display,
    df_cmp,           # comparison dataframe (now vs 7d)
    acq_data,
    overall_clients
):
    if overall_clients is None:
        table_clients_html  = (
            "<tbody><tr>"
            "<td colspan='8'>No schema data available.</td>"
            "</tr></tbody>"
        )
    else:
        overall_clients.sort(key=lambda x: x["now"]["total"], reverse=True)
        rows_c = []
        warn_c = []
        for client_data in overall_clients:

            if (int(client_data['now']['total']) + int(client_data['d7']['total'])) == 0:
                continue

            if client_data['div_class'] == "":
                continue

            diff_rate_now_d7 = client_data['now']['taxa'] - client_data['d7']['taxa']
            delta_arrow = "+" if diff_rate_now_d7 >= 0 else ""
            delta_class = "ok" if diff_rate_now_d7 >= 0 else ("err" if diff_rate_now_d7 < -20 else "warn")

            if client_data['d7']['total'] > 0 :
                vol_rate = ((client_data['now']['total'] / client_data['d7']['total'])-1)*100
            else :
                vol_rate = client_data['now']['total']*100 if client_data['now']['total'] > 10 else 9999

            vol_arrow = "▲" if vol_rate >= 0 else "▼"
            vol_class = "ok" if vol_rate >= 0 else ("err" if vol_rate < -50 else "warn")

            rate_now = client_data['now']['taxa']
            status_class = (
                "ok" if rate_now >= 70 else
                ("warn" if rate_now >= 40 else "err")
            )

            if client_data['client'][0] == "Uber Eats":
                client_data['client'][0] = "Uber"
            elif client_data['client'][0] == "WPGPFBRTIKTOKADSECOM":
                client_data['client'][0] = "TikTok (Ebanx)"
            elif client_data['client'][0] == "Hillside Pasteko":
                client_data['client'][0] = "Bet365"
            elif client_data['client'][0] == "WPGPEYAARSUPERCVV":
                client_data['client'][0] = "PedidosYa"


            win_span = f"""<span class="note">
                       {"("+str(int(client_data['now']['win_minutes']/60))+"h)" if client_data['now']['win_minutes'] > 60 else "("+str(int(client_data['now']['win_minutes']))+"m)"}
                       </span>"""

            if len(rows_c)==0 : 
                rows_c.append(f"""<tr>""")
            elif len(rows_c)%1 == 0 : 
                rows_c.append(f"""</tr><tr>""")

            alert_issuers = client_data['alert_issuers']

            # Alert issuers table
            if alert_issuers.empty:
                issuers_html = ""
            else:
                rows = "".join(
                    f"""<tr><td>{r['codigo_cliente']} </td><td><b>{r['issuer_bank']}</b>
                         <img width='25' alt='{str(r['administradora']).capitalize()} - {r['cred_deb']}' src='{logos.get((r["administradora"], str(r["cred_deb"])[0]),"")} '/> </td>
                         <td> <small> Total last 15min: {r['total_tx']}, 
                         <br>Approval Rate: <span class="badge err">{r['approval_rate']:.2f}%</span></small></td>
                        <!--td>{r['total_tx']}</td>"
                        <td><small>{r['recurring_percentage']:,}%</small></td>"
                        <td>{r['approval_rate']:.2f}%</td></tr-->"""
                    for _, r in alert_issuers.iterrows()
                )
                issuers_html = f"""<table border='0' cellpadding='4' class={client_data['div_class']}>
                                    <tbody>{rows}</tbody>
                                    </table>"""
            alert_m = ""
            if client_data['alert_msg'] != "":
                alert_m = f"""<div class="{client_data['div_class']} card_m"><div class="err" style="color: #003a70;"><b>{client_data['alert_msg']}</b></div></div>"""
            if client_data['alert_bad_iss'] != "":
                alert_m += f"""<div class="{client_data['div_class']} card_m"><div class="err" style="color: #003a70;"><b>{client_data['alert_bad_iss']}</b></div></div>"""


            merchant_slug = slugify(client_data["client"][0].lower())
            client_report_url = (
                f"{APP_BASE_URL.rstrip(chr(47))}/reports/"
                f"{merchant_slug}_issuers.html"
            )
            rows_c.append(
                f"""<td width="100%" valign="top" style="padding:8px;min-width: 700px;" >
                    {alert_m}
                    <div class="card_m">
                     <div class="card-body">
                      <h3><a href="{client_report_url}" style="color:inherit;text-decoration:none;">{client_data['client'][0]} {win_span}</a></h3><p style="margin:6px 0 10px;"><a href="{client_report_url}" style="display:inline-block;background:#005aa3;color:#fff;padding:8px 12px;text-decoration:none;border-radius:4px;">Open client report</a></p>
                      <div class="value">{int(client_data['now']['total']):,} <span class="badge {status_class}">
                      {rate_now:.2f}%
                    </span>
                      </div>
                      <div><span class="{vol_class}">{vol_arrow} {vol_rate:.2f}% </span><span style="font-size: 0.7em;">  | ({delta_arrow}{diff_rate_now_d7:.1f})</span></div>
                      <div class="clients"><b>Top ClientIds:</b> {client_data['top_ids']}</div>
                      <div class="clients"><h4>Clients / User list</h4>{_build_email_clients_table(client_data.get('userlist_rows', []))}</div>
                    </div>
                      <div class="card-chart">
                      <img  alt="last 15 min" src="data:image/png;base64,{client_data['img_ts']}"/>
                      </div>
                    </div>
                    </div>
                      <div class="card-chart">
                    {issuers_html}
                      </div>
                    </div>
                """)

        
        rows_c.append(f"""</tr>""")
        table_clients_html = "\n".join(rows_c)
        table_warns_html = "\n".join(warn_c)

    if df_cmp is None or df_cmp.empty:
        table_html = (
            "<tbody><tr>"
            "<td colspan='8'>No schema data available.</td>"
            "</tr></tbody>"
        )
    else:
        rows = []

        # sort by worst approval degradation
        df_cmp = df_cmp.sort_values("total_tx_now", ascending=False)


        for _, r in df_cmp.iterrows():

            if r['schema'] == "CARNET":
                continue

            delta = r["approval_rate_delta"]
            delta_class = "ok" if delta >= 0 else "err"
            delta_arrow = "▲" if delta >= 0 else "▼"

            if int(r['total_tx_7d']) > 0 :
                delta_total_p =  ((int(r['total_tx_now']) / int(r['total_tx_7d'])) - 1 ) * 100
            else:
                delta_total_p = int(r['total_tx_now'])*100

            delta_class_total = "ok" if delta_total_p >= 0 else "err"
            delta_arrow_total = "▲" if delta_total_p >= 0 else "▼"

            rate_now = r["approval_rate_now"]

            status_class = (
                "ok" if rate_now >= 80 else
                ("warn" if rate_now >= 50 else "err")
            )

            rows.append(
                f"""
                <td width="33%" style="padding:8px;">
                <table>
                  <tbody class="card">
                            <tr>
                              <td><h2>{r['schema']}</h2></td>

                              <td>
                                            <div >
                                      <div class="value">{int(r['total_tx_now']):,} <span class="badge">
                                      {r['approval_rate_now']:.2f}%
                                    </span>
                                      </div>
                                      <div><span class="{delta_class_total}">{delta_arrow_total} {delta_total_p:+.2f}% </span><span style="font-size: 0.7em;">  | ({delta:+.2f})</span></div>
                                  </div>
                              </td>
                            </tr>
                    </tbody>
                </table>
                </td>
                """
            )
        table_html =  "\n".join(rows)


    # ---- regroup acq_data ----
    grouped = defaultdict(dict)

    for df in acq_data:
        if df.empty:
            continue
        country = df["country"].iloc[0]
        days_ago = int(df["days_ago"].iloc[0])
        grouped[country][days_ago] = df

    # ---- ACQ INFO ----
    html_acq_r = []

    for country, data in grouped.items():
        if 0 not in data or 7 not in data:
            continue

        df_now = data[0]
        df_d7  = data[7]

        # ---- summarize NOW ----
        total_now = int(df_now["total_tx"].sum())
        approved_now = int(df_now["approved"].sum())
        rate_now = round((approved_now / total_now * 100) if total_now else 0, 2)

        # ---- summarize D-7 ----
        total_d7 = int(df_d7["total_tx"].sum())
        approved_d7 = int(df_d7["approved"].sum())
        rate_d7 = round((approved_d7 / total_d7 * 100) if total_d7 else 0, 2)

        # ---- delta ----
        delta = round(rate_now - rate_d7, 2)
        delta_symbol = "▲" if delta >= 0 else "▼"
        delta_class = "ok" if delta >= 0 else "err"

        if total_d7 > 0 :
            delta_total_p =  ((int(total_now) / int(total_d7)) - 1 ) * 100
        else:
            delta_total_p = int(total_now)*100

        delta_class_total = "ok" if delta_total_p >= 0 else "err"
        delta_arrow_total = "▲" if delta_total_p >= 0 else "▼"
        
        # ---- rate_class ----
        rate_class = "ok" if rate_now >= 50 else ("err" if rate_now < 25 else "warn")
        
        if country == "AR":
            country_name = f"""<img alt="ARG" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAOBAMAAAA23ZrAAAAAHlBMVEV0rN////+iyOr+9N3/+vH/+vD86b7yz3vxzXjnpBty6toBAAAAKElEQVQI12MgByghgAKDIAiYGYJIATBHtLMEwRGpbIVxEMpQDSADAAASAwihg8yZPwAAAABJRU5ErkJggg=="/> WP Argentina"""
        elif country == "BR":
            country_name = f"""<img alt="BRA" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABYAAAAPCAMAAADXs89aAAAAclBMVEUAmzr93wAAJ3YInTcVO34ILnsToDUopjFArCu1qiLLuhjNuxe4zQ/r2gQhR4AQNoAaOmp+n7RTZFVetCVvuSF/vR2QwhmYxBepyRPBzw7U1Ara1giHp7hulKlafqZmjqVFapKLnJCBkYNWb38wTXssRmKdGTTHAAAAe0lEQVQY04VQVw6FMAx7CS2jLS3wFntz/ytShFBAINVflmXZTl5OeN6TGpZVeBP9PwgBuX9V33GUICZR/DmJgQLJOFoIKIKj6gsAQ9ekaYuZpb+9WoHFggaxr6eNK3JnmjOGbNzdlM0NN1pT9mnJTEtot5R2t/tK+okLK49+BVPNPvMpAAAAAElFTkSuQmCC"/> WP Brasil"""
        elif country == "MX":
            country_name = f"""<img alt="MEX" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAANCAMAAAB1uQVvAAAAaVBMVEUAZ0XODyT///+rTFZYnIbgZ3X3+/v48O2/wcBEeGfPEyjk3tXM2MeMaE/++/nw9O3u7+LMvpVIfGzZ2cvM2MaYvbfjza++xay8sqSTsqKCp5Rxk4i0d36njXygcHa2WGKyhmCLc1t8TDAitl7UAAAAaElEQVQY033PRw6AIBRFUf0WpKnYe9v/IkUgxgh6w+jkDfieKQRd5KvWDw9ujxWnLkcIkMObjVOwPRP8mO09LcXOO2p5xuqhZ3pPHg551bIcpJP3f1IAex//3GX25PICY/nwmOimQLWcfAIE0viIgjsAAAAASUVORK5CYII="/> WP Mexico"""
        elif country == "CO":
            country_name = f"""<img alt="COL" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABcAAAAPBAMAAAD9gUllAAAABGdBTUEAALGPC/xhBQAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAElBMVEX80RZ+hFUAOJObG0HOESYAAAD8bLiPAAAAAWJLR0QF+G/pxwAAAAd0SU1FB+QCGQ0CB7Ja3DMAAAAWSURBVAjXY2JAAkzU5QgigAAqh6p6ANs1A0sZ94y0AAAAJXRFWHRkYXRlOmNyZWF0ZQAyMDIwLTAyLTI1VDEzOjAyOjA3KzAwOjAwN9pO2QAAACV0RVh0ZGF0ZTptb2RpZnkAMjAyMC0wMi0yNVQxMzowMjowNiswMDowMODw/dEAAAAASUVORK5CYII="/>WP Colombia"""
        else:
            country_name = country

        # ---- HTML ----
        html_acq_r.append(f"""
<td width="25%" valign="top" style="padding:8px;">
  <table class="acq-card card">
    <thead>
      <tr>
        <th colspan="2">{country_name}</th>
      </tr>
    </thead>
    <tbody >
      <tr>
        <th>
          <div>
            <div class="value">
              <h1>
                {total_now:,}
                <span class="badge {rate_class}">
                  {rate_now:.2f}%
                </span>
              </h1>
            </div>
            <div>
              <span class="{delta_class_total}">
                {delta_arrow_total} {abs(delta_total_p):.2f}%
              </span>
              <span style="font-size: 0.7em;">
                | ({(rate_now - rate_d7):.2f})
              </span>
            </div>
          </div>
        </th>
      </tr>
    </tbody>
  </table>
</td>""")

    html_acq =  "\n".join(html_acq_r)

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<!--meta http-equiv="refresh" content="{REFRESH_SECONDS}"-->
<title>Schema Approval Comparison</title>

<style>
{html_style_m}
.delta.ok {{ color: #0a7f3f; }}
.delta.err {{ color: #b00020; }}
</style>
</head>

<body>
<main class="wrap">
<div class="top header">
  <div class="wrap"  style="min-width: 700px;background-color: #312af8;">
  <img alt="Global Payments" width="220" style="display:block;max-width:100%;height:auto;background:#fff;padding:8px;border-radius:4px;" src="{GLOBALPAYMENTS_LOGO_URL}" />
   Latam -  Alert Notice
  </div>
</div>
<a href="https://ukdc1-pc-nag101.fnfis.com/tier1/byissuer/" target="reportFrame" style="color: inherit; text-decoration: none;">
<!--table width="100%" cellpadding="0" cellspacing="0" class="err">
    {table_warns_html}
</table-->

  <!--table width="100%" cellpadding="0" cellspacing="0">
    <tr>
    {html_acq}
  </tr>
</table>

<table width="100%" cellpadding="0" cellspacing="0">
    <tr>
    {table_html}
  </tr>
</table>
<table width="100%" cellpadding="0" cellspacing="0" class="err">
    {table_warns_html}
</table-->

<table width="100%" cellpadding="0" cellspacing="0" class="">
    {table_clients_html}
</table>
</a>
<table width="100%" cellpadding="0" cellspacing="0">
                    <div class="note"><span>* </span><span class="badge card">Healthy (< 25%)</span> <span class="badge warn"> Attention (> 26% < 50%)</span> <span class="badge err">Critical (> 50%) </span></div>
                    <div class="note">
                        <div class="kpi">
                            <div class=" card" style="background:#f0f0f0; max-width: max-content;border-style: solid;border-color: #a9a7a7;border-width: 0.5px;padding: 8px;" >		
                              <h3>Merchant Name <span class="note">(Time frame [15m / 24h]) </span></h3>
                              <div class="value" style="font-size: 1.2rem;">Current Volume <span class="badge ok" style="font-size: 0.6rem;">
                              Current App Rate
                            </span> 
                              </div>
                              <div><span class="ok">▼▲ (%) Volume compared to 4 weeks avg.</span><span style="font-size: 0.7em;">  | (App Rate compared 4 weeks avg.)</span></div>
                              <div class="legend"><b>Decliners:</b> Top declined issuers</div>
                            </div>
                        </div>
                    </div>

</table>

  <footer>
    WP Confidential
  </footer>

</main>
</body>
</html>
"""



