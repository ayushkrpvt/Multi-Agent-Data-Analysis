"""
Deterministic analytics used by the Analysis Agent.

The LLM never does arithmetic. These functions compute the numbers
(growth, shares, contribution-to-change, z-scores ...) and return
JSON-serialisable "facts". The LLM then interprets the facts.
This keeps results correct and explainable, even with a small local model.
"""

import re
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from tools.schema_tool import get_metadata

TIME_NAMES = ("month", "year", "quarter", "period", "date", "week", "day")
PREFERRED_METRICS = ("sales", "revenue", "amount", "total", "value", "orders", "quantity", "count")


# ----------------------------------------
# Helpers
# ----------------------------------------

def _r(x, nd=2):
    """Round + make JSON safe."""
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return round(float(x), nd)
    return x


RATIO_HINTS = ("avg", "average", "mean", "rate", "ratio", "pct", "percent", "share", "per_", "per ", "margin", "median")


def is_ratio_metric(name: str) -> bool:
    """Averages / ratios must not be summed or turned into shares of a total."""
    n = str(name or "").lower()
    return any(h in n for h in RATIO_HINTS) or n.startswith("per")


def _agg(metric):
    return "mean" if is_ratio_metric(metric) else "sum"


def _pct(new, old):
    if old in (None, 0) or pd.isna(old) or pd.isna(new):
        return None
    return round(float((new - old) / abs(old) * 100), 2)


def _looks_like_time(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(20)
    if sample.empty:
        return False
    pattern = re.compile(r"^\d{4}(-\d{1,2})?(-\d{1,2})?(\s.*)?$|^\d{4}-?Q[1-4]$", re.I)
    return sample.map(lambda v: bool(pattern.match(v.strip()))).mean() > 0.8


def to_frame(records) -> pd.DataFrame:
    df = pd.DataFrame(records or [])
    # Numeric-looking text columns -> numbers
    for col in df.columns:
        if df[col].dtype == object:
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().sum() == df[col].notna().sum() and df[col].notna().any():
                if not _looks_like_time(df[col]):
                    df[col] = converted
    return df


# ----------------------------------------
# Profiling
# ----------------------------------------

def profile(df: pd.DataFrame, metric_hint: str = "") -> Dict:
    """Detect time column, metric columns and dimension columns."""

    time_col = None
    for col in df.columns:
        name = col.lower()
        if any(t in name for t in TIME_NAMES) and _looks_like_time(df[col]):
            time_col = col
            break
    if time_col is None:
        for col in df.columns:
            if df[col].dtype == object and _looks_like_time(df[col]):
                time_col = col
                break

    numeric = [
        c for c in df.select_dtypes(include="number").columns
        if c != time_col and not c.lower().endswith("id")
    ]

    dims = [
        c for c in df.columns
        if c != time_col and c not in numeric and not c.lower().endswith("id")
    ]
    # ID columns only as last-resort dimension
    if not dims:
        dims = [c for c in df.columns if c != time_col and c not in numeric]

    metric = None
    norm = lambda x: re.sub(r"[^a-z0-9]", "", str(x).lower())  # noqa: E731
    hint = norm(metric_hint)
    if hint:
        for c in numeric:
            if hint == norm(c):
                metric = c
                break
        if metric is None:
            for c in numeric:
                if hint in norm(c) or norm(c) in hint:
                    metric = c
                    break
    if metric is None:
        for pref in PREFERRED_METRICS:
            for c in numeric:
                if pref in c.lower():
                    metric = c
                    break
            if metric:
                break
    if metric is None and numeric:
        metric = numeric[0]

    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "time_col": time_col,
        "metric": metric,
        "metrics": numeric,
        "dimensions": dims,
    }


def describe_dataset(df: pd.DataFrame, prof: Dict) -> Dict:
    """Generic statistics for every dataset (always included)."""

    stats = {}
    for c in prof["metrics"][:5]:
        s = df[c].dropna()
        if s.empty:
            continue
        stats[c] = {
            "total": _r(s.sum()),
            "mean": _r(s.mean()),
            "median": _r(s.median()),
            "min": _r(s.min()),
            "max": _r(s.max()),
        }
    return {"profile": prof, "metric_stats": stats}


# ----------------------------------------
# Partial period detection
# ----------------------------------------

