import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

# 1. Klasör ve Ayarlar
if not os.path.exists('data'):
    os.makedirs('data')

# Session ve Header yapılandırması (Cloudflare ve Bot engelini aşmak için)
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'tr-TR,tr;q=0.8,en-US;q=0.5,en;q=0.3',
    'Referer': 'https://www.fullhdfilmizlesene.live/'
})

def detay_linki_cek(film_url):
    """
    Rapidvid ve gizli player linklerini yakalamak için hibrit tarama yapar.
    """
    try:
        # İstek atarken o sayfanın referer bilgisini kullan
        res = session.get(film_url, timeout=12, headers={'Referer': film_url})
        if res.status_code == 200:
            content = res.text
            
            # --- YÖNTEM 1: Regex ile RapidVid Arama ---
            # Sayfa içinde gizli scriptlerin arasındaki linki cımbızla çeker
            rapid_pattern = r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/[a-zA-Z0-9]+'
            match = re.search(rapid_pattern, content)
            if match:
                return match.group(0).replace('\\', '')

            # --- YÖNTEM 2: iframe ve data-src Kontrolü ---
            soup = BeautifulSoup(content, 'html.parser')
            # id="plx" veya genel iframe'leri tara
            for iframe in soup.find_all('iframe'):
                src = iframe.get('data-src') or iframe.get('src') or ""
                if "rapid" in src or "vid" in src:
                    # Link // ile başlıyorsa protokol ekle
                    return "https:" + src if src.startswith("//") else src

            # --- YÖNTEM 3: JSON/Script Değişken Taraması ---
            # Bazı siteler: video_url: "..." şeklinde saklar
            var_match = re.search(r'["\']?(?:url|file|source|link)["\']?\s*[:=]\s*["\'](https?://[^"\']+)["\']', content)
            if var_match:
                candidate = var_match.group(1).replace('\\', '')
                if "rapid" in candidate:
                    return candidate

    except Exception as e:
        print(f"      ! Hata: {e}")
    return ""

def sayfa_cek(page_num):
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"

    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            print(f"Hata: Sayfa {page_num} durum kodu {response.status_code}")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        
        if not films: return False

        movie_data = []
        for film in films:
            title_tag = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            
            if title_tag and link_tag:
                f_url = link_tag['href'].rstrip('/')
                t_text = title_tag.get_text(strip=True)
                
                print(f"    > Kaynak Aranıyor: {t_text}")
                rapid_link = detay_linki_cek(f_url)

                movie_data.append({
                    "title": t_text,
                    "link": f_url,
                    "rapid_link": rapid_link,
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                time.sleep(1) # Siteyi bloklamamak için

        if movie_data:
            file_name = f'data/yeni-filmler-{page_num}.json'
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            print(f"--- Sayfa {page_num} Kaydedildi ---")
            return True
    except Exception as e:
        print(f"Sayfa {page_num} hatası: {e}")
        return False

def main():
    baslangic = 1
    bitis = 1113 # İsteğe göre ayarlanabilir
    
    print("=== RAPIDVID ODAKLI BOT BASLADI ===")
    for p in range(baslangic, bitis + 1):
        # Eğer GitHub Actions'ta zaman yetmiyorsa, mevcut dosyayı atlayabiliriz
        if os.path.exists(f'data/yeni-filmler-{p}.json'):
             print(f"--- Sayfa {p} zaten var, atlanıyor. ---")
             continue

        success = sayfa_cek(p)
        if not success:
            print(f"Sayfa {p} çekilemedi, 5 saniye mola.")
            time.sleep(5)
            
if __name__ == "__main__":
    main()
