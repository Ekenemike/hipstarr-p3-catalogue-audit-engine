"""
Hipstarr Catalogue Audit Engine — Dashboard
============================================
Streamlit dashboard using only native Streamlit charts.
No external chart library dependencies.

Run: streamlit run p3_dashboard.py

Author : Ekene Ahuche — Hipstarr Music Research
Project: P3 Catalogue Audit Engine · June 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import os
import sys

st.set_page_config(
    page_title="Hipstarr Catalogue Audit Engine",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

GOLD  = "#d4af37"
TEXT  = "#f0eef8"
MUTED = "#8a8a9e"
MC = {"NG":"#ff6b35","ZA":"#34d399","BR":"#f0c040","MX":"#b07ef8","IN":"#5ba8f5","SA":"#f47070"}

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#070709}
[data-testid="stSidebar"]{background:#0e0e12;border-right:1px solid #1e1e28}
h1,h2,h3,h4{color:#f0eef8}
.metric-card{background:#0e0e12;border:1px solid #1e1e28;border-radius:8px;padding:16px 20px;margin-bottom:8px}
.metric-val{font-size:26px;font-weight:700;color:#d4af37;font-family:monospace}
.metric-label{font-size:11px;color:#8a8a9e;letter-spacing:2px;text-transform:uppercase}
</style>
""", unsafe_allow_html=True)

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
PERIOD_ORDER    = ["2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1"]
DIST_COMMISSION = 0.18
US_BENCHMARK    = 0.004
MARKET_RATES    = {"NG":0.0004,"ZA":0.0015,"BR":0.0018,"MX":0.0022,"IN":0.0006,"SA":0.0025}
VALID_RE        = r"^\d{4}-Q[1-4]$"

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

# ── PIPELINE ──────────────────────────────────────────────────────────────────
def load_raw(df):
    df = df.copy()
    df["streams"]     = pd.to_numeric(df.get("streams",0),     errors="coerce").fillna(0).astype(int)
    df["revenue_usd"] = pd.to_numeric(df.get("revenue_usd",0), errors="coerce").fillna(0.0)
    for c in ["isrc","upc","territory","label","artist","reporting_period"]:
        if c in df.columns: df[c] = df[c].fillna("").str.strip()
    return df

def run_flags(df):
    flags=[]
    dup_idx=set(df[df.duplicated(subset=["isrc","dsp","territory","reporting_period","streams"],keep="first")].index)
    known={"wizkid","wizkid ft tems","burna boy","burnaboy","peso pluma","peso pluma & raul vega"}
    canonical={"Wizkid ft. Tems","Burna Boy","Peso Pluma ft. Raul Vega"}
    for idx,row in df.iterrows():
        isrc=row.get("isrc",""); title=row.get("track_title",""); rev=row.get("revenue_usd",0); strms=row.get("streams",0)
        def f(rid,sev,cat,desc,rat): flags.append({"row_index":idx,"isrc":isrc,"track_title":title,"rule_id":rid,"severity":sev,"category":cat,"description":desc,"revenue_at_risk":round(rat,4)})
        if isrc=="": f("INT-001","CRITICAL","Completeness","ISRC missing",rev)
        if row.get("territory","")=="\\" or row.get("territory","")=="": f("INT-003","CRITICAL","Traceability",f"Territory missing — ${rev:.2f} unallocated",rev)
        if strms>0 and rev==0: f("INT-004","HIGH","Traceability",f"Zero revenue for {strms:,} streams",0)
        if row.get("upc","")=="\\" or row.get("upc","")=="": f("INT-002","HIGH","Completeness","UPC missing",rev)
        al=row.get("artist","").lower().replace("ft.","ft").replace(",","")
        if any(v in al for v in known) and row.get("artist","") not in canonical: f("INT-005","MEDIUM","Completeness",f"Non-canonical artist: '{row.get('artist','')}'",rev)
        period=row.get("reporting_period","")
        if period!="" and not pd.Series([period]).str.match(VALID_RE).iloc[0]: f("INT-006","MEDIUM","Reporting",f"Bad period: '{period}'",rev)
        if idx in dup_idx: f("INT-007","HIGH","Traceability","Duplicate row",rev)
        if row.get("label","")=="\\" or row.get("label","")=="": f("INT-008","LOW","Completeness","Label missing",rev)
    return pd.DataFrame(flags) if flags else pd.DataFrame(columns=["row_index","isrc","track_title","rule_id","severity","category","description","revenue_at_risk"])

