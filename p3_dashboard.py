"""
Hipstarr Catalogue Audit Engine — Dashboard
============================================
Narrative-first design. Plain language throughout.
Every number explains itself. Every tab tells one chapter of the story.

Run: streamlit run p3_dashboard.py
Author : Ekene Ahuche · Hipstarr Music Research · Lagos 2026
"""

import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(
    page_title="Hipstarr Catalogue Audit Engine",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"]{background:#070709}
[data-testid="stSidebar"]{background:#0e0e12;border-right:1px solid #1e1e28}
h1,h2,h3,h4,p,li,span{color:#f0eef8}
.story-banner{background:#0e0e12;border-left:3px solid #d4af37;border-radius:0 8px 8px 0;padding:16px 20px;margin-bottom:24px}
.story-headline{font-size:15px;font-weight:700;color:#f0eef8;margin-bottom:4px}
.story-body{font-size:12px;color:#8a8a9e;line-height:1.6}
.insight-card{background:#0e0e12;border:1px solid #1e1e28;border-radius:10px;padding:20px 22px;margin-bottom:12px}
.insight-number{font-size:32px;font-weight:800;color:#d4af37;font-family:monospace;margin-bottom:4px}
.insight-label{font-size:13px;color:#f0eef8;font-weight:600;margin-bottom:4px}
.insight-explain{font-size:11px;color:#8a8a9e;line-height:1.5}
.flag-row{display:flex;align-items:flex-start;gap:12px;padding:12px 0;border-bottom:1px solid #1e1e28}
.verdict-healthy{color:#34d399;font-weight:700}
.verdict-attention{color:#f0c040;font-weight:700}
.verdict-risk{color:#ff8c42;font-weight:700}
.verdict-critical{color:#ff4444;font-weight:700}
</style>
""", unsafe_allow_html=True)

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
PERIOD_ORDER    = ["2024-Q3","2024-Q4","2025-Q1","2025-Q2","2025-Q3","2025-Q4","2026-Q1"]
DIST_COMMISSION = 0.18
US_BENCHMARK    = 0.004
MARKET_RATES    = {"NG":0.0004,"ZA":0.0015,"BR":0.0018,"MX":0.0022,"IN":0.0006,"SA":0.0025}
VALID_RE        = r"^\d{4}-Q[1-4]$"
MARKET_NAMES    = {"NG":"Nigeria","ZA":"South Africa","BR":"Brazil","MX":"Mexico","IN":"India","SA":"Saudi Arabia"}

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
    df=df.copy()
    df["streams"]=pd.to_numeric(df.get("streams",0),errors="coerce").fillna(0).astype(int)
    df["revenue_usd"]=pd.to_numeric(df.get("revenue_usd",0),errors="coerce").fillna(0.0)
    for c in ["isrc","upc","territory","label","artist","reporting_period"]:
        if c in df.columns: df[c]=df[c].fillna("").str.strip()
    return df

def run_flags(df):
    flags=[]
    dup_idx=set(df[df.duplicated(subset=["isrc","dsp","territory","reporting_period","streams"],keep="first")].index)
    canonical={"Wizkid ft. Tems","Burna Boy","Peso Pluma ft. Raul Vega"}
    known={"wizkid","wizkid ft tems","burna boy","burnaboy","peso pluma","peso pluma & raul vega"}
    PLAIN={
        "INT-001":"Track ID (ISRC) missing — can't match to contract or split royalties",
        "INT-002":"Release code (UPC) missing — bundle matching will fail",
        "INT-003":"Country missing — revenue can't be allocated to any territory",
        "INT-004":"Streams recorded but £0 revenue — DSP reporting error, money not received",
        "INT-005":"Artist name inconsistent — won't match against contract database",
        "INT-006":"Date format wrong — won't map to correct accounting period",
        "INT-007":"Duplicate row — same revenue counted twice",
        "INT-008":"Label name missing — needed for publishing/masters royalty split",
    }
    for idx,row in df.iterrows():
        isrc=row.get("isrc",""); title=row.get("track_title",""); rev=row.get("revenue_usd",0); strms=row.get("streams",0)
        def f(rid,sev,rat): flags.append({"row_index":idx,"isrc":isrc,"track_title":title,"rule_id":rid,"severity":sev,"plain_english":PLAIN.get(rid,""),"revenue_at_risk":round(rat,4)})
        if not isrc: f("INT-001","CRITICAL",rev)
        if not row.get("territory",""): f("INT-003","CRITICAL",rev)
        if strms>0 and rev==0: f("INT-004","HIGH",0)
        if not row.get("upc",""): f("INT-002","HIGH",rev)
        al=row.get("artist","").lower().replace("ft.","ft").replace(",","")
        if any(v in al for v in known) and row.get("artist","") not in canonical: f("INT-005","MEDIUM",rev)
        period=row.get("reporting_period","")
        if period and not pd.Series([period]).str.match(VALID_RE).iloc[0]: f("INT-006","MEDIUM",rev)
        if idx in dup_idx: f("INT-007","HIGH",rev)
        if not row.get("label",""): f("INT-008","LOW",rev)
    return pd.DataFrame(flags) if flags else pd.DataFrame(columns=["row_index","isrc","track_title","rule_id","severity","plain_english","revenue_at_risk"])

def score_tracks(df,flags):
    results=[]
    for (isrc,title,market),grp in df.groupby(["isrc","track_title","home_market"]):
        n=len(grp); tf=flags[flags["isrc"]==isrc] if isrc and len(flags)>0 else pd.DataFrame()
        def cf(r): return (tf["rule_id"]==r).sum() if not tf.empty else 0
        c=max(0,round(100-cf("INT-001")/n*40-cf("INT-002")/n*20-cf("INT-008")/n*10-cf("INT-005")/n*15,1))
        t=max(0,round(100-cf("INT-003")/n*40-cf("INT-004")/n*30-cf("INT-007")/n*20,1))
        uv=grp[grp["reporting_period"].str.match(VALID_RE)]["reporting_period"].nunique()
        r=max(0,round(100-cf("INT-006")/n*30-max(0,7-uv)/7*20,1))
        overall=round(c*0.35+t*0.45+r*0.20,1)
        readiness="Ready to pay out" if overall>=90 else "Minor fixes needed" if overall>=75 else "Needs correction before paying" if overall>=55 else "On hold — do not pay yet"
        fc=tf["severity"].value_counts().to_dict() if not tf.empty else {}
        results.append({"isrc":isrc,"track_title":title,"home_market":MARKET_NAMES.get(market,market),"data_score":overall,"payment_status":readiness,"completeness":c,"traceability":t,"reporting":r,"total_revenue_usd":round(grp["revenue_usd"].sum(),2),"revenue_held_back":round(tf["revenue_at_risk"].sum() if not tf.empty else 0,2),"🔴 Blocking":fc.get("CRITICAL",0),"🟠 Serious":fc.get("HIGH",0),"🟡 Minor":fc.get("MEDIUM",0),"⚪ Info":fc.get("LOW",0)})
    return pd.DataFrame(results)

def build_mrc(df,flags):
    excl=set()
    if len(flags)>0:
        excl=set(flags[flags["severity"]=="CRITICAL"]["row_index"])|set(flags[flags["rule_id"]=="INT-007"]["row_index"])
    return df[~df.index.isin(excl)].copy().reset_index(drop=True)

def calc_retention(series):
    series=series.reindex(PERIOD_ORDER,fill_value=0)
    peak=series.max()
    if peak==0: return {"peak_revenue":0,"latest_revenue":0,"retention":0,"trend":"no earnings data"}
    lp=[p for p in reversed(PERIOD_ORDER) if series[p]>0]
    lr=series[lp[0]] if lp else 0
    ret=round(lr/peak,4)
    recent=series[series>0].tail(2)
    if len(recent)<2: trend="not enough data"
    else:
        chg=(recent.iloc[-1]-recent.iloc[-2])/max(recent.iloc[-2],0.0001)
        trend="growing 📈" if chg>0.08 else "holding steady ✓" if chg>-0.10 else "declining ↘" if chg>-0.30 else "dropped significantly ↓"
    return {"peak_revenue":round(peak,2),"latest_revenue":round(lr,2),"retention":ret,"trend":trend}

def classify(gr,pmr):
    if gr>=0.75 and pmr>=0.70: return "🏰 Evergreen Asset"
    elif gr>=0.55 and pmr>=0.50: return "📦 Solid Catalogue"
    elif gr>=0.30 and pmr>=0.30: return "📉 Fading — Still Earning"
    else: return "⚡ One-Time Spike"

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
        pm_label=MARKET_NAMES.get(pm,pm)
        home_label=MARKET_NAMES.get(market,market)
        rows.append({
            "isrc":isrc,"track_title":title,"home_market":home_label,
            "biggest_streaming_market":pm_label,
            "same_as_home":"Yes" if pm==market else f"No — it's {pm_label}",
            "earnings_at_peak":f"${gr['peak_revenue']:,.0f}",
            "earnings_now":f"${gr['latest_revenue']:,.0f}",
            "still_earning_pct":f"{gr['retention']*100:.0f}% of peak",
            "trend":gr["trend"],
            "global_retention":gr["retention"],
            "primary_retention":pmr["retention"],
            "asset_type":classify(gr["retention"],pmr["retention"]),
        })
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
    ret["retention_leakage_usd"]=((ret["global_retention"].apply(lambda x: 1-x)*ret["global_retention"].apply(lambda x: x)*4*100)).clip(lower=0)
    # Simpler: peak gap × 4 quarters
    df_clean2=df_clean.copy()
    df_clean2["streams"]=pd.to_numeric(df_clean2["streams"],errors="coerce").fillna(0)
    df_clean2["revenue_usd"]=pd.to_numeric(df_clean2["revenue_usd"],errors="coerce").fillna(0)
    peak_rev=df_clean2[df_clean2["reporting_period"].isin(PERIOD_ORDER)].groupby(["isrc","reporting_period"])["revenue_usd"].sum().groupby("isrc").max()
    latest_rev=df_clean2[df_clean2["reporting_period"]==PERIOD_ORDER[-1]].groupby("isrc")["revenue_usd"].sum()
    gap=(peak_rev-latest_rev).clip(lower=0)*4
    ret["retention_leakage_usd"]=ret["isrc"].map(gap).fillna(0).round(2)
    home=df_clean2.groupby(["isrc","home_market","territory"])["streams"].sum().reset_index()
    home=home[home["territory"]==home["home_market"]].copy()
    home["home_rate"]=home["home_market"].map(MARKET_RATES).fillna(0.002)
    home["rate_gap"]=(US_BENCHMARK-home["home_rate"]).clip(lower=0)
    home["structural_leakage_usd"]=(home["streams"]/7*home["rate_gap"]*4).round(2)
    home["vfg_score"]=(home["rate_gap"]/US_BENCHMARK*100).round(2)
    int_scores=scores[["isrc","revenue_held_back","data_score"]].rename(columns={"revenue_held_back":"integrity_leakage","data_score":"integrity_score"})
    m=ret.merge(int_scores,on="isrc",how="left")
    m=m.merge(home[["isrc","home_rate","vfg_score","structural_leakage_usd"]],on="isrc",how="left")
    m["integrity_leakage"]=m["integrity_leakage"].fillna(0)
    m["structural_leakage_usd"]=m["structural_leakage_usd"].fillna(0)
    m["integrity_score"]=m["integrity_score"].fillna(100)
    m["total_leakage_usd"]=(m["integrity_leakage"]+m["retention_leakage_usd"]+m["structural_leakage_usd"]).round(2)
    annual_potential=peak_rev*4
    m["annual_potential_usd"]=m["isrc"].map(annual_potential).fillna(0)
    m["leakage_pct"]=(m["total_leakage_usd"]/(m["annual_potential_usd"]+m["total_leakage_usd"]).replace(0,np.nan)*100).fillna(0).round(1)
    rate_score=(1-m["vfg_score"].fillna(0)/100)*100
    m["audit_score"]=(m["integrity_score"]*0.40+m["global_retention"]*100*0.35+rate_score*0.25).round(1)
    def verdict(s):
        if s>=80: return "✅ Healthy"
        elif s>=65: return "⚠️ Needs Attention"
        elif s>=50: return "🔶 At Risk"
        else: return "🔴 Critical"
    m["health"]=m["audit_score"].apply(verdict)
    return m

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h3 style='color:#d4af37;font-family:monospace;letter-spacing:3px'>HIPSTARR</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color:#8a8a9e;font-size:11px;margin-top:-12px'>CATALOGUE AUDIT ENGINE</p>", unsafe_allow_html=True)
    st.markdown("---")
    uploaded=st.file_uploader("Upload your distributor CSV", type=["csv"], help="The raw revenue file from your distributor — Spotify, Apple Music, or any DSP report.")
    st.markdown("---")
    use_sample=st.button("▶  See it in action (sample data)", use_container_width=True)
    st.markdown("---")
    st.markdown("""
    <p style='color:#555568;font-size:10px'>
    Upload any distributor revenue CSV.<br>
    The engine will find every problem,<br>
    calculate what artists are owed,<br>
    and show where money is being lost.<br><br>
    <a href='https://substack.com/@ekenemike' style='color:#d4af37'>substack.com/@ekenemike</a><br>
    <a href='https://hipstarr-p3.streamlit.app' style='color:#d4af37'>hipstarr-p3.streamlit.app</a>
    </p>
    """, unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style='border-top:2px solid;border-image:linear-gradient(90deg,#ff6b35,#d4af37,#5ba8f5) 1;padding-top:16px;margin-bottom:8px'>
<span style='font-family:monospace;font-size:11px;color:#d4af37;letter-spacing:4px'>HIPSTARR MUSIC RESEARCH</span><br>
<span style='font-size:26px;font-weight:800;color:#f0eef8'>Catalogue Audit Engine</span><br>
<span style='font-size:13px;color:#8a8a9e'>Upload a distributor revenue file and find out: what's wrong with the data, which tracks are still earning, what each artist gets paid, and where money is being lost.</span>
</div>
""", unsafe_allow_html=True)

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
df_raw=None
if uploaded:
    df_raw=pd.read_csv(uploaded,dtype=str)
    st.success(f"File loaded — {len(df_raw):,} rows across {df_raw.get('track_title',pd.Series()).nunique() if 'track_title' in df_raw.columns else '?'} tracks")
elif use_sample:
    sample=os.path.join(os.path.dirname(__file__),"p3_catalogue_raw.csv")
    if os.path.exists(sample):
        df_raw=pd.read_csv(sample,dtype=str)
        st.info("Running on sample data — 42 tracks across Nigeria, South Africa, Brazil, Mexico, India and Saudi Arabia")

if df_raw is None:
    st.markdown("""
    <div style='background:#0e0e12;border:1px solid #1e1e28;border-radius:10px;padding:48px;text-align:center;margin-top:32px'>
    <p style='font-size:16px;color:#f0eef8;font-weight:600;margin-bottom:8px'>Upload a distributor CSV or click the button in the sidebar to see a demo</p>
    <p style='font-size:12px;color:#555568;font-family:monospace'>Expected columns: isrc · upc · track_title · artist · label · home_market · dsp · territory · reporting_period · streams · revenue_usd</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── RUN PIPELINE ──────────────────────────────────────────────────────────────
with st.spinner("Analysing your catalogue..."):
    df=load_raw(df_raw)
    flags=run_flags(df)
    scores=score_tracks(df,flags)
    mrc=build_mrc(df,flags)
    ret=score_retention(df)
    clean_path=os.path.join(os.path.dirname(__file__),"p3_catalogue_clean.csv")
    df_clean=load_raw(pd.read_csv(clean_path,dtype=str)) if os.path.exists(clean_path) else df
    stmt=reconcile(mrc,contracts_df)
    leak=calc_leakage(scores,ret,df_clean)

# ── TOP STORY STRIP ───────────────────────────────────────────────────────────
tl=leak["total_leakage_usd"].sum(); tp=leak["annual_potential_usd"].sum()
lpct=tl/(tp+tl)*100 if (tp+tl)>0 else 0
crit=(flags["severity"]=="CRITICAL").sum() if len(flags)>0 else 0
blocked=len(df)-len(mrc)
payable=stmt["payable_usd"].sum()

st.markdown(f"""
<div style='background:#0e0e12;border:1px solid #1e1e28;border-radius:10px;padding:24px 28px;margin-bottom:8px'>
<p style='font-family:monospace;font-size:10px;color:#8a8a9e;letter-spacing:3px;margin-bottom:8px'>THE HEADLINE</p>
<p style='font-size:17px;color:#f0eef8;font-weight:600;line-height:1.6;margin:0'>
This catalogue has <span style='color:#ff6b35;font-weight:800'>{crit:,} blocking data problems</span> that stopped
<span style='color:#f0c040;font-weight:800'>{blocked:,} revenue rows</span> from being processed.
After fixing what could be fixed, <span style='color:#34d399;font-weight:800'>${payable:,.0f} is payable to artists</span> this cycle.
But the catalogue is still leaving <span style='color:#d4af37;font-weight:800'>{lpct:.0f}% of its potential value</span> on the table.
</p>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── TABS ──────────────────────────────────────────────────────────────────────
t1,t2,t3,t4 = st.tabs([
    "📋 What's Wrong With the Data",
    "📈 Which Tracks Are Still Earning",
    "💰 What Artists Get Paid",
    "🕳️ Where the Money Goes Missing"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: DATA INTEGRITY
# ══════════════════════════════════════════════════════════════════════════════
with t1:
    st.markdown("""
    <div class='story-banner'>
    <div class='story-headline'>Every row in a distributor file needs to be clean before money can move.</div>
    <div class='story-body'>
    A track without a proper ID (ISRC) can't be matched to a contract. Revenue without a country can't be allocated.
    Duplicate rows mean an artist gets charged twice. This tab shows every problem we found — and how much money is stuck because of it.
    </div>
    </div>
    """, unsafe_allow_html=True)

    if len(flags)>0:
        rev_at_risk=flags["revenue_at_risk"].sum()
        critical_count=(flags["severity"]=="CRITICAL").sum()
        high_count=(flags["severity"]=="HIGH").sum()

        c1,c2,c3,c4=st.columns(4)
        with c1:
            st.markdown(f"""<div class='insight-card'>
            <div class='insight-number' style='color:#ff4444'>{critical_count:,}</div>
            <div class='insight-label'>Blocking Problems</div>
            <div class='insight-explain'>These stop revenue from being paid out entirely. Must be fixed before any payment can happen.</div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class='insight-card'>
            <div class='insight-number' style='color:#ff8c42'>{high_count:,}</div>
            <div class='insight-label'>Serious Problems</div>
            <div class='insight-explain'>Don't block payment but cause incorrect amounts, duplicate entries, or DSP reporting errors.</div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class='insight-card'>
            <div class='insight-number' style='color:#f0c040'>${rev_at_risk:,.0f}</div>
            <div class='insight-label'>Revenue Held Back</div>
            <div class='insight-explain'>Money that arrived from DSPs but can't be paid to artists until the data problems above are resolved.</div>
            </div>""", unsafe_allow_html=True)
        with c4:
            submission_pct=len(mrc)/len(df)*100
            st.markdown(f"""<div class='insight-card'>
            <div class='insight-number' style='color:#34d399'>{submission_pct:.0f}%</div>
            <div class='insight-label'>Cleared for Payment</div>
            <div class='insight-explain'>{len(mrc):,} of {len(df):,} rows passed all checks and are ready to submit to the royalty processor.</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**What exactly is wrong — in plain terms:**")

        problem_summary=flags.groupby(["rule_id","plain_english","severity"]).agg(
            occurrences=("row_index","count"),
            revenue_at_risk=("revenue_at_risk","sum")
        ).reset_index().sort_values("revenue_at_risk",ascending=False)

        for _,row in problem_summary.iterrows():
            sev_colour="#ff4444" if row["severity"]=="CRITICAL" else "#ff8c42" if row["severity"]=="HIGH" else "#f0c040" if row["severity"]=="MEDIUM" else "#8a8a9e"
            st.markdown(f"""
            <div style='display:flex;align-items:flex-start;gap:14px;padding:12px 0;border-bottom:1px solid #1e1e28'>
            <div style='min-width:80px;font-family:monospace;font-size:10px;color:{sev_colour};padding-top:2px'>{row["severity"]}</div>
            <div style='flex:1'>
                <div style='font-size:13px;color:#f0eef8;font-weight:600;margin-bottom:3px'>{row["plain_english"]}</div>
                <div style='font-family:monospace;font-size:10px;color:#555568'>{row["occurrences"]:,} rows affected · ${row["revenue_at_risk"]:,.2f} at risk</div>
            </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Track-by-track breakdown**")
    st.caption("Data Score = how clean is this track's data on a scale of 0–100. Payment Status = what happens next.")
    display=scores[["track_title","home_market","data_score","payment_status","revenue_held_back","🔴 Blocking","🟠 Serious","🟡 Minor"]].copy()
    display.columns=["Track","Market","Data Score","Payment Status","Revenue Held Back ($)","🔴 Blocking","🟠 Serious","🟡 Minor"]
    st.dataframe(display.sort_values("Data Score"),use_container_width=True,height=350,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: RETENTION
# ══════════════════════════════════════════════════════════════════════════════
with t2:
    st.markdown("""
    <div class='story-banner'>
    <div class='story-headline'>Not all tracks age the same way.</div>
    <div class='story-body'>
    Some tracks peak and disappear in weeks. Others keep earning for years.
    This tab shows how much of each track's peak earnings it's still generating today — and which territory is actually driving those streams
    (which isn't always the artist's home country).
    </div>
    </div>
    """, unsafe_allow_html=True)

    asset_counts=ret["asset_type"].value_counts()
    c1,c2,c3,c4=st.columns(4)
    for col,(label,emoji) in zip([c1,c2,c3,c4],[("🏰 Evergreen Asset","#d4af37"),("📦 Solid Catalogue","#34d399"),("📉 Fading — Still Earning","#5ba8f5"),("⚡ One-Time Spike","#ff4444")]):
        count=asset_counts.get(label,0)
        explain={"🏰 Evergreen Asset":"Still earning 75%+ of peak. Long-term value. These are your crown jewels.","📦 Solid Catalogue":"Holding well at 55–75% of peak. Reliable earners.","📉 Fading — Still Earning":"Down to 30–55% of peak. Declining but still contributing.","⚡ One-Time Spike":"Below 30% of peak. Viral moment has passed."}
        with col:
            st.markdown(f"""<div class='insight-card'>
            <div class='insight-number' style='color:{emoji.split("(")[0] if "(" not in emoji else "#f0eef8"}'>{count}</div>
            <div class='insight-label'>{label}</div>
            <div class='insight-explain'>{explain.get(label,"")}</div>
            </div>""", unsafe_allow_html=True)

    pm_diff=ret[ret["same_as_home"]!="Yes"]
    if not pm_diff.empty:
        st.markdown("---")
        st.markdown(f"**{len(pm_diff)} tracks whose biggest audience isn't in their home country**")
        st.caption("This matters because it changes who you prioritise for marketing, syncs, and live touring.")
        st.dataframe(
            pm_diff[["track_title","home_market","biggest_streaming_market","still_earning_pct","trend"]].rename(columns={"track_title":"Track","home_market":"Home Country","biggest_streaming_market":"Biggest Market","still_earning_pct":"Still Earning","trend":"Trend"}),
            use_container_width=True, hide_index=True
        )

    st.markdown("---")
    st.markdown("**All 42 tracks — how they're holding up**")
    st.caption("'Still Earning' = current earnings as a % of this track's best-ever quarter.")
    display_ret=ret[["track_title","home_market","asset_type","earnings_at_peak","earnings_now","still_earning_pct","trend","biggest_streaming_market"]].copy()
    display_ret.columns=["Track","Home","Category","Peak Earnings/Qtr","Latest Earnings/Qtr","Still Earning","Trend","Biggest Market"]
    st.dataframe(display_ret.sort_values("Still Earning",ascending=False),use_container_width=True,height=400,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: STATEMENTS
# ══════════════════════════════════════════════════════════════════════════════
with t3:
    st.markdown("""
    <div class='story-banner'>
    <div class='story-headline'>Between the DSP and the artist, money passes through several hands.</div>
    <div class='story-body'>
    The distributor takes a cut. Publishing deductions come off the top for songwriters.
    The label holds a reserve against future corrections. Advances get repaid before cash goes out.
    What's left at the end is what the artist actually receives. This tab shows every step.
    </div>
    </div>
    """, unsafe_allow_html=True)

    tg=stmt["gross_receipts"].sum(); tn=stmt["net_receipts"].sum()
    tm=stmt["mech_deduction"].sum(); tr=stmt["reserve_held"].sum()
    trec=stmt["recouped_this_period"].sum(); tp=stmt["payable_usd"].sum()

    st.markdown("**The money journey — from DSP to artist**")
    waterfall_data={
        "Step":[
            "1. What came from DSPs",
            "2. After distributor takes 18%",
            "3. After publishing deductions",
            "4. After label reserve (held back)",
            "5. After repaying advances",
            "→ What artists actually receive"
        ],
        "Amount ($)":[tg, tg*(1-DIST_COMMISSION), tg*(1-DIST_COMMISSION)-tm, tg*(1-DIST_COMMISSION)-tm-tr, tg*(1-DIST_COMMISSION)-tm-tr-trec, tp]
    }
    wf=pd.DataFrame(waterfall_data)
    st.bar_chart(wf.set_index("Step"),color="#d4af37")

    c1,c2=st.columns([3,2])
    with c1:
        st.markdown("**Who gets paid what this period**")
        st.caption("Showing the most recent quarter only.")
        latest=stmt[stmt["reporting_period"]==stmt["reporting_period"].max()]
        artist_pay=latest.groupby("artist")["payable_usd"].sum().sort_values(ascending=False).reset_index()
        artist_pay.columns=["Artist","Gets Paid ($)"]
        artist_pay["Gets Paid ($)"]=artist_pay["Gets Paid ($)"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(artist_pay.head(15),use_container_width=True,hide_index=True,height=380)

    with c2:
        st.markdown("**Advance repayment tracker**")
        st.caption("Artists with outstanding advances receive royalties but don't get cash until the advance is repaid.")
        fully=stmt[(stmt["recouped_this_period"]>0)&(stmt["unrecouped_balance"]==0)].drop_duplicates("contract_id")
        still=stmt[stmt["unrecouped_balance"]>0].drop_duplicates("contract_id")
        st.metric("✅ Advances fully repaid this cycle", len(fully))
        st.metric("⏳ Still repaying advances", f"{len(still)} artists")
        if len(still)>0:
            st.caption(f"Total still outstanding: **${still['unrecouped_balance'].sum():,.0f}**")
            still_display=still[["artist","unrecouped_balance"]].rename(columns={"artist":"Artist","unrecouped_balance":"Still Owes ($)"}).head(10)
            st.dataframe(still_display,use_container_width=True,hide_index=True,height=250)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: LEAKAGE
# ══════════════════════════════════════════════════════════════════════════════
with t4:
    st.markdown("""
    <div class='story-banner'>
    <div class='story-headline'>This catalogue is earning less than it should. Here's exactly why.</div>
    <div class='story-body'>
    Three things drain value from a music catalogue: messy data that stops revenue being processed,
    tracks that have decayed below their earning potential, and structural rate gaps where
    home market streams are paid a fraction of what the same stream earns in the US.
    Together they explain why the catalogue is undervalued by 60%.
    </div>
    </div>
    """, unsafe_allow_html=True)

    tl=leak["total_leakage_usd"].sum()
    il=leak["integrity_leakage"].sum()
    rl=leak["retention_leakage_usd"].sum()
    sl=leak["structural_leakage_usd"].sum()

    c1,c2,c3=st.columns(3)
    with c1:
        st.markdown(f"""<div class='insight-card'>
        <div class='insight-number' style='color:#ff8c42'>${il:,.0f}</div>
        <div class='insight-label'>Lost to Data Problems</div>
        <div class='insight-explain'>Revenue that arrived from DSPs but couldn't be processed and paid out because of missing track IDs, unallocated territories, or other data errors. Fixable.</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class='insight-card'>
        <div class='insight-number' style='color:#ff4444'>${rl:,.0f}</div>
        <div class='insight-label'>Lost to Track Decay</div>
        <div class='insight-explain'>The gap between what these tracks earned at their peak and what they earn today, projected forward. One-time spikes have lost up to 85% of their peak earnings.</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class='insight-card'>
        <div class='insight-number' style='color:#d4af37'>${sl:,.0f}</div>
        <div class='insight-label'>Lost to Rate Gap</div>
        <div class='insight-explain'>Nigerian streams pay $0.0004. US streams pay $0.004. The same stream generates 10x more revenue depending on where the listener is. This is the structural gap — not fixable by the label alone.</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    c1,c2=st.columns(2)
    with c1:
        st.markdown("**Where each market loses the most**")
        market_leak=leak.groupby("home_market").agg(
            total_leakage=("total_leakage_usd","sum"),
            tracks=("isrc","count"),
            avg_health=("audit_score","mean")
        ).reset_index().sort_values("total_leakage",ascending=False)
        market_leak["total_leakage"]=market_leak["total_leakage"].round(0)
        market_leak["avg_health"]=market_leak["avg_health"].round(1)
        market_leak.columns=["Market","Total Lost ($)","Tracks","Avg Health Score"]
        st.dataframe(market_leak,use_container_width=True,hide_index=True)

    with c2:
        st.markdown("**Tracks with the lowest health scores**")
        st.caption("Health score combines data quality, how well the track is holding its earnings, and rate fairness.")
        bottom=leak.nsmallest(10,"audit_score")[["track_title","home_market","audit_score","health","total_leakage_usd"]].copy()
        bottom.columns=["Track","Market","Health Score","Status","Annual Loss ($)"]
        bottom["Annual Loss ($)"]=bottom["Annual Loss ($)"].apply(lambda x:f"${x:,.0f}")
        st.dataframe(bottom,use_container_width=True,hide_index=True)

    st.markdown("---")
    st.markdown("**Full catalogue health report**")
    full_display=leak[["track_title","home_market","audit_score","health","integrity_leakage","retention_leakage_usd","structural_leakage_usd","total_leakage_usd"]].copy()
    full_display.columns=["Track","Market","Health Score","Status","Data Loss ($)","Decay Loss ($)","Rate Gap Loss ($)","Total Annual Loss ($)"]
    st.dataframe(full_display.sort_values("Health Score",ascending=False),use_container_width=True,height=380,hide_index=True)

    st.download_button(
        "⬇  Download Full Audit Report",
        data=leak.to_csv(index=False),
        file_name="hipstarr_catalogue_audit.csv",
        mime="text/csv",
        help="Download the complete audit results as a CSV file"
    )
