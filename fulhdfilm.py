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
PARALEL = 3  # Bot korumasını tetiklememek için ideal seviye

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
            try:
                return {film['link']: film for film in json.load(f)}
            except json.JSONDecodeError:
                return {}
    return {}

def kaydet(filmler_dict):
    with open(SONUC_DOSYA, 'w', encoding='utf-8') as f:
        json.dump(list(filmler_dict.values()), f, ensure_ascii=False, indent=2)

# Liste sayfalarını çekmek için de Playwright kullanıyoruz
async def sayfa_filmlerini_cek_playwright(browser, page_num):
    url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    context = await browser.new_context(user_agent=HEADERS['User-Agent'])
    page = await context.new_page()
    
    try:
        # Sadece HTML çekmek istediğimiz için statik dosyaları engelliyoruz
        await page.route("**/*", lambda route: route.abort() 
                         if route.request.resource_type in ["image", "font", "media", "stylesheet"] 
                         else route.continue_())
        
        response = await page.goto(url, timeout=30000, wait_until='domcontentloaded')
        if not response or response.status != 200:
            print(f"⚠️ Sayfa {page_num} yüklenemedi. Durum Kodu: {response.status if response else 'No Response'}")
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
        print(f"⚠️ Sayfa {page_num} taranırken hata oluştu: {str(e)}")
        return None
    finally:
        await page.close()
        await context.close()

async def rapid_link_cek(browser, film_url, deneme=2):
    # Eşzamanlı isteklerde çerez çakışması olmaması için her filme özel temiz context
    context = await browser.new_context(
        user_agent=HEADERS['User-Agent'],
        viewport={'width': 1280, 'height': 720},
        java_script_enabled=True
    )
    await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    
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
                for pattern in PLAYER_PATTERNS:
                    if re.search(pattern, url):
                        caught_url.append(url)
                        break

            page.on("request", on_request)
            await page.goto(film_url, timeout=30000, wait_until='domcontentloaded')
            await page.wait_for_timeout(4000) # JS frame'lerin yüklenmesi için ideal süre

            if caught_url:
                await page.close()
                await context.close()
                return caught_url[0]

            # DOM element kontrolü
            iframe_selectors = ['#plx iframe', '.player-box iframe', 'iframe[src*="rapid"]', 'iframe']
            for selector in iframe_selectors:
                try:
                    src = await page.eval_on_selector(
                        selector,
                        'el => el.getAttribute("data-src") || el.getAttribute("src") || ""',
                        timeout=2000
                    )
                    if src and src.startswith('http'):
                        await page.close()
                        await context.close()
                        return src.strip()
                except:
                    continue

            # Sayfa kaynağı kontrolü
            content = await page.content()
            for pattern in PLAYER_PATTERNS:
                match = re.search(pattern, content)
                if match:
                    url = match.group(0).rstrip('"\' ')
                    if len(url) > 15:
                        await page.close()
                        await context.close()
                        return url
                        
        except Exception as e:
            if attempt < deneme - 1:
                await asyncio.sleep(3)
        finally:
            await page.close()
            
    await context.close()
    return ""

async def main():
    filmler_dict = mevcut_filmleri_yukle()
    bos = [f for f in filmler_dict.values() if not f.get('rapid_link')]
    dolu = len(filmler_dict) - len(bos)
    print(f"✓ {len(filmler_dict)} film yüklendi (Veritabanından)")
    print(f"  → {dolu} filmde link var, {len(bos)} filmde link boş\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--mute-audio',
                  '--disable-blink-features=AutomationControlled']
        )

        # === AŞAMA 1: Yeni sayfaları tara ===
        print("=== AŞAMA 1: Yeni filmler taranıyor ===")
        bos_sayfa = 0
        for page_num in range(1, 100):  # Test amaçlı veya ilk aşamada sınırı kontrol altında tutmak için 100 yapıldı
            filmler = await sayfa_filmlerini_cek_playwright(browser, page_num)
            if filmler is None:
                bos_sayfa += 1
                if bos_sayfa >= 3:
                    print(f"✓ Veri akışı kesildi veya son sayfaya ulaşıldı.\n")
                    break
                continue
                
            bos_sayfa = 0
            yeni = [f for f in filmler if f['link'] not in filmler_dict]
            if yeni:
                print(f"Sayfa {page_num}: {len(yeni)} yeni film veritabanına eklendi.")
                for f in yeni:
                    filmler_dict[f['link']] = f
                kaydet(filmler_dict) # Yeni filmleri anında diske yazalım
            else:
                print(f"Sayfa {page_num}: Yeni film yok, mevcutlar güncel.")

        # === AŞAMA 2: Boş rapid_link olanları doldur ===
        bos_filmler = [f for f in filmler_dict.values() if not f.get('rapid_link')]
        print(f"\n=== AŞAMA 2: {len(bos_filmler)} film için iframe/video linkleri çözülüyor ===\n")

        semaphore = asyncio.Semaphore(PARALEL)

        async def isle(film):
            async with semaphore:
                link = await rapid_link_cek(browser, film['link'])
                film['rapid_link'] = link
                durum = "✓" if link else "✗"
                print(f"  {durum} {film['title']}")
                return film

        # 50'şerli gruplar halinde işleme ve periyodik kaydetme
        islenen = 0
        for i in range(0, len(bos_filmler), 50):
            grup = bos_filmler[i:i+50]
            await asyncio.gather(*[isle(f) for f in grup])
            
            for f in grup:
                filmler_dict[f['link']] = f
                
            islenen += len(grup)
            kaydet(filmler_dict)
            dolu_sayisi = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
            print(f"\n💾 İlerleme Kaydedildi — {islenen}/{len(bos_filmler)} film tarandı. Toplam linkli film: {dolu_sayisi}\n")

        await browser.close()

    dolu_sayisi = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
    print(f"\n✓ Görev Tamamlandı. Toplam: {len(filmler_dict)} film, {dolu_sayisi} link hazır.")

if __name__ == "__main__":
    asyncio.run(main())
