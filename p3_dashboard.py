"""
Hipstarr Catalogue Audit Engine — Dashboard
============================================
Streamlit app that runs all 4 modules in sequence and
displays results in a tabbed interface.

Run locally:
  streamlit run p3_dashboard.py

Author : Ekene Ahuche — Hipstarr Music Research
Project: P3 Catalogue Audit Engine
Date   : May 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io
import sys
import os

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Hipstarr Catalogue Audit Engine",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── BRAND COLOURS ─────────────────────────────────────────────────────────────
GOLD   = "#d4af37"
BG     = "#070709"
SURF   = "#0e0e12"
TEXT   = "#f0eef8"
MUTED  = "#8a8a9e"
MC = {
    "NG":"#ff6b35","ZA":"#34d399","BR":"#f0c040",
    "MX":"#b07ef8","IN":"#5ba8f5","SA":"#f47070",
}

# ── STYLES ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background:#070709; }
[data-testid="stSidebar"]          { background:#0e0e12; border-right:1px solid #1e1e28; }
h1,h2,h3,h4                        { color:#f0eef8; }
.metric-card {
    background:#0e0e12; border:1px solid #1e1e28;
    border-radius:8px; padding:16px 20px; margin-bottom:8px;
}
.metric-val   { font-size:28px; font-weight:700; color:#d4af37; font-family:monospace; }
.metric-label { font-size:11px; color:#8a8a9e; letter-spacing:2px; text-transform:uppercase; }
.flag-critical { color:#ff4444; font-weight:700; }
.flag-high     { color:#ff8c42; font-weight:600; }
.flag-medium   { color:#f0c040; }
.flag-low      { color:#8a8a9e; }
.verdict-healthy   { color:#34d399; }
.verdict-attention { color:#f0c040; }
.verdict-risk      { color:#ff8c42; }
.verdict-critical  { color:#ff4444; }
</style>
""", unsafe_allow_html=True)

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"<h3 style='color:{GOLD};font-family:monospace;letter-spacing:3px'>HIPSTARR</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color:#8a8a9e;font-size:11px;margin-top:-12px'>CATALOGUE AUDIT ENGINE</p>", unsafe_allow_html=True)
    st.markdown("---")

    uploaded = st.file_uploader(
        "Upload distributor CSV",
        type=["csv"],
        help="Upload a raw distributor revenue CSV. Must include: isrc, upc, track_title, artist, label, home_market, dsp, territory, reporting_period, streams, revenue_usd"
    )

    st.markdown("---")
    st.markdown("<p style='color:#555568;font-size:11px'>Or run on sample data</p>", unsafe_allow_html=True)
    use_sample = st.button("▶  Run on Sample Data", use_container_width=True)
    st.markdown("---")
    st.markdown(f"<p style='color:#555568;font-size:10px'>Hipstarr Music Research<br>Lagos · 2026<br><a href='https://substack.com/@ekenemike' style='color:{GOLD}'>substack.com/@ekenemike</a></p>", unsafe_allow_html=True)

# ── PIPELINE IMPORTS ──────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

PERIOD_ORDER = ["2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1"]
DIST_COMMISSION = 0.18
US_BENCHMARK    = 0.004
MARKET_RATES    = {"NG":0.0004,"ZA":0.0015,"BR":0.0018,"MX":0.0022,"IN":0.0006,"SA":0.0025}
VALID_PERIODS_RE = r"^\d{4}-Q[1-4]$"

