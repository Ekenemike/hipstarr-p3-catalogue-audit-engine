"""
Hipstarr Catalogue Audit Engine — Module 3: Statement Reconciliation
=====================================================================
Takes the MRC-ready CSV from Module 1 and produces draft royalty
statements per artist per accounting period.

This module models the core monthly workflow at a label royalty desk:

  GROSS RECEIPTS       Raw DSP revenue in the data file
       ↓
  NET RECEIPTS         Gross minus distributor commission (typically 15–20%)
       ↓
  GROSS ROYALTY        Net receipts × artist participation rate
       ↓
  RESERVE HELD         Label withholds % against future corrections (10–25%)
       ↓
  NET ROYALTY          Gross royalty minus reserve
       ↓
  RECOUPMENT CHECK     If advance outstanding, deduct from net royalty
       ↓
  PAYABLE              Cash the artist actually receives this period

Key terminology used in this module:
  Participation rate  — artist's contractual share of net receipts
  Mechanical deduction— publishing deduction for mechanical rights
  Reserve             — % of earned royalties held back against returns
  Recoupment          — advances repaid from royalties before cash out
  Unrecouped balance  — outstanding advance not yet repaid

Author : Ekene Ahuche — Hipstarr Music Research
Project: P3 Catalogue Audit Engine
Date   : May 2026
"""

import pandas as pd
import numpy as np
import os

MRC_PATH      = "outputs/p3_mrc_ready.csv"
OUT_DIR       = "outputs"
DIST_COMMISSION = 0.18   # 18% distributor commission (industry standard)

# ── MOCK CONTRACT TABLE ───────────────────────────────────────────────────────
# In Curve, every track maps to a contract ID.
# Participation rate = artist share of net receipts.
# Reserve rate = % of gross royalty held back per period.
# Advance = unrecouped advance balance outstanding.

CONTRACTS = [
    # ISRC         Contract ID   Participation  Reserve  Advance($)  Contract Type
    ("NG001", "C-001001", 0.78, 0.15, 0,       "Masters"),
    ("NG002", "C-001002", 0.82, 0.15, 12000,   "Masters"),
    ("NG003", "C-001003", 0.75, 0.10, 0,       "Masters+Publishing"),
    ("NG004", "C-001004", 0.80, 0.15, 8000,    "Masters"),
    ("NG005", "C-001005", 0.72, 0.10, 0,       "Masters+Publishing"),
    ("NG006", "C-001006", 0.80, 0.10, 0,       "Masters"),
    ("NG007", "C-001007", 0.72, 0.15, 5000,    "Masters"),
    ("ZA001", "C-002001", 0.85, 0.10, 0,       "Masters+Publishing"),
    ("ZA002", "C-002002", 0.78, 0.20, 6000,    "Masters"),
    ("ZA003", "C-002003", 0.78, 0.20, 4000,    "Masters"),
    ("ZA004", "C-002004", 0.75, 0.20, 0,       "Masters"),
    ("ZA005", "C-002005", 0.75, 0.20, 0,       "Masters"),
    ("ZA006", "C-002006", 0.80, 0.20, 3000,    "Masters"),
    ("ZA007", "C-002007", 0.80, 0.15, 0,       "Masters"),
    ("BR001", "C-003001", 0.82, 0.10, 0,       "Masters+Publishing"),
    ("BR002", "C-003002", 0.82, 0.10, 0,       "Masters+Publishing"),
    ("BR003", "C-003003", 0.78, 0.15, 15000,   "Masters"),
    ("BR004", "C-003004", 0.78, 0.15, 0,       "Masters"),
    ("BR005", "C-003005", 0.80, 0.20, 2000,    "Masters"),
    ("BR006", "C-003006", 0.82, 0.15, 0,       "Masters"),
    ("BR007", "C-003007", 0.80, 0.20, 1500,    "Masters"),
    ("MX001", "C-004001", 0.75, 0.10, 25000,   "Masters+Publishing"),
    ("MX002", "C-004002", 0.75, 0.10, 20000,   "Masters"),
    ("MX003", "C-004003", 0.78, 0.15, 0,       "Masters"),
    ("MX004", "C-004004", 0.80, 0.15, 0,       "Masters"),
    ("MX005", "C-004005", 0.78, 0.10, 18000,   "Masters+Publishing"),
    ("MX006", "C-004006", 0.80, 0.15, 0,       "Masters"),
    ("MX007", "C-004007", 0.75, 0.10, 22000,   "Masters"),
    ("IN001", "C-005001", 0.72, 0.15, 0,       "Masters+Publishing"),
    ("IN002", "C-005002", 0.72, 0.15, 30000,   "Masters+Publishing"),
    ("IN003", "C-005003", 0.78, 0.20, 0,       "Masters"),
    ("IN004", "C-005004", 0.78, 0.20, 0,       "Masters"),
    ("IN005", "C-005005", 0.82, 0.20, 5000,    "Masters"),
    ("IN006", "C-005006", 0.72, 0.15, 20000,   "Masters+Publishing"),
    ("IN007", "C-005007", 0.78, 0.20, 0,       "Masters"),
    ("SA001", "C-006001", 0.75, 0.20, 0,       "Masters"),
    ("SA002", "C-006002", 0.75, 0.20, 0,       "Masters"),
    ("SA003", "C-006003", 0.78, 0.20, 8000,    "Masters"),
    ("SA004", "C-006004", 0.75, 0.15, 0,       "Masters"),
    ("SA005", "C-006005", 0.80, 0.20, 3000,    "Masters"),
    ("SA006", "C-006006", 0.78, 0.20, 0,       "Masters"),
    ("SA007", "C-006007", 0.75, 0.15, 0,       "Masters"),
]

