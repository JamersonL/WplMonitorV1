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

def build_html_mail(now_display, merchants, overall, alert_issuers, daily_curr):
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

      <p style="color:#888;font-size:12px;">WP Confidential</p>
    </body>
    </html>
    """


def build_html_mail_client(now_display, merchants, overall, alert_issuers, daily_curr):
    merchants_str = ", ".join(merchants)

    now_display = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    html_style_c = f"""
      .header{{background:#0A2A3F;color:#fff;}}
      .h1{{font-size:24px;line-height:24px;margin:0;padding:8px 0;}}
      .sub{{font-size:12px;opacity:0.9;}}
      .card{{background:#fff;border:1px solid #e2e6ea;border-radius:6px;padding:12px;}}
      .kpi-title{{font-size:12px;color:#555;margin:0 0 6px;}}
      .kpi-value{{font-size:22px;font-weight:600;margin:0;}}
      .kpi-sub{{font-size:12px;color:#666;margin-top:4px;}}
      .muted{{color:#666;font-size:12px;}}
      .footer{{font-size:11px;color:#666;text-align:center;padding:16px 0;}}

      """
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

    return f"""
    <html>
    <body style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#333;">
<style>
{html_style_c}
{html_style}
</style>
     <div class="header">
  <div class="wrap">
  <img alt="WP" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABAgAAADBCAYAAABCMYJ1AAAQAElEQVR4AeydB5wTxRfHf3OA+LeCHWwgSkd6F2k2ihXsgKBiVxCxF0DFXrB3RcEuig0bSu9dilTLX8X2t4KNNv/327scuVzKJpnNJXcvn2yyOzvz5s13dqe8mZ3Ng36UgBJQAkpACSgBJaAElIASUAJKQAkogdJOIGH61ECQEJF6UAJKQAkoASWgBJSAElACSkAJKAElkO0E0tdPDQTpM1QJSkAJKAEloASUgBJQAkpACSgBJaAEgiWQAelqIMgAZI1CCSgBJaAElIASUAJKQAkoASWgBJRAPALZcE4NBNmQC6qDElACSkAJKAEloASUgBJQAkpACZRmAjmRNjUQ5EQ2qZJKQAkoASWgBJSAElACSkAJKAElkL0ESodmaiAoHfmoqVACSkAJKAEloASUgBJQAkpACSiBoAiUEblqICgjGa3JVAJKQAkoASWgBJSAElACSkAJKIHoBNQ1n4AaCPI56K8SUAJKIBACdtHyBXbgcGt7XWbt6ZemvjH8xTdaO3uRDUTRMiDU3veMtX2vTD0PvPwbZG2fy6195jXNhzJwzWgSlYASUAJKoNQQ0IT4JKAGAp+g1JsSUAJKICUClwxthLc+AaYtAKYvSn1j+HcmAQNvhv1szZCUdCnDgeyQERYPvQBMmpN6Hnj5txCYMh8Y9hDsU6+qkQD6UQJKQAkoASWQDQRUB1cE1EDgiqTKUQJKQAlEELCvvmfxzU/A5k3AFhfbRuD7X4B5S4dGRKWHiQh8MAXYIPxc5YMxwMfTEsWq55WAElACSkAJKAEXBFRGxgiogSBjqDUiJaAEyhwBdkjheJDZijxPbpmjmV6CN21OL3xkaLsl3+AQ6a7HSkAJKAEloASUQNIENED2EFADQfbkhWqiBJRAaSOQJ6PMQaQpT4vupLEGwSwImUknTAMoASWgBJSAEsh6AqpgDhHQVmYOZZaqqgSUgBJQAkpACSgBJaAElIASyC4Cqk1pIqAGgtKUm5oWJaAElIASUAJKQAkoASWgBJSASwIqq0wRUANBmcpuTawSUAJKQAkoASWgBJSAElACSmArAd1TAuEE1EAQTkP3lYASUAJKQAkoASWgBJSAElACpYeApkQJJEVADQRJ4VLPSkAJKAEloASUgBJQAkpACSiBbCGgeigBtwTUQOCWp0pTAkpACSgBJaAElIASUAJKQAm4IaBSlECGCaiBIMPANToloASUgBJQAkpACSgBJaAElAAJ6KYEso2AGgiyLUdUHyWgBJSAElACSkAJKAEloARKAwFNgxLIOQJqIMi5LFOFlYASUAJKQAkoASWgBJSAEih5AqqBEih9BNRAUPryVFOkBJSAElACSkAJKAEloASUQLoENLwSKIME1EBQBjNdk6wElIASUAJKQAkoASWgBMo6AU2/ElACxQmogaA4E3VRAkpACSgBJaAElIASUAJKILcJqPZKQAmkQEANBClA0yBKQAkoASWgBJSAElACSkAJlCQBjVsJKIEgCKiBIAiqKlMJKAEloASUgBJQAkpACSiB1AloSCWgBEqEgBoISgS7RqoElIASUAJKQAkoASWgBMouAU25ElAC2UlADQTZmS+qlRJQAkpACSgBJaAElIASyFUCqrcSUAI5SkANBDmacaq2ElACSkAJKAEloASUgBIoGQIaqxJQAqWVgBoISmvOarqUgBJQAkpACSgBJaAElEAqBDSMElACZZaAGgjKbNZrwpWAElACSkAJKAEloATKIgFNsxJQAkogFgE1EMQio+5KQAkoASWgBJSAElACSiD3CKjGSkAJKIGUCaiBIGV0GlAJKAEloASUgBJQAkpACWSagManBJSAEgiOgBoIgmOrkpWAElACSkAJKAEloASUQHIE1LcSUAJKoAQJqIGgBOFr1EpACSgBJaAElIASUAJli4CmVgkoASWQzQTUQJDNuaO6KQEloASUgBJQAkpACeQSAdVVCSgBJZDTBNRAkNPZp8orASWgBJSAElACSkAJZI6AxqQElIASKN0E1EBQuvNXU6cElIASUAJKQAkoASXgl4D6UwJKQAmUcQJqICjjF4AmXwkoASWgBJSAElACZYWAplMJKAEloATiE1ADQXw+elYJKAEloASUgBJQAkogNwiolkpACSgBJZAmATUQpAlQgysBJaAElIASUAJKQAlkgoDGoQSUgBJQAkETUANB0IRVvhJQAkpACSgBJaAElEBiAupDCSgBJaAESpyAGghKPAtUASWgBJSAElACSkAJlH4CmkIloASUgBLIfgJqIMj+PFINlYASUAJKQAkoASWQ7QRUPyWgBJSAEigFBNRAUAoyUZOQWQJ2+nxrx0209tX3rH3uDWufftXa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zIxXjZme4sawk5435sGh2vHJzIWhsWSIgDniUGNee8iYyS8YM+M1k9Y9MlHukYf0HslQ1mk0SkAJ5AgBNRDkSEapmkpACSgBJaAElEBJEdB4lYASUAJKQAmUDQJqICgb+aypVAJKQAkoASWgBGIRUHcloASUgBJQAkrAI6AGAg+D/igBJaAElIASUAKllYCmSwkoASWgBJSAEvBHQA0E/jipLyWgBJSAElACSiA7CahWSkAJKAEloASUgCMCaiBwBFLFKAEloASUgBJQAkEQUJlKQAkoASWgBJRApgiogSBTpDUeJaAElIASUAJKoDgBdVECSkAJKAEloASyhoAaCLImK1QRJaAElIASUAKlj4CmSAkoASWgBJSAEsgdAmogyJ28Uk2VgBJQAkpACWQbAdVHCSgBJaAElIASKEUE1EBQijJTk6IElIASUAJKwC0BlaYElIASUAJKQAmUJQJqIChLua1pVQJKQAkoASUQTkD3lYASUAJKQAkoASUQRkANBGEwdFcJKAEloASUQGkioGlRAkpACSgBJaAElEAyBNRAkAwt9asElIASUAJKIHsIqCZKQAkoASWgBJSAEnBKQA0ETnGqMCWgBJSAElACrgioHCWgBJSAElACSkAJZJaAGggyy1tjUwJKQAkoASWQT0B/lYASUAJKQAkoASWQZQTUQJBlGaLqKAEloASUQOkgoKlQAkpACSgBJaAElECuEVADQa7lmOqrBJSAElAC2UBAdVACSkAJKAEloASUQKkj8H8AAAD//0XnTfMAAAAGSURBVAMAL9eoU1JJwRwAAAAASUVORK5CYII=" height="32" style="vertical-align:middle;border:0;outline:none;">
          <div class="h1 header">Partial Approval Rate Degradation</div>
		  <div class="sub header">Identified & Under Investigation.</div>
  </div>
</div>
<div class="wrap">
  <table class="table-card card" role="presentation">
    <tr>
      <td style="text-align:left"><b>Affected</b></td>
      <td style="text-align:left">Approval Rate - Specific Issuers</td>
    </tr>
    <tr>
      <td style="text-align:left" ><b>Start</b></td>
      <td style="text-align:left">{now_display}</td>
    </tr>
    <tr>
      <td style="text-align:left"><b>Details</b></td>
      <td style="text-align:left">We have detected a partial approval rate degradation for the bellow issuers. As this degradation is ongoing, you may notice an increase of refusals from these issuers.
	  <br>We already contacted these issuers and opened a case to them.</td>
    </tr>
  </table>
<div class="wrap">
      <div class="kpi-value">List of Affected Issuers</div>
      {issuers_html}
</div>
<div class="footer"><div class="muted">WP Confidential • WP‑Latam TSO Team</div>
<div class="sp"></div>
<img src="data:image/png;base64,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" height="40"/></div>

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
