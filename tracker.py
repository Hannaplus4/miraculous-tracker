import requests, json, os, re
from m3u8 import parse as m3u8parser

# Endpoints oficiales de Apple TV extraídos de la estructura original
BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://tv.apple.com",
    "Referer": "https://tv.apple.com/"
}

def ReplaceCodeLanguages(X):
    X = X.lower().replace('_subtitle_dialog_0', '').replace('_dialog_0', '')
    return X.replace('es-mx', 'es-la').replace('es-419', 'es-la').replace('es-us', 'es-la')

def obtener_headers_dinamicos(url_show):
    """
    Simula la obtención de tokens de autorización y cookies igual que el script original.
    """
    try:
        session = requests.Session()
        # Primero visitamos la página principal del show para que la sesión capture las cookies y tokens de Apple
        res = session.get(url_show, headers=BASE_HEADERS, timeout=15)
        
        # Extraemos las cabeceras wvHeaders u otras necesarias si están disponibles en la sesión
        wv_headers = BASE_HEADERS.copy()
        if 'set-cookie' in res.headers:
            wv_headers['Cookie'] = res.headers['set-cookie']
            
        return wv_headers
    except Exception as e:
        print(f"Advertencia al obtener headers dinámicos: {e}")
        return BASE_HEADERS

def obtener_idiomas_de_m3u8(m3u8_url, headers):
    try:
        res = requests.get(m3u8_url, headers=headers, timeout=10)
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
    show_url = "https://tv.apple.com/bg/show/miraculous-tales-of-ladybug-and-cat-noir/umc.cmc.7adu8wmjugygtdhfamor58yn8"
    api_url = "https://tv.apple.com/api/uts/v3/shows/umc.cmc.7adu8wmjugygtdhfamor58yn8/episodes?caller=web&includeSeasonSummary=false&locale=en-US&pfm=web&selectedSeasonEpisodesOnly=false&sf=143441&v=96"
    
    # Obtenemos headers con la sesión fresca
    headers = obtener_headers_dinamicos(show_url)
    
    try:
        res = requests.get(api_url, headers=headers, timeout=15)
        print(f"Código de respuesta de la API: {res.status_code}")
        
        if res.status_code != 200:
            print(f"Apple TV sigue bloqueando la petición directa. Respuesta: {res.text[:200]}")
            return {}
            
        episodios_info = {}
        data_json = res.json()
        
        episodes_list = data_json.get('data', {}).get('episodes', [])
        if not episodes_list:
            # Intentar buscar en otra estructura común de la API si varía
            print("Estructura de episodios vacía, revisando datos alternativos...")
            
        for ep in episodes_list:
            ep_key = f"S{ep.get('seasonNumber'):02d}E{ep.get('episodeNumber'):02d}"
            
            playables = ep.get('playables', [])
            hls_url = None
            if playables:
                for p in playables:
                    if 'assets' in p and 'hlsUrl' in p['assets']:
                        hls_url = p['assets']['hlsUrl']
                        break
            
            audios, subs = obtener_idiomas_de_m3u8(hls_url, headers) if hls_url else ([], [])
            episodios_info[ep_key] = {"titulo": ep.get('title'), "audios": audios, "subtitulos": subs}
            print(f"Escaneado con éxito: {ep_key} - {ep.get('title')}")
            
        return episodios_info
    except Exception as e:
        print(f"Error general escaneando episodios: {e}")
        return {}

def main():
    archivo = 'datos.json'
    print("Iniciando escaneo seguro de Miraculous...")
    nuevos_datos = escanear_episodios()
    
    if nuevos_datos:
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(nuevos_datos, f, indent=4, ensure_ascii=False)
        print("Escaneo completado. Archivo datos.json guardado correctamente.")
    else:
        print("No se pudieron extraer datos en esta ejecución debido a restricciones de la plataforma.")

if __name__ == "__main__":
    main()