CONTRACT_COLS = ["isrc","contract_id","participation_rate",
                 "reserve_rate","advance_usd","contract_type"]
contracts_df  = pd.DataFrame(CONTRACTS, columns=CONTRACT_COLS)

MECH_DEDUCTION = 0.091   # 9.1% mechanical deduction rate (US statutory 2024)

# ── LOAD MRC-READY DATA ───────────────────────────────────────────────────────
def load_mrc(path):
    df = pd.read_csv(path)
    df["revenue_usd"] = pd.to_numeric(df["revenue_usd"], errors="coerce").fillna(0)
    df["streams"]     = pd.to_numeric(df["streams"],     errors="coerce").fillna(0)
    df["reporting_period"] = df["reporting_period"].str.replace("/Q","-Q",regex=False)
    print(f"  Loaded {len(df):,} MRC-ready rows")
    return df

# ── RECONCILIATION ENGINE ─────────────────────────────────────────────────────
def reconcile(df, contracts):
    df = df.merge(contracts, on="isrc", how="left")

    # Flag rows with no contract match
    no_contract = df["contract_id"].isna()
    if no_contract.sum() > 0:
        print(f"  ⚠  {no_contract.sum()} rows have no contract match — excluded from statements")
    df = df[~no_contract].copy()

    # ── Step 1: Net receipts (after distributor commission) ───────────────────
    df["net_receipts"] = df["revenue_usd"] * (1 - DIST_COMMISSION)

    # ── Step 2: Mechanical deduction for publishing contracts ─────────────────
    has_publishing = df["contract_type"].str.contains("Publishing", na=False)
    df["mechanical_deduction"] = 0.0
    df.loc[has_publishing, "mechanical_deduction"] = \
        df.loc[has_publishing, "net_receipts"] * MECH_DEDUCTION
    df["net_after_mechanical"] = df["net_receipts"] - df["mechanical_deduction"]

    # ── Step 3: Gross royalty = net × participation rate ─────────────────────
    df["gross_royalty"] = df["net_after_mechanical"] * df["participation_rate"]

    # ── Step 4: Reserve ───────────────────────────────────────────────────────
    df["reserve_held"]  = df["gross_royalty"] * df["reserve_rate"]
    df["net_royalty"]   = df["gross_royalty"] - df["reserve_held"]

    return df

