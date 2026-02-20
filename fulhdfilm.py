import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

if not os.path.exists('data'):
    os.makedirs('data')

def detay_link_sokucu(film_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Referer': 'https://www.fullhdfilmizlesene.live/'
    }
    try:
        res = requests.get(film_url, headers=headers, timeout=10)
        if res.status_code != 200: return ""
        
        html = res.text
        
        # 1. YÖNTEM: HTML içinde direkt linki ara (Regex)
        match = re.search(r'https?://rapidvid\.net/vod/[a-zA-Z0-9]+', html)
        if match: return match.group(0)
        
        # 2. YÖNTEM: VidID yakalayıp API'den asıl linki iste
        # Site bazen linki: "vidid = '12345'" şeklinde saklar.
        vid_match = re.search(r'vidid\s*=\s*[\'"]([^\'"]+)[\'"]', html)
        if vid_match:
            vid_id = vid_match.group(1)
            api_url = f"https://www.fullhdfilmizlesene.live/player/api.php?id={vid_id}&type=t&name=atom&get=video&format=json"
            api_res = requests.get(api_url, headers=headers, timeout=5)
            if api_res.status_code == 200:
                api_json = api_res.json()
                # API içindeki HTML'den iframe src'sini çek
                if 'html' in api_json:
                    src_match = re.search(r'src=["\']([^"\']+)["\']', api_json['html'])
                    if src_match: return src_match.group(1)
        
        # 3. YÖNTEM: BeautifulSoup ile iframe tara
        soup = BeautifulSoup(html, 'html.parser')
        iframe = soup.find('iframe', {'data-src': True}) or soup.find('iframe', {'src': True})
        if iframe:
            src = iframe.get('data-src') or iframe.get('src')
            if 'rapidvid' in src: return src
            
    except Exception as e:
        print(f"Detay çekme hatası: {e}")
    return ""

def sayfa_cek(page_num):
    url = f"https://www.fullhdfilmizlesene.live/yeni-filmler/{page_num}" if page_num > 1 else "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'}

    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        
        results = []
        for film in films:
            t_node = film.find('span', class_='film-title')
            l_node = film.find('a', class_='tt')
            
            if t_node and l_node:
                f_url = l_node['href'].rstrip('/')
                f_title = t_node.get_text(strip=True)
                print(f"-> {f_title} işleniyor...")
                
                # İşte o eksik dediğimiz 'derine inme' kısmı
                r_link = detay_link_sokucu(f_url)
                
                results.append({
                    "title": f_title,
                    "link": f_url,
                    "rapid_link": r_link,
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                time.sleep(1) # Siteyi kızdırmayalım

        if results:
            with open(f'data/yeni-filmler-{page_num}.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
            return True
    except Exception as e:
        print(f"Ana sayfa hatası: {e}")
    return False

def main():
    # İlk 5 sayfayı test et
    for p in range(1, 6):
        print(f"\n*** SAYFA {p} ***")
        sayfa_cek(p)

if __name__ == "__main__":
    main()
