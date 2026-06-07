"""
Hipstarr Catalogue Audit Engine — Module 1: Data Integrity Layer
=================================================================
Ingests a raw distributor revenue CSV and produces:
  1. Per-track integrity scores (Completeness, Traceability, Reporting Frequency)
  2. Row-level flag report with severity and recommended action
  3. MRC-ready clean CSV (rows that pass all critical checks)
  4. Console summary report

Designed to mirror the data preparation workflow described in royalty
operations roles: identify missing identifiers, flag unallocated income,
catch zero-revenue reporting errors, and surface duplicate submissions.

Author : Ekene Ahuche — Hipstarr Music Research
Project: P3 Catalogue Audit Engine
Date   : May 2026
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
RAW_PATH   = "p3_catalogue_raw.csv"
OUT_DIR    = "outputs"
os.makedirs(OUT_DIR, exist_ok=True)

VALID_PERIODS_RE = r"^\d{4}-Q[1-4]$"   # Canonical format: 2025-Q1
VALID_DSPS = {"Spotify", "Apple Music", "YouTube Music", "Boomplay", "Deezer"}

# Severity weights for scoring (higher = worse problem)
SEVERITY_WEIGHTS = {
    "CRITICAL": 1.00,
    "HIGH":     0.60,
    "MEDIUM":   0.30,
    "LOW":      0.10,
}

# ── LOAD ──────────────────────────────────────────────────────────────────────
def load_raw(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)
    df["streams"]     = pd.to_numeric(df["streams"],     errors="coerce").fillna(0).astype(int)
    df["revenue_usd"] = pd.to_numeric(df["revenue_usd"], errors="coerce").fillna(0.0)
    df["isrc"]        = df["isrc"].fillna("").str.strip()
    df["upc"]         = df["upc"].fillna("").str.strip()
    df["territory"]   = df["territory"].fillna("").str.strip()
    df["label"]       = df["label"].fillna("").str.strip()
    df["artist"]      = df["artist"].fillna("").str.strip()
    df["reporting_period"] = df["reporting_period"].fillna("").str.strip()
    print(f"  Loaded {len(df):,} rows from {path}")
    return df

# ── FLAG ENGINE ───────────────────────────────────────────────────────────────
def run_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Evaluate every row against integrity rules.
    Returns a flags DataFrame with one row per problem detected.
    """
    flags = []

    def flag(row_idx, isrc, track, rule_id, severity, category, description, revenue_at_risk):
        flags.append({
            "row_index":       row_idx,
            "isrc":            isrc,
            "track_title":     track,
            "rule_id":         rule_id,
            "severity":        severity,
            "category":        category,
            "description":     description,
            "revenue_at_risk": round(revenue_at_risk, 4),
            "recommended_action": ACTIONS.get(rule_id, "Review manually"),
        })

    ACTIONS = {
        "INT-001": "Match to catalogue by UPC or track title; hold revenue until ISRC confirmed",
        "INT-002": "Match to catalogue by ISRC or track title; update UPC before MRC submission",
        "INT-003": "Assign to 'Unallocated Income' holding bucket; investigate territory with distributor",
        "INT-004": "Raise reporting query with DSP; request corrected statement or credit note",
        "INT-005": "Standardise artist name to canonical form before contract matching",
        "INT-006": "Normalise period to YYYY-QN format; verify it maps to correct accounting period",
        "INT-007": "De-duplicate before MRC submission; flag transaction ID for reconciliation check",
        "INT-008": "Update missing label info from catalogue master; required for royalty split",
    }

    # Duplicate detection by (isrc, dsp, territory, reporting_period, streams)
    dup_mask = df.duplicated(
        subset=["isrc", "dsp", "territory", "reporting_period", "streams"],
        keep="first"
    )
    dup_indices = set(df[dup_mask].index)

    for idx, row in df.iterrows():
        isrc  = row["isrc"]
        title = row["track_title"]
        rev   = row["revenue_usd"]
        strms = row["streams"]

        # INT-001: Missing ISRC — CRITICAL
        if isrc == "":
            flag(idx, isrc, title, "INT-001", "CRITICAL", "Completeness",
                 "ISRC missing — cannot match to contract or royalty split", rev)

        # INT-002: Missing UPC — HIGH
        if row["upc"] == "":
            flag(idx, isrc, title, "INT-002", "HIGH", "Completeness",
                 "UPC missing — bundle/album matching will fail", rev)

        # INT-003: Missing territory — CRITICAL (unallocated income)
        if row["territory"] == "":
            flag(idx, isrc, title, "INT-003", "CRITICAL", "Traceability",
                 f"Territory missing — ${rev:.4f} revenue unallocated", rev)

        # INT-004: Zero revenue with streams > 0 — HIGH (reporting error)
        if strms > 0 and rev == 0.0:
            flag(idx, isrc, title, "INT-004", "HIGH", "Traceability",
                 f"Zero revenue reported for {strms:,} streams — DSP reporting error", 0)

        # INT-005: Inconsistent artist name — MEDIUM
        known_variants = {
            "wizkid", "wizkid ft tems", "wizkid feat. tems",
            "burna boy", "burnaboy",
            "peso pluma", "peso pluma & raul vega",
        }
        artist_lower = row["artist"].lower().replace("ft.", "ft").replace(",", "")
        if any(v in artist_lower for v in known_variants) and row["artist"] not in [
            "Wizkid ft. Tems", "Burna Boy", "Peso Pluma ft. Raul Vega"
        ]:
            flag(idx, isrc, title, "INT-005", "MEDIUM", "Completeness",
                 f"Non-canonical artist name: '{row['artist']}' — contract matching may fail", rev)

        # INT-006: Non-standard period format — MEDIUM
        period = row["reporting_period"]
        if period != "" and not pd.Series([period]).str.match(VALID_PERIODS_RE).iloc[0]:
            flag(idx, isrc, title, "INT-006", "MEDIUM", "Reporting Frequency",
                 f"Period format '{period}' is non-standard — expected YYYY-QN", rev)

        # INT-007: Duplicate row — HIGH
        if idx in dup_indices:
            flag(idx, isrc, title, "INT-007", "HIGH", "Traceability",
                 "Duplicate submission detected — revenue double-counted", rev)

        # INT-008: Missing label — LOW
        if row["label"] == "":
            flag(idx, isrc, title, "INT-008", "LOW", "Completeness",
                 "Label missing — required for publishing/masters royalty split", rev)

    return pd.DataFrame(flags)

