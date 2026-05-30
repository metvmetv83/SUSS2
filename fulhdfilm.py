import asyncio
import json
import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

if not os.path.exists('data'):
    os.makedirs('data')

BASE = "https://www.fullhdfilmizlesene.life"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
SONUC_DOSYA = "data/tum_filmler.json"
PARALEL = 4  # Bot koruması için düşürüldü

# Desteklenen tüm player domainleri
PLAYER_PATTERNS = [
    r'https?://(?:www\.)?rapidvid\.net/[^\s"\'<>]+',
    r'https?://cdn\.imgz\.me/[^\s"\'<>]+',
    r'https?://[^\s"\'<>]*(?:player|embed|watch|vod|stream)[^\s"\'<>]*',
    r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)/(?:embed/|watch\?v=)[^\s"\'<>]+',
    r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)[^\s"\'<>]*',
]

def mevcut_filmleri_yukle():
    if os.path.exists(SONUC_DOSYA):
        with open(SONUC_DOSYA, 'r', encoding='utf-8') as f:
            return {film['link']: film for film in json.load(f)}
    return {}

def kaydet(filmler_dict):
    with open(SONUC_DOSYA, 'w', encoding='utf-8') as f:
        json.dump(list(filmler_dict.values()), f, ensure_ascii=False, indent=2)

async def rapid_link_cek(context, film_url, deneme=3):
    for attempt in range(deneme):
        page = await context.new_page()
        try:
            # Sadece medya/font/resim engelle, script'lere izin ver
            await page.route("**/*", lambda route: route.abort()
                if route.request.resource_type in ["image", "font", "stylesheet"]
                else route.continue_()
            )

            # Ağ isteklerini dinle — iframe src'yi direkt yakala
            caught_url = []
            def on_request(req):
                url = req.url
                for pattern in PLAYER_PATTERNS:
                    if re.search(pattern, url):
                        caught_url.append(url)
                        break

            page.on("request", on_request)

            await page.goto(film_url, timeout=25000, wait_until='domcontentloaded')

            # JS'nin yüklenmesi için bekle
            await page.wait_for_timeout(3000)

            # Ağ isteğinden yakalandıysa döndür
            if caught_url:
                return caught_url[0]

            # iframe seçicilerini genişlet
            iframe_selectors = [
                '#plx iframe',
                '.player-box iframe',
                '.embed-responsive iframe',
                'iframe[src*="rapid"]',
                'iframe[src*="imgz"]',
                'iframe[src*="player"]',
                'iframe[src*="embed"]',
                'iframe[data-src]',
                'iframe',  # herhangi bir iframe
            ]

            for selector in iframe_selectors:
                try:
                    src = await page.eval_on_selector(
                        selector,
                        'el => el.getAttribute("data-src") || el.getAttribute("src") || ""',
                        timeout=3000
                    )
                    if src and src.startswith('http'):
                        return src.strip()
                except:
                    continue

            # Tüm page source'u tara
            content = await page.content()

            # Tüm pattern'ları dene
            for pattern in PLAYER_PATTERNS:
                match = re.search(pattern, content)
                if match:
                    url = match.group(0).rstrip('"\' ')
                    if len(url) > 15:
                        return url

            # JS değişkenlerinden ara
            js_patterns = [
                r'(?:file|src|source|url|link)\s*[=:]\s*["\'](\bhttps?://[^\s"\'<>]{10,})',
                r'iframe\.src\s*=\s*["\']([^"\']+)',
            ]
            for jp in js_patterns:
                match = re.search(jp, content)
                if match:
                    url = match.group(1)
                    if url.startswith('http'):
                        return url

        except Exception as e:
            if attempt < deneme - 1:
                await asyncio.sleep(2)
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
    bos = [f for f in filmler_dict.values() if not f.get('rapid_link')]
    dolu = len(filmler_dict) - len(bos)
    print(f"✓ {len(filmler_dict)} film yüklendi")
    print(f"  → {dolu} filmde link var, {len(bos)} filmde link boş\n")

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

        # Bot tespitini zorlaştır
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        # === AŞAMA 1: Yeni sayfaları tara ===
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

        # === AŞAMA 2: Boş rapid_link olanları doldur ===
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
