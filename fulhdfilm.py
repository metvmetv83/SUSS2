import requests
from bs4 import BeautifulSoup
import json
import os
import base64
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

if not os.path.exists('data'):
    os.makedirs('data')

BASE = "https://www.fullhdfilmizlesene.live"
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
SONUC_DOSYA = "data/tum_filmler.json"
PARALEL = 8  # Aynı anda kaç film çekilsin

def udc_decode(data_no, data_id):
    """
    JS'deki udc() fonksiyonunun Python karşılığı:
    1. key = (data_no + "ajax")[0] XOR len(data_no + "ajax")
    2. data_id'yi ters çevir
    3. Base64 padding ekle, +/ düzelt
    4. Base64 decode
    5. Her byte'ı key ile XOR
    6. UTF-8 decode → iframe HTML
    """
    try:
        c = str(data_no) + "ajax"
        e = 255 & (ord(c[0]) ^ len(c))

        f = data_id[::-1]  # reverse
        # Padding ekle
        pad = "===" 
        f = f + pad[:(( len(f) + 3) % 4)]
        # URL-safe base64 → standart
        f = f.replace('-', '+').replace('_', '/')

        g = bytearray(base64.b64decode(f))
        for i in range(len(g)):
            g[i] ^= e

        html = g.decode('utf-8', errors='ignore')
        return html
    except Exception as ex:
        return ""

def rapid_link_cek(film_url):
    """requests ile film sayfasını çek, data-id'yi decode et, rapidvid linkini bul"""
    try:
        with requests.Session() as s:
            s.headers.update(HEADERS)
            s.get(BASE, timeout=10)  # cookie al
            res = s.get(film_url, timeout=12)
            if res.status_code != 200:
                return ""

            soup = BeautifulSoup(res.text, 'html.parser')

            for div in soup.find_all('div', class_='ajax-data'):
                data_no = div.get('data-no', '')
                data_id = div.get('data-id', '')
                if not data_id:
                    continue

                decoded = udc_decode(data_no, data_id)
                if not decoded:
                    continue

                # iframe data-src içinde rapidvid ara
                match = re.search(
                    r'https?://(?:rapidvid\.net|cdn\.imgz\.me)/(?:vod|player/ifr/vod)/[a-zA-Z0-9]+',
                    decoded
                )
                if match:
                    return match.group(0)

                # data-src attribute olarak ara
                inner_soup = BeautifulSoup(decoded, 'html.parser')
                iframe = inner_soup.find('iframe')
                if iframe:
                    src = iframe.get('data-src') or iframe.get('src') or ''
                    if src and ('rapidvid' in src or 'imgz' in src):
                        return src

    except Exception as e:
        pass
    return ""

def sayfa_filmlerini_cek(slug, page_num):
    url = f"{BASE}/{slug}/" if page_num == 1 else f"{BASE}/{slug}/{page_num}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        if not films:
            return None
        filmler = []
        for film in films:
            title = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            if title and link_tag:
                img_tag = film.find('img')
                filmler.append({
                    "title": title.text.strip(),
                    "link": link_tag['href'].rstrip('/'),
                    "imdb": film.find('span', class_='imdb').text if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').text if film.find('span', class_='film-yil') else "",
                    "image": (img_tag.get('data-src') or img_tag.get('src')) if img_tag else "",
                    "rapid_link": ""
                })
        return filmler
    except:
        return None

def mevcut_filmleri_yukle():
    if os.path.exists(SONUC_DOSYA):
        with open(SONUC_DOSYA, 'r', encoding='utf-8') as f:
            liste = json.load(f)
            return {film['link']: film for film in liste}
    return {}

def kaydet(filmler_dict):
    with open(SONUC_DOSYA, 'w', encoding='utf-8') as f:
        json.dump(list(filmler_dict.values()), f, ensure_ascii=False, indent=2)

def main():
    filmler_dict = mevcut_filmleri_yukle()
    print(f"✓ {len(filmler_dict)} film mevcut, kaldığı yerden devam\n")

    bos_sayfa = 0
    toplam_yeni = 0

    for page_num in range(1, 9999):
        print(f"--- Sayfa {page_num} ---")
        filmler = sayfa_filmlerini_cek("yeni-filmler", page_num)

        if filmler is None:
            bos_sayfa += 1
            print(f"  [Boş/404 — {bos_sayfa}/3]")
            if bos_sayfa >= 3:
                print("✓ Tüm sayfalar tamamlandı.")
                break
            continue

        bos_sayfa = 0
        yeni = [f for f in filmler if f['link'] not in filmler_dict]
        atlanan = len(filmler) - len(yeni)
        if atlanan:
            print(f"  ↷ {atlanan} film atlandı (mevcut)")
        if not yeni:
            print(f"  Yeni film yok\n")
            continue

        print(f"  {len(yeni)} yeni film çekiliyor...")

        # Paralel çek
        with ThreadPoolExecutor(max_workers=PARALEL) as executor:
            futures = {executor.submit(rapid_link_cek, f['link']): f for f in yeni}
            for future in as_completed(futures):
                film = futures[future]
                film['rapid_link'] = future.result()
                durum = "✓" if film['rapid_link'] else "✗"
                print(f"    {durum} {film['title']} — {film['rapid_link'] or 'BULUNAMADI'}")
                filmler_dict[film['link']] = film

        # Her sayfadan sonra kaydet
        kaydet(filmler_dict)
        toplam_yeni += len(yeni)
        print(f"  💾 Toplam: {len(filmler_dict)} film\n")

    print(f"\n✓ Bitti. {toplam_yeni} yeni film. Toplam: {len(filmler_dict)}")

if __name__ == "__main__":
    main()
