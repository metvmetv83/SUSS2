import requests
from bs4 import BeautifulSoup
import json
import os
import time

# Klasör kontrolü
if not os.path.exists('data'):
    os.makedirs('data')

def detay_linki_cek(film_url):
    """Film sayfasına girer ve div#plx içindeki iframe linkini yakalar."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Referer': 'https://www.fullhdfilmizlesene.live/'
    }
    try:
        # Film detay sayfasını indir
        res = requests.get(film_url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # 1. Hedef: id'si 'plx' olan div'i bul
            plx_div = soup.find('div', id='plx')
            if plx_div:
                iframe = plx_div.find('iframe')
                if iframe:
                    # data-src varsa onu al, yoksa src'yi al
                    return iframe.get('data-src') or iframe.get('src') or ""
    except:
        return ""
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
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        
        movie_data = []
        for film in films:
            title = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            
            if title and link_tag:
                f_url = link_tag['href'].rstrip('/')
                
                # Film detayına gidip iframe linkini alıyoruz
                print(f"   > Detay Çekiliyor: {title.get_text(strip=True)}")
                rapid_link = detay_linki_cek(f_url)

                movie_data.append({
                    "title": title.get_text(strip=True),
                    "link": f_url,
                    "rapid_link": rapid_link, # Video linki buraya eklendi
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                # Siteyi yormamak ve banlanmamak için kısa mola
                time.sleep(1)

        if movie_data:
            with open(f'data/yeni-filmler-{page_num}.json', 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            return True
    except:
        return False
    return False

def main():
    baslangic = 1
    bitis = 1113 
    
    for p in range(baslangic, bitis + 1):
        if os.path.exists(f'data/yeni-filmler-{p}.json'):
            continue
            
        print(f"\n--- Sayfa Başlatıldı: {p} / {bitis} ---")
        success = sayfa_cek(p)
        
        if not success:
            print(f"Sayfa {p} çekilemedi. Mola veriliyor...")
            time.sleep(5)
            continue
            
        # Her sayfa değişiminde sunucuyu dinlendirelim
        time.sleep(2)

if __name__ == "__main__":
    main()
