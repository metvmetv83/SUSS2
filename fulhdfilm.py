import asyncio
import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

if not os.path.exists('data'):
    os.makedirs('data')

async def rapid_link_cek(page, film_url):
    try:
        await page.goto(film_url, timeout=20000)
        
        # Play butonuna tıkla
        try:
            await page.click('#play-video', timeout=5000)
        except:
            pass
        
        # iframe src'yi bekle
        for _ in range(16):
            await asyncio.sleep(0.5)
            try:
                iframe = page.locator('#plx iframe')
                src = await iframe.get_attribute('src') or await iframe.get_attribute('data-src') or ''
                if src and ('rapidvid' in src or 'imgz' in src):
                    print(f"      [✓] {src}")
                    return src
            except:
                pass
        
        # Page source'dan regex
        content = await page.content()
        match = re.search(r'https?://(?:rapidvid\.net|cdn\.imgz\.me)/(?:vod|player/ifr/vod)/[a-zA-Z0-9]+', content)
        if match:
            print(f"      [✓ source] {match.group(0)}")
            return match.group(0)
            
    except Exception as e:
        print(f"      [HATA] {e}")
    return ""

async def sayfa_cek(page, page_num):
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

                rapid_link = await rapid_link_cek(page, f_url)
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

async def main():
    print("Playwright başlatılıyor...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--mute-audio']
        )
        page = await browser.new_page()
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36'
        })
        print("✓ Hazır\n")

        consecutive_404 = 0
        max_consecutive_404 = 3

        for p_num in range(1, 9999):
            print(f"\n--- Sayfa {p_num} ---")
            result = await sayfa_cek(page, p_num)

            if result == "404":
                consecutive_404 += 1
                print(f"  [404: {consecutive_404}/{max_consecutive_404}]")
                if consecutive_404 >= max_consecutive_404:
                    print(f"\n✓ Bitti. Son geçerli sayfa: {p_num - max_consecutive_404}")
                    break
            else:
                consecutive_404 = 0

        await browser.close()
        print("Playwright kapatıldı.")

if __name__ == "__main__":
    asyncio.run(main())
