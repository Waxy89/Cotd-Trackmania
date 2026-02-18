6# -*- coding: utf-8 -*-
import re
import time
import base64
import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Credentials läses från Streamlit Secrets (Settings → Secrets i Streamlit Cloud)
# Lägg till detta i dina secrets:
#
# UBI_EMAIL = "din@email.com"
# UBI_PASSWORD = "dittlösenord"
# OAUTH_CLIENT_ID = "..."        # från api.trackmania.com
# OAUTH_CLIENT_SECRET = "..."

UBI_EMAIL = "u1010676629@gmail.com"
UBI_PASSWORD = "wNGsJ39F?C_VQ%c"
OAUTH_CLIENT_ID = "343d2fbc84126eb35a74"
OAUTH_CLIENT_SECRET = "d538cffe0319b3ddcac29e33337c2364debda346"

USER_AGENT = "COTD-dev-tracker / waxy89@personal-project"
UBI_APP_ID = "86263886-327a-4328-ac69-527f0d20a237"  # Trackmania officiellt Ubi-AppId
BASE_URL = "https://trackmania.io/api"
BASE_MEET_URL = "https://meet.trackmania.nadeo.club/api"
BASE_LIVE_URL = "https://live-services.trackmania.nadeo.live/api/token"
# FIX 1: Correct base URL — don't include /v2/authentication/token here, build full paths below
BASE_CORE_URL = "https://prod.trackmania.core.nadeo.online"
BASE_OAUTH_URL = "https://api.trackmania.com/api"
HEADERS = {"User-Agent": USER_AGENT}

st.set_page_config(page_title="COTD & Rerun Progress", layout="wide")

