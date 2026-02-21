import requests
from bs4 import BeautifulSoup

url = "https://www.fullhdfilmizlesene.live/film/sev-beni-sev-beni-love-me-love-me/"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'tr-TR,tr;q=0.8',
    'Referer': 'https://www.fullhdfilmizlesene.live/',
}

with requests.Session() as s:
    s.get('https://www.fullhdfilmizlesene.live/', headers=headers, timeout=10)
    res = s.get(url, headers=headers, timeout=12)
    
    print("HTTP:", res.status_code)
    print("Sayfa boyutu:", len(res.text), "karakter")
    
    # plx div var mı?
    soup = BeautifulSoup(res.text, 'html.parser')
    plx = soup.find('div', id='plx')
    print("plx div:", plx)
    
    # ajax-data var mı?
    ajax = soup.find_all('div', class_='ajax-data')
    print("ajax-data sayısı:", len(ajax))
    
    # rapidvid geçiyor mu?
    print("rapidvid içeriyor mu:", 'rapidvid' in res.text)
    print("plx içeriyor mu:", 'plx' in res.text)
    
    # İlk 3000 karakteri göster
    print("\n--- HTML BAŞLANGIÇ ---")
    print(res.text[:3000])
    print("\n--- HTML SON ---")
    print(res.text[-1000:])
