import streamlit as st
import pandas as pd
import plotly.express as px
import math
from pathlib import Path
from datetime import datetime

from optimizer import (
    TARGETS, FE_LOWER, FE_UPPER, get_default_chemistry,
    solve_blend_with_compensation, calculate_cost_breakdown,
    quality_checks, quality_table, redistribute_adjustment,
    what_if_analysis, compute_achieved
)

st.set_page_config(page_title="Sinter Burden Control", page_icon="🏭", layout="wide")

# ---------- INDUSTRIAL THEME ----------
st.markdown(r'''
<style>
.source-card{background:linear-gradient(145deg,#10242b,#0d1a21);border:1px solid #294b59;border-radius:10px;padding:.72rem .8rem;min-height:88px}
.source-status{font-weight:800;font-size:.74rem;letter-spacing:.05em;margin-bottom:.3rem}
.source-status.ok{color:#39d98a}
.source-status.info{color:#59aee8}
.source-name{font-size:.76rem;font-weight:700;color:#e7f2f7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

:root{--bg:#0b1015;--p:#121a21;--p2:#17232b;--l:#2a3a44;--t:#edf3f6;--m:#91a1ab;--s:#4f8fb8;--g:#35c47a;--a:#e6a63a;--r:#d95757;--o:#e47732}
html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif}
.stApp{background:radial-gradient(circle at 75% 0%,#24475b22,transparent 28%),var(--bg);color:var(--t)}
.block-container{max-width:1800px;padding:1rem 1.15rem 2.5rem}
[data-testid="stSidebar"]{background:#0e161c;border-right:1px solid #263740}
h1,h2,h3{color:var(--t)!important}.sub,.small{color:var(--m);font-size:.7rem}.eyebrow{color:#7194a7;font-size:.58rem;letter-spacing:.16em;font-weight:900}
.panel{background:linear-gradient(145deg,#141e25,#10171d);border:1px solid var(--l);border-radius:11px;padding:.9rem;margin-bottom:.25rem}
.panel-title{font-size:.6rem;font-weight:900;letter-spacing:.12em;color:#9eb2bd;text-transform:uppercase;margin-bottom:.6rem}
.hero{background:linear-gradient(110deg,#17242d,#111a21 65%,#18242b);border:1px solid #314651;border-radius:12px;padding:.8rem}
.kpi{border:1px solid var(--l);border-radius:10px;padding:.7rem;min-height:88px;background:#121b22}
.kpi-label{font-size:.55rem;letter-spacing:.12em;font-weight:900;color:#82949f}.kpi-value{font-size:1.15rem;font-weight:900;margin-top:.2rem}.kpi-sub{font-size:.58rem;color:#778a95}
.kpi-s{border-left:3px solid var(--s)}.kpi-g{border-left:3px solid var(--g)}.kpi-a{border-left:3px solid var(--a)}.kpi-r{border-left:3px solid var(--r)}.kpi-o{border-left:3px solid var(--o)}
.badge{display:inline-block;border-radius:999px;padding:.17rem .45rem;font-size:.53rem;font-weight:900}.ok{background:#123524;color:#64d695;border:1px solid #276a47}.out{background:#351616;color:#ff7d7d;border:1px solid #6e3030}.warn{background:#34270f;color:#f1bd5e;border:1px solid #705322}.info{background:#122b39;color:#79b9dc;border:1px solid #2c5870}
.notice{padding:.55rem .65rem;border-radius:8px;border:1px solid #304550;background:#15222a;font-size:.64rem}.notice-w{border-color:#6a5025;background:#261e11}
.table-wrap{overflow:auto;border:1px solid #263740;border-radius:8px}.pretty{width:100%;border-collapse:collapse;font-size:.6rem}.pretty th{background:#16232b;color:#8ea4b0;padding:.45rem;text-align:left}.pretty td{padding:.43rem;border-top:1px solid #22313a;white-space:nowrap}.pretty tr.total{background:#1a2932;font-weight:900}.pretty tr.iron td:first-child{border-left:3px solid #4f8fb8}.pretty tr.flux td:first-child{border-left:3px solid #35c47a}.pretty tr.recycle td:first-child{border-left:3px solid #e6a63a}.pretty tr.fuel td:first-child{border-left:3px solid #d95757}
.qitem{padding:.45rem 0;border-bottom:1px solid #23333c}.qtop{display:flex;justify-content:space-between;font-size:.63rem;font-weight:800}.qsub{font-size:.56rem;color:#8497a2;margin-top:.15rem}.meter{height:4px;background:#22313a;border-radius:99px;margin-top:.25rem}.meter div{height:100%;background:#35c47a;border-radius:99px}.meter.bad div{background:#d95757}
.navhead{font-size:.54rem;letter-spacing:.14em;font-weight:900;color:#617985;margin:.7rem .2rem .25rem}.side{font-size:.58rem;color:#9aacb6;border:1px solid #263740;border-radius:8px;padding:.55rem;background:#10191f}
.stButton>button{border-radius:7px!important;background:#142029!important;border:1px solid #2b414c!important;color:#e5eef2!important;font-weight:800!important;font-size:.64rem!important}.stButton>button[kind="primary"]{background:linear-gradient(135deg,#2d6f96,#245876)!important}
[data-testid="stDataEditor"]{border:1px solid #293b45;border-radius:8px;overflow:hidden}.stSlider label{font-size:.63rem!important}
.footer{border-top:1px solid #22323b;margin-top:1.2rem;padding-top:.5rem;color:#627681;font-size:.54rem;text-align:right}
</style>
''',unsafe_allow_html=True)

GROUPS=["Iron_ore","Flux","Recycle","Fuel"]
LABEL={"Iron_ore":"Iron Ore","Flux":"Flux","Recycle":"Recycle","Fuel":"Fuel"}
COLORS={"Iron_ore":"#4f8fb8","Flux":"#35c47a","Recycle":"#e6a63a","Fuel":"#d95757"}
MASTER=["Material","Group","Fe","SiO2","Al2O3","CaO","MgO","LOI","Tech_Min","Tech_Max"]

