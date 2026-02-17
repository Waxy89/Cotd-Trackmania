Du har klistrat in koden med debug-raderna **felindenterade** — de sitter inuti `except`-blocket istället för efter `resp.json()`. Det är **exakt** det som ger syntaxfelet.

Här är den fixade `fetch_cotd_history`-funktionen med debug-raden på rätt plats:

```python
def fetch_cotd_history(player_id, max_pages, progress_bar):
    """Hamta COTD-historik sida for sida. Returnerar lista av dict."""
    all_results = []

    for page in range(max_pages):
        progress_bar.progress(
            min((page + 1) / max_pages, 0.99),
            text=f"Hamtar sida {page + 1} / {max_pages}..."
        )

        url = f"{BASE_URL}/player/{player_id}/cotd?page={page}"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        except requests.RequestException:
            break

        if resp.status_code == 429:
            import time
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

        # DEBUG: visa forsta sidans API-svar sa du kan se strukturen
        if page == 0:
            st.write("DEBUG API-svar:", data)

        if isinstance(data, dict):
            cotds = data.get("cotds", data.get("results", []))
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
                "total_players": entry.get("totalplayers", entry.get("total_players", None)),
            })

        import time
        time.sleep(0.3)

    progress_bar.progress(1.0, text="Klar!")
    return all_results
```

**Felet var:** debug-raderna `if page == 0:` och `st.write(...)` satt **inuti** `except ValueError:`-blocket med tab-indentering istället för spaces, så Python tolkade det som ogiltig syntax.

**Vad du gör nu:**

1. Byt ut **hela** `fetch_cotd_history`-funktionen i din fil mot koden ovan
2. Se till att filen **bara använder spaces** (inte tabs) — i VS Code: tryck `Ctrl+Shift+P` → "Convert Indentation to Spaces"
3. Kör:

```powershell
python -m streamlit run cotd_tracker.py
```

När appen startar bör du se **"DEBUG API-svar:"** med den faktiska JSON-strukturen från trackmania.io. **Kopiera det som visas och klistra in här** — då kan jag anpassa koden exakt efter vad API:t faktiskt returnerar, och du kan ta bort debug-raden efteråt.