import cloudscraper
from bs4 import BeautifulSoup
import json
import os
import time
import re

# Klasör kontrolü
if not os.path.exists('data'):
    os.makedirs('data')

# Cloudflare engellerini aşmak için scraper oluştur
scraper = cloudscraper.create_scraper()

def detay_linki_cek(film_url):
    """
    Cloudflare korumasını aşarak rapidvid linkini yakalar.
    """
    try:
        # Siteyi gerçek bir kullanıcı gibi ziyaret et
        res = scraper.get(film_url, timeout=15)
        if res.status_code == 200:
            content = res.text
            
            # --- STRATEJİ 1: Regex ile rapidvid.net Taraması ---
            # En garantici yöntem: Link veya ID metin içinde geçiyor mu?
            rapid_match = re.search(r'https?://(?:www\.)?rapidvid\.net/(?:vod|v|embed)/([a-zA-Z0-9]+)', content)
            if rapid_match:
                return rapid_match.group(0).replace('\\', '')

            # --- STRATEJİ 2: BeautifulSoup ile Iframe Arama ---
            soup = BeautifulSoup(content, 'html.parser')
            for iframe in soup.find_all('iframe'):
                src = iframe.get('data-src') or iframe.get('src') or ""
                if "rapidvid" in src:
                    return "https:" + src if src.startswith("//") else src

            # --- STRATEJİ 3: JSON/Variable Taraması ---
            # Site bazen linki bir değişkene atar: videoSource = "..."
            json_match = re.search(r'["\']?link["\']?\s*[:=]\s*["\'](https?://rapidvid\.net/[^"\']+)["\']', content)
            if json_match:
                return json_match.group(1).replace('\\', '')

    except Exception as e:
        print(f"      ! Detay çekme hatası: {e}")
    return ""

def sayfa_cek(page_num):
    base_url = "https://www.fullhdfilmizlesene.live/yeni-filmler/"
    url = base_url if page_num == 1 else f"{base_url}page/{page_num}/"

    try:
        response = scraper.get(url, timeout=20)
        if response.status_code != 200:
            print(f"Hata: Sayfa {page_num} (Kod: {response.status_code})")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')
        films = soup.find_all('li', class_='film')
        
        movie_data = []
        for film in films:
            title_tag = film.find('span', class_='film-title')
            link_tag = film.find('a', class_='tt')
            
            if title_tag and link_tag:
                f_url = link_tag['href'].rstrip('/')
                t_text = title_tag.get_text(strip=True)
                
                print(f"    > Analiz ediliyor: {t_text}")
                rapid_link = detay_linki_cek(f_url)

                movie_data.append({
                    "title": t_text,
                    "link": f_url,
                    "rapid_link": rapid_link,
                    "imdb": film.find('span', class_='imdb').get_text(strip=True) if film.find('span', class_='imdb') else "0",
                    "year": film.find('span', class_='film-yil').get_text(strip=True) if film.find('span', class_='film-yil') else "",
                    "image": (film.find('img').get('data-src') or film.find('img').get('src')) if film.find('img') else ""
                })
                time.sleep(1.5) # Cloudflare banlanmamak için hızı düşürdük

        if movie_data:
            file_name = f'data/yeni-filmler-{page_num}.json'
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(movie_data, f, ensure_ascii=False, indent=4)
            print(f"--- Sayfa {page_num} Tamamlandı ---")
            return True
    except Exception as e:
        print(f"Hata oluştu: {e}")
        return False

def main():
    # 1113 sayfaya kadar tara
    for p in range(1, 1114):
        # NOT: Mevcut dosyayı atlamıyoruz (Çünkü linkleri bulamadık, tekrar denememiz lazım)
        # Eğer hızlanmak istersen bu if bloğunu açabilirsin
        # if os.path.exists(f'data/yeni-filmler-{p}.json'): continue

        print(f"\n--- İşleniyor: Sayfa {p} ---")
        sayfa_cek(p)

if __name__ == "__main__":
    main()
