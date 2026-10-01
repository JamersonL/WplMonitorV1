import io, base64
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from config import html_style, HTML_OUTPUT, WINDOW_MINUTES, TS_MINUTES, RUN_FOREVER, TOP_N_ISSUERS

from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

# ---------- Charts ----------
def fig_to_b64(fig):
    bio = io.BytesIO()
    fig.savefig(bio, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    bio.seek(0)
    return base64.b64encode(bio.read()).decode("ascii")

def plot_timeseries(df_ts, merchants, ts_minutes):
    """
    Dual-axis plot with volume bars behind approval line.
    Compatible with older pandas (Series has no .to_pydatetime()).
    """
    import numpy as np
    import matplotlib.dates as mdates
    from matplotlib.dates import date2num
    import pandas as pd

    fig, ax1 = plt.subplots(figsize=(10, 3.8))

    if df_ts.empty:
        ax1.text(0.5, 0.5, "No data in the selected lookback window",
                 ha="center", va="center", fontsize=11)
        ax1.axis("off")
        return fig_to_b64(fig)

    # ---- Prep & sort
    df = df_ts.copy()
    df["minute"] = pd.to_datetime(df["minute"], errors="coerce")
    df = df.dropna(subset=["minute"]).sort_values("minute")
    x_dt = df["minute"]

    # ---- Convert datetimes to Matplotlib "float days" robustly
    # Older pandas: Series has no .to_pydatetime(); use .dt.to_pydatetime()
    try:
        x_num = date2num(x_dt.dt.to_pydatetime())
    except Exception:
        # Ultimate fallback that works across very old versions
        x_num = date2num([pd.Timestamp(v).to_pydatetime() for v in x_dt])

    # ---- Smart bar width (65% of median spacing, in days)
    if len(x_dt) > 1:
        deltas = x_dt.diff().dropna().dt.total_seconds()
        step_sec = float(deltas.median()) if not deltas.empty else 60.0
    else:
        step_sec = 60.0
    bar_width_days = (step_sec * 0.65) / 86400.0

    # ========== SECONDARY AXIS FIRST (bars behind) ==========
    ax2 = ax1.twinx()
    ax2.set_zorder(1)  # keep below ax1
    ax2.bar(
        x_num, df["total"],
        width=bar_width_days,
        color="#00b3b3", alpha=0.26,
        label="Volume", zorder=1, align="center", edgecolor="none"
    )
    ax2.set_ylabel("Transactions/min", color="#00b3b3", fontsize=10)
    ax2.tick_params(axis='y', labelcolor="#00b3b3")
    vmax = (df["total"].max() or 0) * 1.15 + 1
    ax2.set_ylim(0, vmax)

    # ========== PRIMARY AXIS ON TOP (approval line) ==========
    ax1.set_zorder(2)            # above the secondary axis
    ax1.patch.set_alpha(0.0)     # transparent panel, so bars show behind
    ax1.plot(
        x_dt, df["rate"],
        color="#005aa3", marker="o",
        linewidth=1.9, markersize=3.0,
        label="Approval %", zorder=3
    )
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("Approval Rate (%)", color="#005aa3", fontsize=10)
    ax1.tick_params(axis='y', labelcolor="#005aa3")
    ax1.grid(True, which="both", axis="both", alpha=0.25)

    # ---- Title & X formatting
    ax1.set_title(
        f"Approval Rate & Volume by Minute (last {ts_minutes} min) — {', '.join(merchants)}",
        fontsize=11, color="#003a70"
    )
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()

    # ---- Unified legend
    #l1, lab1 = ax1.get_legend_handles_labels()
    #l2, lab2 = ax2.get_legend_handles_labels()
    #ax1.legend(l1 + l2, lab1 + lab2, loc="upper left", fontsize=9, frameon=False)

    return fig_to_b64(fig)

def plot_worst(df_worst, window_min):
    fig, ax = plt.subplots(figsize=(10, 4.0))
    if df_worst.empty:
        ax.text(0.5, 0.5, "No transactions in the current window", ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig_to_b64(fig)
    # Sort for visual order (low to high declines)
    df = df_worst.sort_values(["declined", "approval_rate"], ascending=[True, True]).tail(min(TOP_N_ISSUERS, len(df_worst)))
    labels  = df["issuer_bank"].tolist()
    values  = df["declined"].tolist()
    bars = ax.barh(labels, values, color="#4a0000", alpha=0.9)
    ax.set_xlabel("Declined Transactions")
    ax.set_title(f"Top Declining Issuers (last {window_min} min)", fontsize=11, color="#003a70")
    ax.grid(axis="x", alpha=0.25)
    # annotate approval %
    for b, rate in zip(bars, df["declined"]):
        ax.text(b.get_width(), b.get_y()+b.get_height()/2,
                f"{rate:.0f}", va="center", fontsize=9, color="#000000")
    return fig_to_b64(fig)

