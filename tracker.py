import requests, json, os
from m3u8 import parse as m3u8parser

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://tv.apple.com",
    "Referer": "https://tv.apple.com/"
}

# Parámetros por defecto que usaba tu script original para las consultas de producto/episodio
PARAMS = {
    "caller": "web",
    "locale": "en-US",
    "pfm": "web",
    "sf": "143441",
    "v": "96"
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

def obtener_hls_episodio(episode_id):
    """Consulta el endpoint individual del episodio para obtener su manifiesto HLS real"""
    product_url = f"https://tv.apple.com/api/uts/v3/product?id={episode_id}"
    try:
        res = requests.get(product_url, params=PARAMS, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return None
        
        data = res.json()
        # Navegar por la estructura de playables del producto
        content = data.get('data', {}).get('content', {})
        playables = content.get('playables', [])
        
        for p in playables:
            if 'assets' in p and 'hlsUrl' in p['assets']:
                return p['assets']['hlsUrl']
    except Exception as e:
        print(f"Error obteniendo HLS para ID {episode_id}: {e}")
    return None

def escanear_episodios():
    base_url = "https://tv.apple.com/api/uts/v3/shows/umc.cmc.7adu8wmjugygtdhfamor58yn8/episodes"
    params = PARAMS.copy()
    params.update({
        "includeSeasonSummary": "false",
        "selectedSeasonEpisodesOnly": "false",
        "utscf": "OjAAAAEAAAAAAAIAEAAAACMAKwAtAA~~",
        "utsk": "6e3013c6d6fae3c2:::::235656c069bb0efb"
    })
    
    episodios_info = {}
    next_token = None
    pagina = 1

    try:
        while True:
            current_params = params.copy()
            if next_token:
                current_params["nextToken"] = next_token
            
            res = requests.get(base_url, params=current_params, headers=HEADERS, timeout=15)
            if res.status_code != 200:
                print(f"Error en la API (Página {pagina}): Código {res.status_code}")
                break
                
            data_json = res.json()
            data_block = data_json.get('data', {})
            episodes_list = data_block.get('episodes', [])
            
            if not episodes_list:
                break

            print(f"--- Procesando página {pagina} ({len(episodes_list)} episodios) ---")
            
            for ep in episodes_list:
                season_num = ep.get('seasonNumber')
                ep_num = ep.get('episodeNumber')
                ep_id = ep.get('id')
                title = ep.get('title')
                
                if season_num is None or ep_num is None or not ep_id:
                    continue
                    
                ep_key = f"S{season_num:02d}E{ep_num:02d}"
                
                # Buscamos el HLS usando el ID específico del episodio
                hls_url = obtener_hls_episodio(ep_id)
                audios, subs = obtener_idiomas_de_m3u8(hls_url) if hls_url else ([], [])
                
                episodios_info[ep_key] = {"titulo": title, "audios": audios, "subtitulos": subs}
                print(f"Escaneado: {ep_key} - {title} (Audios: {len(audios)}, Subs: {len(subs)})")
            
            next_token = data_block.get('nextToken')
            if not next_token:
                break
            pagina += 1
            
        return episodios_info
    except Exception as e:
        print(f"Error general en escaneo: {e}")
        return {}

def main():
    archivo = 'datos.json'
    print("Iniciando escaneo profundo de Miraculous...")
    nuevos_datos = escanear_episodios()
    
    if nuevos_datos:
        with open(archivo, 'w', encoding='utf-8') as f:
            json.dump(nuevos_datos, f, indent=4, ensure_ascii=False)
        print(f"Escaneo completado. Total de episodios procesados: {len(nuevos_datos)}")
    else:
        print("No se pudieron extraer datos.")

if __name__ == "__main__":
    main()
