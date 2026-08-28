import requests
import json
import re
import os
from urllib.parse import urlparse, urlunparse
from pathlib import Path

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

STOREFRONT = "ie"
ARCHIVO = "datos.json"
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

# Serie principal (episodios por temporada)
SHOWS = [
    {
        "id": "umc.cmc.7adu8wmjugygtdhfamor58yn8",
        "nombre": "Miraculous (principal)",
        "prefijo": "",  # claves S01E01...
    },
    {
        "id": "umc.cmc.20bez3zpes3ba8r6yx4vql1nq",
        "nombre": "Miraculous Tales (alt)",
        "prefijo": "ALT-",
    },
    {
        "id": "umc.cmc.2v872y53a5ih34r497wektrhf",
        "nombre": "Miraculous Chibi",
        "prefijo": "CHIBI-",
    },
    {
        "id": "umc.cmc.5213w503392e9lxqlnken1ab1",
        "nombre": "Chibi Shorts",
        "prefijo": "SHORTS-",
    },
]

# Películas / especiales (una ficha cada una)
MOVIES = [
    {
        "id": "umc.cmc.njf03z6p926unx34eupch0td",
        "clave": "MOVIE-NY",
        "titulo": "Miraculous World: New York – United HeroeZ",
        "url": "https://tv.apple.com/ie/movie/miraculous-world-new-york-united-heroez/umc.cmc.njf03z6p926unx34eupch0td",
    },
    {
        "id": "umc.cmc.1pud6xbnxk00fpg1dnkpl2qot",
        "clave": "MOVIE-SHANGHAI",
        "titulo": "Miraculous World: Shanghai – The Legend of Ladydragon",
        "url": "https://tv.apple.com/ie/movie/miraculous-world-shanghai-the-legend-of-ladydragon/umc.cmc.1pud6xbnxk00fpg1dnkpl2qot",
    },
    {
        "id": "umc.cmc.6xwtcgi6c7tddo6ds9znhzi8",
        "clave": "MOVIE-PARIS",
        "titulo": "Miraculous World: Paris – Tales of Shadybug and Claw Noir",
        "url": "https://tv.apple.com/ie/movie/miraculous-world-paris-tales-of-shadybug-and-claw-noir/umc.cmc.6xwtcgi6c7tddo6ds9znhzi8",
    },
    {
        "id": "umc.cmc.1bje05arrzrmujs323a6z458i",
        "clave": "MOVIE-LONDON",
        "titulo": "Miraculous World: London – At the Edge of Time",
        "url": "https://tv.apple.com/ie/movie/miraculous-world-london-at-the-edge-of-time/umc.cmc.1bje05arrzrmujs323a6z458i",
    },
    {
        "id": "umc.cmc.16v2i10hid0ja28njxpkzaqmh",
        "clave": "MOVIE-TOKYO",
        "titulo": "Miraculous World: Tokyo – Stellar Force",
        "url": "https://tv.apple.com/ie/movie/miraculous-world-tokyo-stellar-force/umc.cmc.16v2i10hid0ja28njxpkzaqmh",
    },
]

# Overrides cuando el API da un ID malo
URL_OVERRIDES = {
    "vampigami": (
        "https://tv.apple.com/ie/episode/vampigami/"
        "umc.cmc.5gkqyetzv0lui4nnjl568web2"
    ),
    "the-chained-titans": (
        "https://tv.apple.com/ie/episode/the-chained-titans/"
        "umc.cmc.4gaalf5893r6slp2hh14xy22a"
    ),
}