# ── SCORING ───────────────────────────────────────────────────────────────────
def score_tracks(df: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    """
    Per-track integrity scores (0–100) across three dimensions.
    Score = 100 − weighted penalty for each flag type.
    """
    results = []
    tracks = df.groupby(["isrc", "track_title", "home_market"])

    for (isrc, title, market), group in tracks:
        n = len(group)
        track_flags = flags[flags["isrc"] == isrc] if isrc != "" else pd.DataFrame()

        def count_sev(rule, sev=None):
            if track_flags.empty: return 0
            mask = track_flags["rule_id"] == rule
            return mask.sum()

        # ── Completeness Score ────────────────────────────────────────────────
        # Missing ISRC (-40), Missing UPC (-20), Missing Label (-10), Artist name (-15)
        c_score = 100
        c_score -= count_sev("INT-001") / n * 100 * 0.40   # ISRC (CRITICAL)
        c_score -= count_sev("INT-002") / n * 100 * 0.20   # UPC (HIGH)
        c_score -= count_sev("INT-008") / n * 100 * 0.10   # Label (LOW)
        c_score -= count_sev("INT-005") / n * 100 * 0.15   # Artist (MEDIUM)
        c_score  = max(0, round(c_score, 1))

        # ── Traceability Score ────────────────────────────────────────────────
        # Missing territory (-40), Zero revenue (-30), Duplicates (-20)
        t_score = 100
        t_score -= count_sev("INT-003") / n * 100 * 0.40   # Territory (CRITICAL)
        t_score -= count_sev("INT-004") / n * 100 * 0.30   # Zero revenue (HIGH)
        t_score -= count_sev("INT-007") / n * 100 * 0.20   # Duplicates (HIGH)
        t_score  = max(0, round(t_score, 1))

        # ── Reporting Frequency Score ─────────────────────────────────────────
        # Period format errors (-30), missing periods
        periods_reported = group["reporting_period"].str.match(VALID_PERIODS_RE).sum()
        expected_periods = 7  # 7 quarters in our dataset
        unique_valid     = group[group["reporting_period"].str.match(VALID_PERIODS_RE)]["reporting_period"].nunique()
        r_score = 100
        r_score -= count_sev("INT-006") / n * 100 * 0.30   # Bad format (-30)
        r_score -= max(0, (expected_periods - unique_valid)) / expected_periods * 100 * 0.20  # Missing periods
        r_score  = max(0, round(r_score, 1))

        # ── Overall Integrity Score ───────────────────────────────────────────
        overall = round((c_score * 0.35 + t_score * 0.45 + r_score * 0.20), 1)

        # ── Revenue at risk ───────────────────────────────────────────────────
        rev_total    = group["revenue_usd"].sum()
        rev_at_risk  = track_flags["revenue_at_risk"].sum() if not track_flags.empty else 0
        rev_at_risk_pct = round(rev_at_risk / rev_total * 100, 1) if rev_total > 0 else 0

        # ── Readiness classification ──────────────────────────────────────────
        if overall >= 90:   readiness = "MRC-Ready"
        elif overall >= 75: readiness = "Minor Review"
        elif overall >= 55: readiness = "Needs Correction"
        else:               readiness = "Hold — Do Not Submit"

        flag_counts = track_flags["severity"].value_counts().to_dict() if not track_flags.empty else {}

        results.append({
            "isrc":                  isrc,
            "track_title":           title,
            "home_market":           market,
            "rows":                  n,
            "completeness_score":    c_score,
            "traceability_score":    t_score,
            "reporting_freq_score":  r_score,
            "integrity_score":       overall,
            "readiness":             readiness,
            "total_revenue_usd":     round(rev_total, 2),
            "revenue_at_risk_usd":   round(rev_at_risk, 2),
            "revenue_at_risk_pct":   rev_at_risk_pct,
            "flags_critical":        flag_counts.get("CRITICAL", 0),
            "flags_high":            flag_counts.get("HIGH", 0),
            "flags_medium":          flag_counts.get("MEDIUM", 0),
            "flags_low":             flag_counts.get("LOW", 0),
            "total_flags":           len(track_flags),
        })

    return pd.DataFrame(results).sort_values("integrity_score")

# ── MRC-READY OUTPUT ──────────────────────────────────────────────────────────
def build_mrc_ready(df: pd.DataFrame, flags: pd.DataFrame) -> pd.DataFrame:
    """
    Remove rows with CRITICAL flags (INT-001, INT-003) and duplicates (INT-007).
    Standardise remaining rows for MRC submission.
    """
    critical_indices = set(flags[flags["severity"] == "CRITICAL"]["row_index"])
    dup_indices      = set(flags[flags["rule_id"]  == "INT-007"]["row_index"])
    exclude          = critical_indices | dup_indices

    clean = df[~df.index.isin(exclude)].copy()

    # Standardise period format
    clean["reporting_period"] = clean["reporting_period"].str.replace("/Q", "-Q", regex=False)

    # Add submission metadata
    clean["submission_date"]  = datetime.now().strftime("%Y-%m-%d")
    clean["submission_ready"] = True

    return clean.reset_index(drop=True)

# ── SUMMARY REPORT ────────────────────────────────────────────────────────────
def print_summary(df_raw, flags, scores, mrc_ready):
    total_rev      = df_raw["revenue_usd"].sum()
    rev_at_risk    = flags["revenue_at_risk"].sum()
    critical_count = (flags["severity"] == "CRITICAL").sum()
    high_count     = (flags["severity"] == "HIGH").sum()
    medium_count   = (flags["severity"] == "MEDIUM").sum()
    low_count      = (flags["severity"] == "LOW").sum()
    mrc_pct        = len(mrc_ready) / len(df_raw) * 100

    print("\n" + "="*65)
    print("  HIPSTARR CATALOGUE AUDIT ENGINE — DATA INTEGRITY REPORT")
    print("  Module 1: Data Integrity Layer")
    print(f"  Run date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*65)

    print(f"\n  INPUT")
    print(f"  {'Raw rows:':<35} {len(df_raw):>10,}")
    print(f"  {'Tracks:':<35} {scores['isrc'].nunique():>10,}")
    print(f"  {'Total revenue (gross):':<35} ${total_rev:>14,.2f}")

    print(f"\n  FLAGS DETECTED")
    print(f"  {'CRITICAL (block submission):':<35} {critical_count:>10,}")
    print(f"  {'HIGH (review required):':<35} {high_count:>10,}")
    print(f"  {'MEDIUM (monitor):':<35} {medium_count:>10,}")
    print(f"  {'LOW (informational):':<35} {low_count:>10,}")
    print(f"  {'Total flags:':<35} {len(flags):>10,}")

    print(f"\n  REVENUE AT RISK")
    print(f"  {'Revenue flagged:':<35} ${rev_at_risk:>14,.2f}")
    print(f"  {'% of total:':<35} {rev_at_risk/total_rev*100:>9.1f}%")

    print(f"\n  MRC SUBMISSION READINESS")
    print(f"  {'Rows cleared for submission:':<35} {len(mrc_ready):>10,}")
    print(f"  {'Rows blocked:':<35} {len(df_raw)-len(mrc_ready):>10,}")
    print(f"  {'Submission rate:':<35} {mrc_pct:>9.1f}%")

    print(f"\n  TRACK READINESS BREAKDOWN")
    readiness_counts = scores["readiness"].value_counts()
    for status, count in readiness_counts.items():
        print(f"  {status:<35} {count:>10,} tracks")

    print(f"\n  WORST 5 TRACKS BY INTEGRITY SCORE")
    bottom5 = scores.nsmallest(5, "integrity_score")[
        ["track_title","home_market","integrity_score","readiness","revenue_at_risk_usd"]
    ]
    for _, row in bottom5.iterrows():
        print(f"  [{row['integrity_score']:5.1f}] {row['track_title'][:28]:<28} "
              f"{row['home_market']}  ${row['revenue_at_risk_usd']:>8,.2f} at risk  {row['readiness']}")

    print(f"\n  BEST 5 TRACKS BY INTEGRITY SCORE")
    top5 = scores.nlargest(5, "integrity_score")[
        ["track_title","home_market","integrity_score","readiness"]
    ]
    for _, row in top5.iterrows():
        print(f"  [{row['integrity_score']:5.1f}] {row['track_title'][:28]:<28} {row['home_market']}  {row['readiness']}")

    print("\n" + "="*65)
    print("  OUTPUT FILES")
    print("  outputs/p3_integrity_scores.csv  — per-track integrity scores")
    print("  outputs/p3_flags.csv             — all flagged rows with actions")
    print("  outputs/p3_mrc_ready.csv         — clean rows ready for submission")
    print("="*65 + "\n")

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  Hipstarr Catalogue Audit Engine — Module 1")
    print("  Loading raw distributor data...")
    df_raw = load_raw(RAW_PATH)

    print("  Running flag engine...")
    flags = run_flags(df_raw)
    print(f"  {len(flags):,} flags detected")

    print("  Scoring tracks...")
    scores = score_tracks(df_raw, flags)
    print(f"  {len(scores):,} tracks scored")

    print("  Building MRC-ready output...")
    mrc_ready = build_mrc_ready(df_raw, flags)

    # Save outputs
    scores.to_csv(f"{OUT_DIR}/p3_integrity_scores.csv", index=False)
    flags.to_csv(f"{OUT_DIR}/p3_flags.csv", index=False)
    mrc_ready.to_csv(f"{OUT_DIR}/p3_mrc_ready.csv", index=False)

    # Print summary
    print_summary(df_raw, flags, scores, mrc_ready)
