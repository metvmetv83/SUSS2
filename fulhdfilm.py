import asyncio
import json
import os
import re
import urllib.parse
import random
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

if not os.path.exists('data'):
    os.makedirs('data')

BASE = "https://www.fullhdfilmizlesene.life"
SONUC_DOSYA = "data/tum_filmler.json"
PARALEL = 2

PROXIES = [
    "https://api.allorigins.win/get?url=",
    "https://api.codetabs.com/v1/proxy/?quest=",
    "https://corsproxy.io/?"
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

# Sadece gerçek video sağlayıcılarını hedefleyen nokta atışı kalıplar (Sitenin kendi linkleri ve YT elendi)
STRICT_PLAYER_PATTERNS = [
    r'https?://(?:www\.)?rapidvid\.net/embed/[^\s"\'<>]+',
    r'https?://cdn\.imgz\.me/[^\s"\'<>]+',
    r'https?://(?:www\.)?vidmoly\.to/embed-[^\s"\'<>]+',
    r'https?://(?:www\.)?vidmoly\.me/embed-[^\s"\'<>]+',
    r'https?://[^\s"\'<>]+player\d+\.php\?[^\s"\'<>]+',
    r'https?://[^\s"\'<>]+\.(?:mp4|m3u8)(?:\?[^\s"\'<>]+)?'
]

def mevcut_filmleri_yukle():
    if os.path.exists(SONUC_DOSYA):
        with open(SONUC_DOSYA, 'r', encoding='utf-8') as f:
            try:
                # Eğer daha önce hatalı ana sayfa veya youtube linki kaydedildiyse onları temizleyip "boş" sayalım
                filmler = json.load(f)
                cleaned_dict = {}
                for film in filmler:
                    r_link = film.get('rapid_link', '')
                    if BASE in r_link or "youtube.com" in r_link or "youtu.be" in r_link:
                        film['rapid_link'] = "" # Hatalı linki sıfırla ki bot yeniden doğrusunu arasın
                    cleaned_dict[film['link']] = film
                return cleaned_dict
            except json.JSONDecodeError:
                return {}
    return {}

def kaydet(filmler_dict):
    with open(SONUC_DOSYA, 'w', encoding='utf-8') as f:
        json.dump(list(filmler_dict.values()), f, ensure_ascii=False, indent=2)

def unpack_javascript(packed_code):
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
        return re_word.sub(lambda m: symtab.get(m.group(0), m.group(0)), p)
    except Exception:
        return packed_code

async def fetch_with_fallback(page, target_url):
    shuffled_proxies = PROXIES.copy()
    random.shuffle(shuffled_proxies)
    encoded_url = urllib.parse.quote_plus(target_url)
    
    for proxy_base in shuffled_proxies:
        try:
            bypass_url = f"{proxy_base}{target_url}" if "corsproxy.io" in proxy_base else f"{proxy_base}{encoded_url}"
            response = await page.goto(bypass_url, timeout=25000)
            if response and response.status == 200:
                raw_text = await page.locator("body").inner_text()
                if "allorigins" in proxy_base:
                    try:
                        return json.loads(raw_text).get("contents", "")
                    except:
                        pass
                return raw_text
        except Exception:
            await asyncio.sleep(1)
            continue
    return ""

async def sayfa_filmlerini_cek_safe(browser, page_num):
    target_url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    context = await browser.new_context(user_agent=HEADERS['User-Agent'])
    page = await context.new_page()
    try:
        html_content = await fetch_with_fallback(page, target_url)
        if not html_content: return None
        soup = BeautifulSoup(html_content, 'html.parser')
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
                    "imdb": film.find('span', class_='imdb').text if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').text if film.find('span', class_='film-yil') else "",
                    "image": (img.get('data-src') or img.get('src')) if img else "",
                    "rapid_link": ""
                })
        return filmler
    except Exception: return None
    finally:
        await page.close()
        await context.close()