def limpiar_idioma(texto: str) -> str:
    if not texto:
        return ""

    texto = (
        texto.replace("\u2068", "")
        .replace("\u2069", "")
        .replace("\xa0", " ")
        .replace("\u00a0", " ")
        .replace("Â", "")
        .replace("â¨", "")
        .replace("â©", "")
        .replace("â\x81¨", "")
        .replace("â\x81©", "")
    )
    texto = re.sub(r"\s+", " ", texto).strip()

    es_ad = bool(re.search(r"\(\s*AD\b", texto, re.IGNORECASE))

    texto = re.sub(r"\s*\([^)]*\)", "", texto)
    texto = texto.strip(" ,.-")
    texto = re.sub(r"\s+", " ", texto).strip()

    if not texto:
        return ""

    lower = texto.lower()
    if "latin america" in lower or "latino" in lower:
        base = "es-la"
    elif "spanish (spain)" in lower:
        base = "es-es"
    elif lower == "spanish":
        base = "es"
    elif "portuguese (portugal)" in lower:
        base = "pt-pt"
    elif "portuguese (brazil)" in lower or "brazilian" in lower:
        base = "pt-br"
    elif "french (france)" in lower:
        base = "fr-fr"
    elif "french (canada)" in lower:
        base = "fr-ca"
    elif "english (united kingdom)" in lower or "english (uk)" in lower:
        base = "en-gb"
    elif "english (united states)" in lower or "english (us)" in lower:
        base = "en-us"
    elif lower.startswith("english"):
        base = "en"
    else:
        base = texto

    if es_ad:
        return f"{base}-ad"
    return base


def parsear_lista_idiomas(info: str) -> list:
    if not info:
        return []

    info = (
        info.replace("\u2068", "")
        .replace("\u2069", "")
        .replace("\xa0", " ")
        .replace("Â", "")
    )

    partes = []
    actual = []
    profundidad = 0

    for ch in info:
        if ch == "(":
            profundidad += 1
            actual.append(ch)
        elif ch == ")":
            profundidad = max(0, profundidad - 1)
            actual.append(ch)
        elif ch == "," and profundidad == 0:
            trozo = "".join(actual).strip()
            if trozo:
                partes.append(trozo)
            actual = []
        else:
            actual.append(ch)

    trozo = "".join(actual).strip()
    if trozo:
        partes.append(trozo)

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


