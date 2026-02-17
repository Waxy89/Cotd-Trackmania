# -*- coding: utf-8 -*-
import re
import time
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
USER_AGENT = "COTD-dev-tracker / waxy89@personal-project"
BASE_URL    = "https://trackmania.io/api"
HEADERS     = {"User-Agent": USER_AGENT}

st.set_page_config(
    page_title="COTD & Rerun Progress",
    page_icon="🏁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Styling – matchar HTML-dashboarden
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=Exo+2:wght@400;600;700;900&display=swap');

html, body, [class*="css"] { font-family: 'Exo 2', sans-serif; }

.stApp {
    background: linear-gradient(160deg, #0a0a0a 0%, #0d0d10 60%, #0a0a0a 100%);
}

/* Hero title */
.hero-title {
    text-align: center;
    font-family: 'Rajdhani', sans-serif;
    font-size: 2.8em;
    font-weight: 700;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin: 0.2em 0 0.1em;
    background: linear-gradient(90deg, #ffffff 20%, #ff4500 50%, #4cff00 80%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-shadow: none;
    filter: drop-shadow(0 0 30px rgba(255,100,0,0.4));
}
.hero-sub {
    text-align: center;
    font-family: 'Rajdhani', sans-serif;
    font-size: 1em;
    letter-spacing: 6px;
    color: #444;
    text-transform: uppercase;
    margin-bottom: 1.2em;
}

/* Stat cards */
.stat-row { display: flex; gap: 12px; margin: 16px 0; }
.stat-card {
    flex: 1;
    background: #161616;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 14px 18px;
    display: flex;
    align-items: center;
    gap: 14px;
    position: relative;
    overflow: hidden;
}
.stat-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
}
.stat-card.gold::before   { background: #f5a623; }
.stat-card.yellow::before { background: #ffd600; }
.stat-card.green::before  { background: #4caf50; }
.stat-card.blue::before   { background: #42a5f5; }
.stat-icon { font-size: 1.8em; }
.stat-label { font-size: 0.7em; color: #666; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }
.stat-value { font-size: 1.9em; font-weight: 900; color: #fff; line-height: 1.1; }
.stat-value.small { font-size: 1.3em; }

/* Player card */
.player-card {
    background: #161616;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    margin: 12px 0;
}
.player-name { font-size: 1.7em; font-weight: 900; color: #fff; margin: 0; }
.player-tag  { color: #42a5f5; font-size: 0.85em; margin: 2px 0 0; }
.player-tag::before { content: '✔  '; }

/* Chart box */
.chart-box {
    background: #161616;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 6px 4px 0;
    margin: 8px 0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0e0e0e !important;
    border-right: 1px solid #1e1e1e;
}
section[data-testid="stSidebar"] * { font-family: 'Exo 2', sans-serif !important; }

/* Hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1rem; }

/* Divider */
hr { border: none; border-top: 1px solid #222; margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────
def clean_tm_name(name: str) -> str:
    s = re.sub(r"\$[0-9a-fA-F]{3}", "", name)
    s = re.sub(r"\$[lhp]\[.*?\]", "", s)
    s = re.sub(r"\$[oiszwntgLHPOISZWNTG$]", "", s)
    return re.sub(r"\$", "", s).strip()


def search_player(username: str):
    url = BASE_URL + "/players/find?search=" + requests.utils.quote(username)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException:
        return None, None, None
    if r.status_code != 200:
        return None, None, None
    try:
        data = r.json()
    except ValueError:
        return None, None, None

    players = data if isinstance(data, list) else data.get("players", [])
    if not players:
        return None, None, None

    for p in players:
        obj = p.get("player", p) if isinstance(p, dict) else {}
        raw = obj.get("name", "")
        pid = obj.get("id", "")
        zone = obj.get("zone", None)
        if clean_tm_name(raw).lower() == username.lower():
            return pid, clean_tm_name(raw), zone

    first = players[0]
    obj = first.get("player", first) if isinstance(first, dict) else {}
    return obj.get("id"), clean_tm_name(obj.get("name", "")), obj.get("zone")


def fetch_cotd_history(player_id: str, max_pages: int, progress_bar) -> list:
    all_results = []
    for page in range(max_pages):
        progress_bar.progress(
            min((page + 1) / max_pages, 0.99),
            text=f"Hämtar sida {page + 1} / {max_pages}…"
        )
        url = BASE_URL + f"/player/{player_id}/cotd/{page}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException:
            break

        if r.status_code == 429:
            time.sleep(3)
            try:
                r = requests.get(url, headers=HEADERS, timeout=15)
            except requests.RequestException:
                break

        if r.status_code != 200:
            break

        try:
            data = r.json()
        except ValueError:
            break

        # trackmania.io returns {"cotds": [...], "total": N}
        if isinstance(data, dict):
            cotds = data.get("cotds", data.get("cups", data.get("results", [])))
        elif isinstance(data, list):
            cotds = data
        else:
            break

        if not cotds:
            break

        for entry in cotds:
            if not isinstance(entry, dict):
                continue
            all_results.append({
                "id":           entry.get("id", 0),
                "timestamp":    entry.get("timestamp", ""),
                "name":         entry.get("name", ""),
                "div":          entry.get("div"),
                "rank":         entry.get("rank"),
                "div_rank":     entry.get("divrank", entry.get("div_rank")),
                "score":        entry.get("score", 0),
                "total_players": entry.get("totalplayers", entry.get("total_players")),
            })

        time.sleep(0.25)

    progress_bar.progress(1.0, text="✔ Klar!")
    return all_results


def process_dataframe(results: list) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).copy()
    df = df.sort_values("timestamp").reset_index(drop=True)

    df["date_local"] = df["timestamp"].dt.tz_convert("Europe/Stockholm")
    df["date_only"]  = df["date_local"].dt.date
    df["date_str"]   = df["date_local"].dt.strftime("%Y-%m-%d %H:%M")

    # First entry per calendar day → Primary COTD, rest → Rerun
    first_of_day = df.groupby("date_only")["timestamp"].idxmin()
    df["type"] = "Rerun"
    df.loc[first_of_day, "type"] = "Primary"

    for col in ["div", "rank", "total_players", "div_rank"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    mask = df["total_players"].notna() & (df["total_players"] > 0) & df["rank"].notna()
    df.loc[mask, "percentile"] = (
        (1 - df.loc[mask, "rank"] / df.loc[mask, "total_players"]) * 100
    )

    df = df.dropna(subset=["div", "rank"])
    return df


def div_rank_color(dr):
    """Return scatter color based on div_rank (placement within division)."""
    if pd.isna(dr):
        return "#888888"
    if dr <= 10:
        return "#ffd600"
    if dr <= 30:
        return "#ff8c00"
    if dr <= 50:
        return "#ff3d00"
    return "#e53935"


def flag_emoji(zone) -> str:
    mapping = {
        "Sweden": "🇸🇪", "France": "🇫🇷", "Germany": "🇩🇪",
        "United States": "🇺🇸", "Norway": "🇳🇴", "Denmark": "🇩🇰",
        "Finland": "🇫🇮", "Netherlands": "🇳🇱", "Belgium": "🇧🇪",
        "Spain": "🇪🇸", "Italy": "🇮🇹", "Poland": "🇵🇱",
        "Brazil": "🇧🇷", "Canada": "🇨🇦", "United Kingdom": "🇬🇧",
        "Portugal": "🇵🇹", "Russia": "🇷🇺", "Australia": "🇦🇺",
        "Switzerland": "🇨🇭", "Austria": "🇦🇹", "Czech Republic": "🇨🇿",
    }
    if not zone:
        return "🌍"
    return mapping.get(zone.get("name", ""), "🌍")


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Inställningar")
    st.markdown("---")
    username_input  = st.text_input("👤 Spelarnamn", value="Waxyhaxxy")
    st.markdown("---")
    show_primary    = st.checkbox("⭐ Visa Main COTD", value=True)
    show_reruns     = st.checkbox("🔁 Visa Reruns", value=True)
    st.markdown("---")
    max_pages_limit = st.slider("📄 Max sidor att hämta", 1, 500, 50,
                                help="1 sida ≈ 25 resultat")
    window_size     = st.slider("📈 Glidande medelvärde", 1, 50, 10)
    metric_choice   = st.radio("📊 Metrik", ["Division", "Global Rank", "Percentil"])
    st.markdown("---")
    st.caption("Data från trackmania.io")

# ─────────────────────────────────────────────
# Hero
# ─────────────────────────────────────────────
st.markdown('<p class="hero-title">COTD &amp; RERUN PROGRESS</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-sub">trackmania.io</p>', unsafe_allow_html=True)

if not username_input:
    st.info("Ange ett spelarnamn i sidopanelen.")
    st.stop()

# ─────────────────────────────────────────────
# Search player
# ─────────────────────────────────────────────
with st.spinner("🔍 Söker spelare…"):
    player_id, display_name, zone = search_player(username_input)

if not player_id:
    st.error(f"❌ Hittade ingen spelare: **{username_input}**")
    st.stop()

flag = flag_emoji(zone)
st.markdown(f"""
<div class="player-card">
  <span style="font-size:2.5em">{flag}</span>
  <div>
    <p class="player-name">{display_name}</p>
    <p class="player-tag">Trackmania Competitor</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Fetch data
# ─────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def load_data(pid, max_pages):
    bar = st.progress(0, text="Startar…")
    results = fetch_cotd_history(pid, max_pages, bar)
    bar.empty()
    return results

with st.spinner("📡 Hämtar COTD-historik…"):
    raw_results = load_data(player_id, max_pages_limit)

if not raw_results:
    st.error("Inga COTD-resultat hittades.")
    st.stop()

df = process_dataframe(raw_results)
if df.empty:
    st.error("Ingen giltig data efter bearbetning.")
    st.stop()

# ─────────────────────────────────────────────
# Filter by type
# ─────────────────────────────────────────────
filter_types = []
if show_primary: filter_types.append("Primary")
if show_reruns:  filter_types.append("Rerun")

dfv = df[df["type"].isin(filter_types)].copy()
if dfv.empty:
    st.warning("Ingen data med valda filter.")
    st.stop()

# ─────────────────────────────────────────────
# Stat cards
# ─────────────────────────────────────────────
pct_mean = dfv["percentile"].mean() if dfv["percentile"].notna().any() else 0
best_div  = int(dfv["div"].min())
avg_div   = round(dfv["div"].mean(), 1)
total     = len(dfv)

st.markdown(f"""
<div class="stat-row">
  <div class="stat-card gold">
    <span class="stat-icon">🏆</span>
    <div><div class="stat-label">Total COTDs</div><div class="stat-value">{total}</div></div>
  </div>
  <div class="stat-card yellow">
    <span class="stat-icon">🥇</span>
    <div><div class="stat-label">Bästa Division</div><div class="stat-value">#{best_div}</div></div>
  </div>
  <div class="stat-card green">
    <span class="stat-icon">📊</span>
    <div><div class="stat-label">Snitt Division</div><div class="stat-value">{avg_div}</div></div>
  </div>
  <div class="stat-card blue">
    <span class="stat-icon">🎯</span>
    <div><div class="stat-label">Snitt Percentil</div><div class="stat-value small">Top {round(100 - pct_mean, 1)}%</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Pick metric
# ─────────────────────────────────────────────
if metric_choice == "Division":
    y_col, y_label, rev = "div", "Division", True
elif metric_choice == "Global Rank":
    y_col, y_label, rev = "rank", "Global Rank", True
else:
    y_col, y_label, rev = "percentile", "Percentil (%)", False

dfv = dfv.sort_values("timestamp").reset_index(drop=True)
dfv["MA"] = dfv[y_col].rolling(window=window_size, min_periods=1).mean()

# ─────────────────────────────────────────────
# Build Plotly chart
# ─────────────────────────────────────────────
fig = go.Figure()

# Scatter colored by div_rank
colors = dfv["div_rank"].apply(div_rank_color).tolist()
hover_data = dfv[["name", "div", "rank", "div_rank", "date_str", "type"]].values

fig.add_trace(go.Scatter(
    x=dfv["timestamp"],
    y=dfv[y_col],
    mode="markers",
    name="Resultat",
    marker=dict(
        color=colors,
        size=6,
        opacity=0.75,
        line=dict(width=0),
    ),
    customdata=hover_data,
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "Div: %{customdata[1]:.0f} &nbsp;|&nbsp; Rank: %{customdata[2]:.0f}<br>"
        "Div Rank: %{customdata[3]}<br>"
        "Typ: %{customdata[5]}<br>"
        "%{customdata[4]}"
        "<extra></extra>"
    ),
))

# Moving average trendline
fig.add_trace(go.Scatter(
    x=dfv["timestamp"],
    y=dfv["MA"],
    mode="lines",
    name=f"MA({window_size})",
    line=dict(color="#ffffff", width=2.5),
    hoverinfo="skip",
))

fig.update_layout(
    title=dict(
        text=f"{display_name}  –  {metric_choice} över tid",
        font=dict(family="Rajdhani, sans-serif", size=20, color="#ffffff"),
        x=0.02,
    ),
    template="plotly_dark",
    height=500,
    plot_bgcolor="rgba(10,10,15,0.95)",
    paper_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.05)",
        title="",
        tickfont=dict(color="#555"),
    ),
    yaxis=dict(
        title=y_label,
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        tickfont=dict(color="#555"),
        autorange="reversed" if rev else True,
    ),
    legend=dict(
        orientation="h",
        yanchor="top", y=-0.08,
        xanchor="center", x=0.5,
        font=dict(size=13, color="#aaa"),
        bgcolor="rgba(0,0,0,0)",
    ),
    margin=dict(l=50, r=20, t=50, b=60),
    hovermode="closest",
)

# Color legend annotation
fig.add_annotation(
    text=(
        "<span style='color:#ffd600'>● 1–10</span>  "
        "<span style='color:#ff8c00'>● 11–30</span>  "
        "<span style='color:#ff3d00'>● 31–50</span>  "
        "<span style='color:#e53935'>● 51+</span>  "
        "<span style='color:#aaa'>  (div_rank)</span>"
    ),
    xref="paper", yref="paper",
    x=0.5, y=-0.14,
    showarrow=False,
    font=dict(size=12),
    align="center",
)

st.markdown('<div class="chart-box">', unsafe_allow_html=True)
st.plotly_chart(fig, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Recent matches table
# ─────────────────────────────────────────────
st.markdown("### Senaste matcher")
recent = (
    dfv.sort_values("timestamp", ascending=False)
    .head(15)[["date_str", "name", "type", "div", "rank", "div_rank"]]
    .rename(columns={
        "date_str": "Datum",
        "name": "Cup",
        "type": "Typ",
        "div": "Division",
        "rank": "Rank",
        "div_rank": "Div Rank",
    })
)
st.dataframe(recent, hide_index=True, use_container_width=True)

# ─────────────────────────────────────────────
# Expandable full data
# ─────────────────────────────────────────────
with st.expander("📋 Visa all data"):
    st.dataframe(
        dfv[["date_str", "name", "type", "div", "rank", "div_rank", "percentile"]]
        .sort_values("date_str", ascending=False)
        .rename(columns={
            "date_str": "Datum", "name": "Cup", "type": "Typ",
            "div": "Division", "rank": "Rank",
            "div_rank": "Div Rank", "percentile": "Percentil %",
        }),
        hide_index=True,
        use_container_width=True,
    )
