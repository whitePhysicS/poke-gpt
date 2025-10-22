import streamlit as st
import os
import string
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def get_openai_api_key() -> str:
    key = None
    try:
        key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass
    key = key or os.getenv("OPENAI_API_KEY")

    if not key:
        st.error(
            "OPENAI_API_KEY bulunamadı. Lütfen lokal kullanımda .env dosyasına "
            "veya Streamlit Cloud'da Secrets'e ekleyin."
        )
        st.stop()
    return key

OPENAI_API_KEY = get_openai_api_key()
llm = ChatOpenAI(
    model="gpt-4o-mini",           # Kullanılan model.
    temperature=0.2,
    openai_api_key=OPENAI_API_KEY  # .env dosyasından gelecek olan api key.
)


# ---------- Modelleri yükleme ve Cacheleme ----------
@st.cache_resource
def load_retriever():
    print("Embedding modeli ve vektör veritabanı yükleniyor...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
    db = Chroma(persist_directory="chroma_db", embedding_function=embeddings)
    
    retriever = db.as_retriever(search_type="similarity", search_kwargs={"k": 5})
    print("Yükleme tamamlandı.")
    return retriever


@st.cache_resource
def load_llm(temperature=0.2, streaming=True):    #LLM modelimizi yükleyelim.
    print(f"OpenAI LLM (gpt-4o-mini) yükleniyor (temp={temperature}, stream={streaming})...")
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=temperature, streaming=streaming)
    print("LLM yüklendi.")
    return llm

# --- Promptlarımızı girelim ki sınırlarını bilsin ---
question_classifier_prompt = ChatPromptTemplate.from_template(
    """Your task is to classify the user's question into one of two categories: 'pokemon' or 'general'.
Focus ONLY on the main subject of the question.

- If the question is about ANYTHING related to the Pokémon universe (e.g., specific Pokémon, abilities, items, characters, games, anime, types, evolution, regions, mechanics), classify it as 'pokemon'.
- If the question is about ANYTHING ELSE (e.g., current events, math, science, history, coding, personal questions, greetings, requests unrelated to Pokémon), classify it as 'general'.

**CRITICAL:** Respond with **only** the single word 'pokemon' or 'general'. No other words, no explanation.

Examples:
Question: What type is Pikachu? -> Response: pokemon
Question: Tell me about the Static ability. -> Response: pokemon
Question: Who is Ash Ketchum? -> Response: pokemon
Question: What year is it? -> Response: general
Question: Write a python function. -> Response: general
Question: Hi, how are you? -> Response: general
Question: What is the capital of Turkey? -> Response: general

User Question: {question}
Response:"""
)
# Sınıflandırıcı hala stream yapmayacak, sadece tek kelime döndürecek.
classifier_llm = load_llm(temperature=0.0, streaming=False)
question_classifier_chain = (
    question_classifier_prompt
    | classifier_llm
    | StrOutputParser()
)
rag_template = """You are 'PokéGPT', a Pokémon expert. Answer the user's question based ONLY on the provided 'Context'.
If the 'Context' does NOT contain the answer, respond exactly with: "Bu bilgi elimdeki Pokémon dokümanlarında mevcut değil." (if language is Türkçe) or "I do not have this information in my Pokémon documents." (if language is English).
Answer ONLY in the language specified: {language}

Context: {context}

Question: {question}
Helpful Answer:"""
rag_prompt = ChatPromptTemplate.from_template(rag_template)
general_template = """Answer the following question using your general knowledge, like a helpful assistant.
Answer ONLY in the language specified: {language}

Question: {question}
Helpful Answer:"""
general_prompt = ChatPromptTemplate.from_template(general_template)


# ---------- Streamlit Arayüz Kısmı ----------
st.set_page_config(page_title="PokéGPT", page_icon="🔴")
st.title("PokéGPT 🔴")
st.subheader("Your AI-Powered Pokémon Assistant")

INITIAL_MESSAGE = {"role": "assistant", "content": "Hi! I'm PokéGPT. Select your language from the sidebar and ask me anything!", "sources": []}


# ---------- Dil Ayarı ve Clear Chat Tuşu  ----------

