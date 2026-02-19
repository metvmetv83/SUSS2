import requests
from bs4 import BeautifulSoup
import json
import time

def scrape_page(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36'}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return []
        soup = BeautifulSoup(res.text, 'html.parser')
        results = []
        # Sizin XPath yapınıza uygun seçici
        items = soup.find_all('li', class_=lambda x: x and 'film' in x)
        for item in items:
            title = item.find('span', class_='film-title')
            link = item.find('a', class_='tt')
            imdb = item.find('span', class_='imdb')
            year = item.find('span', class_='film-yil')
            img = item.find('img')
            
            if title and link:
                results.append({
                    'title': title.get_text(strip=True),
                    'link': link['href'].rstrip('/'),
                    'image': img.get('data-src') or img.get('src') or "",
                    'imdb': imdb.get_text(strip=True) if imdb else "0",
                    'year': year.get_text(strip=True) if year else ""
                })
        return results
    except: return []

def main():
    base_url = "https://www.fullhdfilmizlesene.live/"
    categories = ["yeni-filmler", "aksiyon-filmleri", "komedi-filmleri", "bilim-kurgu"]
    total_data = {}

    for cat in categories:
        total_data[cat] = []
        for page in range(1, 6): # 5 sayfa çekiyoruz
            url = f"{base_url}{cat}/" if page == 1 else f"{base_url}{cat}/{page}"
            if cat != "yeni-filmler":
                url = f"{base_url}filmizle/{cat}/" if page == 1 else f"{base_url}filmizle/{cat}/{page}"
            
            print(f"Cekiliyor: {url}")
            movies = scrape_page(url)
            if not movies: break
            total_data[cat].extend(movies)
            time.sleep(1)

    with open('film.json', 'w', encoding='utf-8') as f:
        json.dump(total_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()
