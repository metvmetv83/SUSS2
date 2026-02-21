import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

BASE_URL = "https://www.fullhdfilmizlesene.live"
LIST_URL = BASE_URL + "/yeni-filmler/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"
}

if not os.path.exists("data"):
    os.makedirs("data")


def get_html(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            return res.text
    except Exception as e:
        print("Hata:", e)
    return ""


def extract_rapidvid(html):
    """
    Sadece HTML içinde açık şekilde varsa Rapidvid linkini döndürür.
    Koruma bypass etmez.
    """
    match = re.search(
        r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/[a-zA-Z0-9]+',
        html
    )
    if match:
        return match.group(0).replace("\\", "")
    return ""


def scrape_page(page_number):
    url = LIST_URL if page_number == 1 else f"{LIST_URL}page/{page_number}/"
    print(f"\n--- Sayfa {page_number} ---")
    
    html = get_html(url)
    if not html:
        print("Sayfa alınamadı.")
        return False

    soup = BeautifulSoup(html, "html.parser")
    films = soup.find_all("li", class_="film")

    if not films:
        print("Film bulunamadı.")
        return False

    results = []

    for film in films:
        title_tag = film.find("span", class_="film-title")
        link_tag = film.find("a", class_="tt")

        if not title_tag or not link_tag:
            continue

        film_url = link_tag["href"].rstrip("/")
        print("  >", title_tag.text.strip())

        detail_html = get_html(film_url)
        rapid_link = extract_rapidvid(detail_html) if detail_html else ""

        results.append({
            "title": title_tag.text.strip(),
            "detail_url": film_url,
            "rapidvid_link": rapid_link,
            "imdb": film.find("span", class_="imdb").text.strip() if film.find("span", class_="imdb") else "",
            "year": film.find("span", class_="film-yil").text.strip() if film.find("span", class_="film-yil") else "",
            "image": film.find("img").get("data-src") or film.find("img").get("src")
        })

        time.sleep(1)

    with open(f"data/page-{page_number}.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    return True


def main():
    for page in range(1, 5):  # test için 1-4 arası
        success = scrape_page(page)
        if not success:
            break


if __name__ == "__main__":
    main()
