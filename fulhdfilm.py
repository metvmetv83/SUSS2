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
        res = requests.get(film_url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            plx_div = soup.find('div', id='plx')
            if plx_div:
                iframe = plx_div.find('iframe')
                if iframe:
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
            print(f"Hata: Sayfa {page_num} için durum kodu {response.status_code}")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        
        movie_data = []
        for film in films:
            title = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            
            if title and link_tag:
                f_url = link_tag['href'].rstrip('/')
                t_text = title.get_text(strip=True)
                
                print(f"   > {t_text} detayları çekiliyor...")
                rapid_link = detay_linki_cek(f_url)

                movie_data.append({
                    "title": t_text,
                    "link": f_url,
                    "rapid_link": rapid_link,
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                time.sleep(1) # Her film arası bekleme

        if movie_data:
            file_name = f'data/yeni-filmler-{page_num}.json'
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            print(f"--- Sayfa {page_num} kaydedildi: {file_name} ---")
            return True
    except Exception as e:
        print(f"Hata oluştu: {e}")
        return False
    return False

def main():
    baslangic = 1
    bitis = 111 
    
    print("İşlem başlıyor...")
    for p in range(baslangic, bitis + 1):
        # NOT: Mevcut dosyaları atlayan 'if exists' kısmını kaldırdım ki 
        # eksik linkli dosyalarınız güncellensin.
        
        print(f"\n--- Sayfa: {p} / {bitis} ---")
        success = sayfa_cek(p)
        
        if not success:
            print(f"Sayfa {p} çekilemedi. 5 saniye mola...")
            time.sleep(5)
            continue
            
        time.sleep(2)

if __name__ == "__main__":
    main()
