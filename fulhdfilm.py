import asyncio
import json
import os
import re
import time
from bs4 import BeautifulSoup

# curl_cffi: Cloudflare TLS parmak izi taklidini yapabilen tek kütüphane
try:
    from curl_cffi import requests as cffi_requests
    CFFI_OK = True
except ImportError:
    CFFI_OK = False
    print("⚠️  curl_cffi bulunamadı, standart requests kullanılacak.")
    import requests

if not os.path.exists('data'):
    os.makedirs('data')

BASE = "https://www.fullhdfilmizlesene.life"
SONUC_DOSYA = "data/tum_filmler.json"

STREAM_DOMAINS = [
    "rapidvid", "vidmoly", "imgz.me", "doodstream",
    "streamtape", "filemoon", "mixdrop", "upstream",
    "vidsrc", "ok.ru", "myvi.ru", "sibnet.ru",
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

# ─── SESSION (curl_cffi ile Chrome TLS taklidi) ───────────────────────────────
def session_olustur():
    if CFFI_OK:
        s = cffi_requests.Session(impersonate="chrome124")
        s.headers.update({
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1",
        })
        return s
    else:
        import requests as req
        s = req.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        return s

SESSION = session_olustur()

# ─── YARDIMCI FONKSİYONLAR ───────────────────────────────────────────────────
def url_gecerli_mi(url):
    if not url or len(url) < 15:
        return False
    for skip in [BASE, "youtube.com", "youtu.be", "google.com",
                 "facebook.com", "twitter.com", "adnxs.com",
                 "doubleclick.net", "cloudflare.com"]:
        if skip in url:
            return False
    return True

def stream_url_mi(url):
    if not url_gecerli_mi(url):
        return False
    for pat in VALID_STREAM_PATTERNS:
        if re.search(pat, url, re.IGNORECASE):
            return True
    return False

def html_stream_ara(html):
    for pat in VALID_STREAM_PATTERNS:
        for m in re.findall(pat, html, re.IGNORECASE):
            if url_gecerli_mi(m):
                return m.strip()
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all(['iframe', 'source', 'video']):
        for attr in ['src', 'data-src', 'data-lazy-src', 'data-url']:
            src = tag.get(attr, '')
            if src and any(d in src for d in STREAM_DOMAINS) and url_gecerli_mi(src):
                return src.strip()
    return None

def sayfa_getir(url, referer=None, deneme=3):
    """curl_cffi ile HTTP GET — Cloudflare'i geçer."""
    headers = {}
    if referer:
        headers["Referer"] = referer
    for i in range(deneme):
        try:
            r = SESSION.get(url, headers=headers, timeout=30, allow_redirects=True)
            if r.status_code == 200:
                return r.text
            elif r.status_code == 403:
                print(f"    403 engeli (deneme {i+1}): {url}")
                time.sleep(4)
            else:
                print(f"    HTTP {r.status_code}: {url}")
                return None
        except Exception as e:
            print(f"    İstek hatası (deneme {i+1}): {e}")
            time.sleep(3)
    return None

# ─── VERİ YÜKLEME / KAYDETME ─────────────────────────────────────────────────
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
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print(f"⚠️ Kaydetme hatası: {e}")

# ─── AŞAMA 1: FİLM LİSTESİ ───────────────────────────────────────────────────
def sayfa_filmlerini_cek(page_num):
    url = f"{BASE}/yeni-filmler/" if page_num == 1 else f"{BASE}/yeni-filmler/{page_num}"
    html = sayfa_getir(url)
    if not html:
        return None

    if "Just a moment" in html or "cf-browser-verification" in html:
        print(f"    ⚠️ Cloudflare challenge aşılamadı: {url}")
        return None

    soup = BeautifulSoup(html, 'html.parser')
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
                "imdb": (film.find('span', class_='imdb') or type('', (), {'text': '0'})()).text.strip(),
                "year": (film.find('span', class_='film-yil') or type('', (), {'text': ''})()).text.strip(),
                "image": (img.get('data-src') or img.get('src', '')) if img else "",
                "rapid_link": ""
            })
    return filmler if filmler else None

