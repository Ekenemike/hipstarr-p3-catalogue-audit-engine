# Hipstarr Catalogue Audit Engine
### Project 3 — Royalty Data Processing & Catalogue Intelligence

**By Ekene Ahuche · Hipstarr Music Research · Lagos · June 2026**
[substack.com/@ekenemike](https://substack.com/@ekenemike)

---

## Overview

A four-module Python pipeline that models the core royalty data workflow at a music label — ingesting raw distributor revenue CSVs, flagging data integrity problems, scoring catalogue retention, reconciling artist statements, and estimating total catalogue value leakage.

Built to demonstrate end-to-end royalty operations capability: from messy distributor file to clean MRC-ready submission and draft artist statements.

**Live dashboard:** [hipstarr-p3.streamlit.app](https://hipstarr-p3.streamlit.app)
**GitHub:** [github.com/Ekenemike/hipstarr-p3-catalogue-audit-engine](https://github.com/Ekenemike/hipstarr-p3-catalogue-audit-engine)

---

## The Workflow This Models

```
Distributor CSV arrives
        ↓
Module 1 — Data Integrity Layer
  Flag missing ISRCs, unallocated territories,
  zero-revenue rows, duplicates, bad formatting
  → Output: integrity scores + MRC-ready clean CSV
        ↓
Module 2 — Retention Layer
  Calculate Global Retention (GR) and Primary
  Market Retention (PMR) per track. Primary market
  determined from data — not assumed to be home market.
  → Output: asset classification per track
        ↓
Module 3 — Statement Reconciliation
  Apply contract terms: distributor commission,
  mechanical deductions, participation rate,
  reserve, recoupment → calculate artist payable
  → Output: draft royalty statements per artist
        ↓
Module 4 — Valuation Leakage Estimator
  Quantify value lost across three sources:
  data integrity gaps, retention decay,
  structural rate gaps
  → Output: catalogue leakage % + audit score
```

---

## Royalty Waterfall

Every row of revenue flows through this chain before an artist sees payment:

| Step | What Happens |
|------|-------------|
| Gross receipts | Raw DSP revenue in the distributor file |
| Distributor commission | Label's distributor takes ~18% off the top |
| Net receipts | What the label actually receives |
| Mechanical deduction | ~9.1% deducted on publishing contracts for mechanical rights |
| Gross royalty | Net receipts × artist participation rate (70–85%) |
| Reserve held | Label withholds 10–25% against future corrections |
| Net royalty | Gross royalty minus reserve |
| Recoupment | Outstanding advance deducted before any cash is paid |
| **Payable** | **What the artist actually receives this period** |

---

## Key Terminology

**ISRC** — International Standard Recording Code. Unique identifier for every recorded track. Missing ISRCs mean revenue cannot be matched to a contract or split between rights holders.

**UPC** — Universal Product Code. Identifies the release/album. Missing UPCs block bundle-level royalty allocation.

**Net receipts** — Revenue after the distributor takes their commission. The royalty calculation starts here, not from gross.

**Participation rate** — The artist's contractual share of net receipts. Typically 70–85% depending on deal terms, artist tier, and whether publishing is included.

**Mechanical deduction** — A deduction applied to publishing contracts covering the mechanical right (the right to reproduce a composition). US statutory rate: 9.1 cents per unit in 2024.

**Reserve** — A percentage of earned royalties withheld by the label per accounting period, held against potential returns, corrections, or adjustments. Typically 10–25%.

**Recoupment** — Advances paid to artists are not free money — they are recouped (repaid) from royalty earnings before any cash is distributed. Until an advance is fully recouped, an artist's payable is zero even if they are earning royalties.

**MRC (Music Royalty Co)** — Outsourced royalty processor. Labels submit prepared revenue data to MRC, who calculate royalties against contract terms and generate draft statements.

**Curve** — Royalty platform used to manage contracts, review draft statements, publish artist-facing royalty reports, and process payments. Contracts in Curve have unique IDs that revenue rows must map to.

**Content ID** — YouTube's system for claiming ad revenue from videos that use copyrighted music. For labels like NCS whose music is widely used by creators, Content ID is a significant revenue stream processed separately from DSP streaming royalties.

**Sentric** — Publishing administration platform. Handles collection of publishing royalties (performance and mechanical) from collecting societies globally.

**Global Retention (GR)** — Ratio of a track's current quarterly revenue to its peak quarterly revenue across all territories. GR 0.86 means the track is earning 86% of what it earned at its highest point.

**Primary Market Retention (PMR)** — Same calculation but for the single territory generating the most streams. Primary market is determined from actual data — not assumed to be the artist's home country.

**Unallocated income** — Revenue received where the territory field is blank or the ISRC cannot be matched. Must be held in a suspense account until resolved with the distributor.

---

## Dataset

42 synthetic tracks modelled on real streaming patterns across 6 markets — Nigeria, South Africa, Brazil, Mexico, India, Saudi Arabia. 7 reporting periods (2024-Q3 to 2026-Q1). 5 DSPs. 18 territories.

Raw file contains deliberate data quality problems:
- 732 missing ISRCs
- 370 missing territories (unallocated income)
- 182 zero-revenue rows (streams recorded, no payment)
- 91 duplicate rows (double-counted submissions)
- Artist name inconsistencies
- Non-standard period formats

| File | Description |
|------|-------------|
| `p3_catalogue_raw.csv` | Raw distributor file (9,156 rows with problems) |
| `p3_catalogue_clean.csv` | Ground truth (9,065 clean rows) |

---

## Module Outputs

| File | Description |
|------|-------------|
| `p3_integrity_scores.csv` | Per-track integrity scores (completeness, traceability, reporting) |
| `p3_flags.csv` | Every flagged row with severity and recommended action |
| `p3_mrc_ready.csv` | Clean rows cleared for MRC submission |
| `p3_retention_scores.csv` | GR, PMR, asset classification per track |
| `p3_statements.csv` | Full per-track per-period royalty statements |
| `p3_payable_summary.csv` | Period-level payable per artist |
| `p3_valuation_leakage.csv` | Full leakage breakdown + audit score per track |

---

## Running Locally

```bash
git clone https://github.com/Ekenemike/hipstarr-p3-catalogue-audit-engine
cd hipstarr-p3-catalogue-audit-engine
pip install -r requirements.txt
streamlit run p3_dashboard.py
```

Upload any distributor CSV or click **Run on Sample Data** to run on the included dataset.

---

## Repository Structure

```
hipstarr-p3-catalogue-audit-engine/
│
├── p3_dashboard.py                  ← Streamlit dashboard (entry point)
├── requirements.txt                 ← Python dependencies
├── README.md                        ← This file
│
├── p3_01_data_integrity.py          ← Module 1: Data Integrity Layer
├── p3_02_retention_layer.py         ← Module 2: Retention Layer
├── p3_03_statement_reconciliation.py← Module 3: Statement Reconciliation
├── p3_04_valuation_leakage.py       ← Module 4: Valuation Leakage Estimator
│
├── p3_catalogue_raw.csv             ← Raw distributor file (with problems)
├── p3_catalogue_clean.csv           ← Clean ground truth dataset
│
└── outputs/
    ├── p3_integrity_scores.csv
    ├── p3_flags.csv
    ├── p3_mrc_ready.csv
    ├── p3_retention_scores.csv
    ├── p3_statements.csv
    ├── p3_payable_summary.csv
    └── p3_valuation_leakage.csv
```

---

## Pipeline Results (Sample Dataset)

- **3,142 flags** detected across 8 rule types
- **$2.6M revenue at risk** from data integrity problems
- **87.4% MRC submission rate** — 1,155 rows blocked
- **18 artists** fully recouped their advances this cycle
- **Total payable:** $2.33M
- **Catalogue undervalued by 60.3%** across three leakage sources

---

## Related Projects

- [Project 1 — Afrobeats vs Latin Pop Streaming Decay Analysis](https://github.com/Ekenemike/hipstarr-streaming-decay-analysis)
- [Project 2 — Value Flow Gap Analysis](https://github.com/Ekenemike/hipstarr-p2-value-flow-gap)

---

**Ekene Ahuche**
Hipstarr Music Research — Music Intelligence, Hipstarr Music
Hipstarr Music is the music vertical of Hipstarr.
Lagos · June 2026

*Project complete. Data as of June 2026. All methodology final.*