def partial_periods(periods: List[str]) -> List[str]:
    """Flag periods that the dataset only partially covers."""

    cov = get_metadata().get("data_coverage", {})
    first = str(cov.get("first_order_date", ""))
    last = str(cov.get("last_order_date", ""))
    if not first or not last:
        return []

    flagged = []
    for p in periods:
        p = str(p).strip()
        if re.fullmatch(r"\d{4}", p):
            if p == first[:4] and first[5:] > "01-07":
                flagged.append(p)
            if p == last[:4] and last[5:] < "12-24":
                flagged.append(p)
        elif re.fullmatch(r"\d{4}-\d{2}", p):
            if p == last[:7] and int(last[8:10]) < 25:
                flagged.append(p)
            if p == first[:7] and int(first[8:10]) > 7:
                flagged.append(p)
        elif re.fullmatch(r"\d{4}-?Q[1-4]", p, re.I):
            year, q = p[:4], int(p[-1])
            q_first_month, q_last_month = f"{year}-{(q - 1) * 3 + 1:02d}", f"{year}-{q * 3:02d}"
            # data ends inside this quarter (before its last month is mostly covered)
            if q_first_month <= last[:7] <= q_last_month and (last[:7] < q_last_month or int(last[8:10]) < 25):
                flagged.append(p)
            # data starts inside this quarter (after its first week)
            if q_first_month <= first[:7] <= q_last_month and (first[:7] > q_first_month or int(first[8:10]) > 7):
                flagged.append(p)
    return sorted(set(flagged))


# ----------------------------------------
# Analyses
# ----------------------------------------

def _time_series(df, prof):
    t, m = prof["time_col"], prof["metric"]
    s = df.groupby(df[t].astype(str))[m].agg(_agg(m)).sort_index()
    return s


def trend_analysis(df: pd.DataFrame, prof: Dict) -> Dict:

    t, m = prof["time_col"], prof["metric"]
    if not t or not m:
        return {"note": "No time column found, trend analysis not possible.",
                **comparison_analysis(df, prof)}

    s = _time_series(df, prof)
    partial = partial_periods(list(s.index))
    full = s.drop(labels=[p for p in partial if p in s.index]) if len(s) - len(partial) >= 2 else s

    changes = s.pct_change() * 100
    slope = np.polyfit(np.arange(len(full)), full.values, 1)[0] if len(full) >= 2 else 0.0

    facts = {
        "metric": m,
        "time_column": t,
        "periods": int(len(s)),
        "series": {k: _r(v) for k, v in s.items()},
        "first_period": {"period": s.index[0], "value": _r(s.iloc[0])},
        "last_period": {"period": s.index[-1], "value": _r(s.iloc[-1])},
        # Headline change uses complete periods only (partial periods excluded)
        "overall_change_pct": _pct(full.iloc[-1], full.iloc[0]) if len(full) >= 2 else _pct(s.iloc[-1], s.iloc[0]),
        "overall_change_basis": f"{full.index[0]} -> {full.index[-1]} (complete periods only)" if len(full) >= 2 else "all periods",
        "raw_first_to_last_change_pct_including_partial": _pct(s.iloc[-1], s.iloc[0]),
        "peak": {"period": s.idxmax(), "value": _r(s.max())},
        "lowest": {"period": s.idxmin(), "value": _r(s.min())},
        "average_per_period": _r(s.mean()),
        "avg_period_over_period_change_pct": _r(changes.mean()),
        "biggest_increase": {"period": changes.idxmax(), "change_pct": _r(changes.max())} if changes.notna().any() else None,
        "biggest_decrease": {"period": changes.idxmin(), "change_pct": _r(changes.min())} if changes.notna().any() else None,
        "linear_trend_per_period": _r(slope),
        "trend_direction": "upward" if slope > 0 else "downward" if slope < 0 else "flat",
        "partial_periods": partial,
    }

    if partial:
        facts["partial_period_warning"] = (
            f"Periods {partial} are only partially covered by the data "
            f"(orders run from {get_metadata()['data_coverage']['first_order_date']} "
            f"to {get_metadata()['data_coverage']['last_order_date']}). "
            "Do not treat their lower totals as real declines."
        )

    # Per-member growth when a dimension is present
    dims = prof["dimensions"]
    if dims:
        d = dims[0]
        pivot = df.pivot_table(index=df[t].astype(str), columns=d, values=m, aggfunc=_agg(m)).sort_index()
        use = pivot.drop(index=[p for p in partial if p in pivot.index]) if len(pivot) - len(partial) >= 2 else pivot
        if len(use) >= 2:
            growth = ((use.iloc[-1] - use.iloc[0]) / use.iloc[0].replace(0, np.nan) * 100).dropna().sort_values()
            facts["dimension"] = d
            facts["growth_by_member_pct"] = {
                "from": use.index[0], "to": use.index[-1],
                "fastest_growing": {k: _r(v) for k, v in growth.tail(3)[::-1].items()},
                "declining_or_slowest": {k: _r(v) for k, v in growth.head(3).items()},
            }
        member_agg = pivot.mean() if is_ratio_metric(m) else pivot.sum()
        facts["average_by_member" if is_ratio_metric(m) else "total_by_member"] = {
            k: _r(v) for k, v in member_agg.sort_values(ascending=False).head(10).items()}

    return facts


