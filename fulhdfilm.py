import asyncio
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

if not os.path.exists('data'):
    os.makedirs('data')

# Çekilecek tüm kategoriler
KATEGORILER = [
    {"slug": "yeni-filmler",        "dosya": "yeni-filmler"},
    {"slug": "en-cok-izlenen-filmler", "dosya": "en-cok-izlenen"},
    {"slug": "trend-filmler",       "dosya": "trend-filmler"},
    {"slug": "populer-filmler",     "dosya": "populer-filmler"},
    {"slug": "filmizle/aksiyon-filmleri",    "dosya": "aksiyon"},
    {"slug": "filmizle/korku-filmleri",      "dosya": "korku"},
    {"slug": "filmizle/komedi-filmleri",     "dosya": "komedi"},
    {"slug": "filmizle/dram-filmleri",       "dosya": "dram"},
    {"slug": "filmizle/bilim-kurgu-filmleri","dosya": "bilim-kurgu"},
    {"slug": "filmizle/animasyon-filmleri",  "dosya": "animasyon"},
    {"slug": "filmizle/gerilim-filmleri",    "dosya": "gerilim"},
    {"slug": "filmizle/romantik-filmler",    "dosya": "romantik"},
    {"slug": "filmizle/aile-filmleri",       "dosya": "aile"},
    {"slug": "filmizle/macera-filmleri",     "dosya": "macera"},
    {"slug": "filmizle/fantastik-filmler",   "dosya": "fantastik"},
    {"slug": "filmizle/yerli-filmler",       "dosya": "yerli"},
    {"slug": "filmizle/turkce-dublaj-filmler","dosya": "dublaj"},
    {"slug": "filmizle/turkce-altyazili-filmler","dosya": "altyazili"},
    {"slug": "yil/2026-filmleri-izle",       "dosya": "2026"},
    {"slug": "yil/2025-filmleri-izle",       "dosya": "2025"},
    {"slug": "yil/2024-filmleri-izle",       "dosya": "2024"},
]

BASE = "https://www.fullhdfilmizlesene.live"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}

async def rapid_link_cek(page, film_url):
    try:
        await page.goto(film_url, timeout=20000, wait_until='domcontentloaded')
        try:
            await page.click('#play-video', timeout=5000)
        except:
            pass

        for _ in range(16):
            await asyncio.sleep(0.5)
            try:
                iframe = page.locator('#plx iframe')
                src = await iframe.get_attribute('src') or await iframe.get_attribute('data-src') or ''
                if src and ('rapidvid' in src or 'imgz' in src):
                    return src
            except:
                pass

        content = await page.content()
        match = re.search(r'https?://(?:rapidvid\.net|cdn\.imgz\.me)/(?:vod|player/ifr/vod)/[a-zA-Z0-9]+', content)
        if match:
            return match.group(0)

    except Exception as e:
        print(f"      [HATA] {e}")
    return ""

def film_listesi_cek(kategori_slug, page_num):
    """requests ile film listesini çek"""
    base_url = f"{BASE}/{kategori_slug}/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"

    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 404:
            return "404", []
        if r.status_code != 200:
            return False, []

        soup = BeautifulSoup(r.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        if not films:
            return "404", []

        filmler = []
        for film in films:
            title = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            if title and link_tag:
                img_tag = film.find('img')
                filmler.append({
                    "title": title.text.strip(),
                    "link": link_tag['href'].rstrip('/'),
                    "imdb": film.find('span', class_='imdb').text if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').text if film.find('span', class_='film-yil') else "",
                    "image": (img_tag.get('data-src') or img_tag.get('src')) if img_tag else "",
                    "rapid_link": ""
                })
        return True, filmler

    except Exception as e:
        print(f"  [HATA] {e}")
        return False, []

async def kategori_cek(pw_page, kategori):
    slug = kategori["slug"]
    dosya_prefix = kategori["dosya"]
    print(f"\n{'='*50}")
    print(f"KATEGORİ: {slug}")
    print(f"{'='*50}")

    consecutive_404 = 0
    toplam_film = 0

    for page_num in range(1, 9999):
        print(f"\n  --- Sayfa {page_num} ---")
        status, filmler = film_listesi_cek(slug, page_num)

        if status == "404":
            consecutive_404 += 1
            print(f"  [404: {consecutive_404}/3]")
            if consecutive_404 >= 3:
                print(f"  ✓ Kategori bitti. Toplam: {toplam_film} film")
                break
            continue
        elif not status:
            consecutive_404 += 1
            continue
        else:
            consecutive_404 = 0

        print(f"  {len(filmler)} film bulundu")

        # Her film için rapidvid linkini Playwright ile çek
        for film in filmler:
            print(f"    > {film['title']}")
            film['rapid_link'] = await rapid_link_cek(pw_page, film['link'])
            print(f"      {'✓ ' + film['rapid_link'] if film['rapid_link'] else '✗ BULUNAMADI'}")

        toplam_film += len(filmler)

        # JSON kaydet
        dosya = f"data/{dosya_prefix}-{page_num}.json"
        with open(dosya, 'w', encoding='utf-8') as f:
            json.dump(filmler, f, ensure_ascii=False, indent=4)
        print(f"  💾 {dosya} kaydedildi")

async def main():
    print("Playwright başlatılıyor...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--mute-audio']
        )
        pw_page = await browser.new_page()
        await pw_page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36'
        })
        print("✓ Hazır\n")

        for kategori in KATEGORILER:
            await kategori_cek(pw_page, kategori)

        await browser.close()
        print("\n✓ Tüm kategoriler tamamlandı. Playwright kapatıldı.")

if __name__ == "__main__":
    asyncio.run(main())
