import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re

if not os.path.exists('data'):
    os.makedirs('data')

# ============================================================
# STRATEJI A: Selenium (JS render eder, en güvenilir)
# pip install selenium webdriver-manager
# ============================================================
def selenium_kur():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36')

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        return driver
    except Exception as e:
        print(f"[Selenium HATA] {e}")
        return None

def selenium_rapid_cek(driver, film_url):
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        driver.get(film_url)

        # #plx div içindeki iframe yüklenene kadar bekle (max 10sn)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#plx iframe"))
            )
        except:
            pass

        time.sleep(2)  # JS'nin iframe src'yi set etmesi için ekstra bekle

        page_source = driver.page_source

        # Önce iframe src'yi doğrudan bul
        soup = BeautifulSoup(page_source, 'html.parser')
        plx = soup.find('div', id='plx')
        if plx:
            iframe = plx.find('iframe')
            if iframe:
                src = iframe.get('src') or iframe.get('data-src') or ''
                if src and 'rapidvid' in src:
                    return "https:" + src if src.startswith("//") else src

        # Regex ile tüm sayfada ara
        match = re.search(
            r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/([a-zA-Z0-9]+)',
            page_source
        )
        if match:
            return match.group(0)

        # Selenium ile iframe'i direkt yakala
        try:
            iframes = driver.find_elements(By.TAG_NAME, 'iframe')
            for iframe_el in iframes:
                src = iframe_el.get_attribute('src') or iframe_el.get_attribute('data-src') or ''
                if 'rapidvid' in src:
                    return "https:" + src if src.startswith("//") else src
        except:
            pass

    except Exception as e:
        print(f"    [Selenium HATA] {film_url} -> {e}")
    return ""

# ============================================================
# STRATEJI B: Ajax/API isteği tahmini (Selenium yoksa fallback)
# ============================================================
def ajax_rapid_cek(film_url):
    """
    Bazı siteler video ID'sini ayrı bir endpoint'ten çeker.
    Film URL'sinden slug çıkarıp tahmin edilen API'lere istek atar.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': film_url,
        'Accept': 'application/json, text/javascript, */*; q=0.01',
    }

    # Film slug'ını URL'den çıkar
    slug = film_url.rstrip('/').split('/')[-1]
    base = "https://www.fullhdfilmizlesene.live"

    # Tahmin edilen Ajax endpoint'leri
    ajax_urls = [
        f"{base}/wp-admin/admin-ajax.php",
        f"{base}/api/video/{slug}",
        f"{base}/embed/{slug}",
        f"{base}/?p={slug}&action=get_video",
    ]

    # admin-ajax.php için POST dene
    try:
        with requests.Session() as s:
            s.get(film_url, headers={'User-Agent': headers['User-Agent']}, timeout=10)

            # action tahminleri
            for action in ['get_player', 'get_video', 'load_player', 'get_embed']:
                try:
                    r = s.post(
                        f"{base}/wp-admin/admin-ajax.php",
                        data={'action': action, 'slug': slug},
                        headers=headers,
                        timeout=8
                    )
                    if r.status_code == 200 and 'rapidvid' in r.text:
                        match = re.search(
                            r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/([a-zA-Z0-9]+)',
                            r.text
                        )
                        if match:
                            print(f"      [AJAX] {action} -> {match.group(0)}")
                            return match.group(0)
                except:
                    continue
    except:
        pass
    return ""

# ============================================================
# ANA FONKSİYON
# ============================================================
USE_SELENIUM = True  # Selenium yoksa False yap

driver = None
if USE_SELENIUM:
    print("Selenium başlatılıyor...")
    driver = selenium_kur()
    if driver:
        print("✓ Selenium hazır (headless Chrome)")
    else:
        print("✗ Selenium başlatılamadı, Ajax moduna geçiliyor")
        USE_SELENIUM = False

def detay_linki_cek(film_url):
    if USE_SELENIUM and driver:
        link = selenium_rapid_cek(driver, film_url)
        if link:
            return link
    # Selenium bulamazsa Ajax dene
    return ajax_rapid_cek(film_url)

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

                time.sleep(1.5 if USE_SELENIUM else 1)

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

    try:
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
    finally:
        if driver:
            driver.quit()
            print("Selenium kapatıldı.")

if __name__ == "__main__":
    main()
