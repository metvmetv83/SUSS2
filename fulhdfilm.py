import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

# Klasör kontrolü
if not os.path.exists('data'):
    os.makedirs('data')

def rapid_link_bul(film_url):
    """Film sayfasının içine girer ve rapidvid linkini söker."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Referer': 'https://www.fullhdfilmizlesene.live/'
    }
    try:
        response = requests.get(film_url, headers=headers, timeout=10)
        if response.status_code == 200:
            # Regex ile iframe içindeki rapidvid linkini yakala
            match = re.search(r'https?://rapidvid\.net/vod/[a-zA-Z0-9]+', response.text)
            if match:
                return match.group(0)
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
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        
        movie_data = []
        for film in films:
            title_node = film.find('span', class_='film-title')
            link_node = film.find('a', class_='tt')
            
            if title_node and link_node:
                film_full_url = link_node['href'].rstrip('/')
                print(f"--- Detay çekiliyor: {title_node.get_text(strip=True)}")
                
                # ASIL İŞLEM: Film detayına git ve rapidvid linkini al
                rapid_url = rapid_link_bul(film_full_url)
                
                movie_data.append({
                    "title": title_node.get_text(strip=True),
                    "link": film_full_url,
                    "rapid_link": rapid_url, # Yeni eklenen alan
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                # Siteyi yormamak ve banlanmamak için her film arası kısa bekleme
                time.sleep(1)

        if movie_data:
            with open(f'data/yeni-filmler-{page_num}.json', 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            return True
    except Exception as e:
        print(f"Hata oluştu: {e}")
        return False
    return False

def main():
    baslangic = 1
    bitis = 1113 
    
    for p in range(baslangic, bitis + 1):
        if os.path.exists(f'data/yeni-filmler-{p}.json'):
            continue
            
        print(f"\n>>> Sayfa İşleniyor: {p} / {bitis}")
        success = sayfa_cek(p)
        
        if not success:
            print(f"!!! Sayfa {p} çekilemedi. 10 saniye mola...")
            time.sleep(10)
            continue
            
        time.sleep(2)

if __name__ == "__main__":
    main()
