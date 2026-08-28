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

SHOW_ID = "umc.cmc.7adu8wmjugygtdhfamor58yn8"
STOREFRONT = "ie"  # preferido (más idiomas); si falla prueba us/gb
ARCHIVO = "datos.json"
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")


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

    # Quitar todo entre paréntesis: (AD, Dolby 5.1), (AAC), (Always On), etc.
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
    """Parte por comas solo fuera de paréntesis."""
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


def obtener_idiomas_pagina(episode_url: str):
    """
    Prueba varios storefronts: ie (más idiomas) -> us -> gb -> URL original.
    Así episodios que dan 404 en IE (ej. Vampigami) no quedan vacíos.
    """
    parsed = urlparse(episode_url)
    path_parts = list(parsed.path.split("/"))

    candidatos = []
    for sf in (STOREFRONT, "us", "gb"):
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

            # Preferir la respuesta con más pistas (suele ser IE)
            if len(audios) + len(subs) > len(mejor_audios) + len(mejor_subs):
                mejor_audios, mejor_subs = audios, subs

            # Si ya tenemos una lista rica, no hace falta seguir
            if len(audios) >= 3 or len(subs) >= 3:
                return audios, subs
        except Exception as e:
            print(f"  Error página: {e}")
            continue

    return mejor_audios, mejor_subs


def obtener_temporadas():
    url = f"https://tv.apple.com/api/uts/v3/shows/{SHOW_ID}/episodes"
    params = PARAMS.copy()
    params["includeSeasonSummary"] = "true"
    params["selectedSeasonEpisodesOnly"] = "false"

    res = requests.get(url, params=params, headers=HEADERS, timeout=15)
    res.raise_for_status()
    summaries = res.json().get("data", {}).get("seasonSummaries", [])
    return sorted(summaries, key=lambda s: s.get("seasonNumber", 0))


def obtener_episodios_temporada(season_id: str, episode_count: int):
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
            ep_num = ep.get("episodeNumber")
            # Ignorar números raros (ej. 107) fuera del rango de la temporada
            if ep_num is None:
                continue
            if episode_count and (ep_num < 1 or ep_num > episode_count + 5):
                continue
            vistos[ep_num] = ep

        if len(vistos) == antes:
            sin_progreso += 1
        else:
            sin_progreso = 0

        selected_episode_id = batch[-1].get("id")
        if not selected_episode_id:
            break

    return [vistos[k] for k in sorted(vistos.keys())]


def escanear_episodios():
    temporadas = obtener_temporadas()
    print(f"Temporadas encontradas: {len(temporadas)}")
    for t in temporadas:
        print(
            f"  S{t.get('seasonNumber'):02d} - {t.get('title')} "
            f"({t.get('episodeCount')} eps)"
        )

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
    print("Iniciando escaneo...")
    anteriores = cargar_anteriores()
    nuevos = escanear_episodios()

    if not nuevos:
        print("No se extrajo ningún dato.")
        return

    with open(ARCHIVO, "w", encoding="utf-8") as f:
        json.dump(nuevos, f, indent=4, ensure_ascii=False)
    print(f"\nGuardado {ARCHIVO}. Total: {len(nuevos)}")

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
