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
    Sadece standart requests kullanarak, 
    siteyi kandırıp rapidvid linkini çekmeye çalışır.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Referer': film_url, # Burası hayati önem taşıyor
        'Accept-Language': 'tr-TR,tr;q=0.8,en-US;q=0.5,en;q=0.3',
    }
    
    try:
        # Session kullanarak oturumu koru
        with requests.Session() as s:
            res = s.get(film_url, headers=headers, timeout=12)
            if res.status_code == 200:
                content = res.text
                
                # --- STRATEJİ: Metin İçinde RapidVid ID ve Link Arama ---
                # Link doğrudan geçiyorsa (https://rapidvid.net/vod/...)
                rapid_match = re.search(r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/[a-zA-Z0-9]+', content)
                if rapid_match:
                    return rapid_match.group(0).replace('\\', '')

                # ID olarak geçiyorsa (video_id: "v1xaadef5ab")
                id_match = re.search(r'["\']?(?:vid|video_id|id)["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{5,})["\']', content)
                if id_match:
                    return f"https://rapidvid.net/vod/{id_match.group(1)}"
                
                # Iframe içinde gizliyse
                soup = BeautifulSoup(content, 'html.parser')
                iframe = soup.find('iframe', src=re.compile(r'rapid|player|embed'))
                if iframe:
                    src = iframe.get('data-src') or iframe.get('src')
                    if src:
                        return "https:" + src if src.startswith("//") else src
    except:
        pass
    return ""

def sayfa_cek(page_num):
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200: return False

        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        
        movie_data = []
        for film in films:
            title = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            
            if title and link_tag:
                f_url = link_tag['href'].rstrip('/')
                print(f"    > Çekiliyor: {title.text}")
                
                rapid_link = detay_linki_cek(f_url)

                movie_data.append({
                    "title": title.text,
                    "link": f_url,
                    "rapid_link": rapid_link,
                    "imdb": film.find('span', class_='imdb').text if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').text if film.find('span', class_='film-yil') else "",
                    "image": film.find('img').get('data-src') or film.find('img').get('src')
                })
                time.sleep(1)

        if movie_data:
            with open(f'data/yeni-filmler-{page_num}.json', 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            return True
    except:
        return False

def main():
    for p in range(1, 1114):
        print(f"\n--- Sayfa {p} ---")
        sayfa_cek(p)

if __name__ == "__main__":
    main()