CONTRACTS = [
    ("NG001","C-001001",0.78,0.15,0,"Masters"),("NG002","C-001002",0.82,0.15,12000,"Masters"),
    ("NG003","C-001003",0.75,0.10,0,"Masters+Publishing"),("NG004","C-001004",0.80,0.15,8000,"Masters"),
    ("NG005","C-001005",0.72,0.10,0,"Masters+Publishing"),("NG006","C-001006",0.80,0.10,0,"Masters"),
    ("NG007","C-001007",0.72,0.15,5000,"Masters"),("ZA001","C-002001",0.85,0.10,0,"Masters+Publishing"),
    ("ZA002","C-002002",0.78,0.20,6000,"Masters"),("ZA003","C-002003",0.78,0.20,4000,"Masters"),
    ("ZA004","C-002004",0.75,0.20,0,"Masters"),("ZA005","C-002005",0.75,0.20,0,"Masters"),
    ("ZA006","C-002006",0.80,0.20,3000,"Masters"),("ZA007","C-002007",0.80,0.15,0,"Masters"),
    ("BR001","C-003001",0.82,0.10,0,"Masters+Publishing"),("BR002","C-003002",0.82,0.10,0,"Masters+Publishing"),
    ("BR003","C-003003",0.78,0.15,15000,"Masters"),("BR004","C-003004",0.78,0.15,0,"Masters"),
    ("BR005","C-003005",0.80,0.20,2000,"Masters"),("BR006","C-003006",0.82,0.15,0,"Masters"),
    ("BR007","C-003007",0.80,0.20,1500,"Masters"),("MX001","C-004001",0.75,0.10,25000,"Masters+Publishing"),
    ("MX002","C-004002",0.75,0.10,20000,"Masters"),("MX003","C-004003",0.78,0.15,0,"Masters"),
    ("MX004","C-004004",0.80,0.15,0,"Masters"),("MX005","C-004005",0.78,0.10,18000,"Masters+Publishing"),
    ("MX006","C-004006",0.80,0.15,0,"Masters"),("MX007","C-004007",0.75,0.10,22000,"Masters"),
    ("IN001","C-005001",0.72,0.15,0,"Masters+Publishing"),("IN002","C-005002",0.72,0.15,30000,"Masters+Publishing"),
    ("IN003","C-005003",0.78,0.20,0,"Masters"),("IN004","C-005004",0.78,0.20,0,"Masters"),
    ("IN005","C-005005",0.82,0.20,5000,"Masters"),("IN006","C-005006",0.72,0.15,20000,"Masters+Publishing"),
    ("IN007","C-005007",0.78,0.20,0,"Masters"),("SA001","C-006001",0.75,0.20,0,"Masters"),
    ("SA002","C-006002",0.75,0.20,0,"Masters"),("SA003","C-006003",0.78,0.20,8000,"Masters"),
    ("SA004","C-006004",0.75,0.15,0,"Masters"),("SA005","C-006005",0.80,0.20,3000,"Masters"),
    ("SA006","C-006006",0.78,0.20,0,"Masters"),("SA007","C-006007",0.75,0.15,0,"Masters"),
]
contracts_df = pd.DataFrame(CONTRACTS, columns=["isrc","contract_id","participation_rate","reserve_rate","advance_usd","contract_type"])

# ── PIPELINE FUNCTIONS ────────────────────────────────────────────────────────
def load_raw(df_or_path):
    if isinstance(df_or_path, str):
        df = pd.read_csv(df_or_path, dtype=str)
    else:
        df = df_or_path.copy()
    df["streams"]          = pd.to_numeric(df.get("streams",0),     errors="coerce").fillna(0).astype(int)
    df["revenue_usd"]      = pd.to_numeric(df.get("revenue_usd",0), errors="coerce").fillna(0.0)
    for col in ["isrc","upc","territory","label","artist","reporting_period"]:
        if col in df.columns:
            df[col] = df[col].fillna("").str.strip()
    return df

def run_flags(df):
    flags = []
    ACTIONS = {
        "INT-001":"Match to catalogue by UPC or title; hold revenue until ISRC confirmed",
        "INT-002":"Match by ISRC or title; update UPC before MRC submission",
        "INT-003":"Assign to Unallocated Income bucket; investigate territory with distributor",
        "INT-004":"Raise query with DSP; request corrected statement or credit note",
        "INT-005":"Standardise artist name to canonical form before contract matching",
        "INT-006":"Normalise period to YYYY-QN format",
        "INT-007":"De-duplicate before MRC submission; flag transaction ID",
        "INT-008":"Update missing label from catalogue master",
    }
    dup_mask = df.duplicated(subset=["isrc","dsp","territory","reporting_period","streams"],keep="first")
    dup_idx  = set(df[dup_mask].index)
    known_variants = {"wizkid","wizkid ft tems","wizkid feat. tems","burna boy","burnaboy","peso pluma","peso pluma & raul vega"}
    for idx, row in df.iterrows():
        isrc=row.get("isrc",""); title=row.get("track_title",""); rev=row.get("revenue_usd",0); strms=row.get("streams",0)
        def flag(rid,sev,cat,desc,rat):
            flags.append({"row_index":idx,"isrc":isrc,"track_title":title,"rule_id":rid,"severity":sev,"category":cat,"description":desc,"revenue_at_risk":round(rat,4),"recommended_action":ACTIONS.get(rid,"Review manually")})
        if isrc=="":          flag("INT-001","CRITICAL","Completeness",f"ISRC missing — ${rev:.2f} unresolvable",rev)
        if row.get("upc","")=="\\":   flag("INT-002","HIGH","Completeness","UPC missing",rev)
        if row.get("territory","")=="\\":   flag("INT-003","CRITICAL","Traceability",f"Territory missing — ${rev:.2f} unallocated",rev)
        if strms>0 and rev==0: flag("INT-004","HIGH","Traceability",f"Zero revenue for {strms:,} streams",0)
        artist_l=row.get("artist","").lower().replace("ft.","ft").replace(",","")
        if any(v in artist_l for v in known_variants) and row.get("artist","") not in ["Wizkid ft. Tems","Burna Boy","Peso Pluma ft. Raul Vega"]:
            flag("INT-005","MEDIUM","Completeness",f"Non-canonical artist: '{row.get('artist','')}'",rev)
        period=row.get("reporting_period","")
        if period!="" and not pd.Series([period]).str.match(VALID_PERIODS_RE).iloc[0]:
            flag("INT-006","MEDIUM","Reporting",f"Bad period format: '{period}'",rev)
        if idx in dup_idx: flag("INT-007","HIGH","Traceability","Duplicate row",rev)
        if row.get("label","")=="\\":  flag("INT-008","LOW","Completeness","Label missing",rev)
    return pd.DataFrame(flags)

