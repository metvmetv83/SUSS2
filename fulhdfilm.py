import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

if not os.path.exists('data'):
    os.makedirs('data')

def detay_linki_cek(film_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
        'Referer': film_url
    }

    try:
        with requests.Session() as s:
            res = s.get(film_url, headers=headers, timeout=15)
            if res.status_code != 200:
                return ""

            soup = BeautifulSoup(res.text, "html.parser")

            # 1️⃣ iframe data-src kontrolü
            iframe = soup.find("iframe", attrs={"data-src": True})
            if iframe:
                link = iframe.get("data-src")
                if "rapidvid.net" in link:
                    return link.strip()

            # 2️⃣ iframe src kontrolü
            iframe = soup.find("iframe", src=True)
            if iframe:
                link = iframe.get("src")
                if "rapidvid.net" in link:
                    return link.strip()

            # 3️⃣ regex fallback
            match = re.search(r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/[a-zA-Z0-9]+', res.text)
            if match:
                return match.group(0)

    except Exception as e:
        print("Hata:", e)

    return ""


def sayfa_cek(page_num):
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'
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
                print(f"Çekiliyor: {title.text}")

                rapid_link = detay_linki_cek(f_url)

                movie_data.append({
                    "title": title.text.strip(),
                    "detail_url": f_url,
                    "rapidvid_link": rapid_link,
                    "imdb": film.find('span', class_='imdb').text if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').text if film.find('span', class_='film-yil') else "",
                    "image": film.find('img').get('data-src') or film.find('img').get('src')
                })

                time.sleep(1)

        if movie_data:
            with open(f'data/yeni-filmler-{page_num}.json', 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)

            return True

    except Exception as e:
        print("Sayfa hata:", e)

    return False


def main():
    for p in range(1, 3):  # test için 2 sayfa
        print(f"\n--- Sayfa {p} ---")
        sayfa_cek(p)


if __name__ == "__main__":
    main()
