import requests
from bs4 import BeautifulSoup
import time
import os
import re

# --- Veri Setini Kaydetmek İçin Klasör ---
# --- Kodumuz "pokemon_data" klasörü varsa içerisine ekleyecek, klasör yoksa "pokemon_data" klasörü oluşturacaktır ----
DATA_DIR = "pokemon_data" 
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    print(f"'{DATA_DIR}' klasörü oluşturuldu.")

# --- Bize Lazım Olmayan Başlıkları Görmezden Geliyoruz ---
TRASH_HEADINGS = [
    re.compile(r"Game data", re.IGNORECASE), re.compile(r"Side Game Locations", re.IGNORECASE),
    re.compile(r"Stats", re.IGNORECASE), re.compile(r"Learnset", re.IGNORECASE),
    re.compile(r"Sprites", re.IGNORECASE), re.compile(r"Appearances", re.IGNORECASE),
    re.compile(r"Gallery", re.IGNORECASE), re.compile(r"References", re.IGNORECASE),
    re.compile(r"See also", re.IGNORECASE)
]
TRASH_TAGS_AND_CLASSES = [
    'table', 'script', 'style', 'aside', 'nav', # Genel çöpler
    '.wikitable', '.navbox', '.gallery', '.side', '.nomobile', '.noprint', # Class'lar
    '.portable-infobox' # Infobox'ı zaten ayrı alıyoruz, ana metinde olmasın
]

#------------------------------------------------------------------------