# ── ARTIST STATEMENTS ─────────────────────────────────────────────────────────
def build_statements(df, contracts):
    """
    Aggregate to period-level per artist/contract.
    Apply recoupment. Calculate payable.
    """
    # Sum by contract + period
    stmt = df.groupby(
        ["isrc","track_title","artist","contract_id","contract_type",
         "participation_rate","reserve_rate","reporting_period"]
    ).agg(
        streams          = ("streams",            "sum"),
        gross_receipts   = ("revenue_usd",        "sum"),
        net_receipts     = ("net_receipts",        "sum"),
        mech_deduction   = ("mechanical_deduction","sum"),
        gross_royalty    = ("gross_royalty",       "sum"),
        reserve_held     = ("reserve_held",        "sum"),
        net_royalty      = ("net_royalty",         "sum"),
    ).reset_index()

    # Apply recoupment per contract across periods (cumulative)
    stmt = stmt.sort_values(["contract_id","reporting_period"])
    advance_lookup = contracts.set_index("isrc")["advance_usd"].to_dict()

    recoup_balances = {}
    payable_list    = []
    recouped_list   = []

    for _, row in stmt.iterrows():
        cid     = row["contract_id"]
        isrc    = row["isrc"]
        net_roy = row["net_royalty"]

        # Initialise advance balance on first encounter
        if cid not in recoup_balances:
            recoup_balances[cid] = advance_lookup.get(isrc, 0)

        balance = recoup_balances[cid]

        if balance > 0:
            # Recoup from this period's net royalty
            recouped_this_period = min(balance, net_roy)
            payable              = max(0, net_roy - balance)
            recoup_balances[cid] = max(0, balance - net_roy)
            just_recouped        = recoup_balances[cid] == 0 and balance > 0
        else:
            recouped_this_period = 0
            payable              = net_roy
            just_recouped        = False

        payable_list.append(round(payable, 2))
        recouped_list.append(round(recouped_this_period, 2))

    stmt["recouped_this_period"] = recouped_list
    stmt["payable_usd"]          = payable_list
    stmt["unrecouped_balance"]   = stmt["contract_id"].map(recoup_balances)

    # Round all currency columns
    currency_cols = ["gross_receipts","net_receipts","mech_deduction",
                     "gross_royalty","reserve_held","net_royalty",
                     "recouped_this_period","payable_usd","unrecouped_balance"]
    stmt[currency_cols] = stmt[currency_cols].round(2)

    return stmt

