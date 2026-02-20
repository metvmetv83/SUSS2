import requests
from bs4 import BeautifulSoup
import json
import os
import time

# Klasör kontrolü
if not os.path.exists('data'):
    os.makedirs('data')

def sayfa_cek(page_num):
    # Sayfa 1 için özel link yapısı, diğerleri için /sayfa_no
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
            link = film.find('a', class_='tt')
            if title and link:
                movie_data.append({
                    "title": title.get_text(strip=True),
                    "link": link['href'].rstrip('/'),
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })

        if movie_data:
            with open(f'data/yeni-filmler-{page_num}.json', 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            return True
    except:
        return False
    return False

def main():
    # 1'den 1113'e kadar döngü
    baslangic = 1
    bitis = 1113 
    
    for p in range(baslangic, bitis + 1):
        # Eğer dosya zaten varsa çekme (Hız kazandırır ve sunucuyu yormaz)
        if os.path.exists(f'data/yeni-filmler-{p}.json'):
            continue
            
        print(f"İşleniyor: Sayfa {p} / {bitis}")
        success = sayfa_cek(p)
        
        if not success:
            print(f"Sayfa {p} çekilemedi. Bir mola veriliyor...")
            time.sleep(5) # Hata alınca biraz daha uzun bekle
            continue
            
        # Her 10 sayfada bir GitHub'ın limitlerine takılmamak için kısa bekleme
        if p % 10 == 0:
            time.sleep(2)

if __name__ == "__main__":
    main()