def score_tracks(df, flags):
    results=[]
    for (isrc,title,market), grp in df.groupby(["isrc","track_title","home_market"]):
        n=len(grp); tf=flags[flags["isrc"]==isrc] if isrc!="" else pd.DataFrame()
        def cf(rule): return (tf["rule_id"]==rule).sum() if not tf.empty else 0
        c = max(0,round(100 - cf("INT-001")/n*40 - cf("INT-002")/n*20 - cf("INT-008")/n*10 - cf("INT-005")/n*15,1))
        t = max(0,round(100 - cf("INT-003")/n*40 - cf("INT-004")/n*30 - cf("INT-007")/n*20,1))
        vp= (grp["reporting_period"].str.match(VALID_PERIODS_RE)).sum()
        uv= grp[grp["reporting_period"].str.match(VALID_PERIODS_RE)]["reporting_period"].nunique()
        r = max(0,round(100 - cf("INT-006")/n*30 - max(0,7-uv)/7*20,1))
        overall=round(c*0.35+t*0.45+r*0.20,1)
        rev_total=grp["revenue_usd"].sum(); rev_risk=tf["revenue_at_risk"].sum() if not tf.empty else 0
        readiness="MRC-Ready" if overall>=90 else "Minor Review" if overall>=75 else "Needs Correction" if overall>=55 else "Hold — Do Not Submit"
        fc=tf["severity"].value_counts().to_dict() if not tf.empty else {}
        results.append({"isrc":isrc,"track_title":title,"home_market":market,"completeness_score":c,"traceability_score":t,"reporting_freq_score":r,"integrity_score":overall,"readiness":readiness,"total_revenue_usd":round(rev_total,2),"revenue_at_risk_usd":round(rev_risk,2),"flags_critical":fc.get("CRITICAL",0),"flags_high":fc.get("HIGH",0),"flags_medium":fc.get("MEDIUM",0),"flags_low":fc.get("LOW",0),"total_flags":len(tf)})
    return pd.DataFrame(results)

def build_mrc_ready(df, flags):
    excl = set(flags[flags["severity"]=="CRITICAL"]["row_index"]) | set(flags[flags["rule_id"]=="INT-007"]["row_index"])
    clean=df[~df.index.isin(excl)].copy()
    clean["reporting_period"]=clean["reporting_period"].str.replace("/Q","-Q",regex=False)
    return clean.reset_index(drop=True)

def calc_retention(series, period_order):
    series=series.reindex(period_order,fill_value=0)
    peak=series.max(); pidx=series.idxmax() if peak>0 else period_order[0]
    active=[p for p in reversed(period_order) if series[p]>0]
    lp=active[0] if active else period_order[-1]; lr=series[lp]
    ret=round(lr/peak,4) if peak>0 else 0
    recent=series[series>0].tail(2)
    if len(recent)<2: trend="insufficient data"
    else:
        chg=(recent.iloc[-1]-recent.iloc[-2])/max(recent.iloc[-2],0.0001)
        trend="growing" if chg>0.08 else "stable" if chg>-0.10 else "declining" if chg>-0.30 else "collapsed"
    return dict(peak_period=pidx,peak_revenue=round(peak,2),latest_period=lp,latest_revenue=round(lr,2),retention=ret,trend=trend)

