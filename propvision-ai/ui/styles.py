"""Global CSS for the dark, premium SaaS look."""

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@500;600;700&display=swap');

:root {
  --pv-bg: #0a0f1d;
  --pv-panel: rgba(255,255,255,0.045);
  --pv-border: rgba(255,255,255,0.09);
  --pv-text: #eceff6;
  --pv-muted: #98a2b8;
  --pv-accent: #d9b56d;
  --pv-accent-2: #b98f45;
  --pv-blue: #7d95ff;
}

html, body, [class*="css"], .stApp {
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  color: var(--pv-text);
}
.stApp {
  background:
    radial-gradient(1100px 600px at 12% -10%, rgba(125,149,255,0.14), transparent 60%),
    radial-gradient(900px 500px at 105% 5%, rgba(217,181,109,0.11), transparent 55%),
    linear-gradient(160deg, #0a0f1d 0%, #0e1527 55%, #0a1020 100%);
}
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { max-width: 1120px; padding-top: 1.6rem; padding-bottom: 4rem; }

/* typography */
h1, h2, h3 { letter-spacing: -0.01em; }
.pv-serif { font-family: 'Playfair Display', Georgia, serif; }
.pv-muted { color: var(--pv-muted); }

/* brand + stepper */
.pv-topbar { display:flex; align-items:center; justify-content:space-between; margin-bottom: 1.2rem; }
.pv-brand { display:flex; align-items:center; gap:12px; font-weight:600; font-size:1.15rem; letter-spacing:.01em; }
.pv-logo { width:34px; height:34px; border-radius:10px; display:grid; place-items:center; color:#161207; font-weight:700;
  background: linear-gradient(140deg, #f1d9a3, #c39a4e); box-shadow: 0 6px 22px rgba(217,181,109,.35); }
.pv-chip { font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color:var(--pv-muted);
  border:1px solid var(--pv-border); padding:.28rem .7rem; border-radius:999px; background:var(--pv-panel); }
.pv-steps { display:flex; gap:8px; flex-wrap:wrap; margin: .2rem 0 1.4rem 0; }
.pv-step { display:flex; align-items:center; gap:9px; padding:.45rem .9rem .45rem .5rem; border-radius:999px;
  border:1px solid var(--pv-border); background:var(--pv-panel); font-size:.82rem; color:var(--pv-muted); }
.pv-step .n { width:22px; height:22px; border-radius:50%; display:grid; place-items:center; font-size:.72rem; font-weight:600;
  background:rgba(255,255,255,.08); color:var(--pv-muted); }
.pv-step.done .n { background: rgba(217,181,109,.22); color: var(--pv-accent); }
.pv-step.active { color:var(--pv-text); border-color: rgba(217,181,109,.55); background: rgba(217,181,109,.08); }
.pv-step.active .n { background: linear-gradient(140deg,#f1d9a3,#c39a4e); color:#161207; }

/* hero */
.pv-hero { padding: 2.6rem 2.4rem; border-radius: 24px; border:1px solid var(--pv-border);
  background: linear-gradient(135deg, rgba(255,255,255,.06), rgba(255,255,255,.015)); position:relative; overflow:hidden; }
.pv-hero::after { content:""; position:absolute; right:-80px; top:-80px; width:320px; height:320px; border-radius:50%;
  background: radial-gradient(circle, rgba(217,181,109,.22), transparent 70%); }
.pv-hero h1 { font-family:'Playfair Display', Georgia, serif; font-size:3.05rem; line-height:1.08; margin:.6rem 0 1rem 0; font-weight:600; max-width: 760px; }
.pv-hero h1 em { font-style:normal; background: linear-gradient(120deg,#f4dfae,#c9a15a); -webkit-background-clip:text; background-clip:text; color:transparent; }
.pv-hero p { font-size:1.06rem; color:#b6bfd2; max-width:640px; line-height:1.65; }
.pv-badges { display:flex; gap:8px; flex-wrap:wrap; margin-top:1.1rem; }

/* cards */
.pv-card { border:1px solid var(--pv-border); background:var(--pv-panel); border-radius:18px; padding:1.25rem 1.3rem; height:100%; }
.pv-card h4 { margin:.2rem 0 .35rem 0; font-size:1rem; font-weight:600; }
.pv-card p { margin:0; color:var(--pv-muted); font-size:.9rem; line-height:1.55; }
.pv-icon { width:38px; height:38px; border-radius:11px; display:grid; place-items:center; font-size:1.1rem;
  background: rgba(217,181,109,.12); border:1px solid rgba(217,181,109,.3); }
.pv-section-title { font-size:1.55rem; font-weight:600; margin: 0 0 .25rem 0; }
.pv-section-sub { color: var(--pv-muted); margin-bottom: 1.1rem; font-size:.95rem; }
.pv-kicker { color: var(--pv-accent); font-size:.74rem; letter-spacing:.18em; text-transform:uppercase; font-weight:600; }

/* streamlit containers as panels */
[data-testid="stVerticalBlockBorderWrapper"] { border-radius:18px !important; border-color: var(--pv-border) !important;
  background: var(--pv-panel); }
[data-testid="stExpander"] { border-radius:14px; border-color: var(--pv-border); background: var(--pv-panel); }

/* inputs */
.stTextInput input, .stTextArea textarea, .stNumberInput input, .stSelectbox [data-baseweb="select"] > div {
  background: rgba(8,12,24,.75) !important; border:1px solid var(--pv-border) !important; border-radius:12px !important; color: var(--pv-text) !important; }
.stTextInput input:focus, .stTextArea textarea:focus { border-color: rgba(217,181,109,.7) !important; box-shadow: 0 0 0 3px rgba(217,181,109,.14) !important; }
label, [data-testid="stWidgetLabel"] p { color:#c5cde0 !important; font-weight:500; font-size:.88rem; }
[data-testid="stFileUploaderDropzone"] { background: rgba(8,12,24,.6); border:1.5px dashed rgba(217,181,109,.4); border-radius:16px; }

/* buttons */
.stButton > button, .stDownloadButton > button { border-radius: 12px; font-weight:600; border:1px solid var(--pv-border);
  background: rgba(255,255,255,.06); color: var(--pv-text); transition: all .15s ease; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: rgba(217,181,109,.6); transform: translateY(-1px); }
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
  background: linear-gradient(140deg,#f1d9a3,#c39a4e); color:#171208; border:none; box-shadow: 0 8px 26px rgba(217,181,109,.28); }
.stButton > button[kind="primary"]:hover { filter: brightness(1.06); box-shadow: 0 10px 30px rgba(217,181,109,.38); }
.stButton > button:disabled { opacity:.45; }

/* progress + metrics */
.stProgress > div > div > div > div { background: linear-gradient(90deg,#c39a4e,#f1d9a3); }
[data-testid="stMetric"] { background: var(--pv-panel); border:1px solid var(--pv-border); padding:.85rem 1rem; border-radius:14px; }
[data-testid="stMetricLabel"] p { color: var(--pv-muted) !important; font-size:.78rem !important; text-transform:uppercase; letter-spacing:.08em; }
[data-testid="stMetricValue"] { font-size:1.35rem !important; }

/* photo tiles */
.pv-thumb-num { display:inline-block; font-size:.72rem; color:#161207; font-weight:700; padding:.1rem .5rem; border-radius:999px;
  background: linear-gradient(140deg,#f1d9a3,#c39a4e); margin-bottom:.35rem; }
.pv-theme { display:flex; gap:10px; align-items:center; padding:.7rem .9rem; border-radius:14px; border:1px solid var(--pv-border); background: var(--pv-panel); margin-top:.4rem; }
.pv-swatch { width:34px; height:34px; border-radius:10px; flex:none; }
.pv-note { border-left:3px solid var(--pv-accent); padding:.55rem .9rem; background: rgba(217,181,109,.07); border-radius:0 10px 10px 0; color:#d5dbe8; font-size:.88rem; }
.pv-pill-ai { display:inline-block; font-size:.72rem; padding:.18rem .6rem; border-radius:999px; font-weight:600; letter-spacing:.04em; }
.pv-pill-rule { background: rgba(125,149,255,.16); color:#a9b9ff; border:1px solid rgba(125,149,255,.35); }
.pv-pill-llm { background: rgba(120,214,160,.14); color:#8ee0b3; border:1px solid rgba(120,214,160,.35); }
video { border-radius: 16px; }
</style>
"""
