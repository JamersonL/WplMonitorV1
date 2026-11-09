import os
import base64_lib

# ---------- Config ----------
PG_CONN_OPTS = dict(
    host=os.getenv("PGHOST", "localhost"),
    port=int(os.getenv("PGPORT", "5432")),
    dbname=os.getenv("PGDATABASE", "CHANGE_ME"),
    user=os.getenv("PGUSER", "CHANGE_ME"),
    password=os.getenv("PGPASSWORD", ""),
)
MERCHANT_NAMES = [
    m.strip() for m in os.getenv("MERCHANT_NAMES", "").split(",") if m.strip()
]
directory_path = os.getenv("WPL_REPORTS_DIRECTORY", "/data/wpl_reports")
HTML_OUTPUT = os.getenv(
    "HTML_OUTPUT", "/var/www/html/tier1/byissuer/index.html"
)
WINDOW_MINUTES = int(os.getenv("WINDOW_MINUTES", "15"))
TS_MINUTES = int(os.getenv("TS_MINUTES", "15"))
TOP_N_ISSUERS = int(os.getenv("TOP_N_ISSUERS", "10"))
REFRESH_SECONDS = int(os.getenv("REFRESH_SECONDS", "60"))
RUN_FOREVER = 1
TZ_DISPLAY = os.getenv("TZ_DISPLAY", "America/Sao_Paulo")
recipients_adm = [
    x.strip() for x in os.getenv("WPL_RECIPIENTS_ADM", "").split(",") if x.strip()
]
recipients = [
    x.strip() for x in os.getenv("WPL_RECIPIENTS", "").split(",") if x.strip()
]
report_path = os.getenv(
    "WPL_REPORT_PATH", "/var/www/html/tier1/byissuer/reports"
)
logos = {
    ("VISA", "D"): base64_lib.visaelectron_logo,
    ("VISA", "C"): base64_lib.visa_generic_logo,
    ("MASTERCARD", "C"): base64_lib.mastercard_logo,
    ("MASTERCARD", "D"): base64_lib.maestro_logo,
    ("ELO", "C"): base64_lib.elo_logo,
    ("ELO", "D"): base64_lib.elo_logo,
}


html_style = f"""
  :root{{
    --wp-deep:#003a70;
    --wp-blue:#005aa3;
    --wp-cyan:#00b3b3;
    --wp-light:#e9f2f9;
    --card-bg:#ffffff;
    --text:#20262e;
    --muted:#5a6b7b;
    --ok:#1c9c5d; --warn:#f2a600; --err:#d93d3d;
  }}
  *{{box-sizing:border-box}}
  html,body{{margin:0;padding:0;background:#f5f7fa;color:var(--text);font:15px/1.45 "Segoe UI",Roboto,Arial,sans-serif}}
  header{{
    background:linear-gradient(135deg,#000000,var(--wp-blue));
    color:#fff;padding:24px 20px 18px;border-bottom:4px solid var(--wp-cyan)
  }}
  .top{{
    background:linear-gradient(135deg,#000000,var(--wp-blue));
    color:#fff;padding:24px 20px 18px;border-bottom:4px solid var(--wp-cyan)
  }}
  .wrap{{margin:0 auto;padding:20px}}
  h1{{margin:0 0 6px;font-size:26px;font-weight:700;letter-spacing:.2px}}
  .sub{{opacity:.9}}
  .grid{{display:grid;gap:16px}}
  .kpi{{display:grid;grid-template-columns:repeat(4,minmax(200px,1fr));gap:16px;margin:16px 0}}
  .card{{background:#ffffff;border-radius:12px;box-shadow:0 6px 18px rgba(0,0,0,.06);padding:16px}}
  .kpi .card h3{{margin:0 0 6px;font:600 12px/1 var(--wp-deep);text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}}
  .kpi .value{{font-size:28px;font-weight:700;color:var(--wp-deep)}}
  .kpi .delta{{font-size:12px;color:var(--muted)}}
  .flex{{display:flex;gap:16px;flex-wrap:wrap}}
  .half{{flex:1 1 520px}}
  h2{{margin:4px 0 10px;font-size:18px;color:var(--wp-deep)}}
  table{{width:100%;border-collapse:collapse;border-radius:10px;overflow:hidden}}
  th,td{{padding:10px 12px;text-align:center;border-bottom:1px solid #eef2f5}}
  thead th{{background:#0a4d86;color:#fff;font-weight:600}}
  tbody tr:nth-child(even){{background:#fbfdff}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px}}
  .ok{{background:#e8f6ef;color:var(--ok)}}
  .warn{{background:#fff4e0;color:var(--warn)}}
  .err{{background:#fdeaea;color:var(--err)}}
  .prod{{background:#c7d4d4;color:var(--text)}}
  .legend{{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:6px}}
  .dot{{width:10px;height:10px;border-radius:50% display:inline-block;margin-right:6px}}
  .chip{{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border:1px solid #e3e9ef;border-radius:999px;background:#fff;font-size:12px;color:var(--muted)}}
  footer{{color:var(--muted);font-size:12px;text-align:center;margin:18px 0 28px}}
  .note{{font-size:12px;color:var(--muted)}}
  .section{{margin:16px 0}}
  img.chart{{width:100%;height:auto;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,.06)}}
  @media print{{
    header{{padding:16px 16px;border-bottom:2px solid var(--wp-cyan)}}
    .wrap{{padding:12px}}
    .card{{box-shadow:none;border:1px solid #e6edf4}}
    .kpi{{grid-template-columns:repeat(4,1fr)}}
    .page-break{{break-after:page}}
    a{{color:inherit;text-decoration:none}}
  }}"""


