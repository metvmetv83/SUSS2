import requests
import re
import os
import warnings

# --- AYARLAR ---
warnings.filterwarnings('ignore')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Referer": "https://www.google.com/"
}

# --- KLASÖR ADI ---
OUTPUT_FOLDER = "yula"

# --- SABİT M3U8 BAŞLIĞI ---
M3U8_HEADER = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=5500000,AVERAGE-BANDWIDTH=8976000,RESOLUTION=1920x1080,CODECS="avc1.640028,mp4a.40.2",FRAME-RATE=25"""

# --- KANAL HARİTASI (Site ID -> Senin İstediğin Dosya Adı) ---
CHANNEL_MAP = [
    ("bein-sports-1", "ceydub1"),
    ("bein-sports-2", "ceydub2"),
    ("bein-sports-3", "ceydub3"),
    ("bein-sports-4", "ceydub4"),
    ("s-sport",       "ceydus1"),
    ("s-sport-2",     "ceydus2"),
    ("tivibu-spor-1", "ceydut1"),
    ("tivibu-spor-2", "ceydut2"),
    ("tivibu-spor-3", "ceydut3"),
    ("tivibu-spor-4", "ceydut4"),
]

# --- ATOMSPOR TV TARAMA FONKSİYONLARI ---

def find_active_atomsportv_domain():
    print("🔍 Aktif AtomSporTV domaini aranıyor (480-1000)...")
    for i in range(480, 1000):
        url = f"https://www.atomsportv{i}.top"
        try:
            response = requests.head(url, headers=HEADERS, timeout=2, allow_redirects=True)
            if 200 <= response.status_code < 400:
                final_url = response.url.rstrip('/')
                print(f"✅ Aktif Domain: {final_url}")
                return final_url
        except:
            continue
    
    fallback = "https://www.atomsportv480.top"
    print(f"❌ Domain bulunamadı, varsayılan deneniyor: {fallback}")
    return fallback

def get_channel_m3u8(channel_id, base_domain):
    local_headers = HEADERS.copy()
    local_headers['Referer'] = base_domain 
    
    try:
        # 1. matches?id= endpoint
        matches_url = f"{base_domain}/matches?id={channel_id}"
        response = requests.get(matches_url, headers=local_headers, timeout=10)
        html = response.text
        
        # 2. fetch URL'sini bul
        fetch_match = re.search(r'fetch\("(.*?)"', html)
        if not fetch_match:
            fetch_match = re.search(r'fetch\(\s*["\'](.*?)["\']', html)
        
        if fetch_match:
            fetch_url_part = fetch_match.group(1).strip()
            custom_headers = local_headers.copy()
            custom_headers['Origin'] = base_domain
            
            if not fetch_url_part.startswith('http'):
                fetch_url = f"{base_domain}{fetch_url_part}"
            else:
                fetch_url = fetch_url_part
                
            if not fetch_url.endswith(channel_id):
                fetch_url = fetch_url + channel_id
            
            response2 = requests.get(fetch_url, headers=custom_headers, timeout=10)
            fetch_data = response2.text
            
            # 4. m3u8 linkini bul
            m3u8_match = re.search(r'"deismackanal":"(.*?)"', fetch_data)
            if not m3u8_match:
                m3u8_match = re.search(r'"(?:stream|url|source)":\s*"(.*?\.m3u8)"', fetch_data)
                
            if m3u8_match:
                return m3u8_match.group(1).replace('\\', '')
        
        return None
    except Exception:
        return None

def main():
    # Klasör oluştur
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    print("--- Ceysu Bot (AtomSporTV) Başlatıldı ---")
    
    # 1. Domain bul
    base_domain = find_active_atomsportv_domain()
    
    print(f"\n⚡ Linkler '{OUTPUT_FOLDER}' klasörüne yazılıyor...")
    
    count = 0
    # 2. Kanalları Tara ve Kaydet
    for site_id, file_name in CHANNEL_MAP:
        m3u8_url = get_channel_m3u8(site_id, base_domain)
        
        if m3u8_url:
            # Dosya İçeriği
            file_content = f"{M3U8_HEADER}\n{m3u8_url}"
            
            # Dosya Yolu (yula/ceydub1.m3u8)
            file_path = os.path.join(OUTPUT_FOLDER, f"{file_name}.m3u8")
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)
                
            print(f"💾 Kaydedildi: {file_name}.m3u8")
            count += 1
        else:
            print(f"⚠️ Bulunamadı: {file_name} (Kaynak: {site_id})")

    print(f"\n✅ İŞLEM TAMAM! Toplam {count} dosya güncellendi.")

if __name__ == "__main__":
    main()
