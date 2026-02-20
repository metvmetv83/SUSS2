import requests
from bs4 import BeautifulSoup
import json
import os
import time

# Ayarlar
DATA_FOLDER = 'data'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Referer': 'https://www.fullhdfilmizlesene.live/'
}

def video_linki_bul(film_url):
    """HTML yapısına göre div#plx içindeki iframe linkini çeker."""
    try:
        response = requests.get(film_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. Yöntem: Direkt id="plx" olan div'in içindeki iframe'i bul
            plx_div = soup.find('div', id='plx')
            if plx_div:
                iframe = plx_div.find('iframe')
                if iframe:
                    link = iframe.get('data-src') or iframe.get('src')
                    if link: return link

            # 2. Yöntem: Eğer plx bulunamazsa tüm sayfadaki iframe'leri tara
            iframes = soup.find_all('iframe')
            for f in iframes:
                src = f.get('data-src') or f.get('src')
                if src and ('rapidvid' in src or 'video' in src):
                    return src
                    
    except Exception as e:
        print(f"      [!] Bağlantı hatası: {e}")
    return ""

def guncelle():
    if not os.path.exists(DATA_FOLDER):
        print(f"Hata: {DATA_FOLDER} klasörü bulunamadı!")
        return

    # Dosyaları listele
    files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.json')]
    files.sort() # 1'den başlayarak ilerle

    for file_name in files:
        file_path = os.path.join(DATA_FOLDER, file_name)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except:
                continue

        degisiklik_var = False
        print(f"\n--- Dosya: {file_name} ---")

        for film in data:
            # Eğer rapid_link yoksa veya boşsa çek
            if not film.get('rapid_link') or film['rapid_link'] == "":
                print(f"   > Sorgulanıyor: {film['title']}")
                
                v_link = video_linki_bul(film['link'])
                
                if v_link:
                    film['rapid_link'] = v_link
                    degisiklik_var = True
                    print(f"     [OK] Link: {v_link}")
                else:
                    print(f"     [!] Link hala bulunamadı.")
                
                # Siteyi yormamak için bekleme (Önemli!)
                time.sleep(1.2)

        # Sadece değişiklik varsa dosyayı kaydet
        if degisiklik_var:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"--- {file_name} güncellendi. ---")

if __name__ == "__main__":
    guncelle()
