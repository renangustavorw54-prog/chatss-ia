import streamlit as st
import os
import base64
import time
import requests
from openai import OpenAI
from config.settings import AVAILABLE_MODELS, AGENT_TEMPLATES
from utils.database import DatabaseManager
from utils.file_handler import process_uploaded_file, export_conversation_to_json, export_conversation_to_text
from streamlit_mic_recorder import mic_recorder
from gtts import gTTS
import io
import speech_recognition as sr
from pydub import AudioSegment

# Configuração da Página
st.set_page_config(
    page_title="ChatSS IA",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar Banco de Dados
try:
    db = DatabaseManager()
except Exception as e:
    st.error(f"Erro ao iniciar banco de dados: {e}")
    st.stop()

# --- DESIGN PREMIUM ESTILO CHATGPT/GEMINI ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    * { font-family: 'Inter', sans-serif; }
    
    .stApp {
        background-color: #171717 !important;
        color: #ececec !important;
    }

    /* Sidebar Estilo ChatGPT */
    [data-testid="stSidebar"] {
        background-color: #0D0D0D !important;
        border-right: 1px solid #2f2f2f !important;
    }
    
    /* Inputs na Sidebar */
    .stSidebar .stTextInput input, .stSidebar .stSelectbox select {
        background-color: #212121 !important;
        color: #ececec !important;
        border: 1px solid #424242 !important;
    }

    /* Botão Nova Conversa */
    .stButton>button {
        background-color: #212121 !important;
        color: #ececec !important;
        border: 1px solid #424242 !important;
        border-radius: 10px !important;
        transition: 0.2s;
    }
    .stButton>button:hover {
        background-color: #2f2f2f !important;
        border-color: #676767 !important;
    }

    /* Container de Mensagens */
    .stChatMessage {
        background-color: transparent !important;
        padding: 20px 0 !important;
        max-width: 850px !important;
        margin: 0 auto !important;
    }
    
    /* Bolhas de Chat */
    [data-testid="stChatMessageUser"] {
        background-color: #2f2f2f !important;
        border-radius: 20px !important;
        padding: 15px !important;
        margin-bottom: 10px !important;
    }
    
    /* Barra de Digitação Estilo Gemini */
    .stChatInputContainer {
        background-color: transparent !important;
        padding-bottom: 30px !important;
    }
    
    .stChatInputContainer textarea {
        background-color: #2f2f2f !important;
        color: #ececec !important;
        border: 1px solid #424242 !important;
        border-radius: 25px !important;
        padding: 15px 25px !important;
        max-width: 850px !important;
        margin: 0 auto !important;
    }

    /* Esconder elementos desnecessários */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .main-title {
        text-align: center;
        font-size: 2rem;
        font-weight: 600;
        margin-top: 10vh;
        color: #ececec;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar Estado
if "messages" not in st.session_state: st.session_state.messages = []
if "current_conversation_id" not in st.session_state: st.session_state.current_conversation_id = None
if "openai_key" not in st.session_state: st.session_state.openai_key = ""
if "groq_key" not in st.session_state: st.session_state.groq_key = ""
if "voice_enabled" not in st.session_state: st.session_state.voice_enabled = True
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang='pt', tld='com.br', slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp
    except: return None

def transcribe_audio_free(audio_bytes):
    try:
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
        wav_io = io.BytesIO()
        audio_segment.export(wav_io, format="wav")
        wav_io.seek(0)
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)
            return recognizer.recognize_google(audio_data, language="pt-BR")
    except: return "[Áudio não compreendido]"

# --- BARRA LATERAL (CONFIGURAÇÕES E HISTÓRICO) ---
with st.sidebar:
    st.markdown("<h2 style='color: #58A6FF;'>ChatSS IA</h2>", unsafe_allow_html=True)
    
    # CONFIGURAÇÕES VISÍVEIS
    st.markdown("### ⚙️ Configurações")
    model_option = st.selectbox("Modelo de IA", list(AVAILABLE_MODELS.keys()), index=0)
    model_full_id = AVAILABLE_MODELS[model_option]
    provider, model_id = model_full_id.split(":")
    
    if provider == "openai":
        st.session_state.openai_key = st.text_input("Chave OpenAI (sk-...)", value=st.session_state.openai_key, type="password")
        api_key = st.session_state.openai_key
        base_url = None
    else:
        st.session_state.groq_key = st.text_input("Chave Groq (gsk-...)", value=st.session_state.groq_key, type="password")
        api_key = st.session_state.groq_key
        base_url = "https://api.groq.com/openai/v1"
    
    st.session_state.voice_enabled = st.toggle("🔊 Resposta em Voz", value=st.session_state.voice_enabled)
    
    st.divider()
    
    # HISTÓRICO
    if st.button("➕ Nova Conversa", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("### 📜 Histórico")
    try:
        conversations = db.get_conversations()
        for conv in conversations:
            if st.button(f"💬 {conv['title'][:20]}...", key=f"c_{conv['id']}", use_container_width=True):
                st.session_state.current_conversation_id = conv['id']
                st.session_state.messages = db.get_messages(conv['id'])
                st.rerun()
    except: pass

# --- ÁREA PRINCIPAL ---

if not st.session_state.messages:
    st.markdown("<div class='main-title'>Como posso ajudar hoje?</div>", unsafe_allow_html=True)
else:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Ferramentas (Microfone e Upload)
col_tools1, col_tools2, _ = st.columns([0.1, 0.1, 0.8])
with col_tools1:
    audio_record = mic_recorder(start_prompt="🎤", stop_prompt="✅", just_once=True, key='recorder')
with col_tools2:
    uploaded_files = st.file_uploader("📎", accept_multiple_files=True, label_visibility="collapsed")

# Input de Chat
user_input = st.chat_input("Digite sua mensagem...")

# Processar Áudio
if audio_record and audio_record.get('id') != st.session_state.last_audio_id:
    st.session_state.last_audio_id = audio_record.get('id')
    with st.spinner("Ouvindo..."):
        user_input = transcribe_audio_free(audio_record['bytes'])

# Lógica de Chat
if user_input:
    if not api_key:
        st.error("⚠️ Insira sua chave na barra lateral!")
    else:
        if st.session_state.current_conversation_id is None:
            st.session_state.current_conversation_id = db.create_conversation(user_input[:30], model_id, "Assistente")
        
        st.session_state.messages.append({"role": "user", "content": user_input})
        db.add_message(st.session_state.current_conversation_id, "user", user_input)
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]],
                stream=True,
            )
            for chunk in response:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            db.add_message(st.session_state.current_conversation_id, "assistant", full_response)
            
            if st.session_state.voice_enabled:
                audio_fp = text_to_speech(full_response)
                if audio_fp: st.audio(audio_fp, format='audio/mp3', autoplay=True)
