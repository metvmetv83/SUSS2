import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        page = await browser.new_page()
        
        await page.goto(
            "https://www.fullhdfilmizlesene.live/film/sev-beni-sev-beni-love-me-love-me/",
            timeout=20000,
            wait_until='domcontentloaded'
        )
        await asyncio.sleep(2)
        
        # udc fonksiyonunu ve ilgili tüm fonksiyonları çek
        result = await page.evaluate("""() => {
            let out = {};
            
            // udc fonksiyonu
            if (typeof udc !== 'undefined') out.udc = udc.toString();
            
            // data-id decode et
            let el = document.querySelector('.ajax-data[data-no="1"]');
            if (el) {
                out.data_id = el.dataset.id;
                out.decoded_html = el.innerHTML;
            }
            
            // plx içeriği
            let plx = document.getElementById('plx');
            if (plx) out.plx_html = plx.innerHTML;
            
            // Tüm global fonksiyon isimleri
            out.globals = Object.getOwnPropertyNames(window)
                .filter(k => typeof window[k] === 'function')
                .slice(0, 50);
            
            return out;
        }""")
        
        print("=== UDC FONKSİYONU ===")
        print(result.get('udc', 'BULUNAMADI'))
        print("\n=== PLX HTML ===")
        print(result.get('plx_html', 'BOŞ'))
        print("\n=== DECODED HTML ===")
        print(result.get('decoded_html', 'BOŞ'))
        print("\n=== GLOBAL FONKSİYONLAR ===")
        print(result.get('globals', []))
        
        await browser.close()

asyncio.run(main())