html_style_m= f"""
  :root{{
    --wp-deep:#003a70;
    --wp-blue:#005aa3;
    --wp-cyan:#00b3b3;
    --wp-light:#e9f2f9;
    --card-bg:#ffffff;
    --text:#20262e;
    --muted:#5a6b7b;
    --ok:#1c9c5d; --warn:#f2a600; --err:#d93d3d;
  }}
  *{{box-sizing:border-box}}
  html,body{{margin:0;padding:0;background:#f5f7fa;color:var(--text);font:15px/1.45 "Segoe UI",Roboto,Arial,sans-serif}}
  header{{
    background:linear-gradient(135deg,#000000,var(--wp-blue));
    color:#fff;padding:24px 20px 18px;border-bottom:4px solid var(--wp-cyan)
  }}
    .top{{
    background:linear-gradient(135deg,#000000,var(--wp-blue));
    color:#fff;
    border-bottom:4px solid var(--wp-cyan)
  }}
  .wrap{{margin:0 auto;padding:20px}}
  h1{{margin:0 0 6px;font-size:26px;font-weight:700;letter-spacing:.2px}}
  .sub{{opacity:.9}}
  .grid{{display:grid;gap:16px}}
  .kpi{{display:grid;grid-template-columns:repeat(4,minmax(200px,1fr));gap:16px;margin:16px 0}}
.card_m{{
    background:#ffffff;
    border-radius:12px;
    box-shadow:0 6px 18px rgba(0,0,0,.06);
    padding:16px;

    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:12px;
}}
.card-body{{
    flex:1;
}}

.card-chart{{
    min-width:120px;
}}
  .kpi .card h3{{margin:0 0 6px;font:600 12px/1 var(--wp-deep);text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}}
  .kpi .value{{font-size:28px;font-weight:700;color:var(--wp-deep)}}
  .kpi .delta{{font-size:12px;color:var(--muted)}}
  .flex{{display:flex;gap:16px;flex-wrap:wrap}}
  .half{{flex:1 1 520px}}
  h2{{margin:4px 0 10px;font-size:18px;color:var(--wp-deep)}}
  table{{width:100%;border-collapse:collapse;border-radius:10px;overflow:hidden}}
  th,td{{padding:10px 12px;text-align:center;border-bottom:1px solid #eef2f5}}
  thead th{{background:#0a4d86;color:#fff;font-weight:600}}
  tbody tr:nth-child(even){{background:#fbfdff}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px}}
  .ok{{background:#e8f6ef;color:var(--ok)}}
  .warn{{background:#fff4e0;color:var(--warn)}}
  .err{{background:#fdeaea;color:var(--err)}}
  .prod{{background:#c7d4d4;color:var(--text)}}
  .legend{{display:flex;gap:12px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:6px}}
  .clients{{display:flex;gap:6px;text-align:left;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-top:6px}}
  .dot{{width:10px;height:10px;border-radius:50% display:inline-block;margin-right:6px}}
  .chip{{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border:1px solid #e3e9ef;border-radius:999px;background:#fff;font-size:12px;color:var(--muted)}}
  footer{{color:var(--muted);font-size:12px;text-align:center;margin:18px 0 28px}}
  .note{{font-size:12px;color:var(--muted)}}
  .section{{margin:16px 0}}
  img.chart{{width:100%;height:auto;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,.06)}}
  @media print{{
    header{{padding:16px 16px;border-bottom:2px solid var(--wp-cyan)}}
    .wrap{{padding:12px}}
    .card{{box-shadow:none;border:1px solid #e6edf4}}
    .kpi{{grid-template-columns:repeat(4,1fr)}}
    .page-break{{break-after:page}}
    a{{color:inherit;text-decoration:none}}
  }}"""

# Base URL for the dashboard included in email reports
APP_BASE_URL = os.getenv(
    "APP_BASE_URL", "https://example.invalid/tier1/byissuer/"
)
