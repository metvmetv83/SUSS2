import requests
from bs4 import BeautifulSoup
import json
import os
import time

# Klasör kontrolü
if not os.path.exists('data'):
    os.makedirs('data')

def video_linki_bul(film_url):
    """Film detay sayfasına girip iframe içindeki video linkini çeker."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Referer': 'https://www.fullhdfilmizlesene.live/'
    }
    try:
        # Detay sayfasına istek at
        response = requests.get(film_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Iframe etiketini bul (Önce data-src, yoksa src)
            iframe = soup.find('iframe')
            if iframe:
                video_url = iframe.get('data-src') or iframe.get('src')
                return video_url
    except Exception as e:
        print(f"      [!] Detay sayfası hatası: {e}")
    return ""

def sayfa_cek(page_num):
    # Sayfa 1 için özel link yapısı
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
            title_tag = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            
            if title_tag and link_tag:
                film_title = title_tag.get_text(strip=True)
                film_url = link_tag['href'].rstrip('/')
                
                print(f"   >>> {film_title} için video linki aranıyor...")
                
                # Film detay sayfasındaki video linkini çek
                video_url = video_linki_bul(film_url)
                
                movie_data.append({
                    "title": film_title,
                    "link": film_url,
                    "video_url": video_url,
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                
                # Sunucuyu yormamak için her film arası kısa bekleme
                time.sleep(0.8)

        if movie_data:
            file_path = f'data/yeni-filmler-{page_num}.json'
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            return True
            
    except Exception as e:
        print(f"Hata oluştu: {e}")
        return False
    return False

def main():
    baslangic = 1
    bitis = 1113 
    
    print(f"İşlem başlatıldı. {baslangic} ile {bitis} arası sayfalar taranacak.")
    
    for p in range(baslangic, bitis + 1):
        if os.path.exists(f'data/yeni-filmler-{p}.json'):
            print(f"Sıra {p}: Dosya zaten var, atlanıyor.")
            continue
            
        print(f"\n--- İşleniyor: Sayfa {p} / {bitis} ---")
        success = sayfa_cek(p)
        
        if not success:
            print(f"Sayfa {p} çekilemedi. 5 saniye mola...")
            time.sleep(5)
            continue
            
        # Sayfa geçişlerinde bloklanmamak için dinlenme
        print(f"Sayfa {p} tamamlandı. Dinleniliyor...")
        time.sleep(2)

if __name__ == "__main__":
    main()