# ─── AŞAMA 2: STREAM LİNK ÇEKME ─────────────────────────────────────────────
def rapid_link_cek(film_url, deneme=3):
    for attempt in range(deneme):
        html = sayfa_getir(film_url, referer=BASE)
        if not html:
            time.sleep(3)
            continue

        if "Just a moment" in html or "cf-browser-verification" in html:
            print(f"    ⚠️ CF challenge (deneme {attempt+1})")
            time.sleep(6)
            continue

        # 1. Doğrudan HTML tarama
        found = html_stream_ara(html)
        if found:
            return found

        # 2. İframe URL'lerini bul ve içlerini de çek
        soup = BeautifulSoup(html, 'html.parser')
        for iframe in soup.find_all('iframe'):
            for attr in ['src', 'data-src', 'data-lazy-src']:
                src = iframe.get(attr, '').strip()
                if not src or not src.startswith('http'):
                    continue
                # Stream domain'i doğrudan iframe src'si mi?
                if any(d in src for d in STREAM_DOMAINS) and url_gecerli_mi(src):
                    return src
                # İframe içeriğini de çek
                if BASE not in src and "youtube" not in src:
                    iframe_html = sayfa_getir(src, referer=film_url)
                    if iframe_html:
                        found = html_stream_ara(iframe_html)
                        if found:
                            return found

        # 3. data-* attribute tarama (dinamik player'lar için)
        for tag in soup.find_all(True):
            for attr, val in tag.attrs.items():
                if isinstance(val, str) and val.startswith('http'):
                    if stream_url_mi(val):
                        return val.strip()

        # 4. Script içi JSON/string tarama
        for script in soup.find_all('script'):
            text = script.string or ''
            found = html_stream_ara(text)
            if found:
                return found

        time.sleep(2)
    return ""

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    filmler_dict = mevcut_filmleri_yukle()
    bos_filmler = [f for f in filmler_dict.values() if not f.get('rapid_link')]
    dolu = len(filmler_dict) - len(bos_filmler)
    print(f"✓ {len(filmler_dict)} film hafızaya alındı.")
    print(f"  → {dolu} geçerli link korundu, {len(bos_filmler)} boş/hatalı link taranacak.\n")

    # AŞAMA 1
    print("=== AŞAMA 1: Yeni filmler taranıyor ===")
    bos_sayfa = 0
    for page_num in range(1, 11):
        filmler = sayfa_filmlerini_cek(page_num)
        if filmler is None:
            bos_sayfa += 1
            print(f"Sayfa {page_num}: Erişilemedi.")
            if bos_sayfa >= 2:
                break
            continue
        bos_sayfa = 0
        yeni = 0
        for f in filmler:
            if f['link'] not in filmler_dict:
                filmler_dict[f['link']] = f
                yeni += 1
        print(f"Sayfa {page_num}: {yeni} yeni film, toplam {len(filmler)} film listelendi.")
        if yeni > 0:
            kesin_kaydet(filmler_dict)
        time.sleep(1.5)

    # AŞAMA 2
    bos_filmler = [f for f in filmler_dict.values() if not f.get('rapid_link')]
    if bos_filmler:
        print(f"\n=== AŞAMA 2: {len(bos_filmler)} film için link çıkarılıyor ===\n")
        for idx, film in enumerate(bos_filmler, 1):
            print(f"  [{idx}/{len(bos_filmler)}] {film['title']}")
            link = rapid_link_cek(film['link'])
            if link:
                film['rapid_link'] = link
                filmler_dict[film['link']] = film
                kesin_kaydet(filmler_dict)
                print(f"    ✓ {link}")
            else:
                print(f"    ✗ Bulunamadı")
            time.sleep(1.5)

    top = len(filmler_dict)
    dolu_s = sum(1 for f in filmler_dict.values() if f.get('rapid_link'))
    print(f"\n{'='*50}")
    print(f"✓ Tamamlandı.")
    if top > 0:
        print(f"  Toplam Film   : {top}")
        print(f"  Geçerli Link  : {dolu_s} ({dolu_s/top*100:.1f}%)")
        print(f"  Eksik Link    : {top - dolu_s}")
    else:
        print("  Hiç film çekilemedi — site erişimi başarısız.")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
