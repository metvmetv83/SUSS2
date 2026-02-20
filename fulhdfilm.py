import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

# Klasör kontrolü
if not os.path.exists('data'):
    os.makedirs('data')

def rapid_bul(film_url):
    """Film sayfasının içine girer ve iframe/rapidvid linkini bulur."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Referer': 'https://www.fullhdfilmizlesene.live/'
    }
    try:
        # Film detay sayfasını çek
        res = requests.get(film_url, headers=headers, timeout=10)
        if res.status_code == 200:
            # HTML içinde rapidvid linkini ara
            match = re.search(r'https?://rapidvid\.net/vod/[a-zA-Z0-9]+', res.text)
            if match:
                return match.group(0)
            
            # Eğer yukarıdaki bulamazsa iframe tag'ini tara
            soup = BeautifulSoup(res.text, 'html.parser')
            iframe = soup.find('iframe', src=re.compile(r'rapidvid\.net'))
            if iframe:
                return iframe['src']
    except:
        pass
    return ""

def sayfa_cek(page_num):
    url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    if page_num > 1:
        url = f"https://www.fullhdfilmizlesene.live/yeni-filmler/{page_num}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Referer': 'https://www.google.com/'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Hata: Sayfa {page_num} için status {response.status_code}")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        
        movie_data = []
        for film in films:
            title = film.find('span', class_='film-title')
            link = film.find('a', class_='tt')
            
            if title and link:
                film_url = link['href'].rstrip('/')
                print(f"--- Detay taranıyor: {title.get_text(strip=True)}")
                
                # ÖNEMLİ: Her film için içeri girip rapid linkini al
                rapid_link = rapid_bul(film_url)
                
                movie_data.append({
                    "title": title.get_text(strip=True),
                    "link": film_url,
                    "rapid_link": rapid_link, # Yeni eklenen alan
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                # Siteyi yormamak için kısa mola
                time.sleep(1)

        if movie_data:
            with open(f'data/yeni-filmler-{page_num}.json', 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            return True
    except Exception as e:
        print(f"Hata: {e}")
        return False
    return False

def main():
    baslangic = 1
    bitis = 1113 # Çok sayfa olduğu için parça parça çekmeni öneririm (örn: 1-10)
    
    for p in range(baslangic, bitis + 1):
        if os.path.exists(f'data/yeni-filmler-{p}.json'):
            continue
            
        print(f"\n>>> İşleniyor: Sayfa {p} / {bitis}")
        success = sayfa_cek(p)
        
        if not success:
            print(f"Sayfa {p} çekilemedi. Bekleniyor...")
            time.sleep(10)
            continue
            
        time.sleep(2)

if __name__ == "__main__":
    main()
