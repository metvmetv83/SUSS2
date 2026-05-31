import asyncio
import json
import os
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

if not os.path.exists('data'):
    os.makedirs('data')

BASE = "https://www.fullhdfilmizlesene.life"
SONUC_DOSYA = "data/tum_filmler.json"
PARALEL = 1

STREAM_DOMAINS = [
    "rapidvid", "vidmoly", "imgz.me", "doodstream",
    "streamtape", "filemoon", "mixdrop", "upstream",
    "vidsrc", "ok.ru", "myvi.ru", "sibnet.ru",
    "dailymotion.com", "vimeo.com", "odysee.com",
]

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

# Cloudflare'i geçmek için gerçekçi tarayıcı başlıkları
BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

def url_gecerli_mi(url):
    if not url or len(url) < 15:
        return False
    for skip in [BASE, "youtube.com", "youtu.be", "google.com",
                 "facebook.com", "twitter.com", "instagram.com",
                 "adnxs.com", "doubleclick.net", "googlesyndication.com",
                 "cloudflare.com", "recaptcha", "captcha"]:
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

async def yeni_sayfa_ac(context):
    """Stealth JS enjeksiyonuyla yeni sayfa aç."""
    page = await context.new_page()
    # Cloudflare bot tespitini geçmek için kritik JS'leri override et
    await page.add_init_script("""
        // navigator.webdriver'ı gizle
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        
        // Chrome runtime'ı simüle et
        window.chrome = {
            runtime: {
                onConnect: { addListener: () => {} },
                onMessage: { addListener: () => {} },
            },
            loadTimes: () => ({}),
            csi: () => ({}),
        };
        
        // Permissions API'yi gerçekçi göster
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
        
        // Plugin listesini doldur (headless'ta boş olur)
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin' },
                { name: 'Chrome PDF Viewer' },
                { name: 'Native Client' },
            ],
        });
        
        // Dil listesi
        Object.defineProperty(navigator, 'languages', {
            get: () => ['tr-TR', 'tr', 'en-US', 'en'],
        });
        
        // Platform
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        
        // Hardware concurrency (gerçekçi değer)
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    """)
    return page

async def cloudflare_bekle(page, timeout=15000):
    """Cloudflare challenge sayfasını geç."""
    try:
        # CF challenge varsa bekle geçsin
        await page.wait_for_function(
            "() => !document.title.includes('Just a moment') && !document.title.includes('Checking')",
            timeout=timeout
        )
    except Exception:
        pass
    await page.wait_for_timeout(1500)

async def sayfa_filmlerini_cek_pw(context, page_num):
    url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    page = await yeni_sayfa_ac(context)
    try:
        response = await page.goto(url, timeout=45000, wait_until='domcontentloaded')
        
        # Cloudflare challenge bekle
        await cloudflare_bekle(page)
        
        # Gerçek içerik yüklenene kadar bekle
        try:
            await page.wait_for_selector('li.film', timeout=10000)
        except Exception:
            pass

        if not response or response.status not in [200, 304]:
            print(f"    HTTP {response.status if response else 'N/A'}: {url}")
            return None

        content = await page.content()
        
        # CF challenge sayfası mı?
        if "Just a moment" in content or "cf-browser-verification" in content:
            print(f"    ⚠️ Cloudflare engeli aşılamadı: {url}")
            return None

        soup = BeautifulSoup(content, 'html.parser')
        films = soup.find_all('li', class_='film')
        if not films:
            print(f"    ℹ️ Film listesi bulunamadı: {url}")
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
                    "imdb": film.find('span', class_='imdb').text.strip() if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').text.strip() if film.find('span', class_='film-yil') else "",
                    "image": (img.get('data-src') or img.get('src', '')) if img else "",
                    "rapid_link": ""
                })
        return filmler
    except Exception as e:
        print(f"    ⚠️ Sayfa hatası ({url}): {e}")
        return None
    finally:
        await page.close()

async def html_stream_ara(html_content):
    """HTML kaynak kodundan stream URL'si çıkar."""
    for pattern in VALID_STREAM_PATTERNS:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        for m in matches:
            if url_gecerli_mi(m):
                return m.strip()

    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup.find_all(['iframe', 'source', 'video']):
        for attr in ['src', 'data-src', 'data-lazy-src', 'data-url']:
            src = tag.get(attr, '')
            if src and any(d in src for d in STREAM_DOMAINS) and url_gecerli_mi(src):
                return src.strip()
    return None

