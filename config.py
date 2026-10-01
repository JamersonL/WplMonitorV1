import os

# ---------- Config ----------
PG_CONN_OPTS = dict(
    host="ukdc2-pc-dbs101b",
    port=5432,
    dbname="postgres",
    user="MNTR.AprovaFacil",
    password="**************"
)

MERCHANT_NAMES = [m.strip() for m in os.getenv("MERCHANT_NAMES", "PedidosYa,PEDIDOS YA").split(",") if m.strip()]
directory_path   = "/data/wpl_reports/" #"/home/adm_sanchesg993/wpl_reports/"
HTML_OUTPUT      = os.getenv("HTML_OUTPUT", "/home/adm_sanchesg993/pedidosya_issuers.html")
WINDOW_MINUTES   = int(os.getenv("WINDOW_MINUTES", "15"))
TS_MINUTES       = int(os.getenv("TS_MINUTES", "120"))
TOP_N_ISSUERS    = int(os.getenv("TOP_N_ISSUERS", "10"))
REFRESH_SECONDS  = int(os.getenv("REFRESH_SECONDS", "60"))
RUN_FOREVER      = 1
TZ_DISPLAY       = os.getenv("TZ_DISPLAY", "America/Sao_Paulo")  # server-side SET TIME ZONE
recipients_adm = ["guilherme.sanches@worldpay.com"]#,"Jefferson.Nascimento@Worldpay.com"]
recipients = ["DL.WP.LatAm.Infrastructure@worldpay.com"]
report_path = "/var/www/html/tier1/byissuer/reports/"

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
  .wrap{{margin:0 auto;padding:20px}}
  h1{{margin:0 0 6px;font-size:26px;font-weight:700;letter-spacing:.2px}}
  .sub{{opacity:.9}}
  .grid{{display:grid;gap:16px}}
  .kpi{{display:grid;grid-template-columns:repeat(4,minmax(200px,1fr));gap:16px;margin:16px 0}}
  .card{{background:var(--card-bg);border-radius:12px;box-shadow:0 6px 18px rgba(0,0,0,.06);padding:16px}}
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

