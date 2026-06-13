#!/usr/bin/env python3
"""
Actualiza automáticamente los resultados del Prode Mundial 2026.

- Lee data/calendario.json (mapeo mi -> equipos + horario)
- Descarga el fixture/resultados desde openfootball/worldcup.json
- Para cada partido cuyo horario de "check" (kickoff + 2h10m, ART) ya pasó
  y que todavía no tiene resultado cargado en index.html, busca el score
  y si lo encuentra, actualiza el objeto `results` embebido en el HTML.
- Si hubo cambios, los deja escritos en index.html (el commit lo hace
  el workflow de GitHub Actions).
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

ART = timezone(timedelta(hours=-3))
SOURCE_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
CALENDARIO_PATH = "data/calendario.json"
INDEX_PATH = "index.html"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "prode-mundial-2026-bot"})
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
        raise RuntimeError("No se encontró 'var results = {...};' en index.html")
    return json.loads(m.group(1)), m


def build_match_index(wc_json):
    """Indexa los partidos de openfootball por (team1, team2) -> match dict."""
    idx = {}
    for m in wc_json.get("matches", []):
        t1 = m.get("team1")
        t2 = m.get("team2")
        if t1 and t2:
            idx[(t1, t2)] = m
    return idx


def result_code(score_ft, home_first):
    """score_ft = [goles_team1, goles_team2]. Devuelve 1 (local), 2 (visitante) o 3 (empate)."""
    g1, g2 = score_ft
    if g1 == g2:
        return 3
    if g1 > g2:
        return 1
    return 2


def main():
    now_art = datetime.now(ART)
    calendario = load_calendario()
    html = load_index_html()
    results, match = extract_results(html)

    wc_json = fetch_json(SOURCE_URL)
    match_idx = build_match_index(wc_json)

    updated = []
    for c in calendario:
        mi = c["mi"]
        if str(mi) in results or mi in results:
            continue  # ya tiene resultado cargado

        check_at = datetime.fromisoformat(c["check_at_art"])
        if now_art < check_at:
            continue  # todavía no llegó el horario de chequeo

        key = (c["team1_en"], c["team2_en"])
        of_match = match_idx.get(key)
        if not of_match:
            continue

        score = of_match.get("score", {}).get("ft")
        if not score:
            continue  # resultado todavía no publicado en la fuente

        code = result_code(score, True)
        results[str(mi)] = code
        updated.append((mi, c["equipo1"], c["equipo2"], score, code))

    if not updated:
        print("Sin novedades. No se actualizó nada.")
        return

    new_results_str = json.dumps(results, ensure_ascii=False, separators=(",", ":"))
    new_html = html[: match.start()] + f"var results = {new_results_str};" + html[match.end():]

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

    for mi, e1, e2, score, code in updated:
        print(f"P{mi+1}: {e1} {score[0]} - {score[1]} {e2} -> codigo {code}")
    print(f"\n{len(updated)} resultado(s) actualizado(s) en {INDEX_PATH}")


if __name__ == "__main__":
    sys.exit(main())
