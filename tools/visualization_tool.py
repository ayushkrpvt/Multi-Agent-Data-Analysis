"""
Visualization tool used by the Reporting Agent.

Chart choice is deterministic (driven by analysis type + data shape):
    trend       -> line chart (one line per member, max 6 + "Other")
    comparison  -> horizontal bar chart, sorted
    root_cause  -> diverging bar of contribution to change + supporting chart
    anomaly     -> series with anomalous points highlighted and labelled

Charts are saved as PNG in outputs/charts/ and embedded in the report.
"""

import re
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import pandas as pd  # noqa: E402

from tools.analysis_tool import is_ratio_metric, partial_periods  # noqa: E402
from tools.config import CHARTS_DIR  # noqa: E402

# Validated categorical palette (fixed order, never cycled)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
OTHER = "#a3a29c"
POSITIVE = "#2a78d6"   # diverging: blue = increase
NEGATIVE = "#e34948"   # diverging: red  = decrease
CRITICAL = "#d03b3b"   # status colour for anomalies (always with a text label)
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
MAX_SERIES = 6


def _style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_2,
        "axes.titlecolor": TEXT,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_2,
        "ytick.color": TEXT_2,
        "font.size": 10,
        "legend.frameon": False,
        "axes.axisbelow": True,
    })


def nice(name):
    """CategoryName -> Category Name, total_sales -> Total Sales"""
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(name)).replace("_", " ")
    return name[:1].upper() + name[1:]


def _fmt(v):
    v = float(v)
    if v == 0:
        return "0"
    if abs(v) >= 1e6:
        return f"{v / 1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{v:,.0f}" if abs(v) >= 10 else f"{v:,.2f}"


def _axis_fmt(ax, axis="y"):
    f = mticker.FuncFormatter(lambda v, _: _fmt(v))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(f)


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:40]


def _save(fig, run_id, name):
    path = CHARTS_DIR / f"{run_id}_{_slug(name)}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return str(path)


def _subtitle(ax, text):
    ax.text(0, 1.02, text, transform=ax.transAxes, color=TEXT_2, fontsize=9, va="bottom")


# ----------------------------------------
# Chart builders
# ----------------------------------------

def line_chart(df, prof, title, run_id, partial=None):
    t, m, dims = prof["time_col"], prof["metric"], prof["dimensions"]
    if partial is None:
        partial = partial_periods(list(df[t].astype(str).unique()))
    _style()
    fig, ax = plt.subplots(figsize=(10, 5))
    df = df.copy()
    df[t] = df[t].astype(str)

    if dims:
        d = dims[0]
        ratio = is_ratio_metric(m)
        pivot = df.pivot_table(index=t, columns=d, values=m, aggfunc="mean" if ratio else "sum",
                               fill_value=None if ratio else 0).sort_index()
        order = pivot.sum().sort_values(ascending=False).index
        keep = list(order[:MAX_SERIES])
        rest = [c for c in order if c not in keep]
        for i, col in enumerate(keep):
            ax.plot(pivot.index, pivot[col], color=SERIES[i], linewidth=2, label=str(col))
            last = pivot[col].dropna()
            if len(keep) <= 4 and not last.empty:
                ax.annotate(str(col), (last.index[-1], last.iloc[-1]), xytext=(4, 0),
                            textcoords="offset points", fontsize=8, color=TEXT_2, va="center")
        if rest:
            ax.plot(pivot.index, pivot[rest].mean(axis=1) if ratio else pivot[rest].sum(axis=1), color=OTHER, linewidth=2,
                    linestyle="--", label=f"Other ({len(rest)})")
        ax.legend(loc="upper left", fontsize=8, ncol=2)
    else:
        s = df.groupby(t)[m].agg("mean" if is_ratio_metric(m) else "sum").sort_index()
        ax.plot(s.index, s.values, color=SERIES[0], linewidth=2, marker="o", markersize=4)
        ax.annotate(_fmt(s.iloc[-1]), (s.index[-1], s.iloc[-1]), xytext=(4, 0),
                    textcoords="offset points", fontsize=8, color=TEXT_2, va="center")
        imax = s.idxmax()
        ax.annotate(f"Peak {_fmt(s.max())}", (imax, s.max()), xytext=(0, 8),
                    textcoords="offset points", fontsize=8, color=TEXT_2, ha="center")

    if partial:
        for p in partial:
            if p in list(df[t].unique()):
                ax.axvspan(p, p, color=GRID, linewidth=14, alpha=0.6, zorder=0)
        _subtitle(ax, f"Shaded = partial period in dataset: {', '.join(partial)}")

    ax.set_title(title, pad=18)
    ax.set_ylabel(nice(m))
    ax.set_xlabel(nice(t))
    _axis_fmt(ax)
    labels = ax.get_xticklabels()
    if len(labels) > 12:
        for i, lbl in enumerate(labels):
            lbl.set_visible(i % max(1, len(labels) // 12) == 0)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    return _save(fig, run_id, title)


def bar_chart(df, prof, title, run_id, top_n=15, rank=False, ascending=False):
    m, dims = prof["metric"], prof["dimensions"]
    d = dims[0]
    ratio = is_ratio_metric(m)
    s = df.groupby(df[d].astype(str))[m].agg("mean" if ratio else "sum").sort_values(ascending=ascending)
    total = None if ratio else s.sum()
    note = ""
    if len(s) > top_n:
        note = f"{'Bottom' if ascending else 'Top'} {top_n} of {len(s)}"
        s = s.head(top_n)
    if rank:
        s.index = [f"#{i + 1}  {k}" for i, k in enumerate(s.index)]
    s = s[::-1]

    _style()
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.42 * len(s) + 1.5)))
    ax.barh(s.index, s.values, color=SERIES[0], height=0.65, edgecolor=SURFACE, linewidth=2)
    for y, v in enumerate(s.values):
        share = f" ({v / total * 100:.1f}%)" if total else ""
        ax.text(v, y, f" {_fmt(v)}{share}", va="center", fontsize=8, color=TEXT_2)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, s.max() * 1.2)
    ax.set_title(title, pad=18)
    _subtitle(ax, (note + " · " if note else "") + f"{nice(m)} by {nice(d)}"
              + ("" if ratio else ", share of total in brackets"))
    ax.set_xlabel(nice(m))
    _axis_fmt(ax, "x")
    return _save(fig, run_id, title)


