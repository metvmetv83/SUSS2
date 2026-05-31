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
PARALEL = 3

# Yedekli Proxy Köprüleri (Allorigins yoğunsa diğeri devreye girer)
PROXIES = [
    "https://api.allorigins.win/get?url=",
    "https://api.codetabs.com/v1/proxy/?quest="
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

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

def unpack_javascript(packed_code):
    """ Dean Edwards Packer ile şifrelenmiş JS kodlarını çözer """
    try:
        payload_match = re.search(r"}\s*\('(.*)',\s*(\d+),\s*(\d+),\s*'(.*)'\.split", packed_code)
        if not payload_match:
            return packed_code
        
        p, a, c, k = payload_match.groups()
        a, c = int(a), int(c)
        k = k.split('|')
        
        def baseN(num, b):
            return "0" if num == 0 else baseN(num // b, b).lstrip("0") + "0123456789abcdefghijklmnopqrstuvwxyz"[num % b]
            
        symtab = {}
        for i in range(c):
            symtab[baseN(i, a) if i >= a else str(i)] = k[i] or baseN(i, a)
            
        re_word = re.compile(r'\b\w+\b')
        unpacked = re_word.sub(lambda m: symtab.get(m.group(0), m.group(0)), p)
        return unpacked
    except Exception:
        return packed_code

async def fetch_with_fallback(page, target_url):
    """ Sırayla proxy havuzunu deneyerek içeriği çeker """
    encoded_url = urllib.parse.quote_plus(target_url)
    for proxy_base in PROXIES:
        try:
            bypass_url = f"{proxy_base}{encoded_url}"
            response = await page.goto(bypass_url, timeout=20000)
            if response and response.status == 200:
                raw_text = await page.locator("body").inner_text()
                # Allorigins için JSON temizliği
                if "allorigins" in proxy_base:
                    data = json.loads(raw_text)
                    return data.get("contents", "")
                return raw_text
        except Exception:
            continue
    return ""

async def sayfa_filmlerini_cek_safe(browser, page_num):
    target_url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    context = await browser.new_context(user_agent=HEADERS['User-Agent'])
    page = await context.new_page()
    
    try:
        html_content = await fetch_with_fallback(page, target_url)
        if not html_content:
            return None
            
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
    context = await browser.new_context(user_agent=HEADERS['User-Agent'])
    page = await context.new_page()
    
    for attempt in range(deneme):
        try:
            html_content = await fetch_with_fallback(page, film_url)
            if not html_content:
                continue

            # Eğer js şifrelenmişse önce onu çözüyoruz
            if "eval(function(p,a,c,k,e,d)" in html_content:
                html_content = unpack_javascript(html_content)

            # 1. Aşama: iframe elementlerini tara
            soup = BeautifulSoup(html_content, 'html.parser')
            iframes = soup.find_all('iframe')
            for iframe in iframes:
                src = iframe.get('data-src') or iframe.get('src') or ''
                for pattern in PLAYER_PATTERNS:
                    if re.search(pattern, src):
                        await page.close()
                        await context.close()
                        return src.strip()

            # 2. Aşama: Kod bloğunun tamamını regex ile tara
            for pattern in PLAYER_PATTERNS:
                match = re.search(pattern, html_content)
                if match:
                    url = match.group(0).rstrip('"\' ')
                    if len(url) > 15:
                        await page.close()
                        await context.close()
                        return url
                        
            # 3. Aşama: Gizli JS değişkenlerini ayrıştır
            js_patterns = [
                r'(?:file|src|source|url|link)\s*[=:]\s*["\'](\bhttps?://[^\s"\'<>]{10,})',
                r'iframe\.src\s*=\s*["\']([^"\']+)',
                r'player\.setSource\(["\']([^"\']+)'
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
                await asyncio.sleep(1.5)
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
            await asyncio.sleep(1)
            
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