async def rapid_link_cek(context, film_url, deneme=3):
    for attempt in range(deneme):
        page = await yeni_sayfa_ac(context)
        caught_urls = []

        def on_request(req):
            if stream_url_mi(req.url):
                caught_urls.append(req.url)

        def on_response(res):
            if stream_url_mi(res.url) and res.url not in caught_urls:
                caught_urls.append(res.url)

        page.on("request", on_request)
        page.on("response", on_response)

        try:
            await page.goto(film_url, timeout=45000, wait_until='domcontentloaded')
            await cloudflare_bekle(page)
            await page.wait_for_timeout(2000)

            if caught_urls:
                return caught_urls[0].strip()

            # HTML tara
            content = await page.content()
            if "Just a moment" in content or "cf-browser-verification" in content:
                print(f"    ⚠️ CF engeli (deneme {attempt+1})")
                await asyncio.sleep(5)
                continue

            found = await html_stream_ara(content)
            if found:
                return found

            # networkidle bekle
            try:
                await page.wait_for_load_state('networkidle', timeout=8000)
            except Exception:
                pass

            if caught_urls:
                return caught_urls[0].strip()

            # Player tıklama
            for sel in ['#plx', '.player-box', '#player', '.video-player',
                        '.film-player', '[class*="player"]', 'video',
                        '.embed-responsive', '.izle-player']:
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

            # Kaynak tabları
            for sel in ['.player-tabs a', '.player-tabs button',
                        '.idSec a', 'li[data-source]', 'li[data-id]',
                        '.source-list li', '[data-video]', '[data-link]',
                        '.alt-sources a', '#kaynaklar a']:
                try:
                    for btn in await page.query_selector_all(sel):
                        if await btn.is_visible():
                            await btn.click(timeout=2000, force=True)
                            await page.wait_for_timeout(1800)
                            if caught_urls:
                                return caught_urls[0].strip()
                            content = await page.content()
                            found = await html_stream_ara(content)
                            if found:
                                return found
                except Exception:
                    continue

            # Frame'leri tara
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    furl = frame.url
                    if any(d in furl for d in STREAM_DOMAINS) and url_gecerli_mi(furl):
                        return furl.strip()
                    fc = await frame.content()
                    found = await html_stream_ara(fc)
                    if found:
                        return found
                except Exception:
                    continue

            # JS değişkenleri tara
            try:
                js_text = await page.evaluate("""() => {
                    const out = [];
                    for (const k of Object.keys(window)) {
                        try {
                            const v = window[k];
                            if (typeof v === 'string' && v.startsWith('http')) out.push(v);
                        } catch(e) {}
                    }
                    document.querySelectorAll('script:not([src])').forEach(s => out.push(s.innerText));
                    return out.join('\\n');
                }""")
                found = await html_stream_ara(js_text)
                if found:
                    return found
            except Exception:
                pass

            # Son HTML tarama
            content = await page.content()
            found = await html_stream_ara(content)
            if found:
                return found

        except Exception as e:
            print(f"    ⚠️ Hata deneme {attempt+1} ({film_url}): {e}")
            if attempt < deneme - 1:
                await asyncio.sleep(5)
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
                '--disable-web-security',
                '--allow-running-insecure-content',
                '--disable-features=IsolateOrigins,site-per-process',
                '--lang=tr-TR',
            ]
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='tr-TR',
            timezone_id='Europe/Istanbul',
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
            extra_http_headers=BROWSER_HEADERS,
        )

        # === AŞAMA 1 ===
        print("=== AŞAMA 1: Yeni filmler taranıyor ===")
        bos_sayfa = 0
        for page_num in range(1, 11):
            filmler = await sayfa_filmlerini_cek_pw(context, page_num)
            if filmler is None:
                bos_sayfa += 1
                if bos_sayfa >= 2:
                    break
                continue
            bos_sayfa = 0
            yeni = sum(1 for f in filmler if f['link'] not in filmler_dict)
            for f in filmler:
                if f['link'] not in filmler_dict:
                    filmler_dict[f['link']] = f
            if yeni > 0:
                print(f"Sayfa {page_num}: {yeni} yeni film eklendi.")
                kesin_kaydet(filmler_dict)
            else:
                print(f"Sayfa {page_num}: Yeni film yok.")

        # === AŞAMA 2 ===
        bos_filmler = [f for f in filmler_dict.values() if not f.get('rapid_link')]
        if bos_filmler:
            print(f"\n=== AŞAMA 2: {len(bos_filmler)} film için link çıkarılıyor ===\n")
            semaphore = asyncio.Semaphore(PARALEL)

            async def isle(film):
                async with semaphore:
                    link = await rapid_link_cek(context, film['link'])
                    if link:
                        film['rapid_link'] = link
                        filmler_dict[film['link']] = film
                        kesin_kaydet(filmler_dict)
                        print(f"  ✓ {film['title']}")
                        print(f"    → {link}")
                    else:
                        print(f"  ✗ {film['title']}")

            for i in range(0, len(bos_filmler), 5):
                await asyncio.gather(*[isle(f) for f in bos_filmler[i:i+5]])
                await asyncio.sleep(3)

        await browser.close()

    dolu_s = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
    top = len(filmler_dict)
    print(f"\n{'='*50}")
    print(f"✓ Tamamlandı. Toplam: {top} | Link var: {dolu_s} ({dolu_s/top*100:.1f}% ) | Eksik: {top-dolu_s}")
    print(f"{'='*50}")

if __name__ == "__main__":
    asyncio.run(main())
