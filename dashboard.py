"""
dashboard.py — Battery Notifier Control Panel
Run with:  streamlit run dashboard.py
"""

import json
import time
import platform
import subprocess
from pathlib import Path

import streamlit as st

THRESHOLDS_FILE = Path(__file__).parent / "thresholds.json"

# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Battery Notifier",
    page_icon="🔋",
    layout="centered",
)

# ── custom CSS ────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    /* dark background */
    .stApp {
        background: #0d1117;
        color: #e6edf3;
    }

    h1, h2, h3 { font-family: 'Space Mono', monospace; }

    /* hero card */
    .hero {
        background: linear-gradient(135deg, #161b22 0%, #1c2633 100%);
        border: 1px solid #30363d;
        border-radius: 16px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .hero h1 { font-size: 2rem; margin: 0; color: #58a6ff; letter-spacing: -1px; }
    .hero p  { color: #8b949e; margin: .4rem 0 0; font-size: .95rem; }

    /* metric row */
    .metric-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        text-align: center;
    }
    .metric-label { color: #8b949e; font-size: .8rem; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-family: 'Space Mono', monospace; font-size: 2.4rem; font-weight: 700; }
    .metric-value.green  { color: #3fb950; }
    .metric-value.yellow { color: #d29922; }
    .metric-value.red    { color: #f85149; }

    /* slider label override */
    .slider-label {
        font-family: 'Space Mono', monospace;
        font-size: .85rem;
        color: #8b949e;
        margin-bottom: .3rem;
    }

    /* status pill */
    .pill {
        display: inline-block;
        padding: .25rem .75rem;
        border-radius: 999px;
        font-size: .8rem;
        font-weight: 600;
        font-family: 'Space Mono', monospace;
    }
    .pill-green  { background: #1a3a2a; color: #3fb950; border: 1px solid #238636; }
    .pill-red    { background: #3a1a1a; color: #f85149; border: 1px solid #da3633; }
    .pill-yellow { background: #3a2e1a; color: #d29922; border: 1px solid #9e6a03; }

    /* save button */
    .stButton > button {
        background: #238636 !important;
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Space Mono', monospace !important;
        font-size: .9rem !important;
        padding: .6rem 2rem !important;
        width: 100%;
        transition: background .2s;
    }
    .stButton > button:hover { background: #2ea043 !important; }

    /* divider */
    hr { border-color: #30363d !important; }

    /* hide streamlit branding */
    #MainMenu, footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── helpers ───────────────────────────────────────────────────────────────────

def load_thresholds():
    try:
        data = json.loads(THRESHOLDS_FILE.read_text())
        return int(data.get("upper", 85)), int(data.get("lower", 20))
    except Exception:
        return 85, 20


def save_thresholds(upper: int, lower: int):
    THRESHOLDS_FILE.write_text(json.dumps({"upper": upper, "lower": lower}, indent=2))


def get_battery():
    try:
        import psutil
        b = psutil.sensors_battery()
        if b:
            return round(b.percent, 1), b.power_plugged
    except ImportError:
        pass

    system = platform.system()
    if system == "Darwin":
        try:
            import re
            out = subprocess.check_output(["pmset", "-g", "batt"], text=True)
            m = re.search(r"(\d+)%", out)
            if m:
                return float(m.group(1)), ("AC Power" in out or "charging" in out.lower())
        except Exception:
            pass
    elif system == "Linux":
        try:
            from pathlib import Path as P
            import glob
            for base in glob.glob("/sys/class/power_supply/BAT*"):
                cap = P(base) / "capacity"
                status = P(base) / "status"
                if cap.exists():
                    pct = float(cap.read_text().strip())
                    plugged = status.exists() and status.read_text().strip().lower() in ("charging", "full")
                    return pct, plugged
        except Exception:
            pass
    return None, None


def battery_color(pct, lower, upper):
    if pct is None:
        return "yellow"
    if pct >= upper:
        return "green"
    if pct <= lower:
        return "red"
    return "green"


# ── layout ────────────────────────────────────────────────────────────────────

st.markdown(
    '<div class="hero"><h1>🔋 Battery Notifier</h1>'
    '<p>Set your charge thresholds — get notified when to plug in or unplug.</p></div>',
    unsafe_allow_html=True,
)

upper_saved, lower_saved = load_thresholds()
pct, plugged = get_battery()

# ── live battery row ──────────────────────────────────────────────────────────

col1, col2, col3 = st.columns(3)

with col1:
    color = battery_color(pct, lower_saved, upper_saved)
    val = f"{pct:.0f}%" if pct is not None else "N/A"
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-label">Current Level</div>'
        f'<div class="metric-value {color}">{val}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with col2:
    if plugged is None:
        pill = '<span class="pill pill-yellow">UNKNOWN</span>'
    elif plugged:
        pill = '<span class="pill pill-green">⚡ CHARGING</span>'
    else:
        pill = '<span class="pill pill-red">🔋 ON BATTERY</span>'
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-label">Status</div>'
        f'<div style="margin-top:.8rem">{pill}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with col3:
    if pct is not None:
        if pct >= upper_saved and plugged:
            advice = '<span class="pill pill-red">UNPLUG NOW</span>'
        elif pct <= lower_saved and not plugged:
            advice = '<span class="pill pill-yellow">PLUG IN</span>'
        else:
            advice = '<span class="pill pill-green">ALL GOOD</span>'
    else:
        advice = '<span class="pill pill-yellow">—</span>'
    st.markdown(
        f'<div class="metric-card">'
        f'<div class="metric-label">Advice</div>'
        f'<div style="margin-top:.8rem">{advice}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")
st.markdown("<br>", unsafe_allow_html=True)

# ── threshold sliders ─────────────────────────────────────────────────────────

st.markdown("### ⚙️ Thresholds")
st.markdown(
    "<p style='color:#8b949e;font-size:.9rem;margin-top:-.5rem'>"
    "Notifications fire when the battery crosses these limits.</p>",
    unsafe_allow_html=True,
)

col_a, col_b = st.columns(2)

with col_a:
    st.markdown('<div class="slider-label">🔴 UPPER LIMIT — "Unplug charger"</div>', unsafe_allow_html=True)
    upper = st.slider(
        "Upper threshold",
        min_value=50, max_value=100,
        value=upper_saved,
        step=1,
        format="%d%%",
        label_visibility="collapsed",
        key="upper_slider",
    )

with col_b:
    st.markdown('<div class="slider-label">🟡 LOWER LIMIT — "Plug in charger"</div>', unsafe_allow_html=True)
    lower = st.slider(
        "Lower threshold",
        min_value=1, max_value=50,
        value=lower_saved,
        step=1,
        format="%d%%",
        label_visibility="collapsed",
        key="lower_slider",
    )

st.markdown("<br>", unsafe_allow_html=True)

# visual range bar
bar_pct = pct if pct is not None else 50
lower_pos = lower
upper_pos = upper

st.markdown(
    f"""
    <div style="position:relative;height:28px;background:#21262d;border-radius:8px;overflow:hidden;border:1px solid #30363d;margin-bottom:1.5rem">
      <!-- safe zone -->
      <div style="position:absolute;left:{lower_pos}%;width:{upper_pos-lower_pos}%;height:100%;background:#1a3a2a;"></div>
      <!-- current battery -->
      <div style="position:absolute;left:0;width:{bar_pct}%;height:100%;
           background:{'#3fb950' if bar_pct > lower else '#f85149'};opacity:.7;border-radius:8px 0 0 8px;"></div>
      <!-- lower marker -->
      <div style="position:absolute;left:{lower_pos}%;top:0;width:2px;height:100%;background:#d29922;"></div>
      <!-- upper marker -->
      <div style="position:absolute;left:{upper_pos}%;top:0;width:2px;height:100%;background:#f85149;"></div>
      <!-- labels -->
      <span style="position:absolute;left:{lower_pos+.5}%;top:4px;font-size:.7rem;color:#d29922;font-family:'Space Mono',monospace">↑{lower}%</span>
      <span style="position:absolute;left:{min(upper_pos-5, 88)}%;top:4px;font-size:.7rem;color:#f85149;font-family:'Space Mono',monospace">↑{upper}%</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# save button
if st.button("💾  Save Thresholds"):
    if lower >= upper:
        st.error("Lower threshold must be less than upper threshold.")
    else:
        save_thresholds(upper, lower)
        st.success(f"✅ Saved — notify above **{upper}%** and below **{lower}%**")

# ── footer ────────────────────────────────────────────────────────────────────

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")
st.markdown(
    f"<p style='color:#484f58;font-size:.8rem;text-align:center;font-family:Space Mono,monospace'>"
    f"app.py polls every 30 s · thresholds saved to <code>thresholds.json</code> · "
    f"platform: {platform.system()}</p>",
    unsafe_allow_html=True,
)

# auto-refresh every 30 s so live stats stay current
time.sleep(0)
st.markdown(
    "<script>setTimeout(()=>window.location.reload(), 30000)</script>",
    unsafe_allow_html=True,
)