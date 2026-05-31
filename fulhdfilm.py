import asyncio
import json
import os
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

if not os.path.exists('data'):
    os.makedirs('data')

BASE = "https://www.fullhdfilmizlesene.life"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
SONUC_DOSYA = "data/tum_filmler.json"
PARALEL = 3

VALID_STREAM_PATTERNS = [
    r'https?://(?:www\.)?rapidvid\.net/(?:vod|embed)/[^\s"\'<>]+',
    r'https?://cdn\.imgz\.me/[^\s"\'<>]+',
    r'https?://(?:www\.)?vidmoly\.(?:to|me)/embed-[^\s"\'<>]+',
    r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)(?:\?[^\s"\'<>]+)?'
]

def mevcut_filmleri_yukle():
    if os.path.exists(SONUC_DOSYA):
        with open(SONUC_DOSYA, 'r', encoding='utf-8') as f:
            try:
                filmler = json.load(f)
                cleaned_dict = {}
                for film in filmler:
                    r_link = film.get('rapid_link', '')
                    if BASE in r_link or "youtube.com" in r_link or "youtu.be" in r_link or len(r_link) < 15:
                        film['rapid_link'] = ""
                    cleaned_dict[film['link']] = film
                return cleaned_dict
            except json.JSONDecodeError:
                return {}
    return {}

def kaydet(filmler_dict):
    with open(SONUC_DOSYA, 'w', encoding='utf-8') as f:
        json.dump(list(filmler_dict.values()), f, ensure_ascii=False, indent=2)

async def sayfa_filmlerini_cek_pw(context, page_num):
    """ Requests yerine Playwright kullanarak sayfayı çeker (Hata önleyici) """
    url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    page = await context.new_page()
    try:
        await page.route("**/*", lambda route: route.abort()
            if route.request.resource_type in ["image", "font", "stylesheet"]
            else route.continue_()
        )
        response = await page.goto(url, timeout=20000, wait_until='domcontentloaded')
        if not response or response.status != 200:
            return None
            
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
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
    finally:
        await page.close()

async def rapid_link_cek(context, film_url, deneme=3):
    for attempt in range(deneme):
        page = await context.new_page()
        try:
            await page.route("**/*", lambda route: route.abort()
                if route.request.resource_type in ["image", "font", "stylesheet"]
                else route.continue_()
            )

            caught_url = []
            def on_request(req):
                url = req.url
                if BASE not in url and "youtube.com" not in url and "youtu.be" not in url:
                    for pattern in VALID_STREAM_PATTERNS:
                        if re.search(pattern, url):
                            caught_url.append(url)
                            break

            page.on("request", on_request)
            await page.goto(film_url, timeout=25000, wait_until='domcontentloaded')
            await page.wait_for_timeout(3500)

            if caught_url:
                await page.close()
                return caught_url[0].strip()

            iframe_selectors = [
                '#plx iframe', '.player-box iframe', '.player-inside iframe',
                'iframe[src*="rapidvid"]', 'iframe[src*="vidmoly"]', 'iframe[data-src]'
            ]

            for selector in iframe_selectors:
                try:
                    src = await page.eval_on_selector(
                        selector,
                        'el => el.getAttribute("data-src") || el.getAttribute("src") || ""',
                        timeout=2000
                    )
                    if src and src.startswith('http') and BASE not in src and "youtube" not in src:
                        await page.close()
                        return src.strip()
                except:
                    continue

        except Exception:
            if attempt < deneme - 1:
                await asyncio.sleep(2)
        finally:
            await page.close()

    return ""

async def main():
    filmler_dict = mevcut_filmleri_yukle()
    bos = [f for f in filmler_dict.values() if not f.get('rapid_link')]
    dolu = len(filmler_dict) - len(bos)
    print(f"✓ {len(filmler_dict)} film yüklendi (Veritabanından temizlendi)")
    print(f"  → {dolu} geçerli link korundu, {len(bos)} hatalı/boş link yeniden taranacak\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--mute-audio',
                  '--disable-blink-features=AutomationControlled']
        )
        context = await browser.new_context(
            user_agent=HEADERS['User-Agent'],
            viewport={'width': 1280, 'height': 720},
            java_script_enabled=True,
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        # === AŞAMA 1: Yeni sayfaları tara (Playwright entegreli) ===
        print("=== AŞAMA 1: Yeni filmler taranıyor ===")
        bos_sayfa = 0
        for page_num in range(1, 20):
            filmler = await sayfa_filmlerini_cek_pw(context, page_num)
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

        # === AŞAMA 2: Boş rapid_link olanları doldur ===
        bos_filmler = [f for f in filmler_dict.values() if not f.get('rapid_link')]
        if bos_filmler:
            print(f"\n=== AŞAMA 2: {len(bos_filmler)} film için gerçek rapid_link kaynakları çekiliyor ===\n")

            islenen = 0
            semaphore = asyncio.Semaphore(PARALEL)

            async def isle(film):
                async with semaphore:
                    link = await rapid_link_cek(context, film['link'])
                    film['rapid_link'] = link
                    durum = "✓" if link else "✗"
                    print(f"  {durum} {film['title']}")
                    return film

            for i in range(0, len(bos_filmler), 30):
                grup = bos_filmler[i:i+30]
                await asyncio.gather(*[isle(f) for f in grup])
                for f in grup:
                    filmler_dict[f['link']] = f
                islenen += len(grup)
                kaydet(filmler_dict)
                dolu = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
                print(f"\n💾 Kaydedildi — {islenen}/{len(bos_filmler)} işlendi, toplam doğrulanmış dolu: {dolu}\n")
                await asyncio.sleep(2)

        await browser.close()

    dolu = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
    print(f"\n✓ Tamamlandı. Toplam: {len(filmler_dict)} film, {dolu} GERÇEK link hazır.")

if __name__ == "__main__":
    asyncio.run(main())
