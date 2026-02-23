import asyncio
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from concurrent.futures import ThreadPoolExecutor

if not os.path.exists('data'):
    os.makedirs('data')

BASE = "https://www.fullhdfilmizlesene.live"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
SONUC_DOSYA = "data/tum_filmler.json"
PARALEL = 6

def mevcut_filmleri_yukle():
    if os.path.exists(SONUC_DOSYA):
        with open(SONUC_DOSYA, 'r', encoding='utf-8') as f:
            return {film['link']: film for film in json.load(f)}
    return {}

def kaydet(filmler_dict):
    with open(SONUC_DOSYA, 'w', encoding='utf-8') as f:
        json.dump(list(filmler_dict.values()), f, ensure_ascii=False, indent=2)

async def rapid_link_cek(context, film_url):
    page = await context.new_page()
    try:
        # Sadece gerekli kaynakları yükle — medya/resim engelle
        await page.route("**/*", lambda route: route.abort()
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]
            else route.continue_()
        )
        await page.goto(film_url, timeout=15000, wait_until='domcontentloaded')

        # data-src'yi direkt oku — play'e tıklamaya gerek yok
        src = await page.eval_on_selector(
            '#plx iframe',
            'el => el.getAttribute("data-src") || el.getAttribute("src") || ""'
        ).catch(lambda _: "")  # type: ignore

        if src and ('rapidvid' in src or 'imgz' in src):
            return src

        # Bulamazsa page source'dan ara
        content = await page.content()
        match = re.search(
            r'https?://(?:rapidvid\.net|cdn\.imgz\.me)/(?:vod|player/ifr/vod)/[a-zA-Z0-9]+',
            content
        )
        if match:
            return match.group(0)

    except:
        pass
    finally:
        await page.close()
    return ""

def sayfa_filmlerini_cek(page_num):
    url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        if not films:
            return None
        filmler = []
        for film in films:
            title = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            if title and link_tag:
                img = film.find('img')
                filmler.append({
                    "title": title.text.strip(),
                    "link": link_tag['href'].rstrip('/'),
                    "imdb": film.find('span', class_='imdb').text if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').text if film.find('span', class_='film-yil') else "",
                    "image": (img.get('data-src') or img.get('src')) if img else "",
                    "rapid_link": ""
                })
        return filmler
    except:
        return None

async def main():
    filmler_dict = mevcut_filmleri_yukle()
    print(f"✓ {len(filmler_dict)} film mevcut, devam ediliyor\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--mute-audio']
        )
        context = await browser.new_context(
            user_agent=HEADERS['User-Agent']
        )

        bos_sayfa = 0

        for page_num in range(1, 9999):
            print(f"--- Sayfa {page_num} ---")
            filmler = sayfa_filmlerini_cek(page_num)

            if filmler is None:
                bos_sayfa += 1
                print(f"  [404: {bos_sayfa}/3]")
                if bos_sayfa >= 3:
                    print("✓ Bitti.")
                    break
                continue

            bos_sayfa = 0
            yeni = [f for f in filmler if f['link'] not in filmler_dict]

            if not yeni:
                print(f"  ↷ Tümü mevcut, atlandı\n")
                continue

            print(f"  {len(yeni)} yeni film — {PARALEL} paralel tab...")

            # Paralel Playwright tab'ları
            semaphore = asyncio.Semaphore(PARALEL)
            async def isle(film):
                async with semaphore:
                    film['rapid_link'] = await rapid_link_cek(context, film['link'])
                    durum = "✓" if film['rapid_link'] else "✗"
                    print(f"    {durum} {film['title']}")
                    return film

            sonuclar = await asyncio.gather(*[isle(f) for f in yeni])

            for film in sonuclar:
                filmler_dict[film['link']] = film

            kaydet(filmler_dict)
            print(f"  💾 Toplam: {len(filmler_dict)} film\n")

        await browser.close()
    print(f"✓ Tamamlandı. Toplam: {len(filmler_dict)} film")

if __name__ == "__main__":
    asyncio.run(main())
