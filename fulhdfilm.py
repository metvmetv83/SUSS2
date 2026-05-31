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
PARALEL = 1  # Engellenmemek için tekli istek

VALID_STREAM_PATTERNS = [
    r'https?://(?:www\.)?rapidvid\.(?:net|to|com)/(?:vod|embed|v|e)/[^\s"\'<>]+',
    r'https?://cdn\.imgz\.me/[^\s"\'<>]+',
    r'https?://(?:www\.)?vidmoly\.(?:to|me|org|net|vc)/[^\s"\'<>]+',
    r'https?://(?:www\.)?doodstream\.com/[^\s"\'<>]+',
    r'https?://(?:www\.)?streamtape\.com/[^\s"\'<>]+',
    r'https?://(?:www\.)?filemoon\.(?:sx|to|in)/[^\s"\'<>]+',
    r'https?://(?:www\.)?mixdrop\.(?:co|ag|bz)/[^\s"\'<>]+',
    r'https?://(?:www\.)?upstream\.to/[^\s"\'<>]+',
    r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)(?:\?[^\s"\'<>]+)?',
]

STREAM_DOMAINS = [
    "rapidvid", "vidmoly", "imgz", "doodstream",
    "streamtape", "filemoon", "mixdrop", "upstream",
    "vidsrc", "embedsito", "ok.ru", "myvi.ru"
]

def url_gecerli_mi(url):
    if not url or len(url) < 15:
        return False
    for skip in [BASE, "youtube.com", "youtu.be", "google.com",
                 "facebook.com", "twitter.com", "instagram.com",
                 "adnxs.com", "doubleclick.net", "googlesyndication.com"]:
        if skip in url:
            return False
    return True

def stream_url_mi(url):
    if not url_gecerli_mi(url):
        return False
    for pattern in VALID_STREAM_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False

def mevcut_filmleri_yukle():
    if os.path.exists(SONUC_DOSYA):
        with open(SONUC_DOSYA, 'r', encoding='utf-8') as f:
            try:
                filmler = json.load(f)
                cleaned_dict = {}
                for film in filmler:
                    r_link = film.get('rapid_link', '')
                    if not url_gecerli_mi(r_link):
                        film['rapid_link'] = ""
                    cleaned_dict[film['link']] = film
                return cleaned_dict
            except json.JSONDecodeError:
                return {}
    return {}

def kesin_kaydet(filmler_dict):
    try:
        with open(SONUC_DOSYA, 'w', encoding='utf-8') as f:
            json.dump(list(filmler_dict.values()), f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print(f"⚠️ Dosya yazma hatası: {str(e)}")

async def sayfa_filmlerini_cek_pw(context, page_num):
    url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    page = await context.new_page()
    await stealth_async(page)
    try:
        response = await page.goto(url, timeout=40000, wait_until='networkidle')
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
    except Exception as e:
        print(f"  ⚠️ Sayfa çekme hatası ({url}): {e}")
        return None
    finally:
        await page.close()

async def html_icerisinde_stream_ara(html_content):
    """HTML source içinde gömülü stream URL'lerini regex ile tara."""
    for pattern in VALID_STREAM_PATTERNS:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        for m in matches:
            if url_gecerli_mi(m):
                return m
    # iframe src tarama
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup.find_all(['iframe', 'source', 'video']):
        for attr in ['src', 'data-src', 'data-lazy-src']:
            src = tag.get(attr, '')
            if src and any(d in src for d in STREAM_DOMAINS) and url_gecerli_mi(src):
                return src.strip()
    return None

async def rapid_link_cek(context, film_url, deneme=3):
    for attempt in range(deneme):
        page = await context.new_page()
        await stealth_async(page)
        caught_urls = []

        def on_request(req):
            url = req.url
            if stream_url_mi(url):
                caught_urls.append(url)

        def on_response(res):
            url = res.url
            if stream_url_mi(url):
                if url not in caught_urls:
                    caught_urls.append(url)

        page.on("request", on_request)
        page.on("response", on_response)

        try:
            # --- ANA SAYFA YÜKLEMESİ ---
            await page.goto(film_url, timeout=40000, wait_until='domcontentloaded')
            await page.wait_for_timeout(2500)

            if caught_urls:
                return caught_urls[0].strip()

            # --- HTML TARAMA (1. tur) ---
            content = await page.content()
            found = await html_icerisinde_stream_ara(content)
            if found:
                return found

            # --- NETWORKIDLe BEKLEME ---
            try:
                await page.wait_for_load_state('networkidle', timeout=8000)
            except Exception:
                pass

            if caught_urls:
                return caught_urls[0].strip()

            # --- PLAYER BOX TIKLAMA ---
            player_selectors = [
                '#plx', '.player-box', '#player', '.video-player',
                '.video-container', '.embed-responsive', '.film-player',
                '[class*="player"]', '[id*="player"]', 'video',
            ]
            for sel in player_selectors:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.scroll_into_view_if_needed()
                        await el.click(timeout=3000, force=True)
                        await page.wait_for_timeout(2500)
                        if caught_urls:
                            return caught_urls[0].strip()
                except Exception:
                    continue

            # --- ALTERNATİF KAYNAK TABLARI ---
            tab_selectors = [
                '#dil-secenekleri .kalip',
                '.player-tabs a', '.player-tabs button',
                '.idSec a', '.idSec button',
                'li[data-source]', 'li[data-id]',
                '.video-alternatives button',
                '.source-list li', '.source-list a',
                '.alt-sources a', '.alt-sources button',
                '[data-video]', '[data-link]',
            ]
            for sel in tab_selectors:
                try:
                    buttons = await page.query_selector_all(sel)
                    for btn in buttons:
                        try:
                            if await btn.is_visible():
                                await btn.click(timeout=2000, force=True)
                                await page.wait_for_timeout(1800)
                                if caught_urls:
                                    return caught_urls[0].strip()
                                # Her tıklamadan sonra HTML tara
                                content = await page.content()
                                found = await html_icerisinde_stream_ara(content)
                                if found:
                                    return found
                        except Exception:
                            continue
                except Exception:
                    continue

            # --- IFRAME FRAME'LERİNE GİR ---
            try:
                frames = page.frames
                for frame in frames:
                    if frame == page.main_frame:
                        continue
                    try:
                        frame_url = frame.url
                        if any(d in frame_url for d in STREAM_DOMAINS):
                            return frame_url.strip()
                        frame_content = await frame.content()
                        found = await html_icerisinde_stream_ara(frame_content)
                        if found:
                            return found
                        # Frame içinde de request dinle
                        for cu in caught_urls:
                            return cu.strip()
                    except Exception:
                        continue
            except Exception:
                pass

            # --- SON HTML TARAMA ---
            content = await page.content()
            found = await html_icerisinde_stream_ara(content)
            if found:
                return found

            # --- JS DEĞİŞKENLERİNİ TARA ---
            try:
                js_vars = await page.evaluate("""() => {
                    const texts = [];
                    // window nesnesindeki string değişkenler
                    for (const key of Object.keys(window)) {
                        try {
                            const val = window[key];
                            if (typeof val === 'string' && val.startsWith('http')) {
                                texts.push(val);
                            }
                        } catch(e) {}
                    }
                    // Script tagları
                    document.querySelectorAll('script:not([src])').forEach(s => {
                        texts.push(s.innerText || '');
                    });
                    return texts.join('\\n');
                }""")
                found = await html_icerisinde_stream_ara(js_vars)
                if found:
                    return found
            except Exception:
                pass

        except Exception as e:
            print(f"    ⚠️ Deneme {attempt+1} hatası ({film_url}): {e}")
            if attempt < deneme - 1:
                await asyncio.sleep(4)
        finally:
            try:
                await page.close()
            except Exception:
                pass

    return ""

async def main():
    filmler_dict = mevcut_filmleri_yukle()
    bos_filmler = [f for f in filmler_dict.values() if not f.get('rapid_link')]
    dolu = len(filmler_dict) - len(bos_filmler)
    print(f"✓ {len(filmler_dict)} film hafızaya alındı.")
    print(f"  → {dolu} geçerli link korundu, {len(bos_filmler)} boş/hatalı link taranacak.\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--mute-audio',
                '--disable-blink-features=AutomationControlled',
                '--window-size=1920,1080',
                '--disable-web-security',         # Cross-origin iframe erişimi
                '--allow-running-insecure-content',
            ]
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='tr-TR',
            timezone_id='Europe/Istanbul',
            java_script_enabled=True,
            bypass_csp=True,          # Content Security Policy'yi atla
            ignore_https_errors=True,
        )

        # --- AŞAMA 1: YENİ FİLM TARAMA ---
        print("=== AŞAMA 1: Yeni filmler taranıyor ===")
        bos_sayfa = 0
        for page_num in range(1, 11):  # 10 sayfaya çıkarıldı
            filmler = await sayfa_filmlerini_cek_pw(context, page_num)
            if filmler is None:
                bos_sayfa += 1
                print(f"Sayfa {page_num}: Erişilemedi veya boş.")
                if bos_sayfa >= 2:
                    break
                continue
            bos_sayfa = 0
            yeni_eklenen = 0
            for f in filmler:
                if f['link'] not in filmler_dict:
                    filmler_dict[f['link']] = f
                    yeni_eklenen += 1
            if yeni_eklenen > 0:
                print(f"Sayfa {page_num}: {yeni_eklenen} yeni film eklendi.")
                kesin_kaydet(filmler_dict)
            else:
                print(f"Sayfa {page_num}: Yeni film yok.")

        # --- AŞAMA 2: STREAMİNG LİNK ÇEKME ---
        bos_filmler = [f for f in filmler_dict.values() if not f.get('rapid_link')]
        if bos_filmler:
            print(f"\n=== AŞAMA 2: {len(bos_filmler)} film için linkler çıkarılıyor ===\n")
            semaphore = asyncio.Semaphore(PARALEL)

            async def isle(film):
                async with semaphore:
                    link = await rapid_link_cek(context, film['link'])
                    if link:
                        film['rapid_link'] = link
                        filmler_dict[film['link']] = film
                        kesin_kaydet(filmler_dict)
                        print(f"  ✓ BAŞARILI: {film['title']}")
                        print(f"    → {link}")
                    else:
                        print(f"  ✗ BULUNAMADI: {film['title']}")
                    return film

            # Gruplar halinde işle, her gruptan sonra kısa bekleme
            for i in range(0, len(bos_filmler), 5):
                grup = bos_filmler[i:i+5]
                await asyncio.gather(*[isle(f) for f in grup])
                await asyncio.sleep(3)

        await browser.close()

    dolu_sayisi = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
    toplam = len(filmler_dict)
    oran = (dolu_sayisi / toplam * 100) if toplam > 0 else 0
    print(f"\n{'='*50}")
    print(f"✓ İşlem tamamlandı.")
    print(f"  Toplam Film   : {toplam}")
    print(f"  Geçerli Link  : {dolu_sayisi} ({oran:.1f}%)")
    print(f"  Eksik Link    : {toplam - dolu_sayisi}")
    print(f"{'='*50}")

if __name__ == "__main__":
    asyncio.run(main())
