import requests
from bs4 import BeautifulSoup
import json
import os
import time

# Create directory
if not os.path.exists('data'):
    os.makedirs('data')

# Use a session for faster requests
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
})

def detay_linki_cek(film_url):
    """Enters film page and grabs iframe link inside div#plx."""
    try:
        # Lower timeout to prevent hanging the whole script
        res = session.get(film_url, timeout=8, headers={'Referer': 'https://www.fullhdfilmizlesene.live/'})
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            plx_div = soup.find('div', id='plx')
            if plx_div:
                iframe = plx_div.find('iframe')
                if iframe:
                    return iframe.get('data-src') or iframe.get('src') or ""
    except Exception:
        return ""
    return ""

def sayfa_cek(page_num):
    url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    if page_num > 1:
        url = f"{url}page/{page_num}/" # Standardized URL structure

    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            print(f"Error: Status code {response.status_code} for page {page_num}")
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
                
                print(f"    > Fetching details for: {t_text}")
                rapid_link = detay_linki_cek(f_url)

                movie_data.append({
                    "title": t_text,
                    "link": f_url,
                    "rapid_link": rapid_link,
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                # Reduced sleep to keep it moving, adjust if you get blocked
                time.sleep(0.5) 

        if movie_data:
            file_name = f'data/yeni-filmler-{page_num}.json'
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            print(f"--- Page {page_num} saved ---")
            return True
    except Exception as e:
        print(f"Error occurred: {e}")
        return False
    return False

def main():
    baslangic = 1
    bitis = 1113 
    
    print("Process starting...")
    for p in range(baslangic, bitis + 1):
        file_path = f'data/yeni-filmler-{p}.json'
        
        # CHECKPOINT: Skip if file already exists
        if os.path.exists(file_path):
            # Check if file is empty or valid if you want to be extra safe
            continue
            
        print(f"\n--- Page: {p} / {bitis} ---")
        success = sayfa_cek(p)
        
        if not success:
            print(f"Page {p} failed. Resting...")
            time.sleep(5)
            continue
            
        time.sleep(1)

if __name__ == "__main__":
    main()