def scrape_wiki_page(page_url, file_prefix):
    """
    Verilen URL'deki sayfayı inceler ve _infobox.txt / _wiki.txt olarak kaydeder.
    """
    try:
        response = requests.get(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        content_div = soup.find('div', class_='mw-parser-output')

        if not content_div:
            print(f"❌ {file_prefix}: Ana içerik alanı bulunamadı.")
            return

        # Adım 1: Infobox'ı Bul, Kaydet.
        infobox = content_div.find('aside', class_='portable-infobox')
        if infobox:
            infobox_text = infobox.get_text(separator=' ', strip=True)
            infobox_file_path = os.path.join(DATA_DIR, f'{file_prefix}_infobox.txt')
            with open(infobox_file_path, 'w', encoding='utf-8') as file:
                file.write(infobox_text)
            print(f"✅ {file_prefix}_infobox.txt (saf bilgi) kaydedildi.")
            # Infobox'ı SİLMİYORUZ, sadece kopyasını alıyoruz, ana div'i sonra temizleyeceğiz.
        
        # Orijinali bozmamak adına klon bir div üzerinde çalışalım.
        clean_content_div = BeautifulSoup(str(content_div), 'lxml').find('div')

        # Adım 2: Gereksizleri daha detaylı elemek.
        
        # Infobox'ı temiz div'den sil (varsa).
        infobox_to_remove = clean_content_div.find('aside', class_='portable-infobox')
        if infobox_to_remove:
            infobox_to_remove.decompose()

        # ID'ye göre gereksiz avı (İçindekiler tablosu gibi).
        toc = clean_content_div.find('div', id='toc')
        if toc:
            toc.decompose()
            
        # Class'lara ve Etiketlere göre gereksiz avı.
        for selector in TRASH_TAGS_AND_CLASSES:
            elements = clean_content_div.select(selector)
            for element in elements:
                element.decompose()

        # Başlıklara göre gereksiz avı.
        all_headings = clean_content_div.find_all(['h2', 'h3', 'h4'])
        for heading in all_headings:
            # Önce başlığın kendisi var mı diye kontrol ettirelim (bazı durumlarda decompose edilmiş olabilir).
            if not heading.parent: 
                continue 
                
            heading_text = heading.get_text(strip=True).replace("[ ]", "").replace("[edit]", "")
            if any(pattern.search(heading_text) for pattern in TRASH_HEADINGS):
                element = heading.next_sibling
                while element and element.name not in ['h2', 'h3', 'h4']:
                    next_element = element.next_sibling 
                    if hasattr(element, 'decompose'):
                        element.decompose()
                    element = next_element 
                # Başlığın kendisini de sil. 
                heading.decompose()
        
        # Adım 3: Geriye Kalan Metni Kaydet.
        main_text = clean_content_div.get_text(separator=' ', strip=True)
        
        if main_text.strip():
            main_file_path = os.path.join(DATA_DIR, f'{file_prefix}_ability.txt')
            with open(main_file_path, 'w', encoding='utf-8') as file:
                file.write(main_text)
            print(f"✅ {file_prefix}_ability.txt  kaydedildi.")
        else:
            print(f"⚠️ {file_prefix} sayfasında elmas metin bulunamadı.")

    except requests.exceptions.RequestException as e:
        print(f"⚠️ {file_prefix} sayfasına ulaşılamadı veya hata oluştu: {e}")
    except Exception as e: # Diğer olası hatalar için genel yakalama.
         print(f"⚠️ {file_prefix} işlenirken beklenmedik bir hata oluştu: {e}")


# --- Yetenek (Ability) Linklerini Çekecek Olan Fonksiyon ---
def get_all_ability_urls():
    ability_list_url = "https://pokemon.fandom.com/wiki/List_of_Abilities"
    print(f"Yetenek listesi çekiliyor: {ability_list_url}")
    ability_urls = {} 
    
    try:
        response = requests.get(ability_list_url, timeout=10) # Timeout ekliyoruz sitenin sıkıntı yaratmaması için.
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        
        content_div = soup.find('div', class_='mw-parser-output')
        if not content_div:
            print("❌ Ana içerik alanı ('mw-parser-output') bulunamadı.")
            return {}

        # SADECE 'wikitable' class'ına sahip TÜM tabloları bul.
        tables = content_div.find_all('table', class_='wikitable')

        if not tables:
            print("❌ Sayfada 'wikitable' class'ına sahip tablo bulunamadı.")
            return {}

        print(f"İşlenecek {len(tables)} adet 'wikitable' bulundu. (Yetenekler filtrelenecek)")
        
        processed_count = 0
        for table in tables:
            rows = table.find_all('tr')[1:] 
            if not rows: continue
            first_row_cols = rows[0].find_all('td')
            if not first_row_cols: continue
            first_cell_link = first_row_cols[0].find('a')
            if not (first_cell_link and first_cell_link.has_attr('href') and '/wiki/' in first_cell_link['href']):
                continue # Bu bir yetenek tablosu değil ise devam et.
            
            # Eğer bu bir yetenek tablosu ise, şimdi içindekileri işle.
            for row in rows:
                columns = row.find_all('td')
                if columns:
                    name_cell = columns[0].find('a') 
                    if name_cell and name_cell.has_attr('href'):
                        ability_name = name_cell.text.strip()
                        if '(Ability)' in ability_name:
                           ability_name = ability_name.replace(' (Ability)', '').strip()
                           
                        ability_url = "https://pokemon.fandom.com" + name_cell['href']
                        if ability_name not in ability_urls:
                            ability_urls[ability_name] = ability_url
                            processed_count += 1 # Sadece yeni eklenenleri say.
                            
        print(f"✅ Toplam {processed_count} adet eşsiz ve YENİ Yetenek sayfası bulundu.")
        return ability_urls
    except requests.exceptions.RequestException as e: # Hata Türlerini Ekleyelim.
        print(f"Yetenek listesi sayfasına ulaşılamadı: {e}")
        return {}
    except Exception as e:
         print(f"Yetenek listesi işlenirken beklenmedik bir hata oluştu: {e}")
         return {}


# --------------------- ANA PROGRAM AKIŞI -----------------------------
def main():
    ability_list = get_all_ability_urls()
    
    if ability_list:
        print("\n--- GÖREV: Sadece Yetenek (Ability) Verileri Çekiliyor ---")
        print(f"Mevcut '{DATA_DIR}' klasörüne ekleme yapılacak.")
        count = 0
        total = len(ability_list)
        for ability_name, ability_url in ability_list.items():
            count += 1
            print(f"\n--- Yetenek {count}/{total}: {ability_name} ---")
            safe_file_prefix = ability_name.replace('/', '_').replace(':', '_')
            scrape_wiki_page(ability_url, safe_file_prefix)
            time.sleep(1) 
    else:
        print("Çekilecek yetenek bulunamadı.")

    print("\n------------------------------------------")
    print("Tüm yetenek veri çekme işlemleri tamamlandı!")

if __name__ == "__main__":
    main()