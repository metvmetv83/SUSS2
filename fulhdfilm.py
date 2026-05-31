import asyncio
import json
import os
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

if not os.path.exists('data'):
    os.makedirs('data')

BASE = "https://www.fullhdfilmizlesene.life"
SONUC_DOSYA = "data/tum_filmler.json"
PARALEL = 1

STREAM_DOMAINS = ["rapidvid", "vidmoly", "imgz.me", "doodstream", "streamtape", "filemoon", "mixdrop", "upstream", "ok.ru", "myvi.ru", "sibnet.ru", "vidsrc"]
VALID_STREAM_PATTERNS = [
    r'https?://(?:www\.)?rapidvid\.(?:net|to|com)/(?:vod|embed|v|e)/[^\s"\'<>]+',
    r'https?://cdn\.imgz\.me/[^\s"\'<>]+',
    r'https?://(?:www\.)?vidmoly\.(?:to|me|org|net|vc)/[^\s"\'<>]+',
    r'https?://(?:www\.)?doodstream\.com/[^\s"\'<>]+',
    r'https?://(?:www\.)?streamtape\.com/[^\s"\'<>]+',
    r'https?://(?:www\.)?filemoon\.(?:sx|to|in)/[^\s"\'<>]+',
    r'https?://(?:www\.)?mixdrop\.(?:co|ag|bz)/[^\s"\'<>]+',
    r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)(?:\?[^\s"\'<>]+)?',
]

def url_gecerli_mi(url):
    if not url or len(url) < 15: return False
    for skip in [BASE, "youtube.com", "youtu.be", "google.com", "cloudflare.com", "adnxs.com", "doubleclick.net", "googlesyndication", "recaptcha"]:
        if skip in url: return False
    return True

def stream_url_mi(url):
    if not url_gecerli_mi(url): return False
    return any(re.search(p, url, re.IGNORECASE) for p in VALID_STREAM_PATTERNS)

def html_stream_ara(html):
    for pat in VALID_STREAM_PATTERNS:
        for m in re.findall(pat, html, re.IGNORECASE):
            if url_gecerli_mi(m): return m.strip()
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all(['iframe', 'source', 'video', 'embed']):
        for attr in ['src', 'data-src', 'data-lazy-src', 'data-url', 'data-source', 'data-video']:
            src = tag.get(attr, '').strip()
            if src and src.startswith('http') and any(d in src for d in STREAM_DOMAINS) and url_gecerli_mi(src):
                return src
    return None

def mevcut_filmleri_yukle():
    if os.path.exists(SONUC_DOSYA):
        with open(SONUC_DOSYA, 'r', encoding='utf-8') as f:
            try:
                filmler = json.load(f)
                return {film['link']: film for film in filmler if url_gecerli_mi(film.get('rapid_link', '')) or not film.get('rapid_link')}
            except json.JSONDecodeError: pass
    return {}

def kesin_kaydet(filmler_dict):
    try:
        with open(SONUC_DOSYA, 'w', encoding='utf-8') as f:
            json.dump(list(filmler_dict.values()), f, ensure_ascii=False, indent=2)
    except Exception as e: print(f"⚠️ Kayıt hatası: {e}")

async def yeni_sayfa(context):
    page = await context.new_page()
    await stealth_async(page) # Donanımsal otomasyon izlerini gizle
    return page

async def sayfa_filmlerini_cek(context, page_num):
    url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    page = await yeni_sayfa(context)
    try:
        await page.goto(url, timeout=60000, wait_until='domcontentloaded')
        await asyncio.sleep(10) # Çerezlerin ve challenge aşamasının arka planda oturması için esnek süre
        
        content = await page.content()
        soup = BeautifulSoup(content, 'html.parser')
        films = soup.find_all('li', class_='film')
        if not films: return None
        
        filmler = []
        for film in films:
            title_tag = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            if title_tag and link_tag:
                img_tag = film.find('img')
                image_url = ""
                if img_tag:
                    for src in [img_tag.get('data-src'), img_tag.get('src'), img_tag.get('data-srcset')]:
                        if src and "http" in src and not src.startswith("data:"):
                            image_url = src.split()[0].strip()
                            break
                filmler.append({
                    "title": title_tag.text.strip(),
                    "link": link_tag['href'].rstrip('/'),
                    "imdb": (film.find('span', class_='imdb') or type('x',(),({"text":"0"}))()).text.strip(),
                    "year": (film.find('span', class_='film-yil') or type('x',(),({"text":""}))()).text.strip(),
                    "image": image_url,
                    "rapid_link": ""
                })
        return filmler
    except Exception: return None
    finally: await page.close()

async def rapid_link_cek(context, film_url, deneme=2):
    for attempt in range(deneme):
        page = await yeni_sayfa(context)
        caught = []
        page.on("request", lambda r: caught.append(r.url) if stream_url_mi(r.url) else None)
        try:
            await page.goto(film_url, timeout=60000, wait_until='domcontentloaded')
            await asyncio.sleep(8)
            if caught: return caught[0].strip()
            
            content = await page.content()
            found = html_stream_ara(content)
            if found: return found
            
            # iFrame Kontrolü
            for frame in page.frames:
                try:
                    if any(d in frame.url for d in STREAM_DOMAINS): return frame.url.strip()
                    f_found = html_stream_ara(await frame.content())
                    if f_found: return f_found
                except: pass
        except: await asyncio.sleep(3)
        finally: await page.close()
    return ""

async def main():
    filmler_dict = mevcut_filmleri_yukle()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled'
        ])
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='tr-TR'
        )

        print("=== AŞAMA 1: Yeni filmler taranıyor ===")
        bos_sayfa = 0
        for page_num in range(1, 10):
            filmler = await sayfa_filmlerini_cek(context, page_num)
            if not filmler:
                bos_sayfa += 1
                print(f"Sayfa {page_num}: Erişilemedi.")
                if bos_sayfa >= 3: break
                continue
            bos_sayfa = 0
            yeni = [f for f in filmler if f['link'] not in filmler_dict]
            for f in yeni: filmler_dict[f['link']] = f
            print(f"Sayfa {page_num}: {len(filmler)} film işlendi.")
            if yeni: kesin_kaydet(filmler_dict)
            await asyncio.sleep(3)

        bos = [f for f in filmler_dict.values() if not f.get('rapid_link')]
        if bos:
            print(f"\n=== AŞAMA 2: {len(bos)} film için link çıkarılıyor ===\n")
            semaphore = asyncio.Semaphore(PARALEL)
            islenen = 0
            async def isle(film):
                nonlocal islenen
                async with semaphore:
                    link = await rapid_link_cek(context, film['link'])
                    film['rapid_link'] = link
                    filmler_dict[film['link']] = film
                    islenen += 1
                    print(f"  {'✓' if link else '✗'} [{islenen}/{len(bos)}] {film['title']}")

            for i in range(0, len(bos), 10):
                grup = bos[i:i+10]
                await asyncio.gather(*[isle(f) for f in grup])
                kesin_kaydet(filmler_dict)
                await asyncio.sleep(3)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