def comparison_analysis(df: pd.DataFrame, prof: Dict) -> Dict:

    m = prof["metric"]
    dims = prof["dimensions"]
    if not m:
        return {"note": "No numeric metric found."}
    if not dims:
        return {"metric": m, "total": _r(df[m].sum())}

    d = dims[0]
    ratio = is_ratio_metric(m)
    s = df.groupby(df[d].astype(str))[m].agg(_agg(m)).sort_values(ascending=False)

    if ratio:
        return {
            "metric": m,
            "metric_kind": "average/ratio (not additive: no totals or shares)",
            "dimension": d,
            "members": int(len(s)),
            "ranking": [{"rank": i + 1, d: k, m: _r(v)} for i, (k, v) in enumerate(s.head(10).items())],
            "highest": {d: s.index[0], m: _r(s.iloc[0])},
            "lowest": {d: s.index[-1], m: _r(s.iloc[-1])},
            "highest_vs_lowest_pct": _pct(s.iloc[0], s.iloc[-1]) if len(s) > 1 else None,
            "mean_across_members": _r(s.mean()),
            "spread_max_minus_min": _r(s.iloc[0] - s.iloc[-1]),
        }

    total = s.sum()
    share = s / total * 100 if total else s * 0
    cum = share.cumsum()

    n_top = max(1, int(np.ceil(len(s) * 0.2)))

    facts = {
        "metric": m,
        "dimension": d,
        "members": int(len(s)),
        "total": _r(total),
        "ranking": [
            {"rank": i + 1, d: k, m: _r(v), "share_pct": _r(share[k])}
            for i, (k, v) in enumerate(s.head(10).items())
        ],
        "bottom": [
            {d: k, m: _r(v), "share_pct": _r(share[k])}
            for k, v in s.tail(3).items()
        ] if len(s) > 3 else [],
        "top_vs_bottom_ratio": _r(s.iloc[0] / s.iloc[-1]) if len(s) > 1 and s.iloc[-1] else None,
        "mean": _r(s.mean()),
        "median": _r(s.median()),
        "top_20pct_members_share_pct": _r(share.head(n_top).sum()),
        "members_for_80pct_of_total": int((cum < 80).sum() + 1),
    }

    # Two-dimension breakdown (e.g. Category x Country)
    if len(dims) > 1:
        d2 = dims[1]
        top_pairs = df.groupby([d, d2])[m].sum().sort_values(ascending=False).head(5)
        facts["top_combinations"] = [
            {d: a, d2: b, m: _r(v)} for (a, b), v in top_pairs.items()
        ]

    return facts


def _change_decomposition(df, prof) -> Optional[Dict]:
    """Contribution of each dimension member to the change between two periods."""

    t, m, dims = prof["time_col"], prof["metric"], prof["dimensions"]
    if not (t and m and dims):
        return None

    d = dims[0]
    pivot = df.pivot_table(index=df[t].astype(str), columns=d, values=m, aggfunc="sum", fill_value=0).sort_index()
    if len(pivot) < 2:
        return None

    partial = partial_periods(list(pivot.index))
    like_for_like = None

    # Monthly data spanning 2+ years -> compare the last two years on the
    # SAME months only (like-for-like), excluding partially covered months.
    if all(re.fullmatch(r"\d{4}-\d{2}", p) for p in pivot.index):
        clean = pivot.drop(index=[p for p in partial if p in pivot.index])
        years = sorted({p[:4] for p in clean.index})
        if len(years) >= 2:
            y_old, y_new = years[-2], years[-1]
            months = sorted(
                {p[5:] for p in clean.index if p[:4] == y_old}
                & {p[5:] for p in clean.index if p[:4] == y_new}
            )
            if months:
                old = clean.loc[[f"{y_old}-{mm}" for mm in months]].sum()
                new = clean.loc[[f"{y_new}-{mm}" for mm in months]].sum()
                label = f"months {months[0]}-{months[-1]}"
                p_old, p_new = f"{y_old} ({label})", f"{y_new} ({label})"
                like_for_like = f"Like-for-like comparison of the same months ({', '.join(months)}) in {y_old} and {y_new}."

    if like_for_like is None:
        p_old, p_new = pivot.index[-2], pivot.index[-1]
        old, new = pivot.loc[p_old], pivot.loc[p_new]
    delta = new - old
    total_delta = delta.sum()

    contrib = delta.sort_values()
    rows = []
    for k, v in contrib.items():
        rows.append({
            d: str(k),
            "before": _r(old[k]),
            "after": _r(new[k]),
            "change": _r(v),
            "change_pct": _pct(new[k], old[k]),
            "share_of_total_change_pct": _r(v / total_delta * 100) if total_delta else None,
        })

    return {
        "dimension": d,
        "metric": m,
        "compared_periods": [p_old, p_new],
        "like_for_like": like_for_like,
        "partial_periods_involved": [p for p in (p_old, p_new) if p in partial],
        "total_before": _r(old.sum()),
        "total_after": _r(new.sum()),
        "total_change": _r(total_delta),
        "total_change_pct": _pct(new.sum(), old.sum()),
        "biggest_negative_contributors": [r for r in rows if (r["change"] or 0) < 0][:5],
        "biggest_positive_contributors": [r for r in rows if (r["change"] or 0) > 0][::-1][:5],
    }