def score_tracks(df,flags):
    results=[]
    for (isrc,title,market),grp in df.groupby(["isrc","track_title","home_market"]):
        n=len(grp); tf=flags[flags["isrc"]==isrc] if isrc!="" and len(flags)>0 else pd.DataFrame()
        def cf(rule): return (tf["rule_id"]==rule).sum() if not tf.empty else 0
        c=max(0,round(100-cf("INT-001")/n*40-cf("INT-002")/n*20-cf("INT-008")/n*10-cf("INT-005")/n*15,1))
        t=max(0,round(100-cf("INT-003")/n*40-cf("INT-004")/n*30-cf("INT-007")/n*20,1))
        uv=grp[grp["reporting_period"].str.match(VALID_RE)]["reporting_period"].nunique()
        r=max(0,round(100-cf("INT-006")/n*30-max(0,7-uv)/7*20,1))
        overall=round(c*0.35+t*0.45+r*0.20,1)
        readiness="MRC-Ready" if overall>=90 else "Minor Review" if overall>=75 else "Needs Correction" if overall>=55 else "Hold"
        fc=tf["severity"].value_counts().to_dict() if not tf.empty else {}
        rev_risk=tf["revenue_at_risk"].sum() if not tf.empty else 0
        results.append({"isrc":isrc,"track_title":title,"home_market":market,"completeness_score":c,"traceability_score":t,"reporting_freq_score":r,"integrity_score":overall,"readiness":readiness,"total_revenue_usd":round(grp["revenue_usd"].sum(),2),"revenue_at_risk_usd":round(rev_risk,2),"flags_critical":fc.get("CRITICAL",0),"flags_high":fc.get("HIGH",0),"flags_medium":fc.get("MEDIUM",0),"flags_low":fc.get("LOW",0)})
    return pd.DataFrame(results)

def build_mrc(df,flags):
    excl=set()
    if len(flags)>0:
        excl=set(flags[flags["severity"]=="CRITICAL"]["row_index"])|set(flags[flags["rule_id"]=="INT-007"]["row_index"])
    return df[~df.index.isin(excl)].copy().reset_index(drop=True)

def calc_retention(series):
    series=series.reindex(PERIOD_ORDER,fill_value=0)
    peak=series.max()
    if peak==0: return {"peak_revenue":0,"latest_revenue":0,"retention":0,"trend":"no data"}
    lp=[p for p in reversed(PERIOD_ORDER) if series[p]>0]
    lr=series[lp[0]] if lp else 0
    ret=round(lr/peak,4)
    recent=series[series>0].tail(2)
    if len(recent)<2: trend="insufficient data"
    else:
        chg=(recent.iloc[-1]-recent.iloc[-2])/max(recent.iloc[-2],0.0001)
        trend="growing" if chg>0.08 else "stable" if chg>-0.10 else "declining" if chg>-0.30 else "collapsed"
    return {"peak_revenue":round(peak,2),"latest_revenue":round(lr,2),"retention":ret,"trend":trend}

def classify(gr,pmr):
    if gr>=0.75 and pmr>=0.70: return "Unicorn Fortress"
    elif gr>=0.55 and pmr>=0.50: return "Stable Hub"
    elif gr>=0.30 and pmr>=0.30: return "Commercial Corridor"
    else: return "Viral Spike"