with st.sidebar:
    st.header("⚙️ Settings")
    selected_language = st.radio("Response Language", ("English", "Türkçe"))
    
    st.divider()
    
    if st.button("Clear Chat History", key="clear_chat"):
        st.session_state.messages = [INITIAL_MESSAGE]
        st.rerun()
        
    # ---------- Bilgi Bölümü ----------
    st.divider()
    with st.expander("ℹ️ About PokéGPT"):
        st.markdown("""
        **What is this?**
        PokéGPT is an AI chatbot specialized in the Pokémon universe. It uses a technique called **RAG (Retrieval-Augmented Generation)**.
        
        **How does it work?**
        1. When you ask a Pokémon-related question, the bot first **retrieves** relevant information from its internal Pokémon database (built from [Fandom Pokémon Wiki](https://pokemon.fandom.com/)).
        2. Then, it uses a powerful language model (**GPT-4o-mini**) to **generate** an answer based *only* on the retrieved information.
        3. For non-Pokémon questions, it uses its general knowledge.
        
        **Why RAG?**
        This ensures answers about Pokémon are accurate and based on the wiki data, preventing the AI from making things up (hallucinating).
        """)

# Gerekli bileşenleri yükle.
retriever = load_retriever()
rag_llm = load_llm(temperature=0.2, streaming=True)
general_llm = load_llm(temperature=0.5, streaming=True)

if "messages" not in st.session_state:
    st.session_state.messages = [INITIAL_MESSAGE]

# Mesajları göster.
for message in st.session_state.messages:
    avatar_icon = "👤" if message["role"] == "user" else "🔴"
    with st.chat_message(message["role"], avatar=avatar_icon):
        st.markdown(message["content"])
        sources = message.get("sources")
        if message["role"] == "assistant" and sources:
             # Kaynaklar boşsa expander'ı gösterme.
             if sources:
                with st.expander("View Sources"):
                    if isinstance(sources, list):
                        for source in sources:
                            if hasattr(source, 'metadata') and isinstance(source.metadata, dict):
                                st.info(f"Source: {os.path.basename(source.metadata.get('source', 'Unknown'))}")
                                if hasattr(source, 'page_content'):
                                    st.markdown(f"> {source.page_content}")
                            else: st.warning("Kaynak formatı beklenenden farklı.")
                    else: st.warning("Kaynaklar liste formatında değil.")

# Kullanıcı girdisini işle.
if user_input := st.chat_input("What is Pikachu?"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    # ---------- Bot cevabını hazırlarken kullanılacak bölüm ----------
    with st.chat_message("assistant", avatar="🔴"):
        response_placeholder = st.empty()
        full_response = ""
        sources = []

        try:
            cleaned_input = user_input.strip().rstrip(string.punctuation)
            if not cleaned_input: cleaned_input = user_input

            # Önce sınıflandır.
            classification_result = question_classifier_chain.invoke(cleaned_input).strip().lower()
            
            # Spinner'ı burada başlat.
            spinner_message = "Thinking..." # Varsayılan mesaj

            if classification_result == "general":
                 spinner_message = "Thinking..." # Genel bilgi için mesaj
                 chain = (
                    {"question": RunnablePassthrough(), "language": lambda x: selected_language}
                    | general_prompt
                    | general_llm
                    | StrOutputParser()
                )
                 # Genel konuda kaynak aramaya gerek yok.
                 with st.spinner(spinner_message):
                     full_response = response_placeholder.write_stream(chain.stream(cleaned_input))
                 sources = []

            else: # Varsayılan RAG
                # RAG yolunda önce kaynakları bul, sonra cevabı üret
                with st.spinner("Searching relevant Pokémon documents..."):
                    context_docs = retriever.invoke(cleaned_input)
                    sources = context_docs
                
                # Kaynaklar bulunduktan sonra cevabı üret.
                spinner_message = "Generating Pokémon answer..."
                input_data = {"context": context_docs, "question": cleaned_input, "language": selected_language}
                rag_response_chain = rag_prompt | rag_llm | StrOutputParser()
                
                with st.spinner(spinner_message):
                    full_response = response_placeholder.write_stream(rag_response_chain.stream(input_data))

            # Stream bitti, placeholder'a gerek yok, write_stream son halini yazdırdı.

            # Kaynakları göster (eğer varsa). "Pokemon" sınıfı İçin
            if sources:
                with st.expander("View Sources"):
                     if isinstance(sources, list):
                        for source in sources:
                            if hasattr(source, 'metadata') and isinstance(source.metadata, dict):
                                st.info(f"Source: {os.path.basename(source.metadata.get('source', 'Unknown'))}")
                                if hasattr(source, 'page_content'):
                                    st.markdown(f"> {source.page_content}")
                            else: st.warning("Kaynak formatı beklenenden farklı.")
                     else: st.warning("Kaynaklar liste formatında değil.")

            st.session_state.messages.append({"role": "assistant", "content": full_response, "sources": sources})

        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.session_state.messages.append({"role": "assistant", "content": f"Sorry, an error occurred: {e}", "sources": []})