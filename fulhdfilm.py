import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
import base64

if not os.path.exists('data'):
    os.makedirs('data')

def decode_data_id(data_id: str) -> str:
    """
    Site data-id değerini özel bir XOR/base64 karışımıyla şifreliyor.
    Önce base64 decode, sonra içinde rapidvid linki arayacağız.
    """
    try:
        # Standart base64 decode
        decoded = base64.b64decode(data_id + '==').decode('utf-8', errors='ignore')
        return decoded
    except:
        pass
    try:
        # URL-safe base64
        decoded = base64.urlsafe_b64decode(data_id + '==').decode('utf-8', errors='ignore')
        return decoded
    except:
        pass
    return ""

def extract_from_data_ids(soup) -> str:
    """Tüm ajax-data div'lerinin data-id'lerini decode edip rapidvid linki arar."""
    for div in soup.find_all('div', class_='ajax-data'):
        data_id = div.get('data-id', '')
        if not data_id:
            continue
        
        decoded = decode_data_id(data_id)
        
        # Decode içinde rapidvid ara
        match = re.search(
            r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/([a-zA-Z0-9]+)',
            decoded
        )
        if match:
            print(f"      [data-id decoded] {match.group(0)}")
            return match.group(0)
        
        # v1x formatı ara
        v1x = re.search(r'(v1x[a-zA-Z0-9]+)', decoded)
        if v1x:
            url = f"https://rapidvid.net/vod/{v1x.group(1)}"
            print(f"      [data-id v1x] {url}")
            return url

        # DEBUG: decode sonucunu yazdır
        if len(decoded) > 5:
            print(f"      [data-id raw] {decoded[:80]}")

    return ""

def detay_linki_cek(film_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Referer': 'https://www.fullhdfilmizlesene.live/',
        'Accept-Language': 'tr-TR,tr;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    
    try:
        with requests.Session() as s:
            s.get('https://www.fullhdfilmizlesene.live/', headers=headers, timeout=10)
            time.sleep(0.3)

            res = s.get(film_url, headers=headers, timeout=12)
            if res.status_code != 200:
                print(f"    [HTTP {res.status_code}] {film_url}")
                return ""
            
            content = res.text
            soup = BeautifulSoup(content, 'html.parser')

            # STRATEJİ 1: #plx iframe data-src (JS doldurmadan önce boş olabilir)
            plx_div = soup.find('div', id='plx')
            if plx_div:
                iframe = plx_div.find('iframe')
                if iframe:
                    src = iframe.get('data-src') or iframe.get('src') or ''
                    if src and 'rapidvid' in src:
                        print(f"      [S1-plx] {src}")
                        return "https:" + src if src.startswith("//") else src

            # STRATEJİ 2: ajax-data data-id decode
            link = extract_from_data_ids(soup)
            if link:
                return link

            # STRATEJİ 3: Regex ile tüm sayfada rapidvid ara
            data_src_match = re.search(
                r'data-src=["\']([^"\']*rapidvid\.net/(?:vod|v|embed)/[a-zA-Z0-9]+[^"\']*)["\']',
                content
            )
            if data_src_match:
                src = data_src_match.group(1)
                print(f"      [S3-regex] {src}")
                return "https:" + src if src.startswith("//") else src

            # STRATEJİ 4: Tüm rapidvid linkleri
            all_rapid = re.findall(
                r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/([a-zA-Z0-9]+)',
                content
            )
            if all_rapid:
                for vid_id in all_rapid:
                    if vid_id.startswith('v'):
                        url = f"https://rapidvid.net/vod/{vid_id}"
                        print(f"      [S4-vx] {url}")
                        return url
                url = f"https://rapidvid.net/vod/{all_rapid[0]}"
                print(f"      [S4-fallback] {url}")
                return url

            # STRATEJİ 5: Script tagları içinde
            for script in soup.find_all('script'):
                sc = script.string or ''
                m = re.search(r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/([a-zA-Z0-9]+)', sc)
                if m:
                    print(f"      [S5-script] {m.group(0)}")
                    return m.group(0)

            print(f"      [DEBUG] Hiçbir strateji çalışmadı — data-id sayısı: {len(soup.find_all('div', class_='ajax-data'))}")

    except Exception as e:
        print(f"    [HATA] {film_url} -> {e}")
    return ""

def sayfa_cek(page_num):
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 404:
            return "404"
        if response.status_code != 200:
            print(f"  [HTTP {response.status_code}] Sayfa {page_num}")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')

        if not films:
            return "404"

        print(f"  [OK] {len(films)} film")

        movie_data = []
        for film in films:
            title = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')

            if title and link_tag:
                f_url = link_tag['href'].rstrip('/')
                print(f"    > {title.text}")

                rapid_link = detay_linki_cek(f_url)
                print(f"      {'✓ ' + rapid_link if rapid_link else '✗ BULUNAMADI'}")

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
        print(f"  [HATA] Sayfa {page_num} -> {e}")
        return False

def main():
    consecutive_404 = 0
    max_consecutive_404 = 3

    for p in range(1, 9999):
        print(f"\n--- Sayfa {p} ---")
        result = sayfa_cek(p)

        if result == "404":
            consecutive_404 += 1
            print(f"  [404: {consecutive_404}/{max_consecutive_404}]")
            if consecutive_404 >= max_consecutive_404:
                print(f"\n✓ Bitti. Son geçerli sayfa: {p - max_consecutive_404}")
                break
        else:
            consecutive_404 = 0

if __name__ == "__main__":
    main()
