import os
import torch
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma

DATA_PATH = "pokemon_data"
DB_PATH = "chroma_db"

# --- Veriyi Yükleme ve Bölme ---
print("Veriler yükleniyor ve bölünüyor...")
loader = DirectoryLoader(
    DATA_PATH,
    glob="*.txt",
    loader_cls=TextLoader,
    loader_kwargs={"encoding": "utf-8"}
)
documents = loader.load()
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
chunks = text_splitter.split_documents(documents)
print(f"Toplam {len(chunks)} adet metin parçası (chunk) oluşturuldu.")

# --- YENİ VE DAHA AKILLI EMBEDDING MODELİ ---
print("Yeni ve daha akıllı embedding modeli başlatılıyor...")
# all-MiniLM-L6-v2 YERİNE all-mpnet-base-v2 KULLANIYORUZ
model_name = "sentence-transformers/all-mpnet-base-v2"

device= "cuda" if torch.cuda.is_available() else "cpu"
print(f"Model '{device}' üzerinde çalıştırılacak.")

embeddings = HuggingFaceEmbeddings(
    model_name=model_name,
    model_kwargs={'device': device}    
                                   )
print("Model yüklendi. (İlk çalıştırmada indirme yapabilir)")

# --- Veritabanını Tek Seferde Oluşturma ---
print("Yeni vektör veritabanı oluşturuluyor. Bu işlem BİRAZ DAHA UZUN sürebilir...")
db = Chroma.from_documents(
    chunks,
    embeddings,
    persist_directory=DB_PATH
)

print("------------------------------------------")
print(f"✅ YENİ vektör veritabanı başarıyla oluşturuldu ve '{DB_PATH}' klasörüne kaydedildi.")