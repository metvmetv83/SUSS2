import asyncio
import json
import os
import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

if not os.path.exists('data'):
    os.makedirs('data')

BASE = "https://www.fullhdfilmizlesene.life"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36'}
SONUC_DOSYA = "data/tum_filmler.json"
PARALEL = 2  # GitHub Actions'ta kararlılık ve engellenmeme için 2 idealdir

VALID_STREAM_PATTERNS = [
    r'https?://(?:www\.)?rapidvid\.net/(?:vod|embed|v)/[^\s"\'<>]+',
    r'https?://cdn\.imgz\.me/[^\s"\'<>]+',
    r'https?://(?:www\.)?vidmoly\.(?:to|me|org|net|vc)/[^\s"\'<>]+',
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
                    if not r_link or BASE in r_link or "youtube.com" in r_link or "youtu.be" in r_link or len(r_link) < 15:
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

async def rapid_link_cek(context, film_url, deneme=2):
    for attempt in range(deneme):
        page = await context.new_page()
        try:
            # Medya yüklerini engelle, script akışına izin ver
            await page.route("**/*", lambda route: route.abort()
                if route.request.resource_type in ["image", "font", "stylesheet", "media"]
                else route.continue_()
            )

            # Dinamik Gelişmiş Ağ İstek İzleyicisi
            caught_url = []
            def on_request(req):
                url = req.url
                if BASE not in url and "youtube.com" not in url and "youtu.be" not in url:
                    for pattern in VALID_STREAM_PATTERNS:
                        if re.search(pattern, url):
                            caught_url.append(url)
                            break

            page.on("request", on_request)

            # Sayfaya git ve DOM'un yüklenmesini bekle
            await page.goto(film_url, timeout=25000, wait_until='domcontentloaded')
            await page.wait_for_timeout(2000)

            # 1. Aşama: Sayfa ilk açıldığında link ağ trafiğine düştü mü?
            if caught_url:
                await page.close()
                return caught_url[0].strip()

            # 2. Aşama: Kritik "Tek Tıklama" Simülasyonu
            # Önce video kutusunun (player box) tam ortasına tek tıklama yaparak oynatıcıyı aktifleştiriyoruz
            player_boxes = ['#plx', '.player-box', '#player', '.video-container', '.embed-responsive']
            for box in player_boxes:
                try:
                    el = await page.query_selector(box)
                    if el:
                        # Element görünür olana kadar bekle ve tam merkezine TEK TIK yap
                        await el.scroll_into_view_if_needed()
                        await el.click(timeout=2000, force=True)
                        await page.wait_for_timeout(1500)
                        if caught_url:
                            await page.close()
                            return caught_url[0].strip()
                        break
                except:
                    continue

            # 3. Aşama: Dil / Alternatif sekmelerine TEK TIKLAMA Uygulama
            # Sitenin güncellenen tüm muhtemel buton seçicileri listelendi
            tab_selectors = [
                '#dil-secenekleri kalip', 
                '.player-tabs a', 
                '.idSec a', 
                'li[data-source]',
                '.video-alternatives button',
                '.source-list li',
                '.player-nav ul li'
            ]
            
            for selector in tab_selectors:
                try:
                    buttons = await page.query_selector_all(selector)
                    for btn in buttons:
                        if await btn.is_visible():
                            await btn.click(timeout=1500, force=True)
                            await page.wait_for_timeout(1200)
                            if caught_url:
                                await page.close()
                                return caught_url[0].strip()
                except:
                    continue

            # 4. Aşama: Sayfa Kaynağından Gelişmiş Regex & ID Ayıklama
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # iframe elementlerini doğrudan kontrol et
            for iframe in soup.find_all('iframe'):
                src = iframe.get('data-src') or iframe.get('src') or ''
                if any(domain in src for domain in ["rapidvid", "vidmoly", "imgz"]):
                    if BASE not in src and "youtube" not in src:
                        await page.close()
                        return src.strip()

            # Gizli script değişkenlerini tara
            js_patterns = [
                r'data-id=["\'](\d+)["\']',
                r'["\']?id["\']?\s*:\s*["\'](\d+)["\']',
                r'video_id\s*=\s*["\'](\d+)["\']',
                r'["\']?source["\']?\s*:\s*["\']([^"\']+(?:rapidvid|vidmoly)[^"\']+)["\']'
            ]
            for pattern in js_patterns:
                match = re.search(pattern, content)
                if match:
                    res = match.group(1)
                    if res.isdigit() and len(res) >= 4:
                        await page.close()
                        return f"https://rapidvid.net/embed/{res}"
                    elif "http" in res:
                        await page.close()
                        return res.strip()

        except Exception:
            if attempt < deneme - 1:
                await asyncio.sleep(2)
        finally:
            await page.close()

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

        # === AŞAMA 1: Yeni Sayfaları Tara ===
        print("=== AŞAMA 1: Yeni filmler taranıyor ===")
        bos_sayfa = 0
        for page_num in range(1, 10):
            filmler = await sayfa_filmlerini_cek_pw(context, page_num)
            if filmler is None:
                bos_sayfa += 1
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
                print(f"Sayfa {page_num}: {yeni_eklenen} yeni film listeye eklendi.")
                kesin_kaydet(filmler_dict)
            else:
                print(f"Sayfa {page_num}: Yeni film yok.")

        # === AŞAMA 2: Link Arama ve Anlık Diske Yazma ===
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
                        print(f"  ✓ BAŞARILI: {film['title']} -> {link}")
                    else:
                        print(f"  ✗ BULUNAMADI: {film['title']}")
                    return film

            for i in range(0, len(bos_filmler), 10):
                grup = bos_filmler[i:i+10]
                await asyncio.gather(*[isle(f) for f in grup])
                await asyncio.sleep(1.5)

        await browser.close()

    dolu_sayisi = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
    print(f"\n✓ İşlem tamamlandı. Toplam Veritabanı: {len(filmler_dict)} film | Geçerli Link Sayısı: {dolu_sayisi}")

if __name__ == "__main__":
    asyncio.run(main())
