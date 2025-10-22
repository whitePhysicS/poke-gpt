import requests
from bs4 import BeautifulSoup
import time
import os
import re

# --- Veri Setini Kaydetmek İçin Klasör ---
DATA_DIR = "pokemon_data" 
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# --- BEYAZ LİSTE (ELMAS BAŞLIKLAR) ---
# Bu başlıkların altındaki paragrafları istiyoruz
ELMAS_BASLIKLAR = [
    re.compile(r"Biology", re.IGNORECASE),
    re.compile(r"Evolution", re.IGNORECASE),
    re.compile(r"Pokédex entries", re.IGNORECASE),
    re.compile(r"Origin", re.IGNORECASE),
    re.compile(r"Etymology", re.IGNORECASE),
    re.compile(r"Trivia", re.IGNORECASE),
    re.compile(r"Effect", re.IGNORECASE), # YETENEKLER için bu başlığı ekledik
    re.compile(r"Description", re.IGNORECASE) # YETENEKLER için bu başlığı ekledik
]

# --- YENİ FONKSİYON: Genel Amaçlı Sayfa Kazıyıcı ---
def scrape_wiki_page(page_url, file_prefix):
    """
    Verilen URL'deki sayfayı kazar ve _infobox.txt / _wiki.txt olarak kaydeder.
    """
    try:
        response = requests.get(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        content_div = soup.find('div', class_='mw-parser-output')

        if not content_div:
            print(f"❌ {file_prefix}: Ana içerik alanı bulunamadı.")
            return

        # 1. Görev: Infobox'ı Bul, Kaydet ve Yok Et
        infobox = content_div.find('aside', class_='portable-infobox')
        if infobox:
            infobox_text = infobox.get_text(separator=' ', strip=True)
            infobox_file_path = os.path.join(DATA_DIR, f'{file_prefix}_infobox.txt')
            with open(infobox_file_path, 'w', encoding='utf-8') as file:
                file.write(infobox_text)
            print(f"✅ {file_prefix}_infobox.txt (saf bilgi) kaydedildi.")
            infobox.decompose()
        
        # 2. Görev: "Elmas" Başlıkları ve İçeriklerini Çek
        wiki_text_parcalari = []
        all_headings = content_div.find_all(['h2', 'h3', 'h4'])
        
        for heading in all_headings:
            heading_text = heading.get_text(strip=True).replace("[ ]", "").replace("[edit]", "")
            if any(pattern.search(heading_text) for pattern in ELMAS_BASLIKLAR):
                wiki_text_parcalari.append(f"\n\n--- {heading_text} ---\n")
                element = heading.next_sibling
                while element and element.name not in ['h2', 'h3', 'h4']:
                    if element.name == 'p':
                        wiki_text_parcalari.append(element.get_text(separator=' ', strip=True))
                    element = element.next_sibling
        
        main_text = " ".join(wiki_text_parcalari)
        
        if main_text.strip():
            main_file_path = os.path.join(DATA_DIR, f'{file_prefix}_wiki.txt')
            with open(main_file_path, 'w', encoding='utf-8') as file:
                file.write(main_text)
            print(f"✅ {file_prefix}_wiki.txt (SADECE ELMAS) kaydedildi.")
        else:
            print(f"⚠️ {file_prefix} sayfasında elmas başlık bulunamadı.")

    except requests.exceptions.RequestException:
        print(f"⚠️ {file_prefix} sayfası bulunamadı veya bir hata oluştu. Atlanıyor.")

# --- Pokemon İsimlerini Çeken Fonksiyon (DEĞİŞİKLİK YOK) ---
def get_all_pokemon_names():
    # ... (Bu fonksiyonun içi bir önceki kodla aynı, o yüzden kısalttım) ...
    pokedex_url = "https://pokemon.fandom.com/wiki/List_of_Pokémon"
    print(f"Pokemon listesi çekiliyor: {pokedex_url}")
    pokemon_names = [] # Bu listeyi doldurduğunu varsayalım
    # ... (Tüm o 'h2', 'table', 'tr' bulma mantığı burada) ...
    # Kodu tam olarak bir öncekinden kopyalayabilirsin
    # Örnek olması için elle birkaçı ekliyorum, sen tam fonksiyonu kullan:
    try:
        response = requests.get(pokedex_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        headers = soup.find_all('h2')
        for header in headers:
            if "Generation" in header.text:
                table = header.find_next_sibling('table')
                if table:
                    rows = table.find_all('tr')[1:]
                    for row in rows:
                        columns = row.find_all('td')
                        if len(columns) > 2:
                            name_cell = columns[2].find('a')
                            if name_cell:
                                pokemon_names.append(name_cell.text.strip())
        unique_names = sorted(list(set(pokemon_names)))
        print(f"✅ Toplam {len(unique_names)} adet eşsiz Pokemon ismi bulundu.")
        return unique_names
    except Exception as e:
        print(f"Hata: {e}")
        return []

# --- YENİ FONKSİYON: Yetenek (Ability) Linklerini Çeken Fonksiyon ---
def get_all_ability_urls():
    ability_list_url = "https://pokemon.fandom.com/wiki/List_of_Abilities"
    print(f"Yetenek listesi çekiliyor: {ability_list_url}")
    ability_urls = {} # Tekrarları önlemek için sözlük (dictionary) kullanalım
    
    try:
        response = requests.get(ability_list_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Sayfadaki tüm yetenek tablolarını bul
        tables = soup.find_all('table', class_='sortable')
        
        for table in tables:
            rows = table.find_all('tr')[1:] # Başlığı atla
            for row in rows:
                columns = row.find_all('td')
                if columns:
                    name_cell = columns[0].find('a')
                    if name_cell and name_cell.has_attr('href'):
                        ability_name = name_cell.text.strip()
                        ability_url = "https://pokemon.fandom.com" + name_cell['href']
                        if ability_name not in ability_urls:
                            ability_urls[ability_name] = ability_url
                            
        print(f"✅ Toplam {len(ability_urls)} adet eşsiz Yetenek sayfası bulundu.")
        return ability_urls
    except Exception as e:
        print(f"Yetenek listesi çekilirken hata: {e}")
        return {}


# --- ANA PROGRAM AKIŞI (ARTIK ÇOK AMAÇLI) ---

# 1. Görev: Pokemon'ları Çek
pokemon_listesi = get_all_pokemon_names()
# pokemon_listesi = pokemon_listesi[:10] # Test için kısalt

if pokemon_listesi:
    print("\n--- 1. GÖREV: Pokemon Verileri Çekiliyor ---")
    for pokemon_adi in pokemon_listesi:
        formatted_name = pokemon_adi.replace(' ', '_')
        url = f"https://pokemon.fandom.com/wiki/{formatted_name}"
        print(f"--- {pokemon_adi} ---")
        scrape_wiki_page(url, pokemon_adi)
        time.sleep(1)

# 2. Görev: Yetenekleri Çek
ability_list = get_all_ability_urls()
# ability_list = dict(list(ability_list.items())[:10]) # Test için kısalt

if ability_list:
    print("\n--- 2. GÖREV: Yetenek (Ability) Verileri Çekiliyor ---")
    for ability_name, ability_url in ability_list.items():
        print(f"--- {ability_name} ---")
        scrape_wiki_page(ability_url, ability_name)
        time.sleep(1)

print("\n------------------------------------------")
print("Tüm veri çekme işlemleri tamamlandı!")