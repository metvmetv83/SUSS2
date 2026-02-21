import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

# Klasör kontrolü
if not os.path.exists('data'):
    os.makedirs('data')

# Session yapılandırması
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Referer': 'https://www.fullhdfilmizlesene.live/'
})

def detay_linki_cek(film_url):
    """
    Özellikle rapidvid.net ve dinamik video ID'lerini yakalamaya odaklanır.
    """
    try:
        res = session.get(film_url, timeout=10)
        if res.status_code == 200:
            content = res.text
            
            # 1. ADIM: Doğrudan Link Arama (Regex ile Rapidvid Odaklı)
            # Sayfa içinde rapidvid.net geçen her şeyi yakalar
            rapidvid_match = re.search(r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/[a-zA-Z0-9]+', content)
            if rapidvid_match:
                return rapidvid_match.group(0)

            # 2. ADIM: iframe İçindeki data-src veya src Kontrolü
            soup = BeautifulSoup(content, 'html.parser')
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('data-src') or iframe.get('src') or ""
                if "rapidvid" in src or "rapid" in src:
                    return "https:" + src if src.startswith("//") else src

            # 3. ADIM: Sayfa İçindeki Gizli ID'lerden Link Oluşturma
            # Bazı siteler sadece ID'yi saklar: video_id = "v1xaadef5ab"
            id_match = re.search(r'(?:video_id|vid|id)\s*[:=]\s*["\']([a-zA-Z0-9]+)["\']', content)
            if id_match:
                video_id = id_match.group(1)
                # Eğer ID uzunluğu makul ise (örn 10-12 karakter) rapidvid formatına sok
                if 8 <= len(video_id) <= 15:
                    return f"https://rapidvid.net/vod/{video_id}"

    except Exception as e:
        print(f"      ! Hata: {e}")
    return ""

def sayfa_cek(page_num):
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"

    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        
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
                time.sleep(1) # Siteyi yormadan ilerle

        if movie_data:
            file_name = f'data/yeni-filmler-{page_num}.json'
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            print(f"--- Sayfa {page_num} Kaydedildi ---")
            return True
    except Exception as e:
        print(f"Hata: {e}")
        return False

def main():
    # Mevcut dosyaları silmek istersen manuel silebilirsin veya
    # üzerine yazması için checkpoint kontrolünü kaldırdım.
    for p in range(1, 11):
        print(f"\n--- Sayfa {p} İşleniyor ---")
        success = sayfa_cek(p)
        if not success:
            time.sleep(5)

if __name__ == "__main__":
    main()