st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #0a0a1a 0%, #0d1117 50%, #0a0a1a 100%);
}
.main-title {
    text-align: center;
    font-size: 2.5em;
    font-weight: bold;
    background: linear-gradient(90deg, #FFD700, #FF6B35, #FF2200);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-style: italic;
    margin-bottom: 0;
}
.player-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #2a2a4a;
    border-radius: 15px;
    padding: 20px;
    margin: 10px 0;
}
.player-name {
    font-size: 1.8em;
    font-weight: bold;
    color: #ffffff;
    margin: 0;
}
.player-tag {
    color: #4CAF50;
    font-size: 0.9em;
}
.stat-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #2a2a4a;
    border-radius: 12px;
    padding: 15px;
    text-align: center;
}
.stat-icon { font-size: 1.5em; margin-bottom: 5px; }
.stat-label { color: #888; font-size: 0.8em; text-transform: uppercase; }
.stat-value { font-size: 1.8em; font-weight: bold; color: #FFD700; }
.chart-box {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #2a2a4a;
    border-radius: 15px;
    padding: 15px;
    margin: 15px 0;
}
</style>
""", unsafe_allow_html=True)


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


def get_nadeo_token():
    """
    Ubisoft two-step auth:
    Steg 1 — hämta Ubisoft-ticket via public-ubiservices.ubi.com
    Steg 2 — växla ticket mot Nadeo access/refresh tokens
    """
    # Steg 1: Ubisoft ticket
    ubi_auth = base64.b64encode(f"{UBI_EMAIL}:{UBI_PASSWORD}".encode()).decode()
    ubi_headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Ubi-AppId": UBI_APP_ID,
        "Authorization": f"Basic {ubi_auth}",
    }
    ubi_resp = requests.post(
        "https://public-ubiservices.ubi.com/v3/profiles/sessions",
        headers=ubi_headers,
        json={},
        timeout=15,
    )
    if ubi_resp.status_code != 200:
        st.error(f"Ubisoft auth misslyckades ({ubi_resp.status_code}): {ubi_resp.text}")
        st.stop()
    ubi_ticket = ubi_resp.json().get("ticket")
    if not ubi_ticket:
        st.error("Fick inget Ubisoft-ticket i svaret.")
        st.stop()

    # Steg 2: Växla mot Nadeo-token (NadeoLiveServices = Meet + Live API)
    nadeo_headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Authorization": f"ubi_v1 t={ubi_ticket}",
    }
    nadeo_resp = requests.post(
        f"{BASE_CORE_URL}/v2/authentication/token/ubiservices",
        headers=nadeo_headers,
        json={"audience": "NadeoLiveServices"},
        timeout=15,
    )
    if nadeo_resp.status_code != 200:
        st.error(f"Nadeo auth misslyckades ({nadeo_resp.status_code}): {nadeo_resp.text}")
        st.stop()
    data = nadeo_resp.json()
    return data["accessToken"], data["refreshToken"]


def refresh_nadeo_token(refresh_token):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
        "Authorization": f"nadeo_v1 t={refresh_token}"
    }
    url = f"{BASE_CORE_URL}/v2/authentication/token/refresh"
    resp = requests.post(url, headers=headers)
    if resp.status_code != 200:
        st.error("Token refresh failed: " + resp.text)
        st.stop()
    data = resp.json()
    return data["accessToken"], data["refreshToken"]


def get_oauth_token():
    body = f"grant_type=client_credentials&client_id={OAUTH_CLIENT_ID}&client_secret={OAUTH_CLIENT_SECRET}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(f"{BASE_OAUTH_URL}/access_token", headers=headers, data=body)
    if resp.status_code != 200:
        st.error("OAuth failed: " + resp.text)
        st.stop()
    return resp.json()["access_token"]


def fetch_competitions(access_token, max_items, progress_bar):
    competitions = []
    offset = 0
    pages = (max_items // 100) + 1
    for page in range(pages):
        progress_bar.progress(min((page + 1) / pages, 0.99), text=f"Hämtar sida {page + 1} / {pages}")
        url = f"{BASE_MEET_URL}/competitions?length=100&offset={offset}"
        headers = {"Authorization": f"nadeo_v1 t={access_token}", "User-Agent": USER_AGENT}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
        except requests.RequestException:
            break
        if resp.status_code == 429:
            time.sleep(2)
            resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        # FIX 3: More robust name filter — docs show both "Cup of the Day" and "COTD" variants
        filtered = [c for c in data if re.search(
            r"(COTD|Cup of the Day).*\d{4}-\d{2}-\d{2}",
            c.get("name", ""),
            re.IGNORECASE
        )]
        competitions.extend(filtered)
        if len(competitions) >= max_items:
            break
        offset += 100
        time.sleep(0.3)
    progress_bar.progress(1.0, text="Klar!")
    return competitions[:max_items]


def fetch_rounds(access_token, competition_id):
    url = f"{BASE_MEET_URL}/competitions/{competition_id}/rounds"
    headers = {"Authorization": f"nadeo_v1 t={access_token}", "User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers)
    return resp.json() if resp.status_code == 200 else []


def fetch_competition_leaderboard_position(access_token, comp_id, player_id):
    """
    Fast check: use competition leaderboard to find if player participated
    and get their approximate rank. Pages through until player found.
    Returns (rank, total) or (None, None) if not found.
    """
    offset = 0
    total = None
    while True:
        url = f"{BASE_MEET_URL}/competitions/{comp_id}/leaderboard?length=100&offset={offset}"
        headers = {"Authorization": f"nadeo_v1 t={access_token}", "User-Agent": USER_AGENT}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
        except requests.RequestException:
            return None, None
        if resp.status_code != 200:
            return None, None
        data = resp.json()
        # Competition leaderboard returns a list directly
        entries = data if isinstance(data, list) else data.get("results", [])
        if not entries:
            return None, None
        for entry in entries:
            if entry.get("participant") == player_id:
                return entry.get("rank"), total
        offset += 100
        time.sleep(0.15)
        if offset > 5000:
            break
    return None, None


def fetch_qual_leaderboard_for_player(access_token, challenge_id, player_id, approx_rank=None):
    """
    Fetches the challenge leaderboard for a specific player.
    If approx_rank is known, jumps close to that page first to find the player fast.
    Returns (result_dict, cardinal) or (None, cardinal).
    """
    cardinal = None

    # Get cardinal from page 0 always (fast, 1 request)
    url0 = f"{BASE_MEET_URL}/challenges/{challenge_id}/leaderboard?length=100&offset=0"
    headers = {"Authorization": f"nadeo_v1 t={access_token}", "User-Agent": USER_AGENT}
    try:
        resp0 = requests.get(url0, headers=headers, timeout=15)
        if resp0.status_code == 200:
            body0 = resp0.json()
            cardinal = body0.get("cardinal", 0)
            results0 = body0.get("results", [])
            hit = next((r for r in results0 if r.get("player") == player_id), None)
            if hit:
                return hit, cardinal
    except requests.RequestException:
        return None, cardinal

    # If we have approx rank, jump to that page first
    offsets_to_try = []
    if approx_rank and approx_rank > 100:
        jump = max(0, (approx_rank // 100) * 100 - 100)
        offsets_to_try = list(range(jump, min(jump + 300, cardinal or 10000), 100))
        # Add remaining pages not already covered
        all_offsets = list(range(100, cardinal or 10000, 100))
        for o in all_offsets:
            if o not in offsets_to_try:
                offsets_to_try.append(o)
    else:
        offsets_to_try = list(range(100, cardinal or 10000, 100))

    for offset in offsets_to_try:
        if cardinal and offset >= cardinal:
            break
        url = f"{BASE_MEET_URL}/challenges/{challenge_id}/leaderboard?length=100&offset={offset}"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
        except requests.RequestException:
            break
        if resp.status_code != 200:
            break
        body = resp.json()
        results = body.get("results", [])
        if not results:
            break
        hit = next((r for r in results if r.get("player") == player_id), None)
        if hit:
            return hit, cardinal
        time.sleep(0.15)

    return None, cardinal


def fetch_matches(access_token, round_id):
    url = f"{BASE_MEET_URL}/rounds/{round_id}/matches?length=100&offset=0"
    headers = {"Authorization": f"nadeo_v1 t={access_token}", "User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers)
    return resp.json().get("matches", []) if resp.status_code == 200 else []


def fetch_match_results(access_token, comp_match_id, player_id):
    """
    API uses 'participant' field in match results. Max length per docs is 255.
    Real-world data shows results can be a LIST of round-result objects
    (roundPosition 0..N), where early rounds have rank=null. We want the
    result from the highest roundPosition where the player has a non-null rank.
    """
    url = f"{BASE_MEET_URL}/matches/{comp_match_id}/results?length=255&offset=0"
    headers = {"Authorization": f"nadeo_v1 t={access_token}", "User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return None
    data = resp.json()

    # Data may be a list of round-result objects, or a single object with 'results'
    if isinstance(data, list):
        round_objects = data
    else:
        round_objects = [data]

    best = None
    best_pos = -1
    for round_obj in round_objects:
        round_pos = round_obj.get("roundPosition", 0)
        for r in round_obj.get("results", []):
            if r.get("participant") == player_id and r.get("rank") is not None:
                if round_pos > best_pos:
                    best_pos = round_pos
                    best = dict(r)
                    best["_roundPosition"] = round_pos
    return best


def fetch_display_names(oauth_token, account_ids):
    names = {}
    for i in range(0, len(account_ids), 50):
        ids_str = "&".join([f"accountId[]={id}" for id in account_ids[i:i+50]])
        url = f"{BASE_OAUTH_URL}/display-names?{ids_str}"
        headers = {"Authorization": f"Bearer {oauth_token}", "User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            names.update(resp.json())
        time.sleep(0.3)
    return names


def fetch_totd_map(access_token, date_str):
    """
    FIX 8: Correct response structure per API docs:
    - Response root key is 'monthList', not a bare list
    - Each day has 'startTimestamp' (epoch) and 'monthDay' (int), not 'startDate' string
    - Need to derive the date from year/month/monthDay fields of the parent month object
    - Offset 0 = current month; need to calculate correct month offset for historical dates
    """
    target_date = pd.Timestamp(date_str, tz="UTC")
    now = pd.Timestamp.now(tz="UTC")

    # Calculate how many months back we need to go
    months_back = (now.year - target_date.year) * 12 + (now.month - target_date.month)

    # Fetch just the relevant month (1 month at a time to be efficient)
    url = f"{BASE_LIVE_URL}/campaign/month?length=1&offset={months_back}&royal=false"
    headers = {"Authorization": f"nadeo_v1 t={access_token}", "User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None

    data = resp.json()
    # FIX: Correct root key is 'monthList'
    month_list = data.get("monthList", [])
    for month_obj in month_list:
        year = month_obj.get("year")
        month = month_obj.get("month")
        for day_obj in month_obj.get("days", []):
            month_day = day_obj.get("monthDay")
            if not month_day:
                continue
            # Build a date string from year/month/monthDay
            day_date_str = f"{year}-{month:02d}-{month_day:02d}"
            if day_date_str == date_str:
                return day_obj.get("mapUid")
    return None


def fetch_map_info(access_token, map_uid):
    if not map_uid:
        return {}
    url = f"{BASE_LIVE_URL}/map/{map_uid}"
    headers = {"Authorization": f"nadeo_v1 t={access_token}", "User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers)
    return resp.json() if resp.status_code == 200 else {}


def process_cotd_data(competitions, access_token, oauth_token, player_id, status_text):
    results = []
    total = len(competitions)

    for i, comp in enumerate(competitions):
        name = comp["name"]
        comp_id = comp["id"]
        timestamp = pd.to_datetime(comp["startDate"], unit="s", utc=True)
        date_str = timestamp.strftime("%Y-%m-%d")

        edition_match = re.search(r"#(\d+)", name)
        edition_num = int(edition_match.group(1)) if edition_match else 1
        type_ = "Primary" if edition_num == 1 else "Rerun"

        status_text.text(f"[{i+1}/{total}] {date_str} {name} …")

        # STEP 1: Fast check — did the player even participate?
        # Competition leaderboard: 1 request, skip entire comp if player absent
        comp_rank, _ = fetch_competition_leaderboard_position(access_token, comp_id, player_id)
        if comp_rank is None:
            # Player didn't participate — skip all further API calls for this comp
            time.sleep(0.1)
            continue

        # STEP 2: Get rounds (needed for qual challenge + match list)
        rounds = fetch_rounds(access_token, comp_id)
        if not rounds:
            continue
        round_ = rounds[0]
        round_id = round_["id"]
        challenge_id = round_.get("qualifierChallengeId")

        # STEP 3: Qual leaderboard — use comp_rank as hint to jump to right page
        player_qual, total_players = fetch_qual_leaderboard_for_player(
            access_token, challenge_id, player_id, approx_rank=comp_rank
        )

        # STEP 4: Find which division match the player was in
        # Estimate which division based on qual rank to skip irrelevant matches
        div = None
        rank = None
        div_rank = None
        matches = fetch_matches(access_token, round_id)

        # Sort matches by position so div 1 = position 0 comes first
        matches_sorted = sorted(matches, key=lambda m: m.get("position", 0))

        for match in matches_sorted:
            comp_match_id = match["id"]
            match_name = match.get("name", "")
            div_from_name = re.search(r"[Dd]ivision\s*(\d+)", match_name)

            player_match = fetch_match_results(access_token, comp_match_id, player_id)
            if player_match:
                if div_from_name:
                    div = int(div_from_name.group(1))
                else:
                    div = match.get("position", 0) + 1
                rank = player_match["rank"]
                div_rank = player_match["rank"]
                break
            time.sleep(0.1)

        results.append({
            "id": comp_id,
            "timestamp": timestamp,
            "name": name,
            "edition": edition_num,
            "div": div,
            "rank": rank,
            "div_rank": div_rank,
            "qual_score": player_qual["score"] if player_qual else None,
            "qual_rank": player_qual["rank"] if player_qual else None,
            "total_players": total_players,
            "type": type_
        })
        time.sleep(0.2)

    return results


def process_dataframe(results):
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["date_local"] = df["timestamp"].dt.tz_convert("Europe/Stockholm")
    df["date_only"] = df["date_local"].dt.date
    df["date_str"] = df["date_local"].dt.strftime("%Y-%m-%d %H:%M")
    for col in ["div", "rank", "total_players", "div_rank", "qual_rank"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # FIX 11: Use qual_rank for percentile, not cup rank (qual covers all participants)
    mask = df["total_players"].notna() & (df["total_players"] > 0) & df["qual_rank"].notna()
    df.loc[mask, "percentile"] = (1 - df.loc[mask, "qual_rank"] / df.loc[mask, "total_players"]) * 100
    df = df.dropna(subset=["div", "rank"])
    return df


# ─── UI ────────────────────────────────────────────────────────────────────────

st.markdown('<p class="main-title">COTD & RERUN PROGRESS</p>', unsafe_allow_html=True)

with st.sidebar:
    username_input = st.text_input("Spelarnamn", value="Waxyhaxxy")
    show_primary = st.checkbox("Visa Main COTD", value=True)
    show_reruns = st.checkbox("Visa Reruns", value=True)
    max_competitions = st.slider("Max competitions", 1, 3000, 500)
    window_size = st.slider("Glidande medelvärde", 1, 50, 10)

if not username_input:
    st.stop()

with st.spinner("Söker spelare..."):
    player_id, display_name = search_player(username_input)

if not player_id:
    st.error("Hittade ingen spelare: " + username_input)
    st.stop()

st.markdown(
    '<div class="player-card"><p class="player-name">' + display_name +
    '</p><p class="player-tag">Trackmania Competitor</p></div>',
    unsafe_allow_html=True
)

progress_bar = st.progress(0, text="Startar...")

access_token, refresh_token = get_nadeo_token()
oauth_token = get_oauth_token()
competitions = fetch_competitions(access_token, max_competitions, progress_bar)
progress_bar.empty()

status_text = st.empty()
results = process_cotd_data(competitions, access_token, oauth_token, player_id, status_text)
status_text.empty()

if not results:
    st.error("Inga COTD-resultat hittades.")
    st.stop()

df = process_dataframe(results)
if df.empty:
    st.error("Ingen giltig data.")
    st.stop()

filter_types = []
if show_primary:
    filter_types.append("Primary")
if show_reruns:
    filter_types.append("Rerun")
dfv = df[df["type"].isin(filter_types)].copy()
if dfv.empty:
    st.warning("Ingen data med valda filter.")
    st.stop()

pct = dfv["percentile"].mean() if "percentile" in dfv.columns and dfv["percentile"].notna().any() else 0

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown('<div class="stat-card"><div class="stat-icon">&#127942;</div><div class="stat-label">Total COTDs</div><div class="stat-value">' + str(len(dfv)) + '</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown('<div class="stat-card"><div class="stat-icon">&#129351;</div><div class="stat-label">Best Division</div><div class="stat-value">#' + str(int(dfv["div"].min())) + '</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown('<div class="stat-card"><div class="stat-icon">&#128202;</div><div class="stat-label">Avg. Division</div><div class="stat-value">' + str(round(dfv["div"].mean(), 1)) + '</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown('<div class="stat-card"><div class="stat-icon">&#128200;</div><div class="stat-label">Qual Percentil</div><div class="stat-value">Top ' + str(round(pct, 1)) + '%</div></div>', unsafe_allow_html=True)

dfv = dfv.sort_values("timestamp").reset_index(drop=True)
dfv["MA"] = dfv["div"].rolling(window=window_size, min_periods=1).mean()

st.markdown('<div class="chart-box">', unsafe_allow_html=True)

fig = go.Figure()

for label, color, filt in [
    ("Div 1-10", "#FFD700", dfv["div_rank"] <= 10),
    ("Div 11-30", "#FFA500", (dfv["div_rank"] > 10) & (dfv["div_rank"] <= 30)),
    ("Div 31-50", "#FF4444", (dfv["div_rank"] > 30) & (dfv["div_rank"] <= 50)),
    ("Div 51+", "#AA0000", dfv["div_rank"] > 50),
]:
    s = dfv[filt]
    if s.empty:
        continue
    fig.add_trace(go.Scatter(
        x=s["timestamp"], y=s["div"], mode="markers", name=label,
        marker=dict(color=color, opacity=0.7, size=6),
        customdata=s[["name", "div", "rank", "date_str", "div_rank", "qual_rank", "total_players"]].values,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Division: %{customdata[1]} | Cup Rank: %{customdata[2]}<br>"
            "Div Rank: %{customdata[4]}<br>"
            "Qual Rank: %{customdata[5]} / %{customdata[6]}<br>"
            "%{customdata[3]}<extra></extra>"
        ),
    ))

fig.add_trace(go.Scatter(
    x=dfv["timestamp"], y=dfv["MA"], mode="lines", name="Trend",
    line=dict(color="#FF2200", width=3),
))

fig.update_layout(
    title=dict(text="Division Over Time", font=dict(size=20, color="#ffffff"), x=0.02),
    template="plotly_dark",
    height=500,
    xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", title=""),
    yaxis=dict(title="Division", showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
    legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="center", x=0.5, font=dict(size=13)),
    plot_bgcolor="rgba(10,10,30,0.8)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=50, r=20, t=50, b=60),
)
fig.update_yaxes(autorange="reversed")

st.plotly_chart(fig, use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("### Senaste matcher")
recent = dfv.nlargest(10, "timestamp")[
    ["id", "date_str", "name", "div", "rank", "div_rank", "qual_rank", "total_players", "type"]
].copy()
recent.columns = ["ID", "Start time", "Cup", "Div", "Cup Rank", "Div Rank", "Qual Rank", "Total Players", "Type"]
st.dataframe(recent, hide_index=True, use_container_width=True)

with st.expander("Visa all data"):
    st.dataframe(
        dfv[["date_str", "name", "type", "div", "rank", "div_rank", "qual_rank", "total_players"]]
        .sort_values("date_str", ascending=False),
        hide_index=True,
    )
