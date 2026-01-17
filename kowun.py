import requests
import re
import os

# --- AYARLAR ---
START_URL = "https://url24.link/AtomSporTV"
OUTPUT_FOLDER = "atom"
GREEN = "\033[92m"
RESET = "\033[0m"

HEADERS = {
    'Accept': '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36',
    'Referer': 'https://url24.link/'
}

# --- SABİT M3U8 BAŞLIĞI ---
M3U8_HEADER = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=5500000,AVERAGE-BANDWIDTH=8976000,RESOLUTION=1920x1080,CODECS="avc1.640028,mp4a.40.2",FRAME-RATE=25"""

def get_base_domain():
    try:
        response = requests.get(START_URL, headers=HEADERS, allow_redirects=False, timeout=10)
        
        if 'location' in response.headers:
            location1 = response.headers['location']
            response2 = requests.get(location1, headers=HEADERS, allow_redirects=False, timeout=10)
            
            if 'location' in response2.headers:
                base_domain = response2.headers['location'].strip().rstrip('/')
                print(f"✅ Ana Domain Bulundu: {base_domain}")
                return base_domain
        
        return "https://www.atomsportv480.top"
        
    except Exception as e:
        print(f"Domain Hatası: {e}")
        return "https://www.atomsportv480.top"

def get_channel_m3u8(channel_id, base_domain):
    try:
        matches_url = f"{base_domain}/matches?id={channel_id}"
        response = requests.get(matches_url, headers=HEADERS, timeout=10)
        html = response.text
        
        fetch_match = re.search(r'fetch\("(.*?)"', html)
        if not fetch_match:
            fetch_match = re.search(r'fetch\(\s*["\'](.*?)["\']', html)
        
        if fetch_match:
            fetch_url = fetch_match.group(1).strip()
            
            custom_headers = HEADERS.copy()
            custom_headers['Origin'] = base_domain
            custom_headers['Referer'] = base_domain
            
            if not fetch_url.endswith(channel_id):
                fetch_url = fetch_url + channel_id
            
            response2 = requests.get(fetch_url, headers=custom_headers, timeout=10)
            fetch_data = response2.text
            
            m3u8_match = re.search(r'"deismackanal":"(.*?)"', fetch_data)
            if m3u8_match:
                return m3u8_match.group(1).replace('\\', '')
            
            m3u8_match = re.search(r'"(?:stream|url|source)":\s*"(.*?\.m3u8)"', fetch_data)
            if m3u8_match:
                return m3u8_match.group(1).replace('\\', '')
        
        return None
        
    except Exception:
        return None

def get_channels_list():
    return [
        {"id": "bein-sports-1", "name": "beIN Sports 1"},
        {"id": "bein-sports-2", "name": "beIN Sports 2"},
        {"id": "bein-sports-3", "name": "beIN Sports 3"},
        {"id": "bein-sports-4", "name": "beIN Sports 4"},
        {"id": "s-sport", "name": "S Sport 1"},
        {"id": "s-sport-2", "name": "S Sport 2"},
        {"id": "tivibu-spor-1", "name": "Tivibu Spor 1"},
        {"id": "tivibu-spor-2", "name": "Tivibu Spor 2"},
        {"id": "tivibu-spor-3", "name": "Tivibu Spor 3"},
        {"id": "trt-spor", "name": "TRT Spor"},
        {"id": "trt-yildiz", "name": "TRT Yildiz"},
        {"id": "trt1", "name": "TRT 1"},
        {"id": "aspor", "name": "A Spor"},
    ]

def main():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    print(f"{GREEN}--- AtomSporTV Tarayıcı (Klasör Modu) ---{RESET}")
    
    base_domain = get_base_domain()
    channels = get_channels_list()

    print(f"⚡ Linkler '{OUTPUT_FOLDER}' klasörüne yazılıyor...")

    count = 0
    for i, channel in enumerate(channels):
        print(f"{i+1}. {channel['name']} taranıyor...", end=" ", flush=True)
        
        m3u8_url = get_channel_m3u8(channel['id'], base_domain)
        
        if m3u8_url:
            file_name = f"{channel['id']}.m3u8"
            file_path = os.path.join(OUTPUT_FOLDER, file_name)
            
            # Değişiklik: Sadece header ve link var, EXTVLCOPT kaldırıldı.
            file_content = f"{M3U8_HEADER}\n{m3u8_url}"
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)
                
            print(f"{GREEN}✓ Kaydedildi: {file_name}{RESET}")
            count += 1
        else:
            print("✗ Link bulunamadı")

    print(f"\n✅ İŞLEM TAMAM! {count} adet kanal '{OUTPUT_FOLDER}' klasörüne kaydedildi.")

if __name__ == "__main__":
    main()
