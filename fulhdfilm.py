import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
import random

# Klasör kontrolü
if not os.path.exists('data'):
    os.makedirs('data')

def detay_linki_cek(film_url, session):
    """
    Karmaşık ID'leri (v1xaadef5ab) bulur ve linki oluşturur.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Referer': film_url,
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive'
    }
    
    try:
        res = session.get(film_url, headers=headers, timeout=15)
        if res.status_code == 200:
            content = res.text
            
            # 1. Strateji: v1 ile başlayan karmaşık ID'yi ara
            # Örnek: v1xaadef5ab
            v_id_match = re.search(r'["\'](v[a-zA-Z0-9]{5,15})["\']', content)
            if v_id_match:
                return f"https://rapidvid.net/vod/{v_id_match.group(1)}"

            # 2. Strateji: Tam link olarak geçiyorsa yakala
            rapid_match = re.search(r'rapidvid\.net/(?:vod|v|embed)/([a-zA-Z0-9_-]+)', content)
            if rapid_match:
                return f"https://rapidvid.net/vod/{rapid_match.group(1)}"

    except Exception:
        pass
    return ""

def sayfa_cek(page_num, session):
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    }

    try:
        # Sitenin korumasını aşmak için kısa bir mola
        time.sleep(random.uniform(2, 4)) 
        
        response = session.get(url, headers=headers, timeout=20)
        
        # Eğer site 403 veya 429 verirse (Engellendiğimizi anlarız)
        if response.status_code != 200:
            print(f"!!! Hata: Durum Kodu {response.status_code} (Site muhtemelen engelledi)")
            return "retry"

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
                print(f"    > Kaynak: {title_tag.text[:30]}...")
                
                rapid_link = detay_linki_cek(f_url, session)

                movie_data.append({
                    "title": title_tag.text,
                    "link": f_url,
                    "rapid_link": rapid_link,
                    "imdb": film.find('span', class_='imdb').text if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').text if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                # Her film arası kısa rastgele bekleme
                time.sleep(random.uniform(1, 2))

        if movie_data:
            with open(f'data/yeni-filmler-{page_num}.json', 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            return True
    except Exception as e:
        print(f"Sistem Hatası: {e}")
        return False

def main():
    session = requests.Session()
    print("--- RAPIDVID (v1 ID) TARAYICI BAŞLATILDI ---")
    
    # Hata aldığın sayfa 268'den başlatabilirsin veya 1'den devam edebilirsin
    for p in range(1, 1114):
        # Eğer dosya zaten varsa ve içi doluysa atla (Zaman kazanmak için)
        if os.path.exists(f'data/yeni-filmler-{p}.json'):
            continue

        print(f"\n--- İşlem: Sayfa {p} ---")
        result = sayfa_cek(p, session)
        
        if result == "retry":
            print("Engellendik! 60 saniye mola veriliyor...")
            time.sleep(60) # 1 dakika bekle ve sonraki sayfaya geçmeye çalış
            
if __name__ == "__main__":
    main()