def score_retention(df):
    df2=df[df["reporting_period"].isin(PERIOD_ORDER)].copy()
    rows=[]
    for (isrc,title,market),grp in df2.groupby(["isrc","track_title","home_market"]):
        gr_rev=grp.groupby("reporting_period")["revenue_usd"].sum()
        gr=calc_retention(gr_rev)
        terr=grp.groupby("territory")["streams"].sum()
        pm=terr.idxmax() if not terr.empty else market
        pm_grp=grp[grp["territory"]==pm]
        if pm_grp.empty: pm=market; pm_grp=grp[grp["territory"]==market]
        pmr=calc_retention(pm_grp.groupby("reporting_period")["revenue_usd"].sum())
        rows.append({"isrc":isrc,"track_title":title,"home_market":market,"primary_market":pm,"primary_is_home":pm==market,"total_revenue_usd":round(grp["revenue_usd"].sum(),2),"gr_peak_revenue":gr["peak_revenue"],"gr_latest_revenue":gr["latest_revenue"],"global_retention":gr["retention"],"global_trend":gr["trend"],"primary_retention":pmr["retention"],"primary_trend":pmr["trend"],"asset_class":classify(gr["retention"],pmr["retention"])})
    return pd.DataFrame(rows)

def reconcile(df_mrc,contracts):
    df=df_mrc.merge(contracts,on="isrc",how="left")
    df=df[~df["contract_id"].isna()].copy()
    df["net_receipts"]=df["revenue_usd"]*(1-DIST_COMMISSION)
    hp=df["contract_type"].str.contains("Publishing",na=False)
    df["mechanical_deduction"]=0.0
    df.loc[hp,"mechanical_deduction"]=df.loc[hp,"net_receipts"]*0.091
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
        if b>0: rt=min(b,nr); p=max(0,nr-b); bal[cid]=max(0,b-nr)
        else: rt=0; p=nr
        pay.append(round(p,2)); rec.append(round(rt,2))
    stmt["recouped_this_period"]=rec; stmt["payable_usd"]=pay
    stmt["unrecouped_balance"]=stmt["contract_id"].map(bal)
    return stmt.round(2)

