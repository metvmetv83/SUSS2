import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

if not os.path.exists('data'):
    os.makedirs('data')

def detay_linki_cek(film_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Referer': 'https://www.fullhdfilmizlesene.live/',
        'Accept-Language': 'tr-TR,tr;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
    }
    
    try:
        with requests.Session() as s:
            # Önce ana sayfayı ziyaret et (cookie al)
            s.get('https://www.fullhdfilmizlesene.live/', headers=headers, timeout=10)
            time.sleep(0.5)

            res = s.get(film_url, headers={**headers, 'Referer': 'https://www.fullhdfilmizlesene.live/yeni-filmler/'}, timeout=12)
            if res.status_code != 200:
                print(f"    [HTTP {res.status_code}] {film_url}")
                return ""
            
            content = res.text

            # DEBUG: İçerikte rapidvid geçiyor mu?
            if 'rapidvid' in content.lower():
                print(f"      [DEBUG] rapidvid bulundu HTML içinde")
            else:
                print(f"      [DEBUG] rapidvid YOK — JS ile yükleniyor olabilir")
                # JS içinde video id arama
                js_match = re.search(r'["\']?(v1x[a-zA-Z0-9]+)["\']?', content)
                if js_match:
                    vid = js_match.group(1)
                    print(f"      [DEBUG-JS] v1x bulundu: {vid}")
                    return f"https://rapidvid.net/vod/{vid}"

            soup = BeautifulSoup(content, 'html.parser')

            # STRATEJİ 1: #plx div içindeki iframe
            plx_div = soup.find('div', id='plx')
            if plx_div:
                iframe = plx_div.find('iframe')
                if iframe:
                    src = iframe.get('data-src') or iframe.get('src') or ''
                    if src:
                        print(f"      [S1-plx] {src}")
                        return "https:" + src if src.startswith("//") else src

            # STRATEJİ 2: data-src içinde v1x... formatı
            data_src_match = re.search(
                r'data-src=["\']([^"\']*rapidvid\.net/(?:vod|v|embed)/v[a-zA-Z0-9]+[^"\']*)["\']',
                content
            )
            if data_src_match:
                src = data_src_match.group(1)
                print(f"      [S2-regex] {src}")
                return "https:" + src if src.startswith("//") else src

            # STRATEJİ 3: Tüm rapidvid linkleri
            all_rapid = re.findall(
                r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/([a-zA-Z0-9]+)',
                content
            )
            if all_rapid:
                for vid_id in all_rapid:
                    if vid_id.startswith('v'):
                        url = f"https://rapidvid.net/vod/{vid_id}"
                        print(f"      [S3-vx] {url}")
                        return url
                url = f"https://rapidvid.net/vod/{all_rapid[0]}"
                print(f"      [S3-fallback] {url}")
                return url

            # STRATEJİ 4: Tüm iframe data-src/src
            for iframe in soup.find_all('iframe'):
                src = iframe.get('data-src') or iframe.get('src') or ''
                if src and ('rapidvid' in src or 'player' in src or 'embed' in src):
                    print(f"      [S4-iframe] {src}")
                    return "https:" + src if src.startswith("//") else src

            # STRATEJİ 5: Script tagları içinde ara
            for script in soup.find_all('script'):
                sc = script.string or ''
                rapid_in_script = re.search(
                    r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/([a-zA-Z0-9]+)',
                    sc
                )
                if rapid_in_script:
                    url = f"https://rapidvid.net/vod/{rapid_in_script.group(1)}"
                    print(f"      [S5-script] {url}")
                    return url

    except Exception as e:
        print(f"    [HATA] {film_url} -> {e}")
    return ""

def sayfa_cek(page_num):
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    
    # Farklı sayfalama formatlarını dene
    url_candidates = [
        base_url if page_num == 1 else f"{base_url}page/{page_num}/",
        base_url if page_num == 1 else f"{base_url}?page={page_num}",
        base_url if page_num == 1 else f"{base_url}?p={page_num}",
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'tr-TR,tr;q=0.8',
    }

    response = None
    used_url = None

    for candidate_url in url_candidates:
        try:
            r = requests.get(candidate_url, headers=headers, timeout=15)
            print(f"  [URL Test] {candidate_url} -> HTTP {r.status_code}")
            if r.status_code == 200:
                response = r
                used_url = candidate_url
                break
        except Exception as e:
            print(f"  [URL Hata] {candidate_url} -> {e}")
            continue

    if not response:
        return "404"

    try:
        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')

        if not films:
            print(f"  [BOŞ SAYFA] {used_url}")
            return "404"

        print(f"  [OK] {len(films)} film bulundu — {used_url}")

        movie_data = []
        for film in films:
            title = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            
            if title and link_tag:
                f_url = link_tag['href'].rstrip('/')
                print(f"    > Çekiliyor: {title.text}")
                
                rapid_link = detay_linki_cek(f_url)
                print(f"      Rapid Link: {rapid_link if rapid_link else 'BULUNAMADI'}")

                movie_data.append({
                    "title": title.text,
                    "link": f_url,
                    "rapid_link": rapid_link,
                    "imdb": film.find('span', class_='imdb').text if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').text if film.find('span', class_='film-yil') else "",
                    "image": film.find('img').get('data-src') or film.find('img').get('src')
                })
                time.sleep(1)

        if movie_data:
            with open(f'data/yeni-filmler-{page_num}.json', 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
        return True

    except Exception as e:
        print(f"  [SAYFA HATA] Sayfa {page_num} -> {e}")
        return False

def main():
    consecutive_404 = 0
    max_consecutive_404 = 3

    for p in range(1, 9999):
        print(f"\n--- Sayfa {p} ---")
        result = sayfa_cek(p)

        if result == "404":
            consecutive_404 += 1
            print(f"  [404 Sayacı: {consecutive_404}/{max_consecutive_404}]")
            if consecutive_404 >= max_consecutive_404:
                print(f"\n✓ Tüm sayfalar çekildi. Son geçerli sayfa: {p - max_consecutive_404}")
                break
        else:
            consecutive_404 = 0

if __name__ == "__main__":
    main()