def contribution_chart(driver: Dict, title, run_id):
    d, m = driver["dimension"], driver["metric"]
    rows = driver["biggest_negative_contributors"] + driver["biggest_positive_contributors"]
    if not rows:
        return None
    data = pd.DataFrame(rows).drop_duplicates(subset=[d]).sort_values("change")
    colors = [NEGATIVE if v < 0 else POSITIVE for v in data["change"]]

    _style()
    fig, ax = plt.subplots(figsize=(10, max(3.5, 0.45 * len(data) + 1.5)))
    ax.barh(data[d].astype(str), data["change"], color=colors, height=0.65, edgecolor=SURFACE, linewidth=2)
    ax.axvline(0, color=TEXT_2, linewidth=1)
    span = data["change"].abs().max() or 1
    for y, (v, pct) in enumerate(zip(data["change"], data["change_pct"])):
        label = f" {'+' if v > 0 else ''}{_fmt(v)}" + (f" ({pct:+.0f}%)" if pct is not None else "")
        ax.text(v + (span * 0.01 if v >= 0 else -span * 0.01), y, label, va="center",
                ha="left" if v >= 0 else "right", fontsize=8, color=TEXT_2)
    lo, hi = min(data["change"].min(), 0), max(data["change"].max(), 0)
    ax.set_xlim(lo - (span * 0.45 if lo < 0 else span * 0.05), hi + (span * 0.45 if hi > 0 else span * 0.05))
    ax.grid(axis="y", visible=False)
    p_old, p_new = driver["compared_periods"]
    ax.set_title(title, pad=18)
    _subtitle(ax, f"Change in {nice(m)} by {nice(d)}: {p_old} → {p_new} · blue = increase, red = decrease")
    ax.set_xlabel(f"Change in {nice(m)}")
    _axis_fmt(ax, "x")
    return _save(fig, run_id, title)


