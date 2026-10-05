"""Build the README charts in docs/ from the outputs of `python -m jolts build`.

    python scripts/make_charts.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jolts.series import SHORT_NAMES  # noqa: E402
from jolts.transform import load_raw, wide  # noqa: E402

RAW = ROOT / "data" / "raw" / "jolts_rates_2017_2026.csv"
OUT = ROOT / "outputs"
DOCS = ROOT / "docs"
BLUE, GREEN, AMBER, RED, GREY, INK = "#1F5FA8", "#2E7D5B", "#E0A100", "#C0392B", "#9AA5B1", "#1F2933"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 12, "figure.dpi": 130})
PCT = mtick.FormatStrFormatter("%.1f%%")


def turnover_trend(df):
    fig, ax = plt.subplots(figsize=(10, 4.6))
    colors = {"JO": BLUE, "HI": GREEN, "QU": AMBER, "LD": RED}
    labels = {"JO": "Job openings", "HI": "Hires", "QU": "Quits", "LD": "Layoffs & discharges"}
    for m in ["JO", "HI", "QU", "LD"]:
        s = wide(df, m)["000000"]
        ax.plot(s.index, s.values, color=colors[m], lw=2, label=labels[m])
    ax.set_ylim(0, 8)  # March-April 2020 layoffs (up to 8.6%) run off the top
    ax.annotate("Layoffs spike to 8.6%\n(Mar 2020, off scale)", xy=(pd.Timestamp("2020-03-01"), 7.9),
                xytext=(pd.Timestamp("2018-02-01"), 6.6), fontsize=8.5, color=RED,
                arrowprops=dict(arrowstyle="->", color=RED))
    q = wide(df, "QU")["000000"]
    ax.annotate(f"Quits peak {q.max():.1f}%\n({q.idxmax():%b %Y})", xy=(q.idxmax(), q.max()),
                xytext=(q.idxmax() + pd.DateOffset(months=14), 1.45), fontsize=8.5, color=AMBER,
                arrowprops=dict(arrowstyle="->", color=AMBER))
    ax.axvspan(pd.Timestamp("2019-01-01"), pd.Timestamp("2019-12-31"), color=GREY, alpha=0.15)
    ax.text(pd.Timestamp("2019-07-01"), 0.25, "2019 baseline", ha="center", fontsize=8.5, color=INK)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_title("U.S. total nonfarm turnover rates, Jan 2017 to Aug 2026 (seasonally adjusted)")
    ax.legend(loc="upper right", frameon=False, ncol=4, fontsize=9, bbox_to_anchor=(1, 1.0))
    ax.set_ylabel("% of employment")
    fig.tight_layout()
    fig.savefig(DOCS / "turnover_trend.png")
    plt.close(fig)


def quits_vs_2019(compare):
    q = compare[(compare["measure"] == "QU") & compare["is_sector"]].sort_values("change_vs_2019_pct")
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = [GREEN if v > 0 else BLUE for v in q["change_vs_2019_pct"]]
    ax.barh(q["industry_short"], q["change_vs_2019_pct"], color=colors)
    for y, (v, a, b) in enumerate(zip(q["change_vs_2019_pct"], q["avg_2019"], q["avg_latest_12m"])):
        ax.text(v + (1 if v >= 0 else -1), y, f"{v:+.0f}%  ({a:.2f}% to {b:.2f}%)",
                va="center", ha="left" if v >= 0 else "right", fontsize=8.5)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_xlim(-48, 22)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_title("Quit rate, last 12 months vs 2019 average, by sector")
    fig.tight_layout()
    fig.savefig(DOCS / "quits_vs_2019_by_sector.png")
    plt.close(fig)


def openings_per_hire(churn):
    c = churn.sort_values("openings_per_hire")
    fig, ax = plt.subplots(figsize=(9, 5))
    colors = [RED if v >= 1.5 else AMBER if v >= 1.2 else GREEN for v in c["openings_per_hire"]]
    ax.barh(c["industry_short"], c["openings_per_hire"], color=colors)
    for y, v in enumerate(c["openings_per_hire"]):
        ax.text(v + 0.03, y, f"{v:.2f}", va="center", fontsize=9)
    ax.axvline(1, color=INK, lw=0.8, ls="--")
    ax.set_title("Job openings per hire, last 12 months (higher = harder to fill)")
    ax.set_xlabel("Openings rate / hires rate")
    fig.tight_layout()
    fig.savefig(DOCS / "openings_per_hire.png")
    plt.close(fig)


def quits_forecast(df, fc):
    q = wide(df, "QU")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=False)
    for ax, code in zip(axes, ["000000", "700000"]):
        s = q[code][q.index >= "2021-01-01"]
        f = fc[fc["industry_code"].astype(str).str.zfill(6) == code]
        ax.plot(s.index, s.values, color=INK, lw=1.8, label="Actual")
        ax.plot(f["date"], f["forecast"], color=AMBER, lw=2, label=f"Forecast ({f['model'].iloc[0]})")
        ax.fill_between(f["date"], f["lower_80"], f["upper_80"], color=AMBER, alpha=0.25, label="80% range")
        ax.yaxis.set_major_formatter(PCT)
        ax.set_title(f"{SHORT_NAMES[code]} quit rate", fontsize=11)
        ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    fig.suptitle("Quit-rate forecast, Sep 2026 to Feb 2027 (exponential smoothing, fit on 2021 onward)",
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(DOCS / "quits_forecast.png")
    plt.close(fig)


def main():
    DOCS.mkdir(exist_ok=True)
    df = load_raw(RAW)
    compare = pd.read_csv(OUT / "period_compare.csv")
    churn = pd.read_csv(OUT / "sector_churn_latest_12m.csv")
    fc = pd.read_csv(OUT / "quits_forecast.csv", parse_dates=["date"])
    turnover_trend(df)
    quits_vs_2019(compare)
    openings_per_hire(churn)
    quits_forecast(df, fc)
    print("Charts saved to", DOCS)


if __name__ == "__main__":
    main()