def classify_asset(gr,pmr):
    if   gr>=0.75 and pmr>=0.70: return "Unicorn Fortress"
    elif gr>=0.55 and pmr>=0.50: return "Stable Hub"
    elif gr>=0.30 and pmr>=0.30: return "Commercial Corridor"
    else:                         return "Viral Spike"

def score_retention(df):
    rows=[]
    df2=df[df["reporting_period"].isin(PERIOD_ORDER)].copy()
    for (isrc,title,market),grp in df2.groupby(["isrc","track_title","home_market"]):
        gr_rev=grp.groupby("reporting_period")["revenue_usd"].sum()
        gr=calc_retention(gr_rev,PERIOD_ORDER)
        terr=grp.groupby("territory")["streams"].sum()
        pm=terr.idxmax() if not terr.empty else market
        pm_grp=grp[grp["territory"]==pm]
        if pm_grp.empty: pm=market; pm_grp=grp[grp["territory"]==market]
        pmr_rev=pm_grp.groupby("reporting_period")["revenue_usd"].sum()
        pmr=calc_retention(pmr_rev,PERIOD_ORDER)
        rows.append({"isrc":isrc,"track_title":title,"home_market":market,"primary_market":pm,"primary_is_home":pm==market,"total_streams":int(grp["streams"].sum()),"total_revenue_usd":round(grp["revenue_usd"].sum(),2),"quarters_active":int((gr_rev>0).sum()),"gr_peak_revenue":gr["peak_revenue"],"gr_latest_revenue":gr["latest_revenue"],"global_retention":gr["retention"],"global_trend":gr["trend"],"pmr_peak_revenue":pmr["peak_revenue"],"pmr_latest_revenue":pmr["latest_revenue"],"primary_retention":pmr["retention"],"primary_trend":pmr["trend"],"asset_class":classify_asset(gr["retention"],pmr["retention"])})
    return pd.DataFrame(rows)

def reconcile_statements(df_mrc, contracts):
    df=df_mrc.merge(contracts,on="isrc",how="left")
    df=df[~df["contract_id"].isna()].copy()
    df["net_receipts"]=df["revenue_usd"]*(1-DIST_COMMISSION)
    has_pub=df["contract_type"].str.contains("Publishing",na=False)
    df["mechanical_deduction"]=0.0
    df.loc[has_pub,"mechanical_deduction"]=df.loc[has_pub,"net_receipts"]*0.091
    df["net_after_mech"]=df["net_receipts"]-df["mechanical_deduction"]
    df["gross_royalty"]=df["net_after_mech"]*df["participation_rate"]
    df["reserve_held"]=df["gross_royalty"]*df["reserve_rate"]
    df["net_royalty"]=df["gross_royalty"]-df["reserve_held"]
    stmt=df.groupby(["isrc","track_title","artist","contract_id","contract_type","participation_rate","reserve_rate","reporting_period"]).agg(streams=("streams","sum"),gross_receipts=("revenue_usd","sum"),net_receipts=("net_receipts","sum"),mech_deduction=("mechanical_deduction","sum"),gross_royalty=("gross_royalty","sum"),reserve_held=("reserve_held","sum"),net_royalty=("net_royalty","sum")).reset_index()
    stmt=stmt.sort_values(["contract_id","reporting_period"])
    adv={r["isrc"]:r["advance_usd"] for _,r in contracts.iterrows()}
    bal={}; pay=[]; rec=[]
    for _,row in stmt.iterrows():
        cid=row["contract_id"]; nr=row["net_royalty"]
        if cid not in bal: bal[cid]=adv.get(row["isrc"],0)
        b=bal[cid]
        if b>0:
            rt=min(b,nr); p=max(0,nr-b); bal[cid]=max(0,b-nr)
        else:
            rt=0; p=nr
        pay.append(round(p,2)); rec.append(round(rt,2))
    stmt["recouped_this_period"]=rec; stmt["payable_usd"]=pay
    stmt["unrecouped_balance"]=stmt["contract_id"].map(bal)
    return stmt.round(2)

