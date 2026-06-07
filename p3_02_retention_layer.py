"""
Hipstarr Catalogue Audit Engine — Module 2: Retention Layer
============================================================
Calculates GR (Global Retention) and PMR (Primary Market Retention).

Primary market = highest streaming territory from data, NOT home market.

Asset Classification:
  Unicorn Fortress    GR >= 0.75 and PMR >= 0.70
  Stable Hub          GR >= 0.55 and PMR >= 0.50
  Commercial Corridor GR >= 0.30 and PMR >= 0.30
  Viral Spike         GR <  0.30 or  PMR <  0.30

Author : Ekene Ahuche — Hipstarr Music Research
Project: P3 Catalogue Audit Engine
Date   : May 2026
"""

import pandas as pd
import numpy as np
import os

CLEAN_PATH  = "p3_catalogue_clean.csv"
SCORES_PATH = "outputs/p3_integrity_scores.csv"
OUT_DIR     = "outputs"

PERIOD_ORDER = ["2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1"]

def load_data():
    df = pd.read_csv(CLEAN_PATH)
    df["streams"]     = pd.to_numeric(df["streams"],     errors="coerce").fillna(0)
    df["revenue_usd"] = pd.to_numeric(df["revenue_usd"], errors="coerce").fillna(0)
    df["reporting_period"] = df["reporting_period"].str.replace("/Q","-Q",regex=False)
    df = df[df["reporting_period"].isin(PERIOD_ORDER)]
    integrity = pd.read_csv(SCORES_PATH)
    return df, integrity

def get_primary_market(group):
    terr = group.groupby("territory")["streams"].sum()
    return terr.idxmax() if not terr.empty else group["home_market"].iloc[0]

def calc_retention(series, period_order):
    series     = series.reindex(period_order, fill_value=0)
    peak_rev   = series.max()
    peak_idx   = series.idxmax() if peak_rev > 0 else period_order[0]
    active     = [p for p in reversed(period_order) if series[p] > 0]
    latest_per = active[0] if active else period_order[-1]
    latest_rev = series[latest_per]
    retention  = round(latest_rev / peak_rev, 4) if peak_rev > 0 else 0
    recent = series[series > 0].tail(2)
    if len(recent) < 2:
        trend = "insufficient data"
    else:
        chg = (recent.iloc[-1] - recent.iloc[-2]) / max(recent.iloc[-2], 0.0001)
        if chg > 0.08:    trend = "growing"
        elif chg > -0.10: trend = "stable"
        elif chg > -0.30: trend = "declining"
        else:             trend = "collapsed"
    return dict(peak_period=peak_idx, peak_revenue=round(peak_rev,2),
                latest_period=latest_per, latest_revenue=round(latest_rev,2),
                retention=retention, trend=trend)

def classify_asset(gr, pmr):
    if   gr >= 0.75 and pmr >= 0.70: return "Unicorn Fortress"
    elif gr >= 0.55 and pmr >= 0.50: return "Stable Hub"
    elif gr >= 0.30 and pmr >= 0.30: return "Commercial Corridor"
    else:                             return "Viral Spike"

def score_retention(df):
    rows = []
    for (isrc, title, market), grp in df.groupby(["isrc","track_title","home_market"]):
        # Global
        global_rev = grp.groupby("reporting_period")["revenue_usd"].sum()
        gr = calc_retention(global_rev, PERIOD_ORDER)
        # Primary market — from data, not assumed
        primary = get_primary_market(grp)
        pm_grp  = grp[grp["territory"] == primary]
        if pm_grp.empty:
            primary = market
            pm_grp  = grp[grp["territory"] == market]
        pm_rev = pm_grp.groupby("reporting_period")["revenue_usd"].sum()
        pmr    = calc_retention(pm_rev, PERIOD_ORDER)
        rows.append({
            "isrc":              isrc,
            "track_title":       title,
            "home_market":       market,
            "primary_market":    primary,
            "primary_is_home":   primary == market,
            "total_streams":     int(grp["streams"].sum()),
            "total_revenue_usd": round(grp["revenue_usd"].sum(), 2),
            "quarters_active":   int((global_rev > 0).sum()),
            "gr_peak_period":    gr["peak_period"],
            "gr_peak_revenue":   gr["peak_revenue"],
            "gr_latest_revenue": gr["latest_revenue"],
            "global_retention":  gr["retention"],
            "global_trend":      gr["trend"],
            "primary_market_territory": primary,
            "pmr_peak_revenue":  pmr["peak_revenue"],
            "pmr_latest_revenue":pmr["latest_revenue"],
            "primary_retention": pmr["retention"],
            "primary_trend":     pmr["trend"],
            "asset_class":       classify_asset(gr["retention"], pmr["retention"]),
        })
    return pd.DataFrame(rows).sort_values("global_retention", ascending=False)

