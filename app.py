# -*- coding: utf-8 -*-
import re
import time
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

USER_AGENT = "COTD-dev-tracker / waxy89@personal-project"
BASE_URL = "https://trackmania.io/api"
HEADERS = {"User-Agent": USER_AGENT}


def clean_tm_name(name):
    cleaned = re.sub(r"\$[0-9a-fA-F]{3}", "", name)
    cleaned = re.sub(r"\$[lhp]\[.*?\]", "", cleaned)
    cleaned = re.sub(r"\$[oiszwntgLHPOISZWNTG$]", "", cleaned)
    cleaned = re.sub(r"\$", "", cleaned)
    return cleaned.strip()


def search_player(username):
    url = BASE_URL + "/players/find?search=" + requests.utils.quote(username)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
    except requests.RequestException:
        return None, None
    if resp.status_code != 200:
        return None, None
    try:
        data = resp.json()
    except ValueError:
        return None, None
    if isinstance(data, list):
        players = data
    elif isinstance(data, dict):
        players = data.get("players", [])
    else:
        players = []
    if not players:
        return None, None
    for p in players:
        if isinstance(p, dict):
            player_obj = p.get("player", p)
            raw_name = player_obj.get("name", "")
            pid = player_obj.get("id", "")
            if clean_tm_name(raw_name).lower() == username.lower():
                return pid, clean_tm_name(raw_name)
    first = players[0]
    if isinstance(first, dict):
        player_obj = first.get("player", first)
        return player_obj.get("id", ""), clean_tm_name(player_obj.get("name", ""))
    return None, None


def fetch_cotd_history(player_id, max_pages, progress_bar):
    all_results = []
    for page in range(max_pages):
        progress_bar.progress(
            min((page + 1) / max_pages, 0.99),
            text="Hamtar sida " + str(page + 1) + " / " + str(max_pages)
        )
        url = BASE_URL + "/player/" + player_id + "/cotd/" + str(page)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException:
            break
        if resp.status_code == 429:
            time.sleep(2)
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
            except requests.RequestException:
                break
        if resp.status_code != 200:
            break
        try:
            data = resp.json()
        except ValueError:
            break
        if page == 0:
            st.write("STATUS:", resp.status_code)
            st.write("KEYS:", list(data.keys()) if isinstance(data, dict) else type(data))
            st.write("COTDS:", "cotds" in data if isinstance(data, dict) else "not dict")
        if isinstance(data, dict):
            cotds = data.get("cups", data.get("cotds", data.get("results", [])))
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
                "id": entry.get("id", 0),
                "timestamp": entry.get("timestamp", ""),
                "name": entry.get("name", ""),
                "div": entry.get("div", None),
                "rank": entry.get("rank", None),
                "div_rank": entry.get("divrank", entry.get("div_rank", None)),
                "score": entry.get("score", 0),
                "total_players": entry.get("totalplayers", None),
            })
        time.sleep(0.3)
    progress_bar.progress(1.0, text="Klar!")
    return all_results


def process_dataframe(results):
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).copy()
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["date_local"] = df["timestamp"].dt.tz_convert("Europe/Stockholm")
    df["date_only"] = df["date_local"].dt.date
    df["date_str"] = df["date_local"].dt.strftime("%Y-%m-%d %H:%M")
    first_of_day = df.groupby("date_only")["timestamp"].idxmin()
    df["type"] = "Rerun"
    df.loc[first_of_day, "type"] = "Primary"
    for col in ["div", "rank", "total_players", "div_rank"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    mask = df["total_players"].notna() & (df["total_players"] > 0) & df["rank"].notna()
    df.loc[mask, "percentile"] = (1 - df.loc[mask, "rank"] / df.loc[mask, "total_players"]) * 100
    df = df.dropna(subset=["div", "rank"])
    return df


st.set_page_config(page_title="COTD Utveckling", layout="wide")
st.title("COTD Utvecklingskurva")

with st.sidebar:
    username_input = st.text_input("Spelarnamn", value="Waxyhaxxy")
    show_primary = st.checkbox("Visa Main COTD", value=True)
    show_reruns = st.checkbox("Visa Reruns", value=True)
    max_pages_limit = st.slider("Max sidor", 1, 500, 50)
    window_size = st.slider("Glidande medelvarde", 1, 50, 10)
    metric_choice = st.radio("Metrik", ["Division", "Global Rank", "Percentil"])

if not username_input:
    st.stop()

with st.spinner("Soker spelare..."):
    player_id, display_name = search_player(username_input)

if not player_id:
    st.error("Hittade ingen spelare: " + username_input)
    st.stop()

st.info("Spelare: " + display_name + " (" + player_id + ")")

progress_bar = st.progress(0, text="Startar...")
results = fetch_cotd_history(player_id, max_pages_limit, progress_bar)
progress_bar.empty()

if not results:
    st.error("Inga COTD-resultat hittades.")
    st.stop()

df = process_dataframe(results)
if df.empty:
    st.error("Ingen giltig data.")
    st.stop()

st.success("Laddade " + str(len(df)) + " resultat for " + display_name)

filter_types = []
if show_primary:
    filter_types.append("Primary")
if show_reruns:
    filter_types.append("Rerun")
dfv = df[df["type"].isin(filter_types)].copy()
if dfv.empty:
    st.warning("Ingen data med valda filter.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Cuper", len(dfv))
c2.metric("Basta div", int(dfv["div"].min()))
c3.metric("Snitt div", str(round(dfv["div"].mean(), 1)))
pct = dfv["percentile"].mean() if "percentile" in dfv.columns and dfv["percentile"].notna().any() else 0
c4.metric("Snitt percentil", str(round(pct, 1)) + "%")

if metric_choice == "Division":
    y_col = "div"
    rev = True
elif metric_choice == "Global Rank":
    y_col = "rank"
    rev = True
else:
    y_col = "percentile"
    rev = False

dfv = dfv.sort_values("timestamp").reset_index(drop=True)
dfv["MA"] = dfv[y_col].rolling(window=window_size, min_periods=1).mean()

fig = go.Figure()
for rt, color in [("Primary", "#00d4ff"), ("Rerun", "#ff6b6b")]:
    s = dfv[dfv["type"] == rt]
    if s.empty:
        continue
    fig.add_trace(go.Scatter(
        x=s["timestamp"], y=s[y_col], mode="markers", name=rt,
        marker=dict(color=color, opacity=0.5, size=6),
        customdata=s[["name", "div", "rank", "date_str"]].values,
        hovertemplate="<b>%{customdata[0]}</b><br>Div:%{customdata[1]} Rank:%{customdata[2]}<br>%{customdata[3]}<extra></extra>",
    ))
fig.add_trace(go.Scatter(
    x=dfv["timestamp"], y=dfv["MA"], mode="lines", name="Trend",
    line=dict(color="white", width=3),
))
fig.update_layout(title=display_name + " - " + metric_choice, template="plotly_dark", height=650)
if rev:
    fig.update_yaxes(autorange="reversed")
st.plotly_chart(fig, use_container_width=True)

with st.expander("Visa all data"):
    st.dataframe(
                dfv[["date_str", "name", "type", "div", "rank"]].sort_values("date_str", ascending=False),
        hide_index=True,
    )