def calc_leakage(integrity, retention, df_clean):
    ret=retention.copy()
    ret["quarterly_gap"]=(ret["gr_peak_revenue"]-ret["gr_latest_revenue"]).clip(lower=0)
    ret["retention_leakage_usd"]=(ret["quarterly_gap"]*4).round(2)
    home=df_clean.groupby(["isrc","track_title","home_market","territory"])["streams"].sum().reset_index()
    home=home[home["territory"]==home["home_market"]].copy()
    home["home_rate"]=home["home_market"].map(MARKET_RATES).fillna(0.002)
    home["rate_gap"]=(US_BENCHMARK-home["home_rate"]).clip(lower=0)
    home["vfg_score"]=(home["rate_gap"]/US_BENCHMARK*100).round(2)
    home["structural_leakage_usd"]=(home["streams"]/7*home["rate_gap"]*4).round(2)
    merged=ret.merge(integrity[["isrc","revenue_at_risk_usd","integrity_score"]],on="isrc",how="left")
    merged=merged.merge(home[["isrc","home_rate","vfg_score","structural_leakage_usd"]],on="isrc",how="left")
    merged["revenue_at_risk_usd"]=merged["revenue_at_risk_usd"].fillna(0)
    merged["structural_leakage_usd"]=merged["structural_leakage_usd"].fillna(0)
    merged["integrity_score"]=merged["integrity_score"].fillna(100)
    merged["total_leakage_usd"]=(merged["revenue_at_risk_usd"]+merged["retention_leakage_usd"]+merged["structural_leakage_usd"]).round(2)
    merged["annual_potential_usd"]=(merged["gr_peak_revenue"]*4).round(2)
    merged["leakage_pct"]=(merged["total_leakage_usd"]/(merged["annual_potential_usd"]+merged["total_leakage_usd"]).replace(0,np.nan)*100).fillna(0).round(1)
    rate_score=(1-merged["vfg_score"].fillna(0)/100)*100
    merged["audit_score"]=(merged["integrity_score"]*0.40+merged["global_retention"]*100*0.35+rate_score*0.25).round(1)
    def verdict(r):
        if r["audit_score"]>=80:   return "Healthy"
        elif r["audit_score"]>=65: return "Attention"
        elif r["audit_score"]>=50: return "At Risk"
        else:                       return "Critical"
    merged["verdict"]=merged.apply(verdict,axis=1)
    return merged

# ── MAIN APP ──────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style='border-top:2px solid;border-image:linear-gradient(90deg,#ff6b35,#d4af37,#5ba8f5) 1;padding-top:16px;margin-bottom:8px'>
<span style='font-family:monospace;font-size:11px;color:{GOLD};letter-spacing:4px'>HIPSTARR MUSIC RESEARCH</span><br>
<span style='font-size:24px;font-weight:800;color:{TEXT}'>Catalogue Audit Engine</span><br>
<span style='font-family:monospace;font-size:11px;color:{MUTED}'>Data Integrity · Retention Analysis · Statement Reconciliation · Valuation Leakage</span>
</div>
""", unsafe_allow_html=True)

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
df_raw = None

if uploaded is not None:
    df_raw = pd.read_csv(uploaded, dtype=str)
    st.success(f"Loaded {len(df_raw):,} rows from uploaded file")
elif use_sample:
    sample_path = os.path.join(os.path.dirname(__file__), "p3_catalogue_raw.csv")
    if os.path.exists(sample_path):
        df_raw = pd.read_csv(sample_path, dtype=str)
        st.info(f"Running on sample dataset — {len(df_raw):,} rows, 42 tracks, 6 markets")
    else:
        st.error("Sample data file not found. Make sure p3_catalogue_raw.csv is in the same directory.")

if df_raw is None:
    st.markdown(f"""
    <div style='background:{SURF};border:1px solid #1e1e28;border-radius:8px;padding:32px;text-align:center;margin-top:40px'>
    <p style='color:{MUTED};font-family:monospace;font-size:13px'>Upload a distributor CSV or click <b style='color:{GOLD}'>Run on Sample Data</b> to begin</p>
    <p style='color:#333340;font-family:monospace;font-size:11px'>Expected columns: isrc · upc · track_title · artist · label · home_market · dsp · territory · reporting_period · streams · revenue_usd</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── RUN PIPELINE ──────────────────────────────────────────────────────────────
with st.spinner("Running audit pipeline..."):
    df     = load_raw(df_raw)
    flags  = run_flags(df)
    scores = score_tracks(df, flags)
    mrc    = build_mrc_ready(df, flags)
    ret    = score_retention(df)
    clean  = load_raw(os.path.join(os.path.dirname(__file__), "p3_catalogue_clean.csv")) if os.path.exists(os.path.join(os.path.dirname(__file__),"p3_catalogue_clean.csv")) else df
    stmt   = reconcile_statements(mrc, contracts_df)
    leak   = calc_leakage(scores, ret, clean)

