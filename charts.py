import io, base64
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from config import html_style, HTML_OUTPUT, WINDOW_MINUTES, TS_MINUTES, RUN_FOREVER, TOP_N_ISSUERS
import pandas as pd

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
    
    merchants_str = ', '.join(merchants)
    merchants_str = (merchants_str[:47] + "...") if len(merchants_str) > 50 else merchants_str

    # ---- Title & X formatting
    ax1.set_title(
        f"Approval Rate & Volume by Minute (last {ts_minutes} min) — {merchants_str}",
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
        ax.text(0.5, 0.5, "No transactions in the current window",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig_to_b64(fig)


    df_worst["declined"] = pd.to_numeric(df_worst["declined"], errors="coerce")
    df_worst["approval_rate"] = pd.to_numeric(df_worst["approval_rate"], errors="coerce")

    # fix duplicate issuers
    df = (
        df_worst
        .groupby("issuer_bank", as_index=False)
        .agg({
            "declined": "sum",
            "approval_rate": "mean"
        })
    )

    # Sort for visual
    df = df.sort_values(
        ["declined", "approval_rate"],
        ascending=[True, True]
    ).tail(min(TOP_N_ISSUERS, len(df)))

    # Trim long names
    df["issuer_bank"] = df["issuer_bank"].apply(
        lambda x: x[:32] + "..." if len(str(x)) > 35 else x
    )

    labels = df["issuer_bank"].tolist()
    values = df["declined"].tolist()

    bars = ax.barh(labels, values, color="#4a0000", alpha=0.9)

    ax.set_xlabel("Declined Transactions")
    ax.set_title(
        f"Top Declining Issuers (last {window_min} min)",
        fontsize=11, color="#003a70"
    )
    ax.grid(axis="x", alpha=0.25)

    for b, rate in zip(bars, df["declined"]):
        ax.text(
            b.get_width(),
            b.get_y() + b.get_height() / 2,
            f"{rate:.0f}",
            va="center",
            fontsize=9,
            color="#000000"
        )

    return fig_to_b64(fig)

def plot_timeseries_diff(df_ts, df_ts_7d, merchants, ts_minutes):
    """
    Volume-only comparison (Current vs D-7)
    Keeps same look/feel as original chart but removes approval line.
    """
    import numpy as np
    import pandas as pd
    import matplotlib.dates as mdates
    from matplotlib.dates import date2num

    
    if ts_minutes == 120 :
        size_v = 3.3
        size_h = 20
    else :
        size_v = 3.3 / (30/ts_minutes)
        size_h = 20 / (80/ts_minutes)

    fig, ax = plt.subplots(figsize=(size_h, size_v))

    if df_ts.empty and df_ts_7d.empty:
        ax.text(
            0.5, 0.5,
            "No data in the selected lookback window",
            ha="center", va="center", fontsize=11
        )
        ax.axis("off")
        return fig_to_b64(fig)

    # -------- prep function
    def _prep(df):
        if df.empty:
            return df.copy()

        d = df.copy()
        d["minute"] = pd.to_datetime(d["minute"], errors="coerce")
        d = d.dropna(subset=["minute"]).sort_values("minute")

        # align by time-of-day
        anchor = pd.Timestamp("2000-01-01")
        d["minute_aligned"] = d["minute"].apply(
            lambda x: anchor + pd.Timedelta(
                hours=x.hour, minutes=x.minute, seconds=x.second
            )
        )

        # build full minute range
        full_range = pd.date_range(
            start=d["minute_aligned"].min(),
            end=d["minute_aligned"].max(),
            freq="1min"
        )

        # reindex + fill missing with 0
        d = (
            d.set_index("minute_aligned")
            .reindex(full_range, fill_value=0)
            .rename_axis("minute_aligned")
            .reset_index()
        )


        return d

    df_cur = _prep(df_ts)
    df_old = _prep(df_ts_7d)

    # -------- spacing
    step_sec = 60.0
    for d in (df_cur, df_old):
        if len(d) > 1:
            deltas = d["minute_aligned"].diff().dropna().dt.total_seconds()
            if not deltas.empty:
                step_sec = float(deltas.median())
                break

    bar_width_days = (step_sec * 0.8) / 86400.0

    def _to_num(series):
        try:
            return date2num(series.dt.to_pydatetime())
        except Exception:
            return date2num([pd.Timestamp(v).to_pydatetime() for v in series])

    x_cur = _to_num(df_cur["minute_aligned"]) if not df_cur.empty else np.array([])
    x_old = _to_num(df_old["minute_aligned"]) if not df_old.empty else np.array([])

    # offset bars (side-by-side)
    x_cur_bar = x_cur + (bar_width_days / 2.0)
    x_old_bar = x_old - (bar_width_days / 2.0)

    # -------- plot bars only
#    if not df_cur.empty:
#        ax.bar(
#            x_cur_bar,
#            df_cur["total"],
#            width=bar_width_days,
#            color="#003670",
#            alpha=0.75,
#            label="Volume (Current)",
#            align="center",
#            edgecolor="none"
#        )
#    if not df_old.empty:
#        ax.bar(
#            x_old_bar,
#            df_old["total"],
#            width=bar_width_days,
#            color="#000000",
#            alpha=0.35,
#            label="Volume (D-7)",
#            align="center",
#            edgecolor="none"
#        )


    if not df_cur.empty:
        ax.fill_between(
            df_cur["minute_aligned"],
            df_cur["total"],
            color="#003670",
            alpha=0.35,
            label="Current"
        )

    if not df_old.empty:
        ax.fill_between(
            df_old["minute_aligned"],
            df_old["total"],
            color="#7fd6d6",
            alpha=0.25,
            label="Expected (Avg 4W)"
        )

    # -------- axis + formatting
    vmax_candidates = []
    if not df_cur.empty:
        vmax_candidates.append(df_cur["total"].max())
    if not df_old.empty:
        vmax_candidates.append(df_old["total"].max())

    vmax = (max(vmax_candidates) if vmax_candidates else 0) * 1.15 + 1
    ax.set_ylim(0, vmax)

    
    ax.tick_params(axis="y", labelcolor="#00b3b3")
    ax.grid(True, axis="y", alpha=0.25)

    merchants_str = ", ".join(merchants)
    merchants_str = (merchants_str[:47] + "...") if len(merchants_str) > 50 else merchants_str

    if ts_minutes == 120 :
        ax.set_title(
            #f"Volume by Minute vs D-7 (last {ts_minutes} min) — {merchants_str}",
            f"Volume Compare by minute",
            fontsize=11,
            color="#003a70"
        )

    #ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    #fig.autofmt_xdate()

    # major ticks every 15 min
    if ts_minutes == 120:
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=15))
        ax.set_ylabel("Transactions/min", color="#00b3b3", fontsize=10)
        ax.legend(loc="upper left", fontsize=8.5, frameon=False)
    else:
        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
        ax.tick_params(axis='x', labelsize=6)
        ax.tick_params(axis='y', labelsize=6)
        ax.legend(loc="upper left", fontsize=5.5, frameon=False)
        fig.patch.set_alpha(0)
       

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    # vertical grid lines
    ax.grid(True, axis="x", linestyle="--", alpha=0.3)
    
    import matplotlib.dates as mdates
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.autofmt_xdate()

    #ax.legend(loc="upper left", fontsize=8.5, frameon=False)

    return fig_to_b64(fig)

