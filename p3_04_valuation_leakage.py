"""
Hipstarr Catalogue Audit Engine — Module 4: Valuation Leakage Estimator
========================================================================
Combines outputs from Modules 1, 2, and 3 to answer one question:

  "How much catalogue value is being lost — and exactly why?"

Three sources of leakage are measured:

  1. DATA INTEGRITY LEAKAGE
     Revenue that exists in the distributor file but cannot be
     processed — missing ISRCs, unallocated territories, zero-revenue
     reporting errors, duplicates. This money sits in a holding bucket
     or disappears between DSP and artist statement.

  2. RETENTION LEAKAGE
     Revenue lost because a track is decaying below its peak.
     Calculated as the gap between what a track earned at peak vs
     what it earns now, projected forward 4 quarters. A fast-burn
     track with GR 0.15 is losing 85% of its peak earning potential
     every period — that gap compounds over time.

  3. STRUCTURAL RATE LEAKAGE (VFG Layer)
     The gap created by low per-stream rates in home markets.
     A Nigerian track earning at $0.0004/stream when the US rate is
     $0.004 loses 90% of potential revenue on every domestic stream.
     This is the Value Flow Gap applied at the catalogue level.
     Relevant for emerging market catalogues — less so for global EDM
     (where NCS operates), but critical for labels like Mavin or YBNL.

Combined output:
  - Per-track leakage breakdown across all three sources
  - Total estimated value lost per quarter
  - Catalogue-level leakage % (how undervalued the catalogue is)
  - Audit Score: data quality × retention × rate structure

Author : Ekene Ahuche — Hipstarr Music Research
Project: P3 Catalogue Audit Engine
Date   : May 2026
"""

import pandas as pd
import numpy as np
import os

INTEGRITY_PATH  = "outputs/p3_integrity_scores.csv"
RETENTION_PATH  = "outputs/p3_retention_scores.csv"
STATEMENTS_PATH = "outputs/p3_statements.csv"
CLEAN_PATH      = "p3_catalogue_clean.csv"
OUT_DIR         = "outputs"

# Per-stream rate benchmarks (USD) — from P2 research
MARKET_RATES = {
    "NG": 0.0004, "ZA": 0.0015, "BR": 0.0018,
    "MX": 0.0022, "IN": 0.0006, "SA": 0.0025,
}
US_BENCHMARK = 0.004

# Projection window for retention leakage
FORWARD_QUARTERS = 4

# ── LOAD ALL MODULE OUTPUTS ───────────────────────────────────────────────────
def load_all():
    integrity  = pd.read_csv(INTEGRITY_PATH)
    retention  = pd.read_csv(RETENTION_PATH)
    statements = pd.read_csv(STATEMENTS_PATH)
    clean      = pd.read_csv(CLEAN_PATH)
    clean["streams"]     = pd.to_numeric(clean["streams"],     errors="coerce").fillna(0)
    clean["revenue_usd"] = pd.to_numeric(clean["revenue_usd"], errors="coerce").fillna(0)
    return integrity, retention, statements, clean

# ── SOURCE 1: DATA INTEGRITY LEAKAGE ─────────────────────────────────────────
def calc_integrity_leakage(integrity):
    """
    Revenue at risk from Module 1 — flagged rows that could not be
    cleanly processed. Per track.
    """
    return integrity[["isrc","track_title","home_market",
                       "revenue_at_risk_usd","integrity_score"]].copy()

# ── SOURCE 2: RETENTION LEAKAGE ──────────────────────────────────────────────
def calc_retention_leakage(retention):
    """
    Gap between peak quarterly revenue and current quarterly revenue,
    projected forward 4 quarters. Shows how much revenue the catalogue
    is haemorrhaging due to decay.

    For non-decay (GR >= 0.80) tracks, retention leakage is near zero.
    For Viral Spikes (GR < 0.30), the leakage compounds fast.
    """
    df = retention[["isrc","track_title","home_market","asset_class",
                     "gr_peak_revenue","gr_latest_revenue",
                     "global_retention","primary_retention",
                     "global_trend"]].copy()

    df["quarterly_gap"]       = (df["gr_peak_revenue"] - df["gr_latest_revenue"]).clip(lower=0)
    df["retention_leakage_usd"] = df["quarterly_gap"] * FORWARD_QUARTERS

    # Annualised retention leakage rate
    df["retention_leakage_pct"] = (
        df["quarterly_gap"] / df["gr_peak_revenue"].replace(0, np.nan) * 100
    ).fillna(0).round(1)

    return df