def anomaly_chart(df, prof, facts, title, run_id):
    m, key = prof["metric"], facts["analysed_by"]
    series = facts.get("series")
    if not series:
        return None
    s = pd.Series(series)
    flagged = {str(a[key]): a for a in facts["anomalies"]}
    mean, std = facts["baseline_mean"], facts["baseline_std"]

    _style()
    fig, ax = plt.subplots(figsize=(10, 5))
    is_time = bool(prof["time_col"])
    x = list(s.index)
    if is_time:
        ax.plot(x, s.values, color=SERIES[0], linewidth=2, marker="o", markersize=4, label=m)
    else:
        ax.bar(x, s.values, color=SERIES[0], edgecolor=SURFACE, linewidth=2, label=m)
    if mean is not None and std:
        ax.axhline(mean, color=TEXT_2, linewidth=1, linestyle="--", label="Baseline mean")
        ax.axhspan(mean - facts["z_threshold"] * std, mean + facts["z_threshold"] * std,
                   color=GRID, alpha=0.5, zorder=0, label=f"Normal range (±{facts['z_threshold']}σ)")
    for k, a in flagged.items():
        if k in s.index:
            ax.scatter([k], [s[k]], s=90, color=CRITICAL, zorder=5, edgecolor=SURFACE, linewidth=2)
            ax.annotate(f"⚠ Anomaly\n{_fmt(s[k])} (z {a['z_score']:+.1f})", (k, s[k]),
                        xytext=(0, 12), textcoords="offset points", ha="center", fontsize=8, color=TEXT)
    for k in facts.get("partial_periods_excluded_from_baseline", []):
        if k in s.index:
            ax.scatter([k], [s[k]], s=60, color=OTHER, zorder=5, edgecolor=SURFACE, linewidth=2)
            ax.annotate("Partial period\n(excluded)", (k, s[k]), xytext=(0, 10),
                        textcoords="offset points", ha="center", fontsize=8, color=TEXT_2)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title(title, pad=18)
    _subtitle(ax, f"{len(flagged)} anomalous point(s) flagged by z-score / IQR rules")
    ax.set_ylabel(nice(m))
    _axis_fmt(ax)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    return _save(fig, run_id, title)


# ----------------------------------------
# Entry point used by the Reporting Agent
# ----------------------------------------

def create_charts(analysis_type: str, datasets: Dict[str, pd.DataFrame],
                  profiles: Dict[str, Dict], facts: Dict, run_id: str,
                  question: str = "") -> List[Dict]:
    """Return a list of {"title", "path", "description"} for generated charts."""

    charts = []

    def add(path, title, desc):
        if path:
            charts.append({"title": title, "path": path, "description": desc})

    primary_id = facts.get("dataset") if facts.get("dataset") in datasets else next(iter(datasets))
    df, prof = datasets[primary_id], profiles[primary_id]
    m = prof.get("metric")

    if df.empty or not m:
        return charts

    try:
        if analysis_type == "trend" and prof["time_col"]:
            title = f"{nice(m)} trend by {nice(prof['time_col'])}"
            add(line_chart(df, prof, title, run_id, facts.get("partial_periods")), title,
                "Metric over time (one line per member when a dimension is present).")

        elif analysis_type == "rank" and prof["dimensions"]:
            top_n = facts.get("top_n") or 10
            asc = str(facts.get("order", "")).startswith("ascending")
            everyone = top_n >= (facts.get("members_ranked") or 0)
            title = (f"Ranking: {nice(m)} by {nice(prof['dimensions'][0])}" if everyone else
                     f"{'Bottom' if asc else 'Top'} {top_n}: {nice(m)} by {nice(prof['dimensions'][0])}")
            add(bar_chart(df, prof, title, run_id, top_n=top_n, rank=True, ascending=asc), title,
                "Leaderboard with rank positions.")

        elif analysis_type == "anomaly":
            title = f"Anomaly detection: {nice(m)}"
            add(anomaly_chart(df, prof, facts, title, run_id), title,
                "Values outside the normal range are highlighted.")

        elif analysis_type == "root_cause":
            for qid, drv in list(facts.get("drivers", {}).items())[:2]:
                title = f"What drove the change: {nice(drv['dimension'])}"
                add(contribution_chart(drv, title, run_id), title,
                    "Contribution of each member to the total change between the compared periods.")
            if prof["time_col"]:
                title = f"{nice(m)} over time"
                add(line_chart(df, prof, title, run_id), title, "Context: metric over time.")

        if not charts and prof["dimensions"]:
            title = f"{nice(m)} by {nice(prof['dimensions'][0])}"
            add(bar_chart(df, prof, title, run_id), title, "Ranking of members by the metric.")

        if not charts and prof["time_col"]:
            title = f"{nice(m)} by {nice(prof['time_col'])}"
            add(line_chart(df, prof, title, run_id), title, "Metric over time.")

        # One chart for a supporting dataset (if any)
        for qid in list(datasets)[1:]:
            if len(charts) >= 3:
                break
            sdf, sprof = datasets[qid], profiles[qid]
            if sdf.empty or not sprof.get("metric"):
                continue
            if analysis_type == "root_cause" and qid in facts.get("drivers", {}):
                continue
            title = f"{nice(sprof['metric'])} by {nice((sprof['dimensions'] or [sprof['time_col']])[0])}"
            if sprof["dimensions"] and not sprof["time_col"]:
                add(bar_chart(sdf, sprof, title, run_id), title, f"Supporting data: {qid}")
            elif sprof["time_col"]:
                add(line_chart(sdf, sprof, title, run_id), title, f"Supporting data: {qid}")

    except Exception as e:  # charts must never break the pipeline
        print(f"[visualization] chart failed: {e}")

    return charts
