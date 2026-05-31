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
PARALEL = 3

STREAM_DOMAINS = [
    "rapidvid", "vidmoly", "imgz.me", "doodstream",
    "streamtape", "filemoon", "mixdrop", "upstream",
    "ok.ru", "myvi.ru", "sibnet.ru", "vidsrc",
]

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

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['tr-TR','tr','en-US','en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
window.chrome = {runtime:{}, loadTimes:()=>({}), csi:()=>({})};
"""

def url_gecerli_mi(url):
    if not url or len(url) < 15: return False
    for skip in [BASE, "youtube.com", "youtu.be", "google.com",
                 "cloudflare.com", "adnxs.com", "doubleclick.net",
                 "googlesyndication", "recaptcha"]:
        if skip in url: return False
    return True

def stream_url_mi(url):
    if not url_gecerli_mi(url): return False
    return any(re.search(p, url, re.IGNORECASE) for p in VALID_STREAM_PATTERNS)

def html_stream_ara(html):
    """HTML metninden stream URL çıkar."""
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
                d = {}
                for film in filmler:
                    if not url_gecerli_mi(film.get('rapid_link', '')):
                        film['rapid_link'] = ""
                    d[film['link']] = film
                return d
            except json.JSONDecodeError:
                return {}
    return {}

def kesin_kaydet(filmler_dict):
    try:
        with open(SONUC_DOSYA, 'w', encoding='utf-8') as f:
            json.dump(list(filmler_dict.values()), f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
    except Exception as e:
        print(f"⚠️ Kaydetme hatası: {e}")

async def yeni_sayfa(context, engelle_media=True):
    page = await context.new_page()
    await page.add_init_script(STEALTH_SCRIPT)
    if engelle_media:
        await page.route("**/*", lambda r: r.abort()
            if r.request.resource_type in ["image", "font", "stylesheet", "media"]
            else r.continue_()
        )
    return page

# ─── JS: Tüm data-* attribute'larını ve script içlerini topla ─────────────────
JS_TOPLAMA = """() => {
    const out = [];

    // Tüm elementlerdeki data-* attribute'ları
    document.querySelectorAll('*').forEach(el => {
        for (const attr of el.attributes) {
            if (attr.value && attr.value.startsWith('http')) out.push(attr.value);
        }
    });

    // Script tag içerikleri
    document.querySelectorAll('script:not([src])').forEach(s => {
        if (s.innerText) out.push(s.innerText);
    });

    // window değişkenleri
    for (const k of Object.keys(window)) {
        try {
            const v = window[k];
            if (typeof v === 'string' && v.startsWith('http')) out.push(v);
            if (typeof v === 'object' && v !== null) {
                try { const s = JSON.stringify(v); if (s.includes('http')) out.push(s); } catch(e) {}
            }
        } catch(e) {}
    }

    return out.join('\\n');
}"""

# ─── AŞAMA 1 ──────────────────────────────────────────────────────────────────
async def sayfa_filmlerini_cek(context, page_num):
    url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    page = await yeni_sayfa(context)
    try:
        r = await page.goto(url, timeout=30000, wait_until='domcontentloaded')
        await page.wait_for_timeout(1500)
        if not r or r.status not in [200, 304]: return None
        content = await page.content()
        if "Just a moment" in content: return None
        soup = BeautifulSoup(content, 'html.parser')
        films = soup.find_all('li', class_='film')
        if not films: return None
        filmler = []
        for film in films:
            title = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            if title and link_tag:
                img = film.find('img')
                filmler.append({
                    "title": title.text.strip(),
                    "link": link_tag['href'].rstrip('/'),
                    "imdb": (film.find('span', class_='imdb') or type('x',(),({"text":"0"}))()).text.strip(),
                    "year": (film.find('span', class_='film-yil') or type('x',(),({"text":""}))()).text.strip(),
                    "image": (img.get('data-src') or img.get('src','')) if img else "",
                    "rapid_link": ""
                })
        return filmler or None
    except Exception as e:
        print(f"    ⚠️ {e}")
        return None
    finally:
        await page.close()

# ─── AŞAMA 2 ──────────────────────────────────────────────────────────────────
async def rapid_link_cek(context, film_url, deneme=3):
    for attempt in range(deneme):
        page = await yeni_sayfa(context, engelle_media=False)
        caught = []

        page.on("request",  lambda r: caught.append(r.url) if stream_url_mi(r.url) else None)
        page.on("response", lambda r: (caught.append(r.url) if stream_url_mi(r.url) and r.url not in caught else None))

        try:
            await page.goto(film_url, timeout=40000, wait_until='domcontentloaded')

            # CF challenge bekle
            try:
                await page.wait_for_function(
                    "() => !document.title.includes('Just a moment')",
                    timeout=15000
                )
            except Exception:
                pass

            await page.wait_for_timeout(3000)
            if caught: return caught[0].strip()

            content = await page.content()
            if "Just a moment" in content:
                await asyncio.sleep(5); continue

            # 1. HTML doğrudan tara
            found = html_stream_ara(content)
            if found: return found

            # 2. networkidle — lazy-load için kritik
            try:
                await page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)
            if caught: return caught[0].strip()

            # 3. JS ile toplu data toplama (BeautifulSoup'un kaçırdıklarını yakala)
            try:
                js_dump = await page.evaluate(JS_TOPLAMA)
                found = html_stream_ara(js_dump)
                if found: return found
            except Exception:
                pass

            # 4. Player'a scroll + JS click simülasyonu
            player_sels = ['#plx', '.player-box', '#player', '.video-player',
                           '.film-player', '.izle-player', '.embed-responsive',
                           '[class*="player"]', '[id*="player"]', 'video']
            for sel in player_sels:
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        # Hem normal click hem JS click dene
                        try: await el.click(timeout=3000, force=True)
                        except Exception: pass
                        try:
                            await page.evaluate("(el) => { el.click(); el.dispatchEvent(new MouseEvent('click', {bubbles:true})); }", el)
                        except Exception: pass
                        await page.wait_for_timeout(3000)
                        if caught: return caught[0].strip()
                        found = html_stream_ara(await page.content())
                        if found: return found
                        try:
                            js_dump = await page.evaluate(JS_TOPLAMA)
                            found = html_stream_ara(js_dump)
                            if found: return found
                        except Exception: pass
                        break
                except Exception:
                    continue

            # 5. Kaynak / dil tablarına tıkla
            tab_sels = ['.player-tabs a', '.player-tabs button',
                        '.idSec a', '.idSec button',
                        'li[data-source]', 'li[data-id]', 'li[data-video]',
                        '.source-list li', '.source-list a',
                        '[data-video]', '[data-link]', '#kaynaklar a',
                        '.dil-tab a', '.tab-link', 'a[href*="rapidvid"]',
                        'a[href*="vidmoly"]', 'a[href*="doodstream"]']
            for sel in tab_sels:
                try:
                    for btn in await page.query_selector_all(sel):
                        if await btn.is_visible():
                            try: await btn.click(timeout=2000, force=True)
                            except Exception: pass
                            await page.wait_for_timeout(2500)
                            if caught: return caught[0].strip()
                            found = html_stream_ara(await page.content())
                            if found: return found
                except Exception:
                    continue

            # 6. Sayfadaki iframe URL'lerini topla + her birini ayrıca ziyaret et
            iframe_urls = []
            try:
                iframe_urls = await page.evaluate("""() =>
                    [...document.querySelectorAll('iframe')].map(f =>
                        f.getAttribute('data-src') || f.getAttribute('src') || ''
                    ).filter(s => s.startsWith('http'))
                """)
            except Exception:
                pass

            # Çalışan frame'lere bak
            for frame in page.frames:
                if frame == page.main_frame: continue
                try:
                    furl = frame.url
                    if furl and furl not in iframe_urls: iframe_urls.append(furl)
                    if furl and any(d in furl for d in STREAM_DOMAINS) and url_gecerli_mi(furl):
                        return furl.strip()
                    found = html_stream_ara(await frame.content())
                    if found: return found
                except Exception:
                    continue

            # iframe URL'lerini ayrı sayfada aç
            for iframe_url in iframe_urls:
                if not iframe_url or not iframe_url.startswith('http'): continue
                if BASE in iframe_url or "youtube" in iframe_url: continue
                if any(d in iframe_url for d in STREAM_DOMAINS) and url_gecerli_mi(iframe_url):
                    return iframe_url.strip()
                # İframe sayfasını yeni tab'da aç ve içini tara
                try:
                    sub = await yeni_sayfa(context, engelle_media=False)
                    sub.on("request",  lambda r: caught.append(r.url) if stream_url_mi(r.url) else None)
                    sub.on("response", lambda r: (caught.append(r.url) if stream_url_mi(r.url) and r.url not in caught else None))
                    await sub.goto(iframe_url, timeout=20000, wait_until='domcontentloaded')
                    await sub.wait_for_timeout(3000)
                    if caught: await sub.close(); return caught[0].strip()
                    found = html_stream_ara(await sub.content())
                    await sub.close()
                    if found: return found
                except Exception:
                    try: await sub.close()
                    except Exception: pass

        except Exception as e:
            print(f"    ⚠️ Deneme {attempt+1}: {e}")
            await asyncio.sleep(4)
        finally:
            try: await page.close()
            except Exception: pass

    return ""

# ─── MAIN ─────────────────────────────────────────────────────────────────────
async def main():
    filmler_dict = mevcut_filmleri_yukle()
    bos = [f for f in filmler_dict.values() if not f.get('rapid_link')]
    dolu = len(filmler_dict) - len(bos)
    print(f"✓ {len(filmler_dict)} film hafızaya alındı.")
    print(f"  → {dolu} geçerli link korundu, {len(bos)} link taranacak.\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox', '--disable-dev-shm-usage', '--mute-audio',
                '--disable-blink-features=AutomationControlled',
                '--window-size=1920,1080', '--disable-web-security',
                '--allow-running-insecure-content', '--lang=tr-TR',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='tr-TR', timezone_id='Europe/Istanbul',
            java_script_enabled=True, bypass_csp=True,
            ignore_https_errors=True,
            extra_http_headers={
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
                "Sec-Ch-Ua": '"Chromium";v="124","Google Chrome";v="124"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
            }
        )

        # AŞAMA 1
        print("=== AŞAMA 1: Yeni filmler taranıyor ===")
        bos_sayfa = 0
        for page_num in range(1, 20):
            filmler = await sayfa_filmlerini_cek(context, page_num)
            if filmler is None:
                bos_sayfa += 1
                print(f"Sayfa {page_num}: Erişilemedi.")
                if bos_sayfa >= 3: break
                continue
            bos_sayfa = 0
            yeni = [f for f in filmler if f['link'] not in filmler_dict]
            for f in yeni: filmler_dict[f['link']] = f
            print(f"Sayfa {page_num}: {len(filmler)} film, {len(yeni)} yeni.")
            if yeni: kesin_kaydet(filmler_dict)

        # AŞAMA 2
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
                    if link:
                        print(f"  ✓ [{islenen}/{len(bos)}] {film['title']}")
                        print(f"    → {link}")
                    else:
                        print(f"  ✗ [{islenen}/{len(bos)}] {film['title']}")

            for i in range(0, len(bos), 30):
                grup = bos[i:i+30]
                await asyncio.gather(*[isle(f) for f in grup])
                kesin_kaydet(filmler_dict)
                dolu_s = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
                print(f"\n💾 Kaydedildi — {islenen}/{len(bos)} işlendi, {dolu_s} link hazır\n")
                await asyncio.sleep(2)

        await browser.close()

    top = len(filmler_dict)
    dolu_s = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
    print(f"\n{'='*50}")
    if top > 0:
        print(f"✓ Tamamlandı. Toplam: {top} | Link: {dolu_s} ({dolu_s/top*100:.1f}%) | Eksik: {top-dolu_s}")
    else:
        print("✗ Hiç film çekilemedi.")
    print('='*50)

if __name__ == "__main__":
    asyncio.run(main())