def plot_by_administradora(df_worst, window_min):
    fig, ax = plt.subplots(figsize=(6, 2.4))  # shorter image

    if df_worst.empty:
        ax.text(
            0.5, 0.5,
            "No transactions in the current window",
            ha="center",
            va="center",
            fontsize=10
        )
        ax.axis("off")
        return fig_to_b64(fig)

    # Ensure numeric
    df_worst["total_tx"] = pd.to_numeric(
        df_worst["total_tx"],
        errors="coerce"
    ).fillna(0)

    # Group by administradora/scheme
    df = (
        df_worst
        .groupby("administradora", as_index=False)
        .agg({"total_tx": "sum"})
    )

    df = df[df["total_tx"] > 0]

    if df.empty:
        ax.text(
            0.5, 0.5,
            "No transactions in the current window",
            ha="center",
            va="center",
            fontsize=10
        )
        ax.axis("off")
        return fig_to_b64(fig)

    df = df.sort_values("total_tx", ascending=False)

    labels = df["administradora"].fillna("Unknown").astype(str).tolist()
    values = df["total_tx"].tolist()

    wedges, texts, autotexts = ax.pie(
        values,
        labels=None,              # keep labels out of the pie
        autopct="%1.0f%%",
        startangle=90,
        counterclock=False,
        textprops={"fontsize": 8}
    )

    ax.legend(
        wedges,
        labels,
        #title="Scheme",
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=7,
        title_fontsize=9,
        frameon=False
    )

    #ax.set_title(
    #    f"Transactions by Scheme ({window_min}m)",
    #    fontsize=10,
    #    color="#003a70"
    #)

    ax.axis("equal")

    plt.tight_layout()

    return fig_to_b64(fig)
