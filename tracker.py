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

# Storefront con más idiomas disponibles (IE)
STOREFRONT = "ie"


def limpiar_idioma(texto: str) -> str:
    """Quita codecs/formatos y normaliza el nombre del idioma."""
    texto = texto.strip()
    # Quitar cosas entre paréntesis: (Dolby 5.1), (AAC), (CC), (Always On), (AD), etc.
    texto = re.sub(r"\s*\([^)]*\)", "", texto)
    # Limpiar caracteres raros de Apple
    texto = texto.replace("\u2068", "").replace("\u2069", "").replace("\xa0", " ")
    texto = texto.strip()
    # Normalizaciones comunes
    lower = texto.lower()
    if "latin america" in lower or "latino" in lower:
        return "es-la"
    if texto.lower().startswith("spanish (spain)") or texto == "Spanish (Spain)":
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
    """Convierte 'English (Dolby 5.1), French (France) (Dolby 5.1), ...' en lista limpia."""
    if not info:
        return []
    partes = [p.strip() for p in info.split(",") if p.strip()]
    resultados = []
    for p in partes:
        limpio = limpiar_idioma(p)
        if limpio:
            resultados.append(limpio)
    # Quitar duplicados manteniendo orden
    vistos = set()
    unicos = []
    for x in resultados:
        key = x.lower()
        if key not in vistos:
            vistos.add(key)
            unicos.append(x)
    return unicos


def obtener_idiomas_pagina(episode_url: str):
    """
    Lee la página del episodio y extrae Audio + Subtitles
    (ignora Original Audio).
    """
    # Forzar storefront con más tracks
    parsed = urlparse(episode_url)
    path_parts = parsed.path.split("/")
    # /us/episode/... -> /ie/episode/...
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


def escanear_episodios():
    base_url = "https://tv.apple.com/api/uts/v3/shows/umc.cmc.7adu8wmjugygtdhfamor58yn8/episodes"
    params = PARAMS.copy()
    params.update({
        "includeSeasonSummary": "false",
        "selectedSeasonEpisodesOnly": "false",
        "utscf": "OjAAAAEAAAAAAAIAEAAAACMAKwAtAA~~",
    })

    episodios_info = {}
    next_token = None
    pagina = 1

    while True:
        current_params = params.copy()
        if next_token:
            current_params["nextToken"] = next_token

        res = requests.get(base_url, params=current_params, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"Error en página {pagina}: {res.status_code}")
            break

        data_block = res.json().get("data", {})
        episodes_list = data_block.get("episodes", [])

        if not episodes_list:
            break

        print(f"--- Página {pagina} ({len(episodes_list)} episodios) ---")

        for ep in episodes_list:
            season_num = ep.get("seasonNumber")
            ep_num = ep.get("episodeNumber")
            title = ep.get("title")
            ep_url = ep.get("url")

            if season_num is None or ep_num is None or not ep_url:
                continue

            ep_key = f"S{season_num:02d}E{ep_num:02d}"

            audios, subs = obtener_idiomas_pagina(ep_url)

            episodios_info[ep_key] = {
                "titulo": title,
                "audios": audios,
                "subtitulos": subs,
            }

            print(f"{ep_key} - {title} | Audios: {len(audios)} | Subs: {len(subs)}")

        next_token = data_block.get("nextToken")
        if not next_token:
            break
        pagina += 1

    return episodios_info


def main():
    print("Iniciando escaneo (idiomas desde página del episodio)...")
    datos = escanear_episodios()

    if datos:
        with open("datos.json", "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
        print(f"\nListo. Total episodios: {len(datos)}")
    else:
        print("No se extrajo ningún dato.")


if __name__ == "__main__":
    main()