# ---------- EXCEL ----------
def clean_cols(df):
    df=df.copy(); df.columns=df.columns.astype(str).str.strip().str.replace(r"\s+","_",regex=True); return df

def _prepare_master_dataframe(df):
    df=clean_cols(df)
    miss=[c for c in MASTER if c not in df.columns]
    if miss: raise ValueError("Master Excel missing: "+", ".join(miss))
    df=df[MASTER].copy()
    df["Material"]=df["Material"].astype(str).str.strip()
    df["Group"]=df["Group"].astype(str).str.strip()
    df=df[df["Material"].notna() & (df["Material"].astype(str).str.strip()!="")].copy()
    if df["Material"].duplicated().any():
        raise ValueError("Duplicate material names in master Excel.")
    if not set(df["Group"]).issubset(GROUPS):
        raise ValueError("Invalid Group. Use Iron_ore, Flux, Recycle or Fuel.")
    df=df.set_index("Material")
    for c in MASTER[2:]:
        df[c]=pd.to_numeric(df[c],errors="raise")
    df["Price_Rs_t"]=0.0
    df["Available_Tonnes"]=0.0
    return df

def load_master_excel(f):
    """Load ONE master workbook.

    The workbook contains all primary materials plus two designated
    alternative-ore slots at the bottom of Master_Chemistry.

    The Notes sheet in the supplied master workbook explicitly defines
    the bottom two rows as ALT_ORE_1 / ALT_ORE_2 slots. Therefore:
      - all rows before those slots remain PRIMARY
      - only the final two non-empty material rows are ALTERNATIVES
      - the alternative material names are NOT hardcoded
      - a blank alternative slot is ignored
    """
    raw = pd.read_excel(f, sheet_name="Master_Chemistry")
    df = _prepare_master_dataframe(raw)

    if df.empty:
        raise ValueError("Master_Chemistry contains no material rows.")

    # Read the Notes sheet where possible. It documents the two bottom
    # rows as the alternative-ore slots. We deliberately do not use
    # yellow formatting because formatting should never turn a primary
    # recycle/flux/fuel into an alternative.
    alt_count = 2
    try:
        notes = pd.read_excel(f, sheet_name="Notes", header=None).fillna("")
        notes_text = " ".join(str(x) for x in notes.astype(str).values.flatten())
        if "two Alternative Ore slots" not in notes_text and "two Alternative Ore" not in notes_text:
            alt_count = 0
    except Exception:
        # If Notes is unavailable, retain the documented two-slot
        # convention rather than using visual formatting.
        alt_count = 2

    if alt_count:
        names = [str(x).strip() for x in df.index.tolist() if str(x).strip()]
        alt_names = names[-2:]
    else:
        alt_names = []

    alt_names = [m for m in alt_names if m and not m.upper().startswith("ALT_ORE_")]

    # If a designated slot is blank / placeholder, it should not appear.
    alt_df = df.loc[alt_names].copy() if alt_names else df.iloc[0:0].copy()
    primary_df = df.drop(index=alt_names).copy() if alt_names else df.copy()

    # Alternative ores are iron-ore candidates in the optimization model.
    if len(alt_df):
        alt_df["Group"] = "Iron_ore"

    return primary_df, alt_df

def load_primary(f):
    # Backward-compatible loader for settings/legacy calls.
    primary,_=load_master_excel(f)
    return primary

def load_alt(f):
    # Kept only for backward compatibility; normal workflow uses one master Excel.
    _,alt=load_master_excel(f)
    if len(alt)==0:
        raise ValueError("No alternative-ore rows were detected in the master Excel.")
    return alt

# ---------- STATE ----------
if "df" not in st.session_state:
    st.session_state.df=get_default_chemistry().copy()
    st.session_state.source="Built-in Master Chemistry"
    st.session_state.primary=list(st.session_state.df.index)
    st.session_state.alts=[]; st.session_state.alt_on={}
    st.session_state.avail={m:True for m in st.session_state.df.index}
    st.session_state.result=None; st.session_state.manual_base=None
    st.session_state.manual=None; st.session_state.changed=False
    st.session_state.whatif=None; st.session_state.runs=0
if "nav" not in st.session_state: st.session_state.nav="Dashboard"

def reset_primary(df,source):
    reset_master(df, df.iloc[0:0].copy(), source)

def reset_master(primary_df, alt_df, source):
    combined=primary_df.copy()
    if len(alt_df):
        combined=pd.concat([combined,alt_df],axis=0)
    st.session_state.df=combined.copy()
    st.session_state.source=source
    st.session_state.primary=list(primary_df.index)
    st.session_state.alts=list(alt_df.index)
    st.session_state.alt_on={m:False for m in st.session_state.alts}
    st.session_state.avail={m:True for m in st.session_state.primary}
    st.session_state.avail.update({m:False for m in st.session_state.alts})
    st.session_state.result=None
    st.session_state.manual_base=None
    st.session_state.manual=None
    st.session_state.changed=False
    st.session_state.whatif=None
    st.session_state.runs=0

def add_alt(df):
    dup=set(df.index)&set(st.session_state.df.index)
    if dup: raise ValueError("Alternative material already exists: "+", ".join(sorted(dup)))
    st.session_state.df=pd.concat([st.session_state.df,df])
    for m in df.index:
        st.session_state.alts.append(m); st.session_state.alt_on[m]=False; st.session_state.avail[m]=False
    st.session_state.changed=True

def active_df():
    df=st.session_state.df.copy()
    for m in df.index:
        if m in st.session_state.alts:
            if not st.session_state.alt_on.get(m,False): df.loc[m,"Available_Tonnes"]=0
        elif not st.session_state.avail.get(m,True): df.loc[m,"Available_Tonnes"]=0
    return df

# ---------- DISPLAY ----------
def chip(g): return f'<span class="badge info">{LABEL.get(g,g)}</span>'

