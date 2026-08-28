import requests
import json
import re
from urllib.parse import urlparse, urlunparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://tv.apple.com",
    "Referer": "https://tv.apple.com/",
}

PARAMS = {
    "caller": "web",
    "locale": "en-US",
    "pfm": "web",
    "sf": "143441",
    "v": "96",
    "utsk": "6e3013c6d6fae3c2:::::235656c069bb0efb",
}

SHOW_ID = "umc.cmc.7adu8wmjugygtdhfamor58yn8"
STOREFRONT = "ie"  # más idiomas que US


def limpiar_idioma(texto: str) -> str:
    texto = texto.strip()
    texto = re.sub(r"\s*\([^)]*\)", "", texto)
    texto = texto.replace("\u2068", "").replace("\u2069", "").replace("\xa0", " ")
    texto = texto.strip()
    lower = texto.lower()
    if "latin america" in lower or "latino" in lower:
        return "es-la"
    if "spanish (spain)" in lower:
        return "es-es"
    if "portuguese (portugal)" in lower:
        return "pt-pt"
    if "portuguese (brazil)" in lower or "brazilian" in lower:
        return "pt-br"
    if "french (france)" in lower:
        return "fr-fr"
    if "french (canada)" in lower:
        return "fr-ca"
    if "english (united kingdom)" in lower or "english (uk)" in lower:
        return "en-gb"
    if "english (united states)" in lower or "english (us)" in lower:
        return "en-us"
    return texto


def parsear_lista_idiomas(info: str):
    if not info:
        return []
    partes = [p.strip() for p in info.split(",") if p.strip()]
    resultados = []
    for p in partes:
        limpio = limpiar_idioma(p)
        if limpio:
            resultados.append(limpio)
    vistos = set()
    unicos = []
    for x in resultados:
        key = x.lower()
        if key not in vistos:
            vistos.add(key)
            unicos.append(x)
    return unicos


def obtener_idiomas_pagina(episode_url: str):
    parsed = urlparse(episode_url)
    path_parts = parsed.path.split("/")
    if len(path_parts) > 1:
        path_parts[1] = STOREFRONT
    new_url = urlunparse(parsed._replace(path="/".join(path_parts), query=""))

    try:
        res = requests.get(new_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return [], []

        m = re.search(
            r'<script[^>]*id="serialized-server-data"[^>]*>(.*?)</script>',
            res.text,
            re.DOTALL,
        )
        if not m:
            return [], []

        data = json.loads(m.group(1))
        shelves = data.get("data", [{}])[1].get("data", {}).get("shelves", [])

        audios, subs = [], []
        for shelf in shelves:
            for item in shelf.get("items", []):
                if item.get("id") != "languages":
                    continue
                for lang_item in item.get("items", []):
                    lid = lang_item.get("id", "")
                    info = lang_item.get("info", "")
                    if lid == "languages-audio":
                        audios = parsear_lista_idiomas(info)
                    elif lid == "languages-subtitles":
                        subs = parsear_lista_idiomas(info)
        return audios, subs
    except Exception as e:
        print(f"  Error página: {e}")
        return [], []


def obtener_temporadas():
    """Lista todas las temporadas del show."""
    url = f"https://tv.apple.com/api/uts/v3/shows/{SHOW_ID}/episodes"
    params = PARAMS.copy()
    params["includeSeasonSummary"] = "true"
    params["selectedSeasonEpisodesOnly"] = "false"

    res = requests.get(url, params=params, headers=HEADERS, timeout=15)
    res.raise_for_status()
    summaries = res.json().get("data", {}).get("seasonSummaries", [])
    return sorted(summaries, key=lambda s: s.get("seasonNumber", 0))


def obtener_episodios_temporada(season_id: str, episode_count: int):
    """
    Recorre la ventana deslizante del API hasta reunir todos
    los episodios de una temporada.
    """
    url = f"https://tv.apple.com/api/uts/v3/shows/{SHOW_ID}/episodes"
    vistos = {}
    selected_episode_id = None
    sin_progreso = 0

    while len(vistos) < episode_count and sin_progreso < 5:
        params = PARAMS.copy()
        params["selectedSeasonEpisodesOnly"] = "true"
        params["selectedSeasonId"] = season_id
        if selected_episode_id:
            params["selectedEpisodeId"] = selected_episode_id

        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            break

        batch = res.json().get("data", {}).get("episodes", [])
        if not batch:
            break

        antes = len(vistos)
        for ep in batch:
            if ep.get("seasonId") != season_id and ep.get("id"):
                # a veces mezcla con temporada anterior/siguiente
                pass
            ep_num = ep.get("episodeNumber")
            if ep_num is not None:
                vistos[ep_num] = ep

        if len(vistos) == antes:
            sin_progreso += 1
        else:
            sin_progreso = 0

        # Avanzar la ventana hacia el final del batch
        selected_episode_id = batch[-1].get("id")
        if not selected_episode_id:
            break

    return [vistos[k] for k in sorted(vistos.keys())]


def escanear_episodios():
    temporadas = obtener_temporadas()
    print(f"Temporadas encontradas: {len(temporadas)}")
    for t in temporadas:
        print(f"  S{t.get('seasonNumber'):02d} - {t.get('title')} ({t.get('episodeCount')} eps) id={t.get('id')}")

    episodios_info = {}

    for t in temporadas:
        season_num = t.get("seasonNumber")
        season_id = t.get("id")
        expected = t.get("episodeCount") or 30

        print(f"\n=== Temporada {season_num} (esperados ~{expected}) ===")
        episodios = obtener_episodios_temporada(season_id, expected)
        print(f"  Obtenidos: {len(episodios)}")

        for ep in episodios:
            ep_num = ep.get("episodeNumber")
            title = ep.get("title")
            ep_url = ep.get("url")

            if ep_num is None or not ep_url:
                continue

            ep_key = f"S{season_num:02d}E{ep_num:02d}"
            audios, subs = obtener_idiomas_pagina(ep_url)

            episodios_info[ep_key] = {
                "titulo": title,
                "audios": audios,
                "subtitulos": subs,
            }
            print(f"  {ep_key} - {title} | Audios: {len(audios)} | Subs: {len(subs)}")

    return episodios_info


def main():
    print("Iniciando escaneo de todas las temporadas...")
    datos = escanear_episodios()

    if datos:
        with open("datos.json", "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
        print(f"\nListo. Total episodios: {len(datos)}")
    else:
        print("No se extrajo ningún dato.")


if __name__ == "__main__":
    main()
