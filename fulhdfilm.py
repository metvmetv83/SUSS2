import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

# Klasör kontrolü
if not os.path.exists('data'):
    os.makedirs('data')

def detay_linki_cek(film_url):
    """
    Film sayfasındaki gizli Rapidvid ID'sini bulur ve linki oluşturur.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://www.fullhdfilmizlesene.live/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    }
    
    try:
        # Session kullanımı bağlantıyı canlı tutar ve hızı artırır
        with requests.Session() as s:
            res = s.get(film_url, headers=headers, timeout=15)
            if res.status_code == 200:
                content = res.text
                
                # --- STRATEJİ 1: Doğrudan Rapidvid Linkini Ara ---
                # Sayfa içinde https://rapidvid.net/vod/v1... gibi geçenleri yakalar
                rapid_pattern = r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/([a-zA-Z0-9_-]+)'
                match = re.search(rapid_pattern, content)
                if match:
                    # Eşleşen ID'yi al ve istediğin formatta döndür
                    video_id = match.group(1)
                    return f"https://rapidvid.net/vod/{video_id}"

                # --- STRATEJİ 2: Gizli Değişkenleri Tara ---
                # Bazı siteler sadece ID'yi saklar: videoId: "v1xaadef5ab"
                id_patterns = [
                    r'["\']?videoId["\']?\s*[:=]\s*["\']([a-zA-Z0-9_-]{5,})["\']',
                    r'["\']?vid["\']?\s*[:=]\s*["\']([a-zA-Z0-9_-]{5,})["\']',
                    r'id\s*[:=]\s*["\'](v[a-zA-Z0-9_-]+)["\']'
                ]
                
                for pattern in id_patterns:
                    id_match = re.search(pattern, content)
                    if id_match:
                        return f"https://rapidvid.net/vod/{id_match.group(1)}"

                # --- STRATEJİ 3: BeautifulSoup ile Iframe Taraması ---
                soup = BeautifulSoup(content, 'html.parser')
                for iframe in soup.find_all('iframe'):
                    src = iframe.get('data-src') or iframe.get('src') or ""
                    if "rapidvid" in src:
                        # Linkin içindeki ID'yi ayıkla
                        id_extract = re.search(r'/(?:vod|v|embed)/([a-zA-Z0-9_-]+)', src)
                        if id_extract:
                            return f"https://rapidvid.net/vod/{id_extract.group(1)}"
    except Exception as e:
        print(f"      ! Hata: {e}")
        
    return ""

def sayfa_cek(page_num):
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}

    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            print(f"Hata: Sayfa {page_num} alınamadı.")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        
        if not films:
            return False

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
                # Ban yememek için 1 saniye mola
                time.sleep(1)

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
    print("--- RAPIDVID TARAYICI BAŞLATILDI ---")
    # Sayfa 1'den 1113'e kadar
    for p in range(1, 1114):
        # Mevcut sayfayı atlamıyoruz, çünkü linkleri yeni formatta bulmamız lazım
        print(f"\n--- İşlem: Sayfa {p} ---")
        success = sayfa_cek(p)
        if not success:
            time.sleep(5)

if __name__ == "__main__":
    main()