def table(df,money=set(),status=None):
    rows=[]
    for _,r in df.iterrows():
        m=str(r.get("Material","")); g=str(r.get("Group","")); cl="total" if m=="TOTAL" else g.replace("_"," ").lower().replace(" ","")
        cells=[]
        for c in df.columns:
            v=r[c]
            if pd.isna(v): v=""
            if c=="Group" and v!="": v=chip(str(v))
            elif c in money and v!="":
                try:v=f"₹{float(v):,.2f}"
                except:pass
            elif isinstance(v,(float,int)) and not isinstance(v,bool): v=f"{float(v):,.2f}"
            if status==c:
                s=str(v); cls="ok" if any(x in s.lower() for x in ["ok","available","optimal","pass","feasible"]) else "out" if any(x in s.lower() for x in ["out","critical","unavailable","review"]) else "warn"
                v=f'<span class="badge {cls}">● {s}</span>'
            cells.append(f"<td>{v}</td>")
        rows.append(f'<tr class="{cl}">{"".join(cells)}</tr>')
    return '<div class="table-wrap"><table class="pretty"><thead><tr>'+''.join(f"<th>{c}</th>" for c in df.columns)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'

def breakdown(blend,df):
    b,c,total=calculate_cost_breakdown(blend,df)
    if len(b):
        b["_o"]=b.Group.map({g:i for i,g in enumerate(GROUPS)}).fillna(99); b=b.sort_values(["_o","Material"]).drop(columns="_o")
    totalrow=pd.DataFrame([{"Material":"TOTAL","Group":"","kg/t":total,"% of Burden":100,"Cost Rs/t":c,"% of Cost":100}])
    return pd.concat([b,totalrow],ignore_index=True),c,total

def donut(vals,center,unit):
    d=pd.DataFrame({"Group":GROUPS,"Value":[vals.get(g,0) for g in GROUPS]}); d=d[d.Value>0]
    fig=px.pie(d,names="Group",values="Value",hole=.65,color="Group",color_discrete_map=COLORS)
    fig.update_layout(height=285,margin=dict(l=2,r=2,t=2,b=2),paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(color="#dfe8ed",size=9),showlegend=True)
    fig.update_traces(textinfo="percent",textposition="inside")
    fig.add_annotation(text=f"<b>{center:,.1f}</b><br><span style='font-size:9px'>{unit}</span>",x=.5,y=.5,showarrow=False,font=dict(size=14,color="#fff"))
    return fig

def qpanel(ach):
    q=quality_table(ach,TARGETS); out=""
    for _,r in q.iterrows():
        ok=str(r.Status)=="OK"
        out+=f'<div class="qitem"><div class="qtop"><span>{r.KPI}</span><span class="badge {"ok" if ok else "out"}">{r.Status}</span></div><div class="qsub">Achieved <b>{float(r.Achieved):.4f}</b> | Target {r.Target}</div><div class="meter {"bad" if not ok else ""}"><div style="width:100%"></div></div></div>'
    return out

def page(title,sub): st.markdown(f'<div class="eyebrow">HOSPET ALLOY STEEL PLANT</div><h2>{title}</h2><div class="sub">{sub}</div>',unsafe_allow_html=True)

# ---------- EDITORS ----------
def primary_editor(key):
    data=[]
    for m in st.session_state.primary:
        r=st.session_state.df.loc[m]
        data.append({"Material":m,"Group":r.Group,"Available":st.session_state.avail.get(m,True),"Price (₹/t)":r.Price_Rs_t,"RM Stock (t)":r.Available_Tonnes,"Tech Max (t/d)":r.Tech_Max})
    ed=st.data_editor(pd.DataFrame(data),hide_index=True,use_container_width=True,height=380,key=key,disabled=["Material","Group"],column_config={
        "Available":st.column_config.CheckboxColumn("Availability"),
        "Price (₹/t)":st.column_config.NumberColumn("Price ₹/t",min_value=0,step=1,format="₹ %.0f"),
        "RM Stock (t)":st.column_config.NumberColumn("RM Stock t",min_value=0,step=100,format="%.0f"),
        "Tech Max (t/d)":st.column_config.NumberColumn("Tech Max t/d ✎",min_value=0,step=1,format="%.0f")})
    for _,r in ed.iterrows():
        m=r.Material; st.session_state.df.loc[m,"Price_Rs_t"]=float(r["Price (₹/t)"]); st.session_state.df.loc[m,"Available_Tonnes"]=float(r["RM Stock (t)"]); st.session_state.df.loc[m,"Tech_Max"]=float(r["Tech Max (t/d)"]); st.session_state.avail[m]=bool(r.Available)
    st.session_state.changed=True

