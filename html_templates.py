from datetime import datetime
from config import html_style, REFRESH_SECONDS, WINDOW_MINUTES, TZ_DISPLAY
from utils import fmt_int, fmt_money
from collections import defaultdict

# ---------- HTML (Your WP-styled template with minimal adaptations) ----------
def build_html(now_display, merchants, overall, df_worst, img_ts_b64, img_worst_b64, *, daily_curr):
    # issuer table logic stays the same...

    merchants_str = ", ".join(merchants)

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
            rows.append(
                f"<tr>"
                f"<td>{r['issuer_bank']}</td>"
                f"<td>{int(r['total_tx']):,}</td>"
                f"<td>{int(r['approved']):,}</td>"
                f"<td>{int(r['declined']):,}</td>"
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
    <h1>Merchant Approval Performance — {merchants_str}</h1>
    <div class="sub">Generated at <strong>{now_display}</strong> ({TZ_DISPLAY}) • Auto-refresh {REFRESH_SECONDS}s</div>
  </div>
</header>

<main class="wrap">

  <!-- Window KPIs -->
  <section class="kpi">
    <div class="card">
      <h3>Total Transactions ({WINDOW_MINUTES} min)</h3>
      <div class="value">{overall['total']:,}</div>
      <div class="delta">Window: last {WINDOW_MINUTES} min</div>
    </div>
    <div class="card">
      <h3>Approved ({WINDOW_MINUTES} min)</h3>
      <div class="value">{overall['aprovadas']:,}</div>
      <div class="delta">Status: {'Good' if overall['taxa']>=90 else ('Watch' if overall['taxa']>=80 else 'Alert')}</div>
    </div>
    <div class="card">
      <h3>Approval Rate ({WINDOW_MINUTES} min)</h3>
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

  <!-- Issuer Table -->
  <section class="section card">
    <h2>Issuer Details — last {WINDOW_MINUTES} minutes</h2>
    <table>
      <thead>
        <tr>
          <th>Issuer Bank</th>
          <th>Total</th>
          <th>Approved</th>
          <th>Declined</th>
          <th>Recurring</th>
          <th>Approval Rate</th>
        </tr>
      </thead>
      {table_html}
    </table>
  </section>

  <footer>WP Confidential • Merchants: {merchants_str}</footer>
</main>
</body>
</html>
"""

def build_html_mail(now_display, merchants, overall, alert_issuers, daily_curr, app_url=""):
    merchants_str = ", ".join(merchants)

    # Currency chips
    if daily_curr:
        currency_html = "<ul>" + "".join(
            f"<li>{fmt_money(row['moeda'], row['approved_amount'])} "
            f"({fmt_int(row['approved_tx'])} tx)</li>"
            for row in daily_curr
        ) + "</ul>"
    else:
        currency_html = "<p>No approved amounts today</p>"

    # Alert issuers table
    if alert_issuers.empty:
        issuers_html = "<p>No issuers triggered the alert condition.</p>"
    else:
        rows = "".join(
            f"<tr><td>{r['issuer_bank']}</td><td>{r['total_tx']}</td>"
            f"<td><small>{r['recurring_percentage']:,}%</small></td>"
            f"<td>{r['approval_rate']:.2f}%</td></tr>"
            for _, r in alert_issuers.iterrows()
        )
        issuers_html = f"<table border='1' cellpadding='4'><thead><tr><th>Issuer</th><th>Total Tx</th><th>%Rec.</th><th>Approval Rate</th></tr></thead><tbody>{rows}</tbody></table>"

    from html import escape

    if app_url:
        safe_url = escape(app_url, quote=True)
        app_link_html = (
            f'<p><a href="{safe_url}" style="display:inline-block;background:#005aa3;color:#fff;'
            f'padding:10px 16px;text-decoration:none;border-radius:4px;">Open WPL LatAm TSO Dashboard</a></p>'
            f'<p style="font-size:12px;color:#666;">Direct link: <a href="{safe_url}">{safe_url}</a></p>'
        )
    else:
        app_link_html = (
            '<p style="font-size:12px;color:#666;">Dashboard link is not configured. '
            'Set APP_BASE_URL in the application environment.</p>'
        )

    return f"""
    <html>
    <body style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#333;">
<style>
{html_style}
</style>
      <h2>Merchant Approval Alert </h2>
      <h2>{merchants_str}</h2>
      <p><strong>Generated:</strong> {now_display}</p>
      <h3>Alert Issuers (Tx > 150 & Approval < 10% & Reccuring < 70%)</h3>
      <div class="card">
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
      <div class="card">
      <h3>Approved Amounts by Currency (Today)</h3>
      {currency_html}
      </div>
      <div class="card">
      <h3>Monitoring Dashboard</h3>
      {app_link_html}
      </div>

      <p style="color:#888;font-size:12px;">WP Confidential</p>
    </body>
    </html>
    """


def build_html_mail_client(now_display, merchants, overall, alert_issuers, daily_curr, app_url=""):
    """Build the merchant-facing alert email with full issuer metrics and an app link."""
    from html import escape

    merchants_str = escape(", ".join(merchants))
    generated_at = escape(now_display)

    email_css = """
      body { font-family: Segoe UI, Arial, sans-serif; font-size: 14px; color: #333; }
      .header { background: #0A2A3F; color: #fff; padding: 16px; }
      .card { background: #fff; border: 1px solid #e2e6ea; border-radius: 6px; padding: 12px; margin: 12px 0; }
      .muted { color: #666; font-size: 12px; }
      .app-link { display: inline-block; background: #005aa3; color: #fff !important; padding: 10px 16px; text-decoration: none; border-radius: 4px; }
      table { width: 100%; border-collapse: collapse; }
      th, td { border: 1px solid #d8e0e8; padding: 8px; text-align: left; }
      th { background: #0a4d86; color: #fff; }
      tr:nth-child(even) { background: #f5f8fb; }
    """

    if daily_curr:
        currency_html = "<ul>" + "".join(
            f"<li>{escape(fmt_money(row['moeda'], row['approved_amount']))} "
            f"({fmt_int(row['approved_tx'])} tx)</li>"
            for row in daily_curr
        ) + "</ul>"
    else:
        currency_html = "<p>No approved amounts today</p>"

    if alert_issuers is None or alert_issuers.empty:
        issuers_html = "<p>No issuers triggered the alert condition.</p>"
    else:
        rows = []
        for _, r in alert_issuers.iterrows():
            bank = escape(str(r["issuer_bank"]))
            total = fmt_int(r["total_tx"])
            approved = fmt_int(r["approved"]) if "approved" in r.index else "N/A"
            declined = fmt_int(r["declined"]) if "declined" in r.index else "N/A"
            recurring = f"{float(r['recurring_percentage']):.1f}%"
            approval_rate = f"{float(r['approval_rate']):.2f}%"
            rows.append(
                "<tr>"
                f"<td>{bank}</td><td>{total}</td><td>{approved}</td><td>{declined}</td>"
                f"<td>{recurring}</td><td>{approval_rate}</td>"
                "</tr>"
            )
        issuers_html = (
            "<table><thead><tr><th>Issuer</th><th>Total Tx</th><th>Approved</th>"
            "<th>Declined</th><th>Recurring</th><th>Approval Rate</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    if app_url:
        safe_url = escape(app_url, quote=True)
        app_link_html = (
            f'<p><a class="app-link" href="{safe_url}">Open WPL LatAm TSO Dashboard</a></p>'
            f'<p class="muted">Direct link: <a href="{safe_url}">{safe_url}</a></p>'
        )
    else:
        app_link_html = (
            '<p class="muted">Dashboard link is not configured. Set APP_BASE_URL '
            'in the application environment to include it in this e-mail.</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Merchant Approval Alert - {merchants_str}</title>
<style>{email_css}</style>
</head>
<body>
  <div class="header">
    <h2 style="margin:0;">Partial Approval Rate Degradation</h2>
    <div>{merchants_str}</div>
  </div>
  <p><strong>Generated:</strong> {generated_at}</p>
  <div class="card">
    <h3>Issuer Details — last {WINDOW_MINUTES} minutes</h3>
    {issuers_html}
  </div>
  <div class="card">
    <h3>Window KPIs (last {WINDOW_MINUTES} min)</h3>
    <ul>
      <li>Total Transactions: {fmt_int(overall['total'])}</li>
      <li>Approved: {fmt_int(overall['aprovadas'])}</li>
      <li>Approval Rate: {float(overall['taxa']):.2f}%</li>
    </ul>
  </div>
  <div class="card">
    <h3>Approved Amounts by Currency (Today)</h3>
    {currency_html}
  </div>
  <div class="card">
    <h3>Monitoring Dashboard</h3>
    {app_link_html}
  </div>
  <p class="muted">WP Confidential • WP-Latam TSO Team</p>
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
        overall_clients.sort(key=lambda x: x["now"]["total"], reverse=True)
        rows_c = []
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

            if client_data['client'][0] == "Uber Eats":
                client_data['client'][0] = "Uber"
            elif client_data['client'][0] == "Hillside Pasteko":
                client_data['client'][0] = "Bet365"


            rows_c.append(
                f"""
                    <div class="card">
                      <h3>{client_data['client'][0]} </h3>
                      <div class="value">{int(client_data['now']['total']):,} <span class="badge {status_class}">
                      {rate_now:.2f}%
                    </span> 
                      </div>
                      <div><span class="{vol_class}">{vol_arrow} {vol_rate:.2f}% </span><span style="font-size: 0.7em;">  | ({delta_arrow}{diff_rate_now_d7:.1f})</span></div>
                      <div class="legend"><b>Decliners:</b> {client_data['decliners']}</div>
                    </div>
                """)

        table_clients_html = "\n".join(rows_c)

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
#            rows.append(
#                f"""
#                <tr>
#                  <td><b>{r['schema']}</b></td>
#
#                  <td>{int(r['total_tx_7d']):,}</td>
#                  <td>{int(r['total_tx_now']):,}
#                    <br/>
#                    <small class="{delta_class_total}">
#                      {delta_arrow_total} {delta_total_p:+.2f}%
#                    </small></td>
#                  <td>{int(r['total_tx_delta']):+,}</td>
#
#                  <td>{int(r['declined_7d']):,}</td>
#                  <td>{int(r['declined_now']):,}</td>
#
#                  <td>
#                    <span class="badge {status_class}">
#                      {r['approval_rate_now']:.2f}%
#                    </span>
#                    <br/>
#                    <small class="{delta_class}">
#                      {delta_arrow} {delta:+.2f}%
#                    </small>
#                  </td>
#
#                  <td>{r['recurring_percentage_now']:.1f}%</td>
#                </tr>
#                """
#            )
#
#        table_html = "<tbody>" + "\n".join(rows) + "</tbody>"


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

        if country == "AR":
            country_name = "WP Argentina"
        elif country == "BR":
            country_name = "WP Brasil"
        elif country == "MX":
            country_name = "WP Mexico"
        elif country == "CO":
            country_name = "WP Colombia"
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
                <span class="badge {delta_class}">
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

  <footer>
    WP Confidential 
  </footer>

</main>
</body>
</html>
"""