def calc_leakage(scores,retention,df_clean):
    ret=retention.copy()
    ret["retention_leakage_usd"]=((ret["gr_peak_revenue"]-ret["gr_latest_revenue"]).clip(lower=0)*4).round(2)
    home=df_clean.groupby(["isrc","home_market","territory"])["streams"].sum().reset_index()
    home=home[home["territory"]==home["home_market"]].copy()
    home["home_rate"]=home["home_market"].map(MARKET_RATES).fillna(0.002)
    home["vfg_score"]=((US_BENCHMARK-home["home_rate"])/US_BENCHMARK*100).clip(lower=0).round(2)
    home["structural_leakage_usd"]=(home["streams"]/7*(US_BENCHMARK-home["home_rate"]).clip(lower=0)*4).round(2)
    m=ret.merge(scores[["isrc","revenue_at_risk_usd","integrity_score"]],on="isrc",how="left")
    m=m.merge(home[["isrc","home_rate","vfg_score","structural_leakage_usd"]],on="isrc",how="left")
    m["revenue_at_risk_usd"]=m["revenue_at_risk_usd"].fillna(0)
    m["structural_leakage_usd"]=m["structural_leakage_usd"].fillna(0)
    m["integrity_score"]=m["integrity_score"].fillna(100)
    m["total_leakage_usd"]=(m["revenue_at_risk_usd"]+m["retention_leakage_usd"]+m["structural_leakage_usd"]).round(2)
    m["annual_potential_usd"]=(m["gr_peak_revenue"]*4).round(2)
    m["leakage_pct"]=(m["total_leakage_usd"]/(m["annual_potential_usd"]+m["total_leakage_usd"]).replace(0,np.nan)*100).fillna(0).round(1)
    rate_score=(1-m["vfg_score"].fillna(0)/100)*100
    m["audit_score"]=(m["integrity_score"]*0.40+m["global_retention"]*100*0.35+rate_score*0.25).round(1)
    m["verdict"]=m["audit_score"].apply(lambda s:"Healthy" if s>=80 else "Attention" if s>=65 else "At Risk" if s>=50 else "Critical")
    return m

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"<h3 style='color:{GOLD};font-family:monospace;letter-spacing:3px'>HIPSTARR</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color:#8a8a9e;font-size:11px;margin-top:-12px'>CATALOGUE AUDIT ENGINE</p>", unsafe_allow_html=True)
    st.markdown("---")
    uploaded = st.file_uploader("Upload distributor CSV", type=["csv"])
    st.markdown("---")
    use_sample = st.button("▶  Run on Sample Data", use_container_width=True)
    st.markdown("---")
    st.markdown(f"<p style='color:#555568;font-size:10px'>Hipstarr Music Research<br>Lagos · 2026<br><a href='https://substack.com/@ekenemike' style='color:{GOLD}'>substack.com/@ekenemike</a></p>", unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style='border-top:2px solid;border-image:linear-gradient(90deg,#ff6b35,#d4af37,#5ba8f5) 1;padding-top:16px;margin-bottom:16px'>
<span style='font-family:monospace;font-size:11px;color:{GOLD};letter-spacing:4px'>HIPSTARR MUSIC RESEARCH</span><br>
<span style='font-size:24px;font-weight:800;color:{TEXT}'>Catalogue Audit Engine</span><br>
<span style='font-family:monospace;font-size:11px;color:{MUTED}'>Data Integrity · Retention · Statement Reconciliation · Valuation Leakage</span>
</div>
""", unsafe_allow_html=True)

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
df_raw = None
if uploaded:
    df_raw = pd.read_csv(uploaded, dtype=str)
    st.success(f"Loaded {len(df_raw):,} rows")
elif use_sample:
    sample = os.path.join(os.path.dirname(__file__), "p3_catalogue_raw.csv")
    if os.path.exists(sample):
        df_raw = pd.read_csv(sample, dtype=str)
        st.info(f"Sample dataset — {len(df_raw):,} rows · 42 tracks · 6 markets")
    else:
        st.error("p3_catalogue_raw.csv not found. Make sure it's in the same folder as p3_dashboard.py")

if df_raw is None:
    st.markdown(f"""
    <div style='background:#0e0e12;border:1px solid #1e1e28;border-radius:8px;padding:40px;text-align:center;margin-top:40px'>
    <p style='color:{MUTED};font-size:14px'>Upload a distributor CSV or click <b style='color:{GOLD}'>▶ Run on Sample Data</b></p>
    <p style='color:#333340;font-size:11px;font-family:monospace'>Expected: isrc · upc · track_title · artist · label · home_market · dsp · territory · reporting_period · streams · revenue_usd</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── RUN PIPELINE ──────────────────────────────────────────────────────────────
with st.spinner("Running audit pipeline..."):
    df      = load_raw(df_raw)
    flags   = run_flags(df)
    scores  = score_tracks(df, flags)
    mrc     = build_mrc(df, flags)
    ret     = score_retention(df)
    clean_path = os.path.join(os.path.dirname(__file__), "p3_catalogue_clean.csv")
    df_clean = load_raw(pd.read_csv(clean_path, dtype=str)) if os.path.exists(clean_path) else df
    stmt    = reconcile(mrc, contracts_df)
    leak    = calc_leakage(scores, ret, df_clean)

# ── KPI ROW ───────────────────────────────────────────────────────────────────
k1,k2,k3,k4,k5 = st.columns(5)
with k1:  st.metric("Raw Rows",          f"{len(df):,}")
with k2:  st.metric("Flags Detected",    f"{len(flags):,}")
with k3:  st.metric("Critical Flags",    f"{(flags['severity']=='CRITICAL').sum():,}" if len(flags)>0 else "0")
with k4:  st.metric("Total Payable",     f"${stmt['payable_usd'].sum():,.0f}")
with k5:
    tl=leak["total_leakage_usd"].sum(); tp=leak["annual_potential_usd"].sum()
    st.metric("Catalogue Undervalued",   f"{tl/(tp+tl)*100:.1f}%")

st.markdown("---")

# ── TABS ──────────────────────────────────────────────────────────────────────
t1,t2,t3,t4 = st.tabs(["🔍 Data Integrity","📈 Retention","💰 Statements","⚠️ Leakage"])

# ── TAB 1: DATA INTEGRITY ─────────────────────────────────────────────────────
with t1:
    st.markdown("### Data Integrity Layer")
    st.caption("Per-track scoring across Completeness, Traceability, and Reporting Frequency. CRITICAL flags block MRC submission.")

    if len(flags) > 0:
        c1,c2 = st.columns(2)
        with c1:
            st.markdown("**Flags by Severity**")
            sev_counts = flags["severity"].value_counts().reset_index()
            sev_counts.columns = ["Severity","Count"]
            st.bar_chart(sev_counts.set_index("Severity"), color="#d4af37")

        with c2:
            st.markdown("**Revenue at Risk by Rule**")
            rule_rev = flags.groupby("rule_id")["revenue_at_risk"].sum().reset_index()
            rule_rev.columns = ["Rule","Revenue at Risk ($)"]
            st.bar_chart(rule_rev.set_index("Rule"), color="#ff6b35")

    st.markdown(f"**{len(mrc):,}** rows cleared for MRC submission · **{len(df)-len(mrc):,}** blocked")

    st.markdown("**Track Integrity Scores**")
    display = scores[["track_title","home_market","integrity_score","readiness",
                       "completeness_score","traceability_score","reporting_freq_score",
                       "flags_critical","flags_high","revenue_at_risk_usd"]].copy()
    display.columns = ["Track","Market","Integrity","Readiness","Completeness",
                        "Traceability","Reporting","🔴 Crit","🟠 High","$ At Risk"]
    st.dataframe(display.sort_values("Integrity"), use_container_width=True, height=350, hide_index=True)

# ── TAB 2: RETENTION ──────────────────────────────────────────────────────────
with t2:
    st.markdown("### Retention Layer")
    st.caption("Global Retention (GR) and Primary Market Retention (PMR). Primary market from data — not assumed to be home market.")

    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**Asset Classification**")
        ac = ret["asset_class"].value_counts().reset_index()
        ac.columns = ["Class","Count"]
        st.bar_chart(ac.set_index("Class"), color="#d4af37")

    with c2:
        st.markdown("**Global Trend Breakdown**")
        gt = ret["global_trend"].value_counts().reset_index()
        gt.columns = ["Trend","Count"]
        st.bar_chart(gt.set_index("Trend"), color="#5ba8f5")

    pm_diff = ret[~ret["primary_is_home"]][["track_title","home_market","primary_market","global_retention","primary_retention","asset_class"]]
    if not pm_diff.empty:
        st.markdown(f"**{len(pm_diff)} tracks** where primary market ≠ home market")
        st.dataframe(pm_diff, use_container_width=True, hide_index=True)

    st.markdown("**Full Retention Scores**")
    ret_display = ret[["track_title","home_market","primary_market","global_retention",
                        "primary_retention","global_trend","asset_class"]].copy()
    ret_display.columns = ["Track","Home","Primary","GR","PMR","Trend","Class"]
    st.dataframe(ret_display.sort_values("GR",ascending=False), use_container_width=True, height=350, hide_index=True)

# ── TAB 3: STATEMENTS ─────────────────────────────────────────────────────────
with t3:
    st.markdown("### Statement Reconciliation")
    st.caption("Royalty waterfall: gross receipts → distributor cut → mechanical → reserve → recoupment → payable.")

    tg=stmt["gross_receipts"].sum(); tn=stmt["net_receipts"].sum()
    tm=stmt["mech_deduction"].sum(); tr=stmt["reserve_held"].sum()
    trec=stmt["recouped_this_period"].sum(); tp=stmt["payable_usd"].sum()

    st.markdown("**Royalty Waterfall**")
    waterfall = pd.DataFrame({
        "Step": ["Gross Receipts","After Distributor (18%)","After Mechanical","After Reserve","After Recoupment","Payable"],
        "Amount ($)": [tg, tg*(1-DIST_COMMISSION), tg*(1-DIST_COMMISSION)-tm, tg*(1-DIST_COMMISSION)-tm-tr, tg*(1-DIST_COMMISSION)-tm-tr-trec, tp]
    })
    st.bar_chart(waterfall.set_index("Step"), color="#34d399")

    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**Top 10 Artists by Payable (Latest Period)**")
        latest = stmt[stmt["reporting_period"]==stmt["reporting_period"].max()]
        top10  = latest.groupby("artist")["payable_usd"].sum().nlargest(10).reset_index()
        top10.columns = ["Artist","Payable ($)"]
        st.dataframe(top10, use_container_width=True, hide_index=True)

    with c2:
        st.markdown("**Recoupment Status**")
        fully = stmt[(stmt["recouped_this_period"]>0)&(stmt["unrecouped_balance"]==0)].drop_duplicates("contract_id")
        unrec = stmt[stmt["unrecouped_balance"]>0].drop_duplicates("contract_id")
        st.metric("Contracts fully recouped", len(fully))
        st.metric("Still unrecouped", f"{len(unrec)} (${unrec['unrecouped_balance'].sum():,.0f} outstanding)")
        if not fully.empty:
            st.dataframe(fully[["artist","contract_id"]].rename(columns={"artist":"Artist","contract_id":"Contract ID"}), use_container_width=True, hide_index=True, height=200)

# ── TAB 4: LEAKAGE ────────────────────────────────────────────────────────────
with t4:
    st.markdown("### Valuation Leakage Estimator")
    st.caption("Three sources: data integrity gaps, retention decay, structural rate gap (VFG). Combined into a single Audit Score per track.")

    tl=leak["total_leakage_usd"].sum()
    il=leak["revenue_at_risk_usd"].sum()
    rl=leak["retention_leakage_usd"].sum()
    sl=leak["structural_leakage_usd"].sum()

    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Data Integrity Leakage", f"${il:,.0f}", f"{il/tl*100:.1f}% of total")
    with c2: st.metric("Retention Leakage",       f"${rl:,.0f}", f"{rl/tl*100:.1f}% of total")
    with c3: st.metric("Rate Gap Leakage (VFG)",  f"${sl:,.0f}", f"{sl/tl*100:.1f}% of total")

    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**Leakage by Market**")
        ml = leak.groupby("home_market")["total_leakage_usd"].sum().reset_index()
        ml.columns = ["Market","Leakage ($)"]
        st.bar_chart(ml.set_index("Market"), color="#ff6b35")

    with c2:
        st.markdown("**Audit Verdict Breakdown**")
        vd = leak["verdict"].value_counts().reset_index()
        vd.columns = ["Verdict","Tracks"]
        st.bar_chart(vd.set_index("Verdict"), color="#d4af37")

    st.markdown("**Full Audit Report**")
    ld = leak[["track_title","home_market","audit_score","verdict","total_leakage_usd",
               "revenue_at_risk_usd","retention_leakage_usd","structural_leakage_usd","vfg_score"]].copy()
    ld.columns = ["Track","Market","Audit Score","Verdict","Total Leakage","Integrity $","Retention $","Rate Gap $","VFG"]
    st.dataframe(ld.sort_values("Audit Score",ascending=False), use_container_width=True, height=350, hide_index=True)

    st.download_button(
        "⬇  Download Full Audit Report (CSV)",
        data=leak.to_csv(index=False),
        file_name="hipstarr_audit_report.csv",
        mime="text/csv"
    )
