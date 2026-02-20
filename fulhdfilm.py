import json
import os
import time
from playwright.sync_api import sync_playwright

# Ayarlar
DATA_FOLDER = 'data'

def video_linki_cek_pro(browser_context, film_url):
    """Gerçek bir tarayıcı kullanarak iframe linkini yakalar."""
    page = browser_context.new_page()
    # Bot olduğumuzu gizlemek için User-Agent
    page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    })
    
    try:
        # Sayfaya git ve yüklenmesini bekle
        page.goto(film_url, wait_until="domcontentloaded", timeout=30000)
        
        # iframe'in gelmesi için kısa bir süre bekle (JavaScript render süresi)
        page.wait_for_selector("#plx iframe", timeout=5000)
        
        # Elementi bul ve linki al
        iframe = page.query_selector("#plx iframe")
        if iframe:
            # Önce data-src'ye bak, yoksa src'yi al
            v_link = iframe.get_attribute("data-src") or iframe.get_attribute("src")
            page.close()
            return v_link
    except Exception as e:
        print(f"      [!] Hata oluştu: {film_url} (Zaman aşımı veya eleman bulunamadı)")
    
    page.close()
    return ""

def main():
    if not os.path.exists(DATA_FOLDER):
        print(f"Hata: {DATA_FOLDER} klasörü bulunamadı!")
        return

    with sync_playwright() as p:
        # Tarayıcıyı başlat (headless=True yaparak arka planda çalıştırıyoruz)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()

        files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.json')]
        files.sort(reverse=True) # En son dosyalardan geriye doğru git

        for file_name in files:
            file_path = os.path.join(DATA_FOLDER, file_name)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            guncellendi = False
            print(f"\n--- Dosya İşleniyor: {file_name} ---")

            for film in data:
                # Sadece linki olmayanları güncelle
                if not film.get('rapid_link') or film['rapid_link'] == "":
                    print(f"   > Link Çekiliyor: {film['title']}")
                    
                    v_link = video_linki_cek_pro(context, film['link'])
                    
                    if v_link:
                        film['rapid_link'] = v_link
                        guncellendi = True
                        print(f"     [OK] Link: {v_link}")
                    else:
                        print(f"     [X] Link bulunamadı.")
                    
                    # Siteyi korumak ve banlanmamak için kısa mola
                    time.sleep(1)

            if guncellendi:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                print(f"--- {file_name} kaydedildi! ---")

        browser.close()

if __name__ == "__main__":
    main()
