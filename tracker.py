import requests
import json
import os
from m3u8 import parse as m3u8parser

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://tv.apple.com",
    "Referer": "https://tv.apple.com/"
}

def ReplaceCodeLanguages(X):
    X = X.lower().replace('_subtitle_dialog_0', '').replace('_dialog_0', '')
    X = X.replace('es-mx', 'es-la').replace('es-419', 'es-la').replace('es-us', 'es-la')
    return X

def obtener_idiomas_de_m3u8(m3u8_url):
    try:
        res = requests.get(m3u8_url, headers=HEADERS)
        if res.status_code != 200: return [], []
        m3u8_data = m3u8parser(res.text)
        audios, subtitulos = set(), set()

        for media in m3u8_data.get('media', []):
            lang = media.get('language')
            if not lang: continue
            lang_clean = ReplaceCodeLanguages(lang)

            if media['type'] == 'AUDIO':
                audios.add(lang_clean)
            elif media['type'] == 'SUBTITLES':
                sub_tag = f"{lang_clean}-forced" if media.get('forced') == 'YES' else lang_clean
                subtitulos.add(sub_tag)
        return sorted(list(audios)), sorted(list(subtitulos))
    except:
        return [], []

def escanear_episodios():
    api_url = "https://tv.apple.com/api/uts/v3/shows/umc.cmc.7adu8wmjugygtdhfamor58yn8/episodes?caller=web&locale=en-US&pfm=web"
    res = requests.get(api_url, headers=HEADERS)
    if res.status_code != 200: return {}
    
    episodios_info = {}
    for ep in res.json().get('data', {}).get('episodes', []):
        ep_key = f"S{ep.get('seasonNumber'):02d}E{ep.get('episodeNumber'):02d}"
        
        playables = ep.get('playables', [])
        hls_url = playables[0].get('assets', {}).get('hlsUrl') if playables else None
        
        audios, subs = obtener_idiomas_de_m3u8(hls_url) if hls_url else ([], [])
        episodios_info[ep_key] = {"titulo": ep.get('title'), "audios": audios, "subtitulos": subs}
    return episodios_info

def main():
    archivo = 'datos.json'
    datos_viejos = {}
    if os.path.exists(archivo):
        with open(archivo, 'r', encoding='utf-8') as f:
            datos_viejos = json.load(f)

    nuevos_datos = escanear_episodios()
    if not nuevos_datos:
        print("No se pudieron obtener datos. Posible bloqueo o token requerido.")
        return

    hay_cambios = False
    for ep, info in nuevos_datos.items():
        if ep not in datos_viejos:
            print(f"NUEVO EPISODIO: {ep} - {info['titulo']}")
            hay_cambios = True
            continue
        
        audios_nuevos = set(info['audios']) - set(datos_viejos[ep]['audios'])
        subs_nuevos = set(info['subtitulos']) - set(datos_viejos[ep]['subtitulos'])
        
        if audios_nuevos or subs_nuevos:
            print(f"ACTUALIZACIÓN EN {ep} - {info['titulo']}:")
            if audios_nuevos: print(f"  + Audios agregados: {', '.join(audios_nuevos)}")
            if subs_nuevos: print(f"  + Subs agregados: {', '.join(subs_nuevos)}")
            hay_cambios = True

    if hay_cambios or not datos_viejos:
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(nuevos_datos, f, indent=4, ensure_ascii=False)
        print("Archivo datos.json actualizado en el repositorio.")
    else:
        print("Sin novedades en audios o subtítulos.")

if __name__ == "__main__":
    main()
