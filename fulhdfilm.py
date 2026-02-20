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
    """Film detay sayfasından iframe linkini çeker."""
    try:
        response = requests.get(film_url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Iframe'i bul (data-src öncelikli, sonra src)
            iframe = soup.find('iframe')
            if iframe:
                return iframe.get('data-src') or iframe.get('src') or ""
    except Exception as e:
        print(f"      [!] Hata: {film_url} çekilemedi: {e}")
    return ""

def guncelle():
    # Klasördeki tüm dosyaları listele
    files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.json')]
    # Dosyaları isim sırasına göre diz (yeni-filmler-1.json, 2.json...)
    files.sort()

    for file_name in files:
        file_path = os.path.join(DATA_FOLDER, file_name)
        print(f"\n--- Dosya İnceleniyor: {file_name} ---")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        guncelleme_yapildi = False
        
        for film in data:
            # Eğer rapid_link anahtarı yoksa veya boşsa çekim yap
            if not film.get('rapid_link') or film['rapid_link'] == "":
                print(f"   > Link çekiliyor: {film['title']}")
                
                v_link = video_linki_bul(film['link'])
                
                if v_link:
                    film['rapid_link'] = v_link
                    guncelleme_yapildi = True
                    print(f"     [OK] Bulundu: {v_link}")
                else:
                    print(f"     [!] Link bulunamadı.")
                
                # Engellenmemek için kısa mola
                time.sleep(1)

        # Eğer dosyada herhangi bir değişiklik yapıldıysa üzerine yaz
        if guncelleme_yapildi:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            print(f"--- {file_name} güncellendi ve kaydedildi. ---")
        else:
            print(f"--- {file_name} zaten güncel, değişiklik yok. ---")

if __name__ == "__main__":
    if not os.path.exists(DATA_FOLDER):
        print("Hata: 'data' klasörü bulunamadı!")
    else:
        guncelle()