# ── SOURCE 3: STRUCTURAL RATE LEAKAGE (VFG Layer) ────────────────────────────
def calc_structural_leakage(clean, retention):
    """
    For each track, estimate how much more revenue would have been
    earned if all home market streams were paid at the US benchmark rate.

    VFG Leakage = home_streams × (US_rate - home_rate) per quarter
    Annualised = × 4 quarters.

    This is the Value Flow Gap applied at catalogue level — the
    structural infrastructure gap that emerging market artists face.
    """
    # Get home market streams from clean data
    home_streams = clean.groupby(["isrc","track_title","home_market","territory"]).agg(
        streams=("streams","sum")
    ).reset_index()

    # Filter to home market territory only
    home_only = home_streams[
        home_streams["territory"] == home_streams["home_market"]
    ].copy()

    home_only["home_rate"]   = home_only["home_market"].map(MARKET_RATES).fillna(0.002)
    home_only["rate_gap"]    = (US_BENCHMARK - home_only["home_rate"]).clip(lower=0)
    home_only["vfg_score"]   = (home_only["rate_gap"] / US_BENCHMARK * 100).round(2)

    # Total streams across all periods → annualise (divide by 7 periods × 4 quarters)
    home_only["avg_quarterly_home_streams"] = home_only["streams"] / 7
    home_only["structural_leakage_usd"] = (
        home_only["avg_quarterly_home_streams"] *
        home_only["rate_gap"] * 4  # annualised
    ).round(2)

    return home_only[["isrc","track_title","home_market",
                       "home_rate","vfg_score","structural_leakage_usd"]]

# ── COMBINE ALL THREE SOURCES ─────────────────────────────────────────────────
def combine_leakage(integrity_l, retention_l, structural_l):
    # Merge on isrc
    merged = retention_l.merge(
        integrity_l[["isrc","revenue_at_risk_usd","integrity_score"]],
        on="isrc", how="left"
    ).merge(
        structural_l[["isrc","home_rate","vfg_score","structural_leakage_usd"]],
        on="isrc", how="left"
    )

    merged["revenue_at_risk_usd"]  = merged["revenue_at_risk_usd"].fillna(0)
    merged["structural_leakage_usd"] = merged["structural_leakage_usd"].fillna(0)
    merged["integrity_score"]      = merged["integrity_score"].fillna(100)

    # Total annual leakage per track
    merged["total_leakage_usd"] = (
        merged["revenue_at_risk_usd"] +
        merged["retention_leakage_usd"] +
        merged["structural_leakage_usd"]
    ).round(2)

    # Realised annual revenue (from statements)
    # Use gr_peak_revenue × 4 as proxy for full-year potential
    merged["annual_potential_usd"] = (merged["gr_peak_revenue"] * 4).round(2)
    merged["annual_realised_usd"]  = (merged["gr_latest_revenue"] * 4).round(2)

    # Leakage as % of potential
    merged["leakage_pct"] = (
        merged["total_leakage_usd"] /
        (merged["annual_potential_usd"] + merged["total_leakage_usd"]).replace(0, np.nan)
        * 100
    ).fillna(0).round(1)

    # ── AUDIT SCORE ───────────────────────────────────────────────────────────
    # Weighted composite:
    # - Data integrity (40%): how clean is the data
    # - Retention (35%):      how well is the catalogue holding
    # - Rate structure (25%): how fair is the rate environment
    rate_score = (1 - merged["vfg_score"].fillna(0) / 100) * 100

    merged["audit_score"] = (
        merged["integrity_score"]  * 0.40 +
        merged["global_retention"] * 100 * 0.35 +
        rate_score                 * 0.25
    ).round(1)

    # ── AUDIT VERDICT ─────────────────────────────────────────────────────────
    def verdict(row):
        if   row["audit_score"] >= 80: return "Healthy — Monitor Quarterly"
        elif row["audit_score"] >= 65: return "Attention — Address Data + Rate Gaps"
        elif row["audit_score"] >= 50: return "At Risk — Immediate Review Required"
        else:                          return "Critical — Catalogue Value Severely Impaired"

    merged["audit_verdict"] = merged.apply(verdict, axis=1)

    return merged.sort_values("audit_score", ascending=False)

