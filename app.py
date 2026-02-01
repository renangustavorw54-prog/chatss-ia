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
    page_title="ChatGPT",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inicializar Banco de Dados
try:
    db = DatabaseManager()
except Exception as e:
    st.error(f"Erro ao iniciar banco de dados: {e}")
    st.stop()

# --- DESIGN PREMIUM ESTILO CHATGPT (DARK MODE) ---
st.markdown("""
<style>
    /* Importar Fonte Inter */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

    /* Reset Geral */
    * { font-family: 'Inter', sans-serif; }
    
    .stApp {
        background-color: #212121 !important;
        color: #ececec !important;
    }

    /* Sidebar Estilo ChatGPT */
    [data-testid="stSidebar"] {
        background-color: #171717 !important;
        border-right: none !important;
        width: 260px !important;
    }
    
    .stSidebar [data-testid="stVerticalBlock"] {
        padding: 10px !important;
    }

    /* Botão Nova Conversa */
    .stButton>button {
        background-color: transparent !important;
        color: #ececec !important;
        border: 1px solid #4d4d4d !important;
        border-radius: 8px !important;
        width: 100% !important;
        text-align: left !important;
        padding: 10px !important;
        font-size: 14px !important;
        transition: background-color 0.2s;
    }
    .stButton>button:hover {
        background-color: #2f2f2f !important;
    }

    /* Container de Mensagens */
    .stChatMessage {
        background-color: transparent !important;
        padding: 20px 0 !important;
        max-width: 800px !important;
        margin: 0 auto !important;
    }
    
    /* Avatar e Conteúdo */
    [data-testid="stChatMessageAvatarUser"] { background-color: #5436da !important; }
    [data-testid="stChatMessageAvatarAssistant"] { background-color: #10a37f !important; }

    /* Barra de Digitação Flutuante */
    .stChatInputContainer {
        background-color: transparent !important;
        border: none !important;
        padding-bottom: 40px !important;
    }
    
    .stChatInputContainer textarea {
        background-color: #2f2f2f !important;
        color: #ececec !important;
        border: 1px solid #4d4d4d !important;
        border-radius: 12px !important;
        padding: 12px 15px !important;
        max-width: 800px !important;
        margin: 0 auto !important;
        box-shadow: 0 0 15px rgba(0,0,0,0.1) !important;
    }
    
    .stChatInputContainer textarea:focus {
        border-color: #676767 !important;
        box-shadow: 0 0 20px rgba(0,0,0,0.2) !important;
    }

    /* Esconder elementos Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Centralizar Título Inicial */
    .main-title {
        text-align: center;
        font-size: 2.5rem;
        font-weight: 600;
        margin-top: 15vh;
        color: #ececec;
    }
    
    /* Estilo para o Microfone e Upload */
    .tools-container {
        max-width: 800px;
        margin: 0 auto 10px auto;
        display: flex;
        gap: 10px;
        align-items: center;
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

def get_weather(city):
    try:
        response = requests.get(f"https://wttr.in/{city}?format=%C+%t")
        return response.text if response.status_code == 200 else "Indisponível"
    except: return "Erro"

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

# --- SIDEBAR (HISTÓRICO) ---
with st.sidebar:
    st.markdown("<div style='padding: 10px 0;'><b style='font-size: 18px;'>ChatSS IA</b></div>", unsafe_allow_html=True)
    
    if st.button("➕ Nova conversa", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("<div style='margin-top: 20px; color: #676767; font-size: 12px; font-weight: 600;'>HISTÓRICO</div>", unsafe_allow_html=True)
    
    try:
        conversations = db.get_conversations()
        for conv in conversations:
            if st.button(f"💬 {conv['title'][:22]}", key=f"c_{conv['id']}", use_container_width=True):
                st.session_state.current_conversation_id = conv['id']
                st.session_state.messages = db.get_messages(conv['id'])
                st.rerun()
    except: pass

    st.divider()
    # Configurações no rodapé da sidebar
    with st.expander("⚙️ Configurações"):
        model_option = st.selectbox("Modelo", list(AVAILABLE_MODELS.keys()), index=0)
        model_full_id = AVAILABLE_MODELS[model_option]
        provider, model_id = model_full_id.split(":")
        
        if provider == "openai":
            st.session_state.openai_key = st.text_input("Chave OpenAI", value=st.session_state.openai_key, type="password")
            api_key = st.session_state.openai_key
            base_url = None
        else:
            st.session_state.groq_key = st.text_input("Chave Groq", value=st.session_state.groq_key, type="password")
            api_key = st.session_state.groq_key
            base_url = "https://api.groq.com/openai/v1"
        
        st.session_state.voice_enabled = st.toggle("Voz Ativa", value=st.session_state.voice_enabled)

# --- ÁREA PRINCIPAL ---

if not st.session_state.messages:
    st.markdown("<div class='main-title'>Como posso ajudar hoje?</div>", unsafe_allow_html=True)
else:
    # Exibir Mensagens
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Ferramentas Auxiliares (Microfone e Upload)
st.markdown("<div class='tools-container'>", unsafe_allow_html=True)
col_mic, col_file = st.columns([0.2, 0.8])
with col_mic:
    audio_record = mic_recorder(start_prompt="🎤", stop_prompt="✅", just_once=True, key='recorder')
with col_file:
    uploaded_files = st.file_uploader("📎", accept_multiple_files=True, label_visibility="collapsed")
st.markdown("</div>", unsafe_allow_html=True)

# Input de Chat
user_input = st.chat_input("Enviar mensagem")

# Processar Áudio
if audio_record and audio_record.get('id') != st.session_state.last_audio_id:
    st.session_state.last_audio_id = audio_record.get('id')
    with st.spinner(""):
        user_input = transcribe_audio_free(audio_record['bytes'])

# Lógica de Chat
if user_input:
    if not api_key:
        st.error("Configure sua chave nas configurações (canto inferior esquerdo).")
    else:
        if "tempo" in user_input.lower() or "temperatura" in user_input.lower():
            weather_info = get_weather("Caraguatatuba")
            user_input += f"\n\n[Sistema: O clima em Caraguatatuba é {weather_info}]"

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
