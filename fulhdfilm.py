import asyncio
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

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
        await page.route("**/*", lambda route: route.abort()
            if route.request.resource_type in ["image", "media", "font", "stylesheet"]
            else route.continue_()
        )
        await page.goto(film_url, timeout=15000, wait_until='domcontentloaded')

        # data-src direkt oku
        try:
            src = await page.eval_on_selector(
                '#plx iframe',
                'el => el.getAttribute("data-src") || el.getAttribute("src") || ""'
            )
            if src and ('rapidvid' in src or 'imgz' in src):
                return src
        except:
            pass

        # page source'dan ara
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

    # Kaç tanesinin rapid_link'i boş?
    bos = [f for f in filmler_dict.values() if not f.get('rapid_link')]
    dolu = len(filmler_dict) - len(bos)
    print(f"✓ {len(filmler_dict)} film yüklendi")
    print(f"  → {dolu} filmde link var, {len(bos)} filmde link boş\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--mute-audio']
        )
        context = await browser.new_context(user_agent=HEADERS['User-Agent'])

        # === AŞAMA 1: Yeni sayfaları tara, eksik filmleri ekle ===
        print("=== AŞAMA 1: Yeni filmler taranıyor ===")
        bos_sayfa = 0
        for page_num in range(1, 9999):
            filmler = sayfa_filmlerini_cek(page_num)

            if filmler is None:
                bos_sayfa += 1
                if bos_sayfa >= 3:
                    print(f"✓ Tüm sayfalar tarandı.\n")
                    break
                continue

            bos_sayfa = 0
            yeni = [f for f in filmler if f['link'] not in filmler_dict]

            if yeni:
                print(f"Sayfa {page_num}: {len(yeni)} yeni film eklendi")
                for f in yeni:
                    filmler_dict[f['link']] = f
            else:
                print(f"Sayfa {page_num}: yeni film yok")

        # === AŞAMA 2: Boş rapid_link olanları Playwright ile doldur ===
        bos_filmler = [f for f in filmler_dict.values() if not f.get('rapid_link')]
        print(f"=== AŞAMA 2: {len(bos_filmler)} film için rapid_link çekiliyor ===\n")

        islenen = 0
        semaphore = asyncio.Semaphore(PARALEL)

        async def isle(film):
            async with semaphore:
                link = await rapid_link_cek(context, film['link'])
                film['rapid_link'] = link
                durum = "✓" if link else "✗"
                print(f"  {durum} {film['title']}")
                return film

        # 50'şer gruplar halinde işle ve kaydet
        for i in range(0, len(bos_filmler), 50):
            grup = bos_filmler[i:i+50]
            await asyncio.gather(*[isle(f) for f in grup])

            for f in grup:
                filmler_dict[f['link']] = f

            islenen += len(grup)
            kaydet(filmler_dict)

            dolu = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
            print(f"\n💾 Kaydedildi — {islenen}/{len(bos_filmler)} işlendi, toplam dolu: {dolu}\n")

        await browser.close()

    dolu = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
    print(f"\n✓ Tamamlandı. Toplam: {len(filmler_dict)} film, {dolu} link dolu")

if __name__ == "__main__":
    asyncio.run(main())
