import requests
from bs4 import BeautifulSoup
import json
import os
import time

# Çıktı klasörünü hazırla
if not os.path.exists('data'):
    os.makedirs('data')

# Oturum yönetimi (Hız ve engel aşma için)
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'tr-TR,tr;q=0.8,en-US;q=0.5,en;q=0.3',
})

def detay_linki_cek(film_url):
    """
    Film sayfasına girer, video oynatıcıyı (rapid_link) bulmak için 
    tüm alternatif etiketleri tarar.
    """
    try:
        # Referer her zaman gidilen sayfanın kendisi olmalı
        res = session.get(film_url, timeout=12, headers={'Referer': film_url})
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 1. Öncelik: div#plx içindeki iframe (Standart yapı)
            plx_div = soup.find('div', id='plx')
            if plx_div:
                iframe = plx_div.find('iframe')
                if iframe:
                    # data-src, src, data-lazy-src gibi tüm ihtimalleri kontrol et
                    link = (iframe.get('data-src') or 
                            iframe.get('src') or 
                            iframe.get('data-lazy-src'))
                    if link:
                        return "https:" + link if link.startswith("//") else link

            # 2. Öncelik: Sayfadaki herhangi bir embed/video iframe'i
            for f in soup.find_all('iframe'):
                src = f.get('data-src') or f.get('src')
                if src and any(x in src for x in ['player', 'embed', 'vidmoly', 'ok.ru', 'mail.ru']):
                    return "https:" + src if src.startswith("//") else src
                    
    except Exception as e:
        print(f"      ! Detay hatası: {e}")
    return ""

def sayfa_cek(page_num):
    """Belirlenen sayfadaki tüm filmleri ve detaylarını çeker."""
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"

    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            print(f"Hata: Sayfa {page_num} (Kod: {response.status_code})")
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
                
                print(f"    > İşleniyor: {t_text}")
                rapid_link = detay_linki_cek(f_url)

                movie_data.append({
                    "title": t_text,
                    "link": f_url,
                    "rapid_link": rapid_link,
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                # Ban yememek için makul bekleme
                time.sleep(0.7)

        if movie_data:
            file_name = f'data/yeni-filmler-{page_num}.json'
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            return True

    except Exception as e:
        print(f"Sayfa hatası: {e}")
        return False
    return False

def main():
    baslangic = 1
    bitis = 11 # İhtiyaca göre güncellenebilir
    
    print("=== Bot Başlatıldı ===")
    for p in range(baslangic, bitis + 1):
        # Kontrol: Dosya zaten varsa atla (Checkpoint özelliği)
        if os.path.exists(f'data/yeni-filmler-{p}.json'):
            print(f"--- Sayfa {p} zaten mevcut, atlanıyor. ---")
            continue
            
        print(f"\n--- Sayfa {p} / {bitis} Çekiliyor ---")
        success = sayfa_cek(p)
        
        if not success:
            print(f"!!! Sayfa {p} başarısız oldu. Bekleniyor...")
            time.sleep(10) # Hata durumunda siteyi yormamak için uzun mola
        else:
            print(f"+++ Sayfa {p} başarıyla tamamlandı.")
            time.sleep(2)

if __name__ == "__main__":
    main()