def _kpi_decomposition(df, prof) -> Optional[Dict]:
    """% change of every KPI between the last two periods (volume vs price etc.)."""

    t = prof["time_col"]
    if not t or not prof["metrics"]:
        return None
    agg = df.groupby(df[t].astype(str))[prof["metrics"]].sum().sort_index()
    if len(agg) < 2:
        return None
    a, b = agg.iloc[-2], agg.iloc[-1]
    return {
        "compared_periods": [agg.index[-2], agg.index[-1]],
        "kpi_change_pct": {c: _pct(b[c], a[c]) for c in agg.columns},
    }


def root_cause_analysis(datasets: Dict[str, pd.DataFrame], profiles: Dict[str, Dict]) -> Dict:
    """Run decomposition on every dataset; each supporting query is a candidate driver."""

    facts = {"drivers": {}, "kpi_changes": {}, "driver_shares": {}}

    for qid, df in datasets.items():
        prof = profiles[qid]

        dec = _change_decomposition(df, prof)
        if dec:
            facts["drivers"][qid] = dec

        kpi = _kpi_decomposition(df, prof)
        if kpi and len(prof["metrics"]) > 1:
            facts["kpi_changes"][qid] = kpi

        if not dec and prof["dimensions"] and prof["metric"]:
            facts["driver_shares"][qid] = comparison_analysis(df, prof)

        if prof["time_col"] and not prof["dimensions"]:
            facts.setdefault("trends", {})[qid] = trend_analysis(df, prof)

    # partial-period caveat
    involved = sorted({
        p for d in facts["drivers"].values() for p in d["partial_periods_involved"]
    })
    if involved:
        cov = get_metadata()["data_coverage"]
        facts["partial_period_warning"] = (
            f"Compared period(s) {involved} are only partially covered by the data "
            f"({cov['first_order_date']} to {cov['last_order_date']}). Part of the "
            "apparent change is caused by fewer months of data, not by real business decline."
        )

    return facts


def anomaly_analysis(df: pd.DataFrame, prof: Dict, z_threshold: float = 2.0) -> Dict:

    m = prof["metric"]
    if not m:
        return {"note": "No numeric metric found."}

    if prof["time_col"]:
        key = prof["time_col"]
        s = _time_series(df, prof)
    elif prof["dimensions"]:
        key = prof["dimensions"][0]
        s = df.groupby(df[key].astype(str))[m].agg(_agg(m))
    else:
        key = "row"
        s = df[m].reset_index(drop=True)
        s.index = s.index.astype(str)

    partial = partial_periods(list(s.index)) if prof["time_col"] else []
    base = s.drop(labels=[p for p in partial if p in s.index]) if len(s) - len(partial) >= 3 else s

    mean, std = base.mean(), base.std(ddof=0)
    q1, q3 = base.quantile(0.25), base.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr

    if len(base) < 8:
        z_threshold = min(z_threshold, 1.5)

    anomalies = []
    for k, v in s.items():
        z = (v - mean) / std if std else 0
        reasons = []
        if abs(z) >= z_threshold:
            reasons.append(f"z-score {z:+.2f}")
        if v < lo or v > hi:
            reasons.append("outside IQR fence")
        if reasons:
            anomalies.append({
                key: k,
                m: _r(v),
                "z_score": _r(z),
                "deviation_from_mean_pct": _pct(v, mean),
                "direction": "high" if v > mean else "low",
                "rule": ", ".join(reasons),
                "partial_period": k in partial,
            })

    return {
        "metric": m,
        "analysed_by": key,
        "points": int(len(s)),
        "baseline_mean": _r(mean),
        "baseline_std": _r(std),
        "z_threshold": z_threshold,
        "iqr_fence": [_r(lo), _r(hi)],
        "anomalies": sorted(anomalies, key=lambda a: -abs(a["z_score"] or 0))[:10],
        "partial_periods_excluded_from_baseline": partial,
        "series": {k: _r(v) for k, v in s.items()} if len(s) <= 40 else None,
    }