def _extraer_idiomas_de_html(html: str):
    m = re.search(
        r'<script[^>]*id="serialized-server-data"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not m:
        return [], []

    data = json.loads(m.group(1))
    items_data = data.get("data", [])
    if len(items_data) < 2:
        return [], []

    page = items_data[1].get("data", {})
    shelves = page.get("shelves", [])

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


def obtener_idiomas_pagina(page_url: str):
    parsed = urlparse(page_url)
    path_parts = list(parsed.path.split("/"))

    candidatos = []
    for sf in (STOREFRONT, "us", "gb", "ie"):
        parts = path_parts[:]
        if len(parts) > 1:
            parts[1] = sf
        candidatos.append(
            urlunparse(parsed._replace(path="/".join(parts), query=""))
        )
    candidatos.append(urlunparse(parsed._replace(query="")))

    vistos_url = set()
    mejor_audios, mejor_subs = [], []

    for new_url in candidatos:
        if new_url in vistos_url:
            continue
        vistos_url.add(new_url)

        try:
            res = requests.get(new_url, headers=HEADERS, timeout=15)
            if res.status_code != 200:
                continue

            audios, subs = _extraer_idiomas_de_html(res.text)
            if not audios and not subs:
                continue

            if len(audios) + len(subs) > len(mejor_audios) + len(mejor_subs):
                mejor_audios, mejor_subs = audios, subs

            if len(audios) >= 3 or len(subs) >= 3:
                return audios, subs
        except Exception as e:
            print(f"  Error página: {e}")
            continue

    return mejor_audios, mejor_subs


def urls_para_episodio(title: str, urls: list) -> list:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    out = []
    if slug in URL_OVERRIDES:
        out.append(URL_OVERRIDES[slug])
    for u in urls or []:
        if u and u not in out:
            out.append(u)
    return out


def idiomas_mejor_url(urls: list):
    mejor_a, mejor_s = [], []
    for u in urls:
        a, s = obtener_idiomas_pagina(u)
        if len(a) + len(s) > len(mejor_a) + len(mejor_s):
            mejor_a, mejor_s = a, s
        if len(a) >= 5:
            return a, s
    return mejor_a, mejor_s


def obtener_temporadas(show_id: str):
    url = f"https://tv.apple.com/api/uts/v3/shows/{show_id}/episodes"
    params = PARAMS.copy()
    params["includeSeasonSummary"] = "true"
    params["selectedSeasonEpisodesOnly"] = "false"

    res = requests.get(url, params=params, headers=HEADERS, timeout=15)
    if res.status_code != 200:
        print(f"  No se pudieron listar temporadas ({res.status_code})")
        return []

    summaries = res.json().get("data", {}).get("seasonSummaries", [])
    return sorted(summaries, key=lambda s: s.get("seasonNumber", 0))


def obtener_episodios_temporada(show_id: str, season_id: str, episode_count: int):
    url = f"https://tv.apple.com/api/uts/v3/shows/{show_id}/episodes"
    por_numero = {}
    por_titulo = {}
    selected_episode_id = None
    sin_progreso = 0
    vistos_ids = set()

    while len(por_numero) < episode_count and sin_progreso < 8:
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

        antes = len(vistos_ids)
        for ep in batch:
            eid = ep.get("id")
            if not eid or eid in vistos_ids:
                continue
            vistos_ids.add(eid)

            ep_num = ep.get("episodeNumber")
            title = ep.get("title") or ""
            ep_url = ep.get("url")
            if not ep_url:
                continue

            key_t = title.strip().lower()
            por_titulo.setdefault(key_t, []).append(ep)

            if ep_num is None or ep_num < 1:
                continue
            if episode_count and ep_num > episode_count + 2:
                continue

            if ep_num not in por_numero:
                por_numero[ep_num] = {
                    "episodeNumber": ep_num,
                    "title": title,
                    "urls": [ep_url],
                    "ids": [eid],
                }
            else:
                if ep_url not in por_numero[ep_num]["urls"]:
                    por_numero[ep_num]["urls"].append(ep_url)
                if eid not in por_numero[ep_num]["ids"]:
                    por_numero[ep_num]["ids"].append(eid)

        if len(vistos_ids) == antes:
            sin_progreso += 1
        else:
            sin_progreso = 0

        selected_episode_id = batch[-1].get("id")
        if not selected_episode_id:
            break

    for ep_num, data in por_numero.items():
        key_t = data["title"].strip().lower()
        for alt in por_titulo.get(key_t, []):
            alt_url = alt.get("url")
            alt_id = alt.get("id")
            if alt_url and alt_url not in data["urls"]:
                data["urls"].append(alt_url)
            if alt_id and alt_id not in data["ids"]:
                data["ids"].append(alt_id)

    return [por_numero[k] for k in sorted(por_numero.keys())]


def escanear_show(show: dict) -> dict:
    show_id = show["id"]
    prefijo = show.get("prefijo", "")
    nombre = show.get("nombre", show_id)

    print(f"\n######## SHOW: {nombre} ({show_id}) ########")
    temporadas = obtener_temporadas(show_id)
    if not temporadas:
        print("  Sin temporadas (¿es un show sin episodios listables?).")
        return {}

    print(f"  Temporadas: {len(temporadas)}")
    for t in temporadas:
        print(
            f"    S{t.get('seasonNumber'):02d} - {t.get('title')} "
            f"({t.get('episodeCount')} eps)"
        )

    info = {}

    for t in temporadas:
        season_num = t.get("seasonNumber")
        season_id = t.get("id")
        expected = t.get("episodeCount") or 30

        print(f"\n  === Temporada {season_num} (esperados ~{expected}) ===")
        episodios = obtener_episodios_temporada(show_id, season_id, expected)
        print(f"    Obtenidos: {len(episodios)}")

        for ep in episodios:
            ep_num = ep.get("episodeNumber")
            title = ep.get("title")
            urls = urls_para_episodio(title, ep.get("urls") or [])

            if ep_num is None or not urls:
                continue

            ep_key = f"{prefijo}S{season_num:02d}E{ep_num:02d}"
            audios, subs = idiomas_mejor_url(urls)

            info[ep_key] = {
                "titulo": title,
                "tipo": "episodio",
                "show": nombre,
                "audios": audios,
                "subtitulos": subs,
            }
            print(
                f"    {ep_key} - {title} | Audios: {len(audios)} | "
                f"Subs: {len(subs)} | fichas: {len(urls)}"
            )

    return info


def escanear_peliculas() -> dict:
    print("\n######## PELÍCULAS / ESPECIALES ########")
    info = {}

    for movie in MOVIES:
        clave = movie["clave"]
        titulo = movie["titulo"]
        url = movie["url"]

        audios, subs = obtener_idiomas_pagina(url)
        info[clave] = {
            "titulo": titulo,
            "tipo": "pelicula",
            "audios": audios,
            "subtitulos": subs,
        }
        print(
            f"  {clave} - {titulo} | Audios: {len(audios)} | Subs: {len(subs)}"
        )

    return info


def escanear_todo() -> dict:
    todo = {}

    for show in SHOWS:
        todo.update(escanear_show(show))

    todo.update(escanear_peliculas())
    return todo


def cargar_anteriores():
    path = Path(ARCHIVO)
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def comparar(anteriores: dict, nuevos: dict) -> list:
    cambios = []

    for key in sorted(nuevos.keys()):
        if key not in anteriores:
            ep = nuevos[key]
            cambios.append(
                f"**NUEVO** `{key}` — {ep.get('titulo')}\n"
                f"Audios: {', '.join(ep.get('audios') or []) or '—'}\n"
                f"Subs: {', '.join(ep.get('subtitulos') or []) or '—'}"
            )
            continue

        old = anteriores[key]
        new = nuevos[key]

        old_audios = set(old.get("audios") or [])
        new_audios = set(new.get("audios") or [])
        old_subs = set(old.get("subtitulos") or [])
        new_subs = set(new.get("subtitulos") or [])

        audios_add = sorted(new_audios - old_audios)
        audios_del = sorted(old_audios - new_audios)
        subs_add = sorted(new_subs - old_subs)
        subs_del = sorted(old_subs - new_subs)

        if audios_add or audios_del or subs_add or subs_del:
            lineas = [f"**CAMBIO** `{key}` — {new.get('titulo')}"]
            if audios_add:
                lineas.append(f"+ Audios: {', '.join(audios_add)}")
            if audios_del:
                lineas.append(f"- Audios: {', '.join(audios_del)}")
            if subs_add:
                lineas.append(f"+ Subs: {', '.join(subs_add)}")
            if subs_del:
                lineas.append(f"- Subs: {', '.join(subs_del)}")
            cambios.append("\n".join(lineas))

    for key in sorted(anteriores.keys()):
        if key not in nuevos:
            cambios.append(
                f"**ELIMINADO** `{key}` — {anteriores[key].get('titulo')}"
            )

    return cambios


def enviar_discord(cambios: list):
    if not DISCORD_WEBHOOK:
        print("DISCORD_WEBHOOK no configurado.")
        for c in cambios:
            print(c)
            print()
        return

    header = f"**Miraculous Tracker** — {len(cambios)} cambio(s)\n\n"
    chunks = []
    actual = header

    for c in cambios:
        bloque = c + "\n\n"
        if len(actual) + len(bloque) > 1900:
            chunks.append(actual)
            actual = bloque
        else:
            actual += bloque
    if actual.strip():
        chunks.append(actual)

    for i, chunk in enumerate(chunks):
        res = requests.post(DISCORD_WEBHOOK, json={"content": chunk}, timeout=15)
        if res.status_code >= 400:
            print(f"Error Discord ({res.status_code}): {res.text}")
        else:
            print(f"Discord OK ({i + 1}/{len(chunks)})")


def main():
    print("Iniciando escaneo completo...")
    anteriores = cargar_anteriores()
    nuevos = escanear_todo()

    if not nuevos:
        print("No se extrajo ningún dato.")
        return

    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(nuevos, f, indent=4, ensure_ascii=False)
    print(f"\nGuardado {ARCHIVO}. Total entradas: {len(nuevos)}")

    if not anteriores:
        print("Primera ejecución: se guardó la base. No hay cambios que notificar.")
        return

    cambios = comparar(anteriores, nuevos)
    if not cambios:
        print("Sin cambios.")
        return

    print(f"Cambios detectados: {len(cambios)}")
    enviar_discord(cambios)


if __name__ == "__main__":
    main()
