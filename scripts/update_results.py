#!/usr/bin/env python3
"""
Actualiza automaticamente los resultados del Prode Mundial 2026
usando football-data.org (API v4, free tier).

- Lee data/calendario.json (mapeo mi -> equipos)
- Pide a football-data.org los partidos del Mundial 2026 (FINISHED)
- Para cada partido FINISHED que todavia no tiene resultado cargado
  en index.html, lo escribe en `var results`.
- Requiere la variable de entorno FOOTBALL_DATA_TOKEN (API key gratis
  de https://www.football-data.org/client/register)
"""

import json
import os
import re
import sys
import urllib.request

API_URL = "https://api.football-data.org/v4/competitions/WC/matches"
CALENDARIO_PATH = "data/calendario.json"
INDEX_PATH = "index.html"


def fetch_matches(token):
    req = urllib.request.Request(API_URL, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_calendario():
    with open(CALENDARIO_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_index_html():
    with open(INDEX_PATH, encoding="utf-8") as f:
        return f.read()


def extract_results(html):
    m = re.search(r"var results = (\{.*?\});", html, re.DOTALL)
    if not m:
        raise RuntimeError("No se encontro 'var results = {...};' en index.html")
    return json.loads(m.group(1)), m


def build_match_index(api_json):
    """Indexa por (homeTeam.name, awayTeam.name) -> match dict, solo FINISHED."""
    idx = {}
    for m in api_json.get("matches", []):
        if m.get("status") != "FINISHED":
            continue
        home = m.get("homeTeam", {}).get("name")
        away = m.get("awayTeam", {}).get("name")
        if home and away:
            idx[(home, away)] = m
    return idx


def result_code(home_goals, away_goals):
    if home_goals == away_goals:
        return 3
    if home_goals > away_goals:
        return 1
    return 2


def main():
    token = os.environ.get("FOOTBALL_DATA_TOKEN")
    if not token:
        print("FOOTBALL_DATA_TOKEN no configurado.", file=sys.stderr)
        return 1

    calendario = load_calendario()
    html = load_index_html()
    results, match = extract_results(html)

    api_json = fetch_matches(token)

    seen = set()
    print("--- Equipos segun football-data.org ---")
    for m in api_json.get("matches", []):
        home = m.get("homeTeam", {}).get("name")
        away = m.get("awayTeam", {}).get("name")
        for name in (home, away):
            if name and name not in seen:
                seen.add(name)
    for name in sorted(seen):
        print(" -", name)
    print("--- Fin lista de equipos ---")

    match_idx = build_match_index(api_json)

    updated = []
    for c in calendario:
        mi = c["mi"]
        if str(mi) in results or mi in results:
            continue

        key = (c["team1_en"], c["team2_en"])
        api_match = match_idx.get(key)
        if not api_match:
            continue

        score = api_match.get("score", {}).get("fullTime", {})
        home_g = score.get("home")
        away_g = score.get("away")
        if home_g is None or away_g is None:
            continue

        code = result_code(home_g, away_g)
        results[str(mi)] = code
        updated.append((mi, c["equipo1"], c["equipo2"], home_g, away_g, code))

    if not updated:
        print("Sin novedades. No se actualizo nada.")
        return 0

    new_results_str = json.dumps(results, ensure_ascii=False, separators=(",", ":"))
    new_html = html[: match.start()] + f"var results = {new_results_str};" + html[match.end():]

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

    for mi, e1, e2, hg, ag, code in updated:
        print(f"P{mi+1}: {e1} {hg} - {ag} {e2} -> codigo {code}")
    print(f"\n{len(updated)} resultado(s) actualizado(s) en {INDEX_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