# ── SUMMARY REPORT ────────────────────────────────────────────────────────────
def print_summary(stmt, df_reconciled):
    total_gross   = stmt["gross_receipts"].sum()
    total_net     = stmt["net_receipts"].sum()
    total_royalty = stmt["gross_royalty"].sum()
    total_reserve = stmt["reserve_held"].sum()
    total_recoup  = stmt["recouped_this_period"].sum()
    total_payable = stmt["payable_usd"].sum()
    still_unrec   = stmt.drop_duplicates("contract_id")["unrecouped_balance"].sum()

    print("\n" + "="*65)
    print("  HIPSTARR CATALOGUE AUDIT ENGINE — STATEMENT RECONCILIATION")
    print("  Module 3: Statement Reconciliation")
    print("="*65)

    print(f"\n  ROYALTY WATERFALL — FULL CATALOGUE")
    print(f"  {'Gross receipts (DSP revenue):':<38} ${total_gross:>12,.2f}")
    print(f"  {'Less: distributor commission (18%):':<38} ${total_gross*0.18:>12,.2f}")
    print(f"  {'Net receipts:':<38} ${total_net:>12,.2f}")
    print(f"  {'Less: mechanical deductions:':<38} ${stmt['mech_deduction'].sum():>12,.2f}")
    print(f"  {'Gross royalty (participation rate):':<38} ${total_royalty:>12,.2f}")
    print(f"  {'Less: reserve held:':<38} ${total_reserve:>12,.2f}")
    print(f"  {'Net royalty:':<38} ${total_royalty-total_reserve:>12,.2f}")
    print(f"  {'Less: recoupment this cycle:':<38} ${total_recoup:>12,.2f}")
    print(f"  {'TOTAL PAYABLE THIS CYCLE:':<38} ${total_payable:>12,.2f}")

    print(f"\n  RECOUPMENT STATUS")
    contracts_with_advance = stmt[stmt["unrecouped_balance"] > 0].drop_duplicates("contract_id")
    fully_recouped = stmt[
        (stmt["recouped_this_period"] > 0) &
        (stmt["unrecouped_balance"]   == 0)
    ].drop_duplicates("contract_id")

    print(f"  Contracts still unrecouped:    {len(contracts_with_advance)}")
    print(f"  Total unrecouped balance:      ${still_unrec:>10,.2f}")
    print(f"  Contracts fully recouped:      {len(fully_recouped)}")
    if not fully_recouped.empty:
        for _, r in fully_recouped.iterrows():
            print(f"    ✓ {r['artist'][:30]:<30} {r['contract_id']}  — advance fully recouped")

    print(f"\n  TOP 5 ARTISTS BY PAYABLE (LATEST PERIOD)")
    latest = stmt[stmt["reporting_period"] == stmt["reporting_period"].max()]
    top5   = latest.groupby(["artist","contract_id"])["payable_usd"].sum().nlargest(5)
    for (artist, cid), amt in top5.items():
        print(f"  {artist[:32]:<32} {cid}   ${amt:>10,.2f}")

    print(f"\n  CONTRACTS WITH ZERO PAYABLE (unrecouped or reserve)")
    zero_pay = latest[latest["payable_usd"] == 0][["artist","contract_id","unrecouped_balance"]].drop_duplicates()
    for _, r in zero_pay.head(8).iterrows():
        print(f"  {r['artist'][:32]:<32} {r['contract_id']}   "
              f"unrecouped: ${r['unrecouped_balance']:>8,.2f}")

    print(f"\n  DSP BREAKDOWN — NET RECEIPTS")
    dsp_rev = df_reconciled.groupby("dsp")["net_receipts"].sum().sort_values(ascending=False)
    for dsp, rev in dsp_rev.items():
        pct = rev / total_net * 100
        print(f"  {dsp:<20} ${rev:>10,.2f}   ({pct:.1f}%)")

    print(f"\n  OUTPUT FILES")
    print(f"  outputs/p3_statements.csv       — full per-track per-period statements")
    print(f"  outputs/p3_payable_summary.csv  — period-level payable per artist")
    print("="*65 + "\n")

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  Hipstarr Catalogue Audit Engine — Module 3")
    print("  Loading MRC-ready data...")
    df_mrc = load_mrc(MRC_PATH)

    print("  Reconciling against contracts...")
    df_rec = reconcile(df_mrc, contracts_df)

    print("  Building artist statements...")
    statements = build_statements(df_rec, contracts_df)

    # Payable summary — per artist, per period
    payable_summary = statements.groupby(
        ["artist","contract_id","reporting_period"]
    ).agg(
        gross_receipts   = ("gross_receipts",  "sum"),
        net_receipts     = ("net_receipts",    "sum"),
        gross_royalty    = ("gross_royalty",   "sum"),
        reserve_held     = ("reserve_held",    "sum"),
        recouped         = ("recouped_this_period","sum"),
        payable_usd      = ("payable_usd",     "sum"),
        unrecouped_balance=("unrecouped_balance","max"),
    ).reset_index().round(2)

    statements.to_csv(    f"{OUT_DIR}/p3_statements.csv",       index=False)
    payable_summary.to_csv(f"{OUT_DIR}/p3_payable_summary.csv", index=False)

    print_summary(statements, df_rec)
