import requests
import re
import os
import urllib3
import warnings

# SSL ve uyarıları kapat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

output_folder = "streams"
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
}

# 1. BÖLÜM: Güncel Site Domainini Bul
base_site_name = "https://trgoals"
active_domain = ""

print("🔍 Ana site domaini aranıyor...")
for i in range(1495, 2101):
    test_url = f"{base_site_name}{i}.xyz"
    try:
        response = requests.get(test_url, headers=HEADERS, timeout=1.5, verify=False)
        if response.status_code == 200:
            active_domain = test_url
            print(f"✅ Güncel Domain: {active_domain}")
            break
    except:
        continue

if not active_domain:
    print("❌ Ana site bulunamadı.")
    exit()

# Kanal Listesi
channel_ids = [
    "yayinzirve", "yayininat", "yayin1", "yayinb2", "yayinb3", "yayinb4",
    "yayinb5", "yayinbm1", "yayinbm2", "yayinss", "yayinss2", "yayint1",
    "yayint2", "yayint3", "yayint4", "yayinsmarts", "yayinsms2", "yayinnbatv", 
    "yayinex1", "yayinex2", "yayinex3", "yayinex4", "yayinex5", "yayinex6",
    "yayinex7", "yayinex8", "yayineu1", "yayineu2"
]

header_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=5500000,AVERAGE-BANDWIDTH=8976000,RESOLUTION=1920x1080,CODECS="avc1.640028,mp4a.40.2",FRAME-RATE=25"""

print("📂 Yayın linkleri ayıklanıyor...")

# 2. BÖLÜM: Yayın Sunucusunu (B_URL) ve Kanalları Bul
for channel_id in channel_ids:
    target_url = f"{active_domain}/channel.html?id={channel_id}"
    try:
        req_headers = HEADERS.copy()
        req_headers['Referer'] = active_domain + "/"
        
        r = requests.get(target_url, headers=req_headers, timeout=5, verify=False)
        
        # ESNEK REGEX: Değişken adı ne olursa olsun (B_URL, BASE_URL vb.) 
        # tırnak içindeki http...sbs/ veya http...xyz/ formatındaki linki bulur.
        found_url = ""
        # 1. Yöntem: B_URL veya BASE_URL araması
        match = re.search(r'(?:B_URL|BASE_URL|server|link)\s*=\s*["\'](https?://[^"\']+/ )["\']', r.text)
        
        if match:
            found_url = match.group(1)
        else:
            # 2. Yöntem: Eğer değişken ismi tamamen değişirse, tırnak içindeki uygun URL'yi ara
            urls = re.findall(r'["\'](https?://[a-z0-9.]+\.(?:sbs|xyz|me|live|com|net)/)["\']', r.text)
            if urls:
                found_url = urls[0]

        if found_url:
            # Linkin sonunda / olduğundan emin ol ve kanalı ekle
            found_url = found_url.rstrip('/') + '/'
            stream_link = f"{found_url}{channel_id}.m3u8"
            
            file_content = f"{header_content}\n{stream_link}"
            file_path = os.path.join(output_folder, f"{channel_id}.m3u8")
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(file_content)
            print(f"✅ {channel_id}.m3u8 -> Sunucu: {found_url}")
        else:
            print(f"⚠️ {channel_id} için sunucu adresi bulunamadı.")
            
    except Exception as e:
        print(f"❌ {channel_id} hatası: {e}")

print("\n🏁 Tüm işlemler bitti. 'streams' klasörünü kontrol et.")
