import asyncio
import json
import os
import re
import urllib.parse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

if not os.path.exists('data'):
    os.makedirs('data')

BASE = "https://www.fullhdfilmizlesene.life"
SONUC_DOSYA = "data/tum_filmler.json"
PARALEL = 3  # Tünel kullanıldığı için paralellik miktarını güvenle artırabiliriz

# Cloudflare Korumasını Aşmak İçin Kullanılan Güvenli API Köprüsü
CLOUD_BYPASS_API = "https://api.allorigins.win/get?url="

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

# Genişletilmiş ve optimize edilmiş oynatıcı kalıpları
PLAYER_PATTERNS = [
    r'https?://(?:www\.)?rapidvid\.net/[^\s"\'<>]+',
    r'https?://cdn\.imgz\.me/[^\s"\'<>]+',
    r'https?://(?:www\.)?vidmoly\.to/embed-[^\s"\'<>]+',
    r'https?://[^\s"\'<>]*(?:player|embed|watch|vod|stream)[^\s"\'<>]+',
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

async def sayfa_filmlerini_cek_safe(browser, page_num):
    target_url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    encoded_url = urllib.parse.quote_plus(target_url)
    bypass_url = f"{CLOUD_BYPASS_API}{encoded_url}"

    context = await browser.new_context(user_agent=HEADERS['User-Agent'])
    page = await context.new_page()
    
    try:
        response = await page.goto(bypass_url, timeout=30000)
        if not response or response.status != 200:
            return None
            
        raw_json = await page.locator("body").inner_text()
        data = json.loads(raw_json)
        html_content = data.get("contents", "")
        
        soup = BeautifulSoup(html_content, 'html.parser')
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
    except Exception:
        return None
    finally:
        await page.close()
        await context.close()

async def rapid_link_cek_safe(browser, film_url, deneme=2):
    # Film detay sayfasını da Cloudflare'e yakalanmamak için tünelden geçiriyoruz
    encoded_url = urllib.parse.quote_plus(film_url)
    bypass_url = f"{CLOUD_BYPASS_API}{encoded_url}"
    
    context = await browser.new_context(user_agent=HEADERS['User-Agent'])
    page = await context.new_page()
    
    for attempt in range(deneme):
        try:
            response = await page.goto(bypass_url, timeout=30000)
            if not response or response.status != 200:
                continue
                
            raw_json = await page.locator("body").inner_text()
            data = json.loads(raw_json)
            html_content = data.get("contents", "")
            
            if not html_content:
                continue

            # 1. Yöntem: HTML içerisindeki iframe src veya data-src yapılarını BS4 ile tara
            soup = BeautifulSoup(html_content, 'html.parser')
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('data-src') or iframe.get('src') or ''
                for pattern in PLAYER_PATTERNS:
                    if re.search(pattern, src):
                        await page.close()
                        await context.close()
                        return src.strip()

            # 2. Yöntem: HTML / JavaScript kod bloğunun tamamında regex taraması yap
            for pattern in PLAYER_PATTERNS:
                match = re.search(pattern, html_content)
                if match:
                    url = match.group(0).rstrip('"\' ')
                    if len(url) > 15:
                        await page.close()
                        await context.close()
                        return url
                        
            # 3. Yöntem: Alternatif JavaScript değişken kalıpları (file: "...", link: "...")
            js_patterns = [
                r'(?:file|src|source|url|link)\s*[=:]\s*["\'](\bhttps?://[^\s"\'<>]{10,})',
                r'iframe\.src\s*=\s*["\']([^"\']+)',
            ]
            for jp in js_patterns:
                match = re.search(jp, html_content)
                if match:
                    url = match.group(1).rstrip('"\' ')
                    if url.startswith('http'):
                        await page.close()
                        await context.close()
                        return url

        except Exception:
            if attempt < deneme - 1:
                await asyncio.sleep(2)
        finally:
            pass
            
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
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-infobars']
        )

        print("=== AŞAMA 1: Yeni filmler taranıyor ===")
        bos_sayfa = 0
        for page_num in range(1, 15):
            filmler = await sayfa_filmlerini_cek_safe(browser, page_num)
            await asyncio.sleep(1.5)
            
            if filmler is None:
                bos_sayfa += 1
                if bos_sayfa >= 3:
                    print(f"✓ Tarama tamamlandı veya sınır değerlere ulaşıldı.\n")
                    break
                continue
                
            bos_sayfa = 0
            yeni = [f for f in filmler if f['link'] not in filmler_dict]
            if yeni:
                print(f"Sayfa {page_num}: {len(yeni)} yeni film veritabanına eklendi.")
                for f in yeni:
                    filmler_dict[f['link']] = f
                kaydet(filmler_dict)
            else:
                print(f"Sayfa {page_num}: Yeni film yok, içerik güncel.")

        # === AŞAMA 2: Boş olan rapid_link alanlarını doldur ===
        bos_filmler = [f for f in filmler_dict.values() if not f.get('rapid_link')]
        if bos_filmler:
            print(f"\n=== AŞAMA 2: {len(bos_filmler)} film için medya linkleri çözülüyor ===\n")
            semaphore = asyncio.Semaphore(PARALEL)

            async def isle(film):
                async with semaphore:
                    link = await rapid_link_cek_safe(browser, film['link'])
                    film['rapid_link'] = link
                    durum = "✓" if link else "✗"
                    print(f"  {durum} {film['title']}")
                    return film

            islenen = 0
            for i in range(0, len(bos_filmler), 30):
                grup = bos_filmler[i:i+30]
                await asyncio.gather(*[isle(f) for f in grup])
                
                for f in grup:
                    filmler_dict[f['link']] = f
                    
                islenen += len(grup)
                kaydet(filmler_dict)
                dolu_sayisi = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
                print(f"\n💾 Değişiklikler Diske Yazıldı — {islenen}/{len(bos_filmler)} film tarandı.\n")
                await asyncio.sleep(2)

        await browser.close()

    dolu_sayisi = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
    print(f"\n✓ Görev Başarıyla Tamamlandı. Toplam: {len(filmler_dict)} film, {dolu_sayisi} link hazır.")

if __name__ == "__main__":
    asyncio.run(main())