def merge_with_integrity(retention, integrity):
    merged = retention.merge(
        integrity[["isrc","integrity_score","readiness",
                   "revenue_at_risk_usd","completeness_score","traceability_score"]],
        on="isrc", how="left"
    )
    merged["audit_score"] = round(
        merged["integrity_score"].fillna(100) * 0.40 +
        merged["global_retention"]  * 100 * 0.35 +
        merged["primary_retention"] * 100 * 0.25, 1
    )
    return merged

def print_summary(r):
    print("\n" + "="*65)
    print("  HIPSTARR CATALOGUE AUDIT ENGINE — RETENTION LAYER REPORT")
    print("  Module 2: Retention Layer")
    print("="*65)

    print(f"\n  ASSET CLASSIFICATION")
    for cls in ["Unicorn Fortress","Stable Hub","Commercial Corridor","Viral Spike"]:
        n   = (r["asset_class"] == cls).sum()
        pct = n / len(r) * 100
        print(f"  {cls:<25} {n:>4} tracks  ({pct:.0f}%)")

    same = r["primary_is_home"].sum()
    diff = (~r["primary_is_home"]).sum()
    print(f"\n  PRIMARY vs HOME MARKET")
    print(f"  Primary = Home:   {same:>3} tracks")
    print(f"  Primary ≠ Home:   {diff:>3} tracks  ← tracks with diaspora-driven primary market")

    pm_diff = r[~r["primary_is_home"]][
        ["track_title","home_market","primary_market","global_retention","primary_retention"]
    ].head(8)
    for _, row in pm_diff.iterrows():
        print(f"    {row['track_title'][:26]:<26}  home={row['home_market']}  "
              f"primary={row['primary_market']}  "
              f"GR={row['global_retention']:.2f}  PMR={row['primary_retention']:.2f}")

    print(f"\n  GLOBAL TREND")
    for t in ["growing","stable","declining","collapsed","insufficient data"]:
        print(f"  {t:<22} {(r['global_trend']==t).sum():>3} tracks")

    print(f"\n  TOP 5 UNICORN FORTRESS")
    for _, row in r[r["asset_class"]=="Unicorn Fortress"].head(5).iterrows():
        print(f"  {row['track_title'][:28]:<28}  GR={row['global_retention']:.2f}  "
              f"PMR={row['primary_retention']:.2f}  trend={row['global_trend']}")

    print(f"\n  VIRAL SPIKE TRACKS (bottom GR)")
    for _, row in r[r["asset_class"]=="Viral Spike"].tail(5).iterrows():
        print(f"  {row['track_title'][:28]:<28}  GR={row['global_retention']:.2f}  "
              f"PMR={row['primary_retention']:.2f}  trend={row['global_trend']}")

    print(f"\n  OUTPUT: outputs/p3_retention_scores.csv")
    print("="*65 + "\n")

if __name__ == "__main__":
    print("\n  Hipstarr Catalogue Audit Engine — Module 2")
    print("  Loading data...")
    df, integrity = load_data()
    print("  Calculating retention scores...")
    retention = score_retention(df)
    print(f"  {len(retention)} tracks scored")
    print("  Merging with integrity layer...")
    full = merge_with_integrity(retention, integrity)
    full.to_csv(f"{OUT_DIR}/p3_retention_scores.csv", index=False)
    print_summary(retention)