def alt_editor():
    if not st.session_state.alts:
        st.markdown(
            '<div class="notice info">No alternative ore is currently defined in the '
            'two alternative slots of the Master Chemistry Excel.</div>',
            unsafe_allow_html=True
        )
        return

    data = []
    for m in st.session_state.alts:
        r = st.session_state.df.loc[m]
        data.append({
            "Material": m,
            "Allow Alternative": st.session_state.alt_on.get(m, False),
            "Fe": r.Fe,
            "SiO2": r.SiO2,
            "Al2O3": r.Al2O3,
            "CaO": r.CaO,
            "MgO": r.MgO,
            "LOI": r.LOI,
            "Price (₹/t)": r.Price_Rs_t,
            "RM Stock (t)": r.Available_Tonnes,
            "Tech Min": r.Tech_Min,
            "Tech Max (t/d)": r.Tech_Max
        })

    ed = st.data_editor(
        pd.DataFrame(data),
        hide_index=True,
        use_container_width=True,
        height=330,
        key="alt_editor",
        # Material is intentionally editable for alternatives.
        disabled=[],
        column_config={
            "Material": st.column_config.TextColumn(
                "Material Name ✎",
                help="Rename the alternative material. This name is used in the optimization output."
            ),
            "Allow Alternative": st.column_config.CheckboxColumn(
                "Include in Mix",
                help="OFF = completely excluded. ON = eligible, but optimizer does not have to use it."
            ),
            "Fe": st.column_config.NumberColumn("Fe ✎", min_value=0, step=.01),
            "SiO2": st.column_config.NumberColumn("SiO₂ ✎", min_value=0, step=.01),
            "Al2O3": st.column_config.NumberColumn("Al₂O₃ ✎", min_value=0, step=.01),
            "CaO": st.column_config.NumberColumn("CaO ✎", min_value=0, step=.01),
            "MgO": st.column_config.NumberColumn("MgO ✎", min_value=0, step=.01),
            "LOI": st.column_config.NumberColumn("LOI ✎", min_value=0, step=.01),
            "Price (₹/t)": st.column_config.NumberColumn(
                "Price ₹/t ✎", min_value=0, step=1, format="₹ %.0f"
            ),
            "RM Stock (t)": st.column_config.NumberColumn(
                "RM Stock t ✎", min_value=0, step=100, format="%.0f"
            ),
            "Tech Min": st.column_config.NumberColumn(
                "Tech Min ✎", min_value=0, step=1, format="%.0f"
            ),
            "Tech Max (t/d)": st.column_config.NumberColumn(
                "Tech Max t/d ✎", min_value=0, step=1, format="%.0f"
            )
        }
    )

    # Apply edits safely, including alternative material renaming.
    old_names = list(st.session_state.alts)
    rename_map = {}

    for i, old_name in enumerate(old_names):
        row = ed.iloc[i]
        new_name = str(row["Material"]).strip()

        if not new_name:
            new_name = old_name

        # Prevent collisions with primary materials or another alternative.
        existing_other = set(st.session_state.df.index) - {old_name}
        duplicate = new_name in existing_other
        duplicate_among_rows = new_name in {
            str(ed.iloc[j]["Material"]).strip()
            for j in range(len(ed))
            if j != i
        }

        if duplicate or duplicate_among_rows:
            st.warning(
                f"Alternative material name '{new_name}' already exists. "
                f"Keeping '{old_name}'."
            )
            new_name = old_name

        rename_map[old_name] = new_name

    # Rename rows in the master dataframe and preserve all alternative state.
    for old_name, new_name in rename_map.items():
        if old_name != new_name:
            st.session_state.df = st.session_state.df.rename(
                index={old_name: new_name}
            )
            st.session_state.alt_on[new_name] = st.session_state.alt_on.pop(
                old_name, False
            )
            st.session_state.avail[new_name] = st.session_state.avail.pop(
                old_name, False
            )

    new_alt_names = [rename_map[m] for m in old_names]
    st.session_state.alts = new_alt_names

    # Apply chemistry/commercial edits.
    for i, m in enumerate(new_alt_names):
        r = ed.iloc[i]

        st.session_state.alt_on[m] = bool(r["Allow Alternative"])

        for c in ["Fe", "SiO2", "Al2O3", "CaO", "MgO", "LOI"]:
            st.session_state.df.loc[m, c] = float(r[c])

        st.session_state.df.loc[m, "Tech_Min"] = float(r["Tech Min"])
        st.session_state.df.loc[m, "Tech_Max"] = float(r["Tech Max (t/d)"]
        )
        st.session_state.df.loc[m, "Price_Rs_t"] = float(r["Price (₹/t)"])
        st.session_state.df.loc[m, "Available_Tonnes"] = float(r["RM Stock (t)"])

        # Availability for alternatives is controlled by Include in Mix.
        st.session_state.avail[m] = bool(r["Allow Alternative"])

    st.session_state.changed = True

    st.markdown(
        '<div class="small" style="margin-top:.4rem">'
        '🟢 <b>ON</b> = alternative eligible for optimization &nbsp; '
        '• &nbsp; ⚪ <b>OFF</b> = alternative completely excluded'
        '</div>',
        unsafe_allow_html=True
    )


def run(ref=None):
    cur=active_df(); prev=st.session_state.result["cost"] if st.session_state.result else None
    x=solve_blend_with_compensation(cur,1000,TARGETS,baseline_blend=ref)
    st.session_state.result={"status":x[0],"blend":x[1],"cost":x[2],"achieved":x[3],"diagnostics":x[4],"fallback":x[5],"df":cur.copy()}

    # A fresh optimizer result must become the new manual-adjustment baseline.
    # Clear old slider widget state so Streamlit cannot reuse a value that is
    # outside the new slider's min/max range.
    for k in list(st.session_state.keys()):
        if str(k).startswith("man_"):
            del st.session_state[k]

    st.session_state.manual_base=x[1].copy() if x[1] else None
    st.session_state.manual=x[1].copy() if x[1] else None
    st.session_state.changed=False; st.session_state.prev_cost=prev; st.session_state.runs+=1

# ---------- SIDEBAR ----------
with st.sidebar:
    st.markdown("### BAJAJ MUKAND"); st.markdown('<div class="small">Kalyani Steels × Mukand • Hospet</div>',unsafe_allow_html=True); st.markdown("---")
    groups=[("WORKSPACE",["Dashboard"]),("OPERATIONS",["RM Stock","Optimization Results","Manual Burden Control","Alternative Raw Material"]),("ANALYSIS",["Burden Composition","Cost Composition","What-if Analysis","Bottleneck Analysis"]),("REPORTING",["Reports"]),("SYSTEM",["Upload & Settings"])]
    for h,items in groups:
        st.markdown(f'<div class="navhead">{h}</div>',unsafe_allow_html=True)
        for item in items:
            if st.button(item,key="nav_"+item,use_container_width=True,type="primary" if st.session_state.nav==item else "secondary"): st.session_state.nav=item; st.rerun()
    st.markdown("---")
    st.markdown(f'<div class="side"><b>DATA</b><br>{st.session_state.source}<br>{len(st.session_state.primary)} primary<br>{len(st.session_state.alts)} alternative<br><br><b>MODEL</b><br>● Ready</div>',unsafe_allow_html=True)