# ── SUMMARY REPORT ────────────────────────────────────────────────────────────
def print_summary(full):
    total_potential   = full["annual_potential_usd"].sum()
    total_realised    = full["annual_realised_usd"].sum()
    total_int_leakage = full["revenue_at_risk_usd"].sum()
    total_ret_leakage = full["retention_leakage_usd"].sum()
    total_str_leakage = full["structural_leakage_usd"].sum()
    total_leakage     = full["total_leakage_usd"].sum()
    catalogue_leakage_pct = total_leakage / (total_potential + total_leakage) * 100

    print("\n" + "="*65)
    print("  HIPSTARR CATALOGUE AUDIT ENGINE — VALUATION LEAKAGE REPORT")
    print("  Module 4: Valuation Leakage Estimator")
    print("="*65)

    print(f"\n  CATALOGUE LEAKAGE SUMMARY (ANNUALISED)")
    print(f"  {'Annual potential (at peak rates):':<40} ${total_potential:>12,.2f}")
    print(f"  {'Annual realised (current):':<40} ${total_realised:>12,.2f}")
    print(f"  {'Gap:':<40} ${total_potential-total_realised:>12,.2f}")

    print(f"\n  LEAKAGE BY SOURCE")
    print(f"  {'Data integrity leakage:':<40} ${total_int_leakage:>12,.2f}  "
          f"({total_int_leakage/total_leakage*100:.1f}%)")
    print(f"  {'Retention leakage (decay):':<40} ${total_ret_leakage:>12,.2f}  "
          f"({total_ret_leakage/total_leakage*100:.1f}%)")
    print(f"  {'Structural rate leakage (VFG):':<40} ${total_str_leakage:>12,.2f}  "
          f"({total_str_leakage/total_leakage*100:.1f}%)")
    print(f"  {'TOTAL ANNUAL LEAKAGE:':<40} ${total_leakage:>12,.2f}")
    print(f"\n  This catalogue is undervalued by {catalogue_leakage_pct:.1f}%")

    print(f"\n  AUDIT VERDICT BREAKDOWN")
    for v in ["Healthy — Monitor Quarterly",
              "Attention — Address Data + Rate Gaps",
              "At Risk — Immediate Review Required",
              "Critical — Catalogue Value Severely Impaired"]:
        n = (full["audit_verdict"] == v).sum()
        print(f"  {v:<45} {n:>3} tracks")

    print(f"\n  TOP 5 TRACKS — HIGHEST AUDIT SCORE")
    for _, r in full.nlargest(5,"audit_score").iterrows():
        print(f"  [{r['audit_score']:5.1f}] {r['track_title'][:28]:<28} "
              f"{r['home_market']}  leakage: ${r['total_leakage_usd']:>8,.0f}  "
              f"{r['audit_verdict'].split('—')[0].strip()}")

    print(f"\n  BOTTOM 5 TRACKS — MOST VALUE AT RISK")
    for _, r in full.nsmallest(5,"audit_score").iterrows():
        print(f"  [{r['audit_score']:5.1f}] {r['track_title'][:28]:<28} "
              f"{r['home_market']}  leakage: ${r['total_leakage_usd']:>8,.0f}  "
              f"{r['audit_verdict'].split('—')[0].strip()}")

    print(f"\n  LEAKAGE BY MARKET")
    market_leak = full.groupby("home_market").agg(
        tracks=("isrc","count"),
        total_leakage=("total_leakage_usd","sum"),
        avg_audit_score=("audit_score","mean"),
        avg_vfg=("vfg_score","mean")
    ).sort_values("avg_audit_score",ascending=False)
    for mkt, row in market_leak.iterrows():
        print(f"  {mkt}  tracks={int(row.tracks)}  "
              f"leakage=${row.total_leakage:>10,.0f}  "
              f"avg_audit={row.avg_audit_score:.1f}  "
              f"avg_vfg={row.avg_vfg:.1f}")

    print(f"\n  OUTPUT: outputs/p3_valuation_leakage.csv")
    print("="*65 + "\n")

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  Hipstarr Catalogue Audit Engine — Module 4")
    print("  Loading all module outputs...")
    integrity, retention, statements, clean = load_all()

    print("  Calculating integrity leakage...")
    integrity_l  = calc_integrity_leakage(integrity)

    print("  Calculating retention leakage...")
    retention_l  = calc_retention_leakage(retention)

    print("  Calculating structural rate leakage (VFG)...")
    structural_l = calc_structural_leakage(clean, retention)

    print("  Combining all leakage sources...")
    full = combine_leakage(integrity_l, retention_l, structural_l)

    full.to_csv(f"{OUT_DIR}/p3_valuation_leakage.csv", index=False)
    print_summary(full)
