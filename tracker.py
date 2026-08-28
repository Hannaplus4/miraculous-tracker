import requests, json, os
from m3u8 import parse as m3u8parser

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://tv.apple.com",
    "Referer": "https://tv.apple.com/"
}

def ReplaceCodeLanguages(X):
    X = X.lower().replace('_subtitle_dialog_0', '').replace('_dialog_0', '')
    return X.replace('es-mx', 'es-la').replace('es-419', 'es-la').replace('es-us', 'es-la')

def obtener_idiomas_de_m3u8(m3u8_url):
    try:
        res = requests.get(m3u8_url, headers=HEADERS, timeout=10)
        if res.status_code != 200: 
            return [], []
            
        audios, subtitulos = set(), set()
        for media in m3u8parser(res.text).get('media', []):
            lang = media.get('language')
            if not lang: continue
            
            lang_clean = ReplaceCodeLanguages(lang)
            if media['type'] == 'AUDIO': 
                audios.add(lang_clean)
            elif media['type'] == 'SUBTITLES':
                sub_tag = f"{lang_clean}-forced" if media.get('forced') == 'YES' else lang_clean
                subtitulos.add(sub_tag)
                
        return sorted(list(audios)), sorted(list(subtitulos))
    except Exception as e:
        print(f"Error leyendo M3U8: {e}")
        return [], []

def escanear_episodios():
    # URL completa con todos los parámetros de la API, incluyendo el utsk y utscf requeridos
    api_url = "https://tv.apple.com/api/uts/v3/shows/umc.cmc.7adu8wmjugygtdhfamor58yn8/episodes?caller=web&includeSeasonSummary=false&locale=en-US&pfm=web&selectedSeasonEpisodesOnly=false&sf=143441&utscf=OjAAAAEAAAAAAAIAEAAAACMAKwAtAA%7E%7E&utsk=6e3013c6d6fae3c2%3A%3A%3A%3A%3A%3A235656c069bb0efb&v=96"
    
    try:
        res = requests.get(api_url, headers=HEADERS, timeout=15)
        print(f"Código de respuesta de la API: {res.status_code}")
        
        if res.status_code != 200:
            print(f"Error en la API. Respuesta: {res.text[:200]}")
            return {}
            
        episodios_info = {}
        data_json = res.json()
        
        episodes_list = data_json.get('data', {}).get('episodes', [])
        
        for ep in episodes_list:
            ep_key = f"S{ep.get('seasonNumber'):02d}E{ep.get('episodeNumber'):02d}"
            
            playables = ep.get('playables', [])
            hls_url = None
            if playables:
                for p in playables:
                    if 'assets' in p and 'hlsUrl' in p['assets']:
                        hls_url = p['assets']['hlsUrl']
                        break
            
            audios, subs = obtener_idiomas_de_m3u8(hls_url) if hls_url else ([], [])
            episodios_info[ep_key] = {"titulo": ep.get('title'), "audios": audios, "subtitulos": subs}
            print(f"Escaneado con éxito: {ep_key} - {ep.get('title')}")
            
        return episodios_info
    except Exception as e:
        print(f"Error general escaneando episodios: {e}")
        return {}

def main():
    archivo = 'datos.json'
    print("Iniciando escaneo de Miraculous...")
    nuevos_datos = escanear_episodios()
    
    if nuevos_datos:
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(nuevos_datos, f, indent=4, ensure_ascii=False)
        print("Escaneo completado. Archivo datos.json guardado correctamente.")
    else:
        print("No se pudieron extraer datos.")

if __name__ == "__main__":
    main()
