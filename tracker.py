```python
import requests
import json
from m3u8 import parse as m3u8parser

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

def ReplaceCodeLanguages(x: str) -> str:
    x = x.lower().replace("_subtitle_dialog_0", "").replace("_dialog_0", "")
    return (
        x.replace("es-mx", "es-la")
         .replace("es-419", "es-la")
         .replace("es-us", "es-la")
         .replace("_", "-")
    )

def obtener_idiomas_de_m3u8(m3u8_url: str):
    """Parsea el master playlist y extrae idiomas de AUDIO y SUBTITLES."""
    try:
        res = requests.get(m3u8_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return [], []

        master = m3u8parser(res.text)
        audios, subtitulos = set(), set()

        for media in master.get("media", []):
            lang = media.get("language")
            if not lang:
                continue

            lang_clean = ReplaceCodeLanguages(lang)

            if media["type"] == "AUDIO":
                audios.add(lang_clean)
            elif media["type"] == "SUBTITLES":
                forced = media.get("forced") == "YES"
                tag = f"{lang_clean}-forced" if forced else lang_clean
                subtitulos.add(tag)

        return sorted(audios), sorted(subtitulos)
    except Exception as e:
        print(f"Error parseando M3U8: {e}")
        return [], []

def obtener_hls_url(episode_id: str):
    """Obtiene el hlsUrl real usando el endpoint personalized."""
    url = f"https://tv.apple.com/api/uts/v2/view/product/{episode_id}/personalized"
    try:
        res = requests.get(url, params=PARAMS, headers=HEADERS, timeout=12)
        if res.status_code != 200:
            return None

        data = res.json()
        playables = data.get("data", {}).get("content", {}).get("playables", [])

        for p in playables:
            assets = p.get("assets") or {}
            if "hlsUrl" in assets:
                return assets["hlsUrl"]

            itunes = p.get("itunesMediaApiData") or {}
            for offer in itunes.get("offers", []):
                if "hlsUrl" in offer:
                    return offer["hlsUrl"]

        return None
    except Exception:
        return None

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
            ep_id = ep.get("id")
            title = ep.get("title")

            if season_num is None or ep_num is None or not ep_id:
                continue

            ep_key = f"S{season_num:02d}E{ep_num:02d}"

            # Solo audios y subtítulos del manifiesto HLS
            hls_url = obtener_hls_url(ep_id)
            audios, subs = obtener_idiomas_de_m3u8(hls_url) if hls_url else ([], [])

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
    print("Iniciando escaneo...")
    datos = escanear_episodios()

    if datos:
        with open("datos.json", "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
        print(f"\nListo. Total episodios: {len(datos)}")
    else:
        print("No se extrajo ningún dato.")

if __name__ == "__main__":
    main()
```
