import requests
from bs4 import BeautifulSoup
import json
import os
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

if not os.path.exists('data'):
    os.makedirs('data')

def selenium_kur():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--mute-audio')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36')
    # Gereksiz kaynakları engelle (hız için)
    options.add_argument('--blink-settings=imagesEnabled=false')
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    driver.set_page_load_timeout(20)
    return driver

def rapid_link_cek(driver, film_url):
    try:
        driver.get(film_url)
        
        # Play butonunu bekle ve tıkla
        wait = WebDriverWait(driver, 10)
        play_btn = wait.until(
            EC.element_to_be_clickable((By.ID, 'play-video'))
        )
        play_btn.click()
        
        # iframe src'nin dolmasını bekle (max 8 sn)
        for _ in range(16):
            time.sleep(0.5)
            try:
                iframe = driver.find_element(By.CSS_SELECTOR, '#plx iframe')
                src = iframe.get_attribute('src') or iframe.get_attribute('data-src') or ''
                if 'rapidvid' in src or 'imgz' in src:
                    print(f"      [✓ selenium] {src}")
                    return src
            except:
                pass
        
        # Bulunamazsa page source'dan regex ile ara
        source = driver.page_source
        match = re.search(r'https?://(?:rapidvid\.net|cdn\.imgz\.me)/(?:vod|player/ifr/vod)/[a-zA-Z0-9]+', source)
        if match:
            print(f"      [✓ source] {match.group(0)}")
            return match.group(0)
            
        # Son çare: tüm iframe src'leri tara
        iframes = driver.find_elements(By.TAG_NAME, 'iframe')
        for ifr in iframes:
            src = ifr.get_attribute('src') or ''
            if src and ('rapidvid' in src or 'imgz' in src or 'vod' in src):
                print(f"      [✓ iframe] {src}")
                return src
                
    except Exception as e:
        print(f"      [HATA] {e}")
    return ""

def sayfa_cek(driver, page_num):
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 404:
            return "404"
        if response.status_code != 200:
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

                rapid_link = rapid_link_cek(driver, f_url)
                print(f"      {'✓ ' + rapid_link if rapid_link else '✗ BULUNAMADI'}")

                movie_data.append({
                    "title": title.text,
                    "link": f_url,
                    "rapid_link": rapid_link,
                    "imdb": film.find('span', class_='imdb').text if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').text if film.find('span', class_='film-yil') else "",
                    "image": film.find('img').get('data-src') or film.find('img').get('src')
                })

        if movie_data:
            with open(f'data/yeni-filmler-{page_num}.json', 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
        return True

    except Exception as e:
        print(f"  [HATA] {e}")
        return False

def main():
    print("Selenium başlatılıyor...")
    driver = selenium_kur()
    print("✓ Hazır\n")

    consecutive_404 = 0
    max_consecutive_404 = 3

    try:
        for p in range(1, 9999):
            print(f"\n--- Sayfa {p} ---")
            result = sayfa_cek(driver, p)

            if result == "404":
                consecutive_404 += 1
                print(f"  [404: {consecutive_404}/{max_consecutive_404}]")
                if consecutive_404 >= max_consecutive_404:
                    print(f"\n✓ Bitti. Son geçerli sayfa: {p - max_consecutive_404}")
                    break
            else:
                consecutive_404 = 0
    finally:
        driver.quit()
        print("Selenium kapatıldı.")

if __name__ == "__main__":
    main()