# ── TOP KPI ROW ───────────────────────────────────────────────────────────────
k1,k2,k3,k4,k5 = st.columns(5)
with k1:
    st.markdown(f"""<div class='metric-card'><div class='metric-val'>{len(df):,}</div><div class='metric-label'>Raw Rows</div></div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""<div class='metric-card'><div class='metric-val'>{len(flags):,}</div><div class='metric-label'>Flags Detected</div></div>""", unsafe_allow_html=True)
with k3:
    crit=(flags["severity"]=="CRITICAL").sum()
    st.markdown(f"""<div class='metric-card'><div class='metric-val' style='color:#ff4444'>{crit:,}</div><div class='metric-label'>Critical Flags</div></div>""", unsafe_allow_html=True)
with k4:
    payable=stmt["payable_usd"].sum()
    st.markdown(f"""<div class='metric-card'><div class='metric-val'>${payable:,.0f}</div><div class='metric-label'>Total Payable</div></div>""", unsafe_allow_html=True)
with k5:
    tl=leak["total_leakage_usd"].sum(); tp=leak["annual_potential_usd"].sum()
    lpct=tl/(tp+tl)*100
    st.markdown(f"""<div class='metric-card'><div class='metric-val' style='color:#ff8c42'>{lpct:.1f}%</div><div class='metric-label'>Catalogue Undervalued By</div></div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── TABS ──────────────────────────────────────────────────────────────────────
t1,t2,t3,t4 = st.tabs(["🔍 Data Integrity","📈 Retention","💰 Statements","⚠️ Leakage"])

# ── TAB 1: DATA INTEGRITY ─────────────────────────────────────────────────────
with t1:
    st.markdown("### Data Integrity Layer")
    st.markdown(f"<p style='color:{MUTED};font-size:12px'>Scoring every track on Completeness, Traceability, and Reporting Frequency. Rows with CRITICAL flags are blocked from MRC submission.</p>", unsafe_allow_html=True)

    c1,c2 = st.columns(2)

    with c1:
        flag_counts = flags["severity"].value_counts()
        fig = go.Figure(go.Bar(
            x=flag_counts.index,
            y=flag_counts.values,
            marker_color=["#ff4444","#ff8c42","#f0c040","#8a8a9e"],
            text=flag_counts.values,
            textposition="outside",
        ))
        fig.update_layout(title="Flags by Severity",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color=TEXT,showlegend=False,height=300,margin=dict(t=40,b=20))
        fig.update_xaxes(tickfont_color=MUTED); fig.update_yaxes(gridcolor="#1e1e28",tickfont_color=MUTED)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        rule_counts=flags["rule_id"].value_counts().reset_index()
        rule_counts.columns=["Rule","Count"]
        rule_rev=flags.groupby("rule_id")["revenue_at_risk"].sum().reset_index()
        rule_rev.columns=["Rule","Revenue at Risk"]
        rule_df=rule_counts.merge(rule_rev,on="Rule")
        fig2=px.bar(rule_df,x="Rule",y="Revenue at Risk",title="Revenue at Risk by Rule",color_discrete_sequence=[GOLD])
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color=TEXT,height=300,margin=dict(t=40,b=20))
        fig2.update_xaxes(tickfont_color=MUTED); fig2.update_yaxes(gridcolor="#1e1e28",tickfont_color=MUTED)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown(f"**{len(mrc):,}** rows cleared for MRC submission — **{len(df)-len(mrc):,}** blocked")

    display_scores = scores[["track_title","home_market","integrity_score","readiness",
                              "completeness_score","traceability_score","reporting_freq_score",
                              "flags_critical","flags_high","revenue_at_risk_usd"]].copy()
    display_scores.columns=["Track","Market","Integrity","Readiness","Completeness","Traceability","Reporting","🔴 Critical","🟠 High","$ At Risk"]
    st.dataframe(display_scores.style.background_gradient(subset=["Integrity"],cmap="RdYlGn"),use_container_width=True,height=350)

# ── TAB 2: RETENTION ──────────────────────────────────────────────────────────
with t2:
    st.markdown("### Retention Layer")
    st.markdown(f"<p style='color:{MUTED};font-size:12px'>Global Retention (GR) vs Primary Market Retention (PMR). Primary market determined from actual streaming data — not assumed to be home market.</p>", unsafe_allow_html=True)

    c1,c2 = st.columns(2)

    with c1:
        asset_counts=ret["asset_class"].value_counts().reset_index()
        asset_counts.columns=["Class","Count"]
        colours={"Unicorn Fortress":GOLD,"Stable Hub":"#34d399","Commercial Corridor":"#5ba8f5","Viral Spike":"#ff4444"}
        fig3=px.pie(asset_counts,names="Class",values="Count",title="Asset Classification",color="Class",color_discrete_map=colours,hole=0.4)
        fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)",font_color=TEXT,height=320,legend=dict(font_color=MUTED))
        st.plotly_chart(fig3, use_container_width=True)

    with c2:
        fig4=px.scatter(ret,x="global_retention",y="primary_retention",
                        color="asset_class",hover_name="track_title",
                        color_discrete_map=colours,
                        title="GR vs PMR by Track",
                        labels={"global_retention":"Global Retention","primary_retention":"Primary Market Retention"})
        fig4.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color=TEXT,height=320,legend=dict(font_color=MUTED))
        fig4.update_xaxes(gridcolor="#1e1e28",tickfont_color=MUTED)
        fig4.update_yaxes(gridcolor="#1e1e28",tickfont_color=MUTED)
        fig4.add_hline(y=0.5,line_dash="dash",line_color="#1e1e28")
        fig4.add_vline(x=0.5,line_dash="dash",line_color="#1e1e28")
        st.plotly_chart(fig4, use_container_width=True)

    pm_diff = ret[~ret["primary_is_home"]][["track_title","home_market","primary_market","global_retention","primary_retention","asset_class"]]
    if not pm_diff.empty:
        st.markdown(f"**{len(pm_diff)} tracks** where primary market ≠ home market:")
        st.dataframe(pm_diff, use_container_width=True, hide_index=True)

# ── TAB 3: STATEMENTS ─────────────────────────────────────────────────────────
with t3:
    st.markdown("### Statement Reconciliation")
    st.markdown(f"<p style='color:{MUTED};font-size:12px'>Royalty waterfall: gross receipts → distributor commission → net receipts → participation rate → reserve → recoupment → payable.</p>", unsafe_allow_html=True)

    # Waterfall
    total_gross=stmt["gross_receipts"].sum(); total_net=stmt["net_receipts"].sum()
    total_mech=stmt["mech_deduction"].sum(); total_roy=stmt["gross_royalty"].sum()
    total_res=stmt["reserve_held"].sum(); total_rec=stmt["recouped_this_period"].sum()
    total_pay=stmt["payable_usd"].sum()

    fig5=go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute","relative","relative","relative","relative","relative","total"],
        x=["Gross Receipts","Distributor (18%)","Mechanical","Reserve","Recoupment","","Payable"],
        y=[total_gross, -(total_gross-total_net), -total_mech, -total_res, -total_rec, 0, 0],
        connector={"line":{"color":"#1e1e28"}},
        decreasing={"marker":{"color":"#ff4444"}},
        increasing={"marker":{"color":"#34d399"}},
        totals={"marker":{"color":GOLD}},
        text=[f"${v:,.0f}" for v in [total_gross,-(total_gross-total_net),-total_mech,-total_res,-total_rec,0,total_pay]],
        textposition="outside",
    ))
    fig5.update_layout(title="Royalty Waterfall — Full Catalogue",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color=TEXT,height=380,showlegend=False,margin=dict(t=40,b=20))
    fig5.update_xaxes(tickfont_color=MUTED); fig5.update_yaxes(gridcolor="#1e1e28",tickfont_color=MUTED)
    st.plotly_chart(fig5, use_container_width=True)

    c1,c2=st.columns(2)
    with c1:
        latest=stmt[stmt["reporting_period"]==stmt["reporting_period"].max()]
        top10=latest.groupby("artist")["payable_usd"].sum().nlargest(10).reset_index()
        fig6=px.bar(top10,x="payable_usd",y="artist",orientation="h",title="Top 10 Artists by Payable (Latest Period)",color_discrete_sequence=[GOLD])
        fig6.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color=TEXT,height=350,margin=dict(t=40,l=160))
        fig6.update_xaxes(gridcolor="#1e1e28",tickfont_color=MUTED); fig6.update_yaxes(tickfont_color=MUTED)
        st.plotly_chart(fig6, use_container_width=True)

    with c2:
        fully_rec=stmt[(stmt["recouped_this_period"]>0)&(stmt["unrecouped_balance"]==0)].drop_duplicates("contract_id")
        still_unrec=stmt[stmt["unrecouped_balance"]>0].drop_duplicates("contract_id")
        st.markdown(f"**Recoupment Status**")
        st.markdown(f"✅ **{len(fully_rec)}** contracts fully recouped this cycle")
        st.markdown(f"⏳ **{len(still_unrec)}** contracts still unrecouped — outstanding: **${still_unrec['unrecouped_balance'].sum():,.0f}**")
        if not fully_rec.empty:
            st.dataframe(fully_rec[["artist","contract_id","recouped_this_period"]].rename(columns={"recouped_this_period":"Recouped ($)"}), use_container_width=True, hide_index=True, height=200)

# ── TAB 4: LEAKAGE ────────────────────────────────────────────────────────────
with t4:
    st.markdown("### Valuation Leakage Estimator")
    st.markdown(f"<p style='color:{MUTED};font-size:12px'>Three sources of value loss: data integrity gaps, retention decay, and structural rate gaps (VFG). Combined into a single Audit Score per track.</p>", unsafe_allow_html=True)

    tl=leak["total_leakage_usd"].sum()
    il=leak["revenue_at_risk_usd"].sum()
    rl=leak["retention_leakage_usd"].sum()
    sl=leak["structural_leakage_usd"].sum()

    fig7=go.Figure(go.Pie(
        labels=["Data Integrity","Retention Decay","Structural Rate Gap"],
        values=[il,rl,sl],
        hole=0.5,
        marker_colors=["#ff8c42","#ff4444",GOLD],
        textfont_color=TEXT,
    ))
    fig7.update_layout(
        title=f"Leakage by Source — Total ${tl:,.0f}/yr",
        paper_bgcolor="rgba(0,0,0,0)",font_color=TEXT,
        annotations=[dict(text=f"{tl/(leak['annual_potential_usd'].sum()+tl)*100:.1f}%<br>undervalued",x=0.5,y=0.5,font_size=16,font_color=GOLD,showarrow=False)],
        height=380,legend=dict(font_color=MUTED)
    )
    st.plotly_chart(fig7, use_container_width=True)

    c1,c2=st.columns(2)
    with c1:
        market_leak=leak.groupby("home_market")["total_leakage_usd"].sum().reset_index()
        market_leak.columns=["Market","Leakage"]
        market_leak["colour"]=market_leak["Market"].map(MC)
        fig8=px.bar(market_leak,x="Market",y="Leakage",title="Annual Leakage by Market",color="Market",color_discrete_map=MC)
        fig8.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color=TEXT,showlegend=False,height=300,margin=dict(t=40,b=20))
        fig8.update_xaxes(tickfont_color=MUTED); fig8.update_yaxes(gridcolor="#1e1e28",tickfont_color=MUTED)
        st.plotly_chart(fig8, use_container_width=True)

    with c2:
        fig9=px.scatter(leak,x="audit_score",y="total_leakage_usd",color="home_market",hover_name="track_title",
                        color_discrete_map=MC,title="Audit Score vs Total Leakage",
                        labels={"audit_score":"Audit Score","total_leakage_usd":"Total Leakage ($/yr)"})
        fig9.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color=TEXT,height=300,legend=dict(font_color=MUTED),margin=dict(t=40,b=20))
        fig9.update_xaxes(gridcolor="#1e1e28",tickfont_color=MUTED); fig9.update_yaxes(gridcolor="#1e1e28",tickfont_color=MUTED)
        st.plotly_chart(fig9, use_container_width=True)

    st.markdown("**Full Audit Score by Track**")
    display_leak=leak[["track_title","home_market","audit_score","verdict","total_leakage_usd","revenue_at_risk_usd","retention_leakage_usd","structural_leakage_usd","vfg_score"]].copy()
    display_leak.columns=["Track","Market","Audit Score","Verdict","Total Leakage","Integrity $","Retention $","Rate Gap $","VFG"]
    st.dataframe(display_leak.style.background_gradient(subset=["Audit Score"],cmap="RdYlGn"),use_container_width=True,height=350)

    # Download button
    csv_out=leak.to_csv(index=False)
    st.download_button("⬇  Download Full Audit Report (CSV)",data=csv_out,file_name="hipstarr_audit_report.csv",mime="text/csv")