async def rapid_link_cek_safe(browser, film_url, deneme=2):
    context = await browser.new_context(user_agent=HEADERS['User-Agent'])
    page = await context.new_page()
    
    for attempt in range(deneme):
        try:
            html_content = await fetch_with_fallback(page, film_url)
            if not html_content or len(html_content) < 200: continue

            if "eval(function(p,a,c,k,e,d)" in html_content:
                html_content = unpack_javascript(html_content)

            # 1. Aşama: DOM / Iframe Ayıklama (Öncelikli)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Sitenin asıl video konteynerlerini hedef alıyoruz (#plx, .player-inside vb.)
            player_containers = soup.select('#plx, .player-box, .player-inside, #player')
            for container in player_containers:
                iframes = container.find_all('iframe')
                for iframe in iframes:
                    src = iframe.get('data-src') or iframe.get('src') or ''
                    # YouTube veya sitenin kendi linki değilse ve pattern'e uyuyorsa dön
                    if "youtube.com" not in src and "youtu.be" not in src and BASE not in src:
                        for pattern in STRICT_PLAYER_PATTERNS:
                            if re.search(pattern, src):
                                await page.close()
                                await context.close()
                                return src.strip()

            # 2. Aşama: Eğer Iframe elementlerinden bulunamadıysa, JavaScript bloklarından katı kural taraması yap
            for pattern in STRICT_PLAYER_PATTERNS:
                matches = re.findall(pattern, html_content)
                for match in matches:
                    url = match.rstrip('"\' ').replace('\\', '')
                    if "youtube.com" not in url and BASE not in url and len(url) > 15:
                        await page.close()
                        await context.close()
                        return url

            # 3. Aşama: data-id veya alternatif ajax parametreleri taraması (Sitenin özel yapıları için)
            data_id_match = re.search(r'data-id=["\'](\d+)["\']', html_content)
            if data_id_match:
                # Eğer korumalı bir player kimliği varsa alternatif yapı türetilebilir
                generated_src = f"https://rapidvid.net/embed/{data_id_match.group(1)}"
                await page.close()
                await context.close()
                return generated_src

        except Exception:
            if attempt < deneme - 1: await asyncio.sleep(2)
        finally: pass
            
    await page.close()
    await context.close()
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
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-infobars']
        )

        print("=== AŞAMA 1: Yeni filmler taranıyor ===")
        bos_sayfa = 0
        for page_num in range(1, 15):
            filmler = await sayfa_filmlerini_cek_safe(browser, page_num)
            await asyncio.sleep(random.uniform(1.5, 2.5))
            if filmler is None:
                bos_sayfa += 1
                if bos_sayfa >= 3: break
                continue
            bos_sayfa = 0
            yeni = [f for f in filmler if f['link'] not in filmler_dict]
            if yeni:
                print(f"Sayfa {page_num}: {len(yeni)} yeni film veritabanına eklendi.")
                for f in yeni: filmler_dict[f['link']] = f
                kaydet(filmler_dict)
            else:
                print(f"Sayfa {page_num}: Yeni film yok, içerik güncel.")

        # === AŞAMA 2: Filtrelenmiş ve Doğrulanmış Linkleri Çöz ===
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
                    await asyncio.sleep(random.uniform(0.8, 1.5))
                    return film

            islenen = 0
            for i in range(0, len(bos_filmler), 20):
                grup = bos_filmler[i:i+20]
                await asyncio.gather(*[isle(f) for f in grup])
                for f in grup: filmler_dict[f['link']] = f
                islenen += len(grup)
                kaydet(filmler_dict)
                print(f"\n💾 Değişiklikler Diske Yazıldı — {islenen}/{len(bos_filmler)} film tarandı.\n")
                await asyncio.sleep(4)

        await browser.close()

    dolu_sayisi = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
    print(f"\n✓ Görev Başarıyla Tamamlandı. Toplam: {len(filmler_dict)} film, {dolu_sayisi} gerçek link hazır.")

if __name__ == "__main__":
    asyncio.run(main())