result=st.session_state.result
good=True if not result else all(quality_checks(result["achieved"],TARGETS).values())
st.markdown(f'<div style="display:flex;justify-content:space-between;align-items:end"><div><div class="eyebrow">HOSPET ALLOY STEEL PLANT</div><h1>SINTER BURDEN CONTROL</h1><div class="sub">Cost optimization • quality assurance • raw material decision support</div></div><div style="text-align:right"><span class="badge {"ok" if good else "out"}">● {"QUALITY OK" if good else "QUALITY ALERT"}</span><br><span class="small">PLANT: HOSPET • {datetime.now():%d %b %Y %H:%M}</span></div></div>',unsafe_allow_html=True)

# ---------- PAGES ----------
def dashboard():
    # ---------- ONE MASTER EXCEL / DATA SOURCE ----------
    st.markdown(
        '<div class="panel" style="margin-bottom:.8rem">'
        '<div class="panel-title">DATA CONTROL CENTER</div>'
        '<div class="small">Upload one Master Chemistry Excel. Primary materials and optional alternative ores are read from the same workbook. '
        'Alternative ores remain excluded until the user explicitly switches them ON.</div>'
        '</div>',
        unsafe_allow_html=True
    )

    upload_col, source_col, info_col = st.columns([2.0,1.45,1.15], gap="medium")

    with upload_col:
        st.markdown(
            '<div class="notice"><b>MASTER CHEMISTRY EXCEL</b><br>'
            '<span class="small">12 Primary + 2 Alternative Ore slots in the same workbook</span></div>',
            unsafe_allow_html=True
        )
        master_file=st.file_uploader(
            "Upload Master Chemistry Excel",
            type=["xlsx"],
            key="dashboard_master_upload",
            label_visibility="collapsed"
        )
        if master_file:
            try:
                primary_df,alt_df=load_master_excel(master_file)
                st.success(
                    f"{len(primary_df)} primary + {len(alt_df)} alternative material(s) detected."
                )
                if st.button(
                    "ACTIVATE MASTER EXCEL",
                    type="primary",
                    use_container_width=True,
                    key="dashboard_activate_master"
                ):
                    reset_master(
                        primary_df,
                        alt_df,
                        "Master Excel • " + master_file.name
                    )
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    with source_col:
        source_is_excel=str(st.session_state.source).startswith("Master Excel")
        source_label="MASTER EXCEL IN USE" if source_is_excel else "BUILT-IN MASTER IN USE"
        source_cls="ok" if source_is_excel else "info"
        st.markdown(
            f'<div class="source-card">'
            f'<div class="source-status {source_cls}">● {source_label}</div>'
            f'<div class="source-name">{st.session_state.source}</div>'
            f'<div class="small">{len(st.session_state.primary)} primary • {len(st.session_state.alts)} alternative</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    with info_col:
        st.markdown(
            f'<div class="source-card">'
            f'<div class="source-status {"ok" if st.session_state.alts else "info"}">'
            f'● ALTERNATIVE ORE</div>'
            f'<div class="source-name">'
            f'{sum(bool(st.session_state.alt_on.get(m,False)) for m in st.session_state.alts)} enabled'
            f'</div>'
            f'<div class="small">{len(st.session_state.alts)} loaded • OFF by default</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown('<div style="height:12px"></div>',unsafe_allow_html=True)

    # ---------- CONTROL ROOM ----------
    st.markdown(
        '<div class="hero"><b>CONTROL ROOM</b>'
        '<div class="sub">Primary chemistry is read-only from the active master Excel. '
        'Price, RM Stock, Tech Max and availability are daily inputs. '
        'Alternative chemistry is editable only in the Alternative Ore section below.</div></div>',
        unsafe_allow_html=True
    )

    a,b,c=st.columns([4.2,1.7,1.25],gap="large")
    with a:
        st.markdown(
            f'<div class="notice"><b>ACTIVE MASTER SOURCE:</b> {st.session_state.source}</div>',
            unsafe_allow_html=True
        )
    with b:
        if st.button("🚀 RUN OPTIMIZER",type="primary",use_container_width=True):
            with st.spinner("Optimizing…"):
                run()
            st.rerun()
    with c:
        st.markdown(
            f'<div class="notice" style="text-align:center">'
            f'<b>RUN {st.session_state.runs}</b><br>{len(st.session_state.alts)} alt. RM</div>',
            unsafe_allow_html=True
        )

    if st.session_state.changed:
        st.markdown(
            '<div class="notice notice-w" style="margin-top:.65rem">'
            '△ Inputs changed — run optimizer to apply.</div>',
            unsafe_allow_html=True
        )

    st.markdown('<div style="height:12px"></div>',unsafe_allow_html=True)

    if result and result["blend"]:
        bd,cost,total=breakdown(result["blend"],result["df"])
        ach=result["achieved"]
        ok=all(quality_checks(ach,TARGETS).values())
        cards=[
            ("TOTAL COST",f"₹{cost:,.2f}/t","Optimized","kpi-s"),
            ("TOTAL BURDEN",f"{total:,.1f} kg/t","Per tonne sinter","kpi-g"),
            ("Fe",f"{ach['Fe']:.3f}%",f"{FE_LOWER:.1f}–{FE_UPPER:.1f} target","kpi-a"),
            ("QUALITY","PASS" if ok else "REVIEW","Mandatory constraints","kpi-g" if ok else "kpi-r"),
            ("ALT ORE","USED" if any(result["blend"].get(m,0)>0 for m in st.session_state.alts) else "NOT USED","Contingency","kpi-o")
        ]
        cc=st.columns(5,gap="medium")
        for col,(l,v,s,cl) in zip(cc,cards):
            col.markdown(
                f'<div class="kpi {cl}"><div class="kpi-label">{l}</div>'
                f'<div class="kpi-value">{v}</div><div class="kpi-sub">{s}</div></div>',
                unsafe_allow_html=True
            )

        st.write("")
        a,b=st.columns([1,2],gap="medium")
        with a:
            st.markdown(
                '<div class="panel"><div class="panel-title">ACHIEVED CHEMISTRY</div>'
                +qpanel(ach)+'</div>',
                unsafe_allow_html=True
            )
        with b:
            st.markdown(
                '<div class="panel"><div class="panel-title">OPTIMIZED BURDEN & COST</div>'
                +table(bd.round(2),{"Cost Rs/t"})+'</div>',
                unsafe_allow_html=True
            )

        st.write("")
        a,b=st.columns(2,gap="medium")
        with a:
            gv={g:sum(result["blend"].get(m,0) for m in result["blend"]
                      if result["df"].loc[m,"Group"]==g) for g in GROUPS}
            st.markdown('<div class="panel"><div class="panel-title">BURDEN COMPOSITION</div>',unsafe_allow_html=True)
            st.plotly_chart(donut(gv,total,"kg/t"),use_container_width=True,config={"displayModeBar":False})
            st.markdown('</div>',unsafe_allow_html=True)
        with b:
            gv={g:sum(result["blend"].get(m,0)*result["df"].loc[m,"Price_Rs_t"]/1000
                      for m in result["blend"]
                      if result["df"].loc[m,"Group"]==g) for g in GROUPS}
            st.markdown('<div class="panel"><div class="panel-title">COST COMPOSITION</div>',unsafe_allow_html=True)
            st.plotly_chart(donut(gv,cost,"₹/t"),use_container_width=True,config={"displayModeBar":False})
            st.markdown('</div>',unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="panel" style="margin-top:.7rem;text-align:center;padding:2rem">'
            '<b>Optimization workspace ready</b>'
            '<div class="small">Enter daily inputs and run the optimizer.</div></div>',
            unsafe_allow_html=True
        )

    # ---------- PRIMARY INPUTS ----------
    st.write("")
    st.markdown(
        '<div class="panel"><div class="panel-title">PRIMARY RAW MATERIAL INPUTS</div>'
        '<div class="small">Primary chemistry is read-only from the active master. '
        'Price, RM Stock, Tech Max and Availability are editable daily controls.</div>',
        unsafe_allow_html=True
    )
    primary_editor("dashboard_primary")
    st.markdown('</div>',unsafe_allow_html=True)

    # ---------- ALTERNATIVE ORES FROM SAME EXCEL ----------
    st.write("")
    st.markdown(
        '<div class="panel"><div class="panel-title">ALTERNATIVE ORE — USER CONTROL</div>'
        '<div class="small">Alternative ores detected from the <b>same Master Chemistry Excel</b> are shown here. '
        'Their chemistry is fetched from Excel and is editable only in this section. '
        '<b>Include in Mix OFF</b> means the optimizer cannot use the ore. '
        '<b>ON</b> makes it eligible but does not force usage.</div>',
        unsafe_allow_html=True
    )
    if st.session_state.alts:
        alt_editor()
    else:
        st.markdown(
            '<div class="notice info" style="margin-top:.65rem">'
            'No alternative ore rows detected in the active Master Excel.</div>',
            unsafe_allow_html=True
        )
    st.markdown('</div>',unsafe_allow_html=True)

def rm_stock():
    page("RM Stock & Commercial Inputs","Daily inputs for primary raw materials.")
    st.markdown('<div class="notice">✎ Editable: Price • RM Stock • Tech Max • Availability &nbsp; | &nbsp; 🔒 Chemistry / Tech Min</div>',unsafe_allow_html=True); st.write("")
    st.markdown('<div class="panel"><div class="panel-title">PRIMARY COMMERCIAL MASTER</div>',unsafe_allow_html=True); primary_editor("rm_primary"); st.markdown('</div>',unsafe_allow_html=True)

def alternative():
    page("Alternative Raw Material","Alternative ores are loaded from the same Master Chemistry Excel and remain OFF until explicitly enabled.")
    st.markdown(
        '<div class="panel"><div class="panel-title">ALTERNATIVE ORE WORKSPACE</div>'
        '<div class="notice">OFF = excluded from optimization. ON = eligible for optimization; it is still not forced into the final mix.</div>'
        '<div class="small" style="margin-top:.5rem">Chemistry is fetched from the active Master Excel and is editable only here. '
        'Price, RM Stock, Tech Min and Tech Max are also editable.</div></div>',
        unsafe_allow_html=True
    )
    st.write("")
    st.markdown('<div class="panel"><div class="panel-title">ALTERNATIVE MATERIAL INPUTS</div>',unsafe_allow_html=True)
    alt_editor()
    st.markdown('</div>',unsafe_allow_html=True)


def composition(kind):
    if not result or not result["blend"]: page("Composition","Run optimizer first."); return
    bd,cost,total=breakdown(result["blend"],result["df"]); base=bd[bd.Material!="TOTAL"]
    vals={g:float(base.loc[base.Group==g,"Cost Rs/t"].sum() if kind=="cost" else base.loc[base.Group==g,"kg/t"].sum()) for g in GROUPS}
    title="Cost Structure & Cost Drivers" if kind=="cost" else "Burden Mix & Material Contribution"; unit="₹/t" if kind=="cost" else "kg/t"; center=cost if kind=="cost" else total
    page(title,"Sequential view: Iron Ore → Flux → Recycle → Fuel.")
    a,b=st.columns([1,1.6])
    with a: st.markdown(f'<div class="panel"><div class="panel-title">{kind.upper()} DISTRIBUTION</div>',unsafe_allow_html=True); st.plotly_chart(donut(vals,center,unit),use_container_width=True,config={"displayModeBar":False}); st.markdown('</div>',unsafe_allow_html=True)
    with b:
        rows=[{"Material":LABEL[g],"Group":g,("Cost Rs/t" if kind=="cost" else "kg/t"):vals[g],("% of Cost" if kind=="cost" else "% of Burden"):(vals[g]/center*100 if center else 0)} for g in GROUPS]
        rows.append({"Material":"TOTAL","Group":"","Cost Rs/t":cost,"% of Cost":100} if kind=="cost" else {"Material":"TOTAL","Group":"","kg/t":total,"% of Burden":100})
        st.markdown('<div class="panel"><div class="panel-title">GROUP CONTRIBUTION</div>'+table(pd.DataFrame(rows),{"Cost Rs/t"})+'</div>',unsafe_allow_html=True)
    st.write(""); st.markdown('<div class="panel"><div class="panel-title">MATERIAL LEVEL</div>'+table(bd.round(2),{"Cost Rs/t"})+'</div>',unsafe_allow_html=True)

def results():
    page("Optimized Sinter Recipe","Latest solver result.")
    if not result or not result["blend"]: st.info("Run optimizer first."); return
    bd,cost,total=breakdown(result["blend"],result["df"]); a=result["achieved"]; ok=all(quality_checks(a,TARGETS).values())
    cc=st.columns(4)
    for col,l,v,s,cl in [(cc[0],"TOTAL COST",f"₹{cost:,.2f}/t","Current optimum","kpi-s"),(cc[1],"BURDEN",f"{total:,.1f} kg/t","Optimized","kpi-g"),(cc[2],"Fe",f"{a['Fe']:.3f}%","Target band","kpi-a"),(cc[3],"QUALITY","PASS" if ok else "REVIEW","Gate","kpi-g" if ok else "kpi-r")]: col.markdown(f'<div class="kpi {cl}"><div class="kpi-label">{l}</div><div class="kpi-value">{v}</div><div class="kpi-sub">{s}</div></div>',unsafe_allow_html=True)
    st.write(""); a,b=st.columns([1,2]); a.markdown('<div class="panel"><div class="panel-title">QUALITY</div>'+qpanel(result["achieved"])+'</div>',unsafe_allow_html=True); b.markdown('<div class="panel"><div class="panel-title">RECIPE</div>'+table(bd.round(2),{"Cost Rs/t"})+'</div>',unsafe_allow_html=True)

def manual():
    page("Manual Burden Control","Adjust the optimized burden and see burden, cost and chemistry impact inside this tab only.")
    if not result or not result["blend"]: st.info("Run optimizer first."); return
    df=result["df"]

    # Always use the latest optimizer result if the stored manual baseline
    # belongs to an older result/dataset.
    current_blend=result["blend"].copy()
    stored_base=st.session_state.manual_base
    if not stored_base or set(stored_base.keys()) != set(current_blend.keys()):
        stored_base=current_blend.copy()
        st.session_state.manual_base=stored_base.copy()

    base=stored_base.copy()
    adj=[m for m in base if m in df.index and df.loc[m,"Group"] in ("Iron_ore","Flux")]
    fixed=[m for m in base if m in df.index and df.loc[m,"Group"] in ("Recycle","Fuel")]
    st.markdown('<div class="notice">Iron Ore ±15% • Flux ±10% • Recycle/Fuel fixed • total burden preserved.</div>',unsafe_allow_html=True)
    req={}; cols=st.columns(2)
    for i,m in enumerate(adj):
        # Defensive slider bounds. Streamlit requires min <= value <= max,
        # and values from a previous rerun can otherwise become stale.
        try:
            b=float(base[m])
        except (TypeError, ValueError):
            b=0.0
        if not math.isfinite(b) or b < 0:
            b=0.0

        r=.15 if df.loc[m,"Group"]=="Iron_ore" else .10
        mn=max(0.0, b*(1.0-r))
        mx=b*(1.0+r)

        # Guarantee a usable range even for zero/tiny quantities.
        if not math.isfinite(mx) or mx <= mn:
            mx=mn+1.0
        if (mx-mn) < 0.5:
            mx=mn+0.5

        key="man_"+m
        current=st.session_state.get(key,b)
        try:
            current=float(current)
        except (TypeError, ValueError):
            current=b
        if not math.isfinite(current):
            current=b

        # Clamp stale widget state into the current valid range.
        current=max(mn,min(current,mx))

        with cols[i%2]:
            req[m]=st.slider(
                f"{m} — kg/t",
                min_value=float(mn),
                max_value=float(mx),
                value=float(current),
                step=0.5,
                key=key
            )
    adjusted=redistribute_adjustment(base,df,req)

    # Defensive cleanup: keep only valid material keys and numeric quantities.
    adjusted = {
        m: float(qty)
        for m, qty in adjusted.items()
        if m in df.index and pd.notna(qty)
    }
    for m in fixed:
        if m in df.index:
            adjusted[m]=float(base[m])

    # Recalculate the adjusted recipe using the SAME backend chemistry engine.
    ach=compute_achieved(adjusted,df,1000)

    # Cost is calculated from the current dashboard prices.
    ac=sum(
        float(adjusted[m]) * float(df.loc[m,"Price_Rs_t"]) / 1000
        for m in adjusted
        if m in df.index
    )

    bc=float(result["cost"] or 0)
    total=sum(float(v) for v in adjusted.values())
    ok=all(quality_checks(ach,TARGETS).values())
    cc=st.columns(5, gap="medium")
    for col,l,v,s,cl in [(cc[0],"BASE COST",f"₹{bc:,.2f}","Optimized","kpi-s"),(cc[1],"ADJUSTED COST",f"₹{ac:,.2f}",f"{ac-bc:+,.2f}","kpi-o"),(cc[2],"BURDEN",f"{total:,.1f}","Preserved","kpi-g"),(cc[3],"Fe",f"{ach['Fe']:.3f}%","After adjustment","kpi-a"),(cc[4],"QUALITY","PASS" if ok else "REVIEW","After adjustment","kpi-g" if ok else "kpi-r")]: col.markdown(f'<div class="kpi {cl}"><div class="kpi-label">{l}</div><div class="kpi-value">{v}</div><div class="kpi-sub">{s}</div></div>',unsafe_allow_html=True)
    st.write(""); a,b=st.columns(2)
    gv={g:sum(adjusted.get(m,0) for m in adjusted if df.loc[m,"Group"]==g) for g in GROUPS}; gc={g:sum(adjusted.get(m,0)*df.loc[m,"Price_Rs_t"]/1000 for m in adjusted if df.loc[m,"Group"]==g) for g in GROUPS}
    with a: st.markdown('<div class="panel"><div class="panel-title">ADJUSTED BURDEN COMPOSITION</div>',unsafe_allow_html=True);st.plotly_chart(donut(gv,total,"kg/t"),use_container_width=True,config={"displayModeBar":False});st.markdown('</div>',unsafe_allow_html=True)
    with b: st.markdown('<div class="panel"><div class="panel-title">ADJUSTED COST COMPOSITION</div>',unsafe_allow_html=True);st.plotly_chart(donut(gc,ac,"₹/t"),use_container_width=True,config={"displayModeBar":False});st.markdown('</div>',unsafe_allow_html=True)
    st.write(""); a,b=st.columns([1,2])
    with a: st.markdown('<div class="panel"><div class="panel-title">ACHIEVED CHEMISTRY</div>'+qpanel(ach)+'</div>',unsafe_allow_html=True)
    with b:
        bd,_,_=breakdown(adjusted,df); st.markdown('<div class="panel"><div class="panel-title">ADJUSTED BURDEN & COST</div>'+table(bd.round(2),{"Cost Rs/t"})+'</div>',unsafe_allow_html=True)
    st.write(""); st.markdown('<div class="panel"><div class="panel-title">OPTIMIZED vs MANUAL</div>',unsafe_allow_html=True)
    cmp=pd.DataFrame([["Cost",bc,ac,ac-bc],["Burden",sum(base.values()),total,total-sum(base.values())],["Fe",result["achieved"]["Fe"],ach["Fe"],ach["Fe"]-result["achieved"]["Fe"]],["SiO2",result["achieved"]["SiO2"],ach["SiO2"],ach["SiO2"]-result["achieved"]["SiO2"]],["Basicity",result["achieved"]["Basicity"],ach["Basicity"],ach["Basicity"]-result["achieved"]["Basicity"]]],columns=["Parameter","Optimized","Manual","Change"])
    st.dataframe(cmp.round(4),hide_index=True,use_container_width=True); st.markdown('</div>',unsafe_allow_html=True)
    if st.button("↩ RESET TO OPTIMIZED",use_container_width=True):
        for m in adj: st.session_state["man_"+m]=float(base[m])
        st.rerun()

def whatif():
    page("Scenario & Material Risk","Test material unavailability.")
    if st.button("▶ RUN MATERIAL SHORTAGE SCENARIOS",type="primary"):
        with st.spinner("Evaluating…"): st.session_state.whatif=what_if_analysis(active_df(),TARGETS)
    if st.session_state.whatif is not None:
        w=st.session_state.whatif.copy(); st.markdown('<div class="panel">'+table(w.fillna("—"),status="Status")+'</div>',unsafe_allow_html=True)
    else: st.info("Run the scenario analysis.")

def bottleneck():
    page("Quality Constraint Pressure","Identify the constraints closest to limits.")
    if not result or not result["achieved"]: st.info("Run optimizer first."); return
    q=quality_table(result["achieved"],TARGETS); st.markdown('<div class="panel">'+table(q.round(4),status="Status")+'</div>',unsafe_allow_html=True)

def reports():
    page("Reports & Export","Export the latest optimized recipe.")
    if not result or not result["blend"]: st.info("Run optimizer first."); return
    bd,_,_=breakdown(result["blend"],result["df"]); st.markdown('<div class="panel">'+table(bd.round(2),{"Cost Rs/t"})+'</div>',unsafe_allow_html=True)
    st.download_button("⬇ DOWNLOAD OPTIMIZATION REPORT",bd.to_csv(index=False).encode(),"sinter_optimization_report.csv","text/csv",use_container_width=True)

def settings():
    page("Upload & Settings","Upload one Master Chemistry workbook containing primary rows and optional alternative-ore rows.")
    a,b=st.columns([1.6,1],gap="medium")
    with a:
        st.markdown('<div class="panel"><div class="panel-title">MASTER CHEMISTRY EXCEL</div>',unsafe_allow_html=True)
        f=st.file_uploader("Upload master chemistry",type=["xlsx"],key="primary_upload")
        if f:
            try:
                primary_df,alt_df=load_master_excel(f)
                st.success(f"{len(primary_df)} primary + {len(alt_df)} alternative material(s) detected.")
                if st.button("ACTIVATE MASTER EXCEL",type="primary",use_container_width=True):
                    reset_master(primary_df,alt_df,"Master Excel • "+f.name)
                    st.rerun()
            except Exception as e:
                st.error(str(e))
        st.markdown(
            '<div class="small">The workbook contains Material, Group, Fe, SiO2, Al2O3, CaO, MgO, LOI, Tech_Min and Tech_Max. '
            'Commercial inputs are entered in the dashboard.</div>',
            unsafe_allow_html=True
        )
        st.markdown('</div>',unsafe_allow_html=True)
    with b:
        st.markdown('<div class="panel"><div class="panel-title">SYSTEM</div>',unsafe_allow_html=True)
        if st.button("↺ RESTORE BUILT-IN MASTER",use_container_width=True):
            reset_primary(get_default_chemistry(),"Built-in Master Chemistry")
            st.rerun()
        st.markdown(
            '<div class="notice">Alternative ores are detected from the same workbook and start OFF. '
            'Use the Alternative Ore section on Dashboard to edit and enable them.</div>',
            unsafe_allow_html=True
        )
        st.markdown('</div>',unsafe_allow_html=True)


# ---------- ROUTE ----------
pages={"Dashboard":dashboard,"RM Stock":rm_stock,"Optimization Results":results,"Manual Burden Control":manual,"Alternative Raw Material":alternative,"Burden Composition":lambda:composition("burden"),"Cost Composition":lambda:composition("cost"),"What-if Analysis":whatif,"Bottleneck Analysis":bottleneck,"Reports":reports,"Upload & Settings":settings}
pages[st.session_state.nav]()
st.markdown('<div class="footer">Sinter Burden Control • Hospet Alloy Steel Plant • Production decision-support interface</div>',unsafe_allow_html=True)
