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
    page_title="ChatSS IA - Elite Agent",
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

# --- DESIGN FORÇADO (AZUL ESCURO E PRETO) ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117 !important; color: #E0E0E0 !important; }
    [data-testid="stSidebar"] { background-color: #0D1117 !important; border-right: 1px solid #1F2328 !important; }
    .stChatInputContainer textarea {
        background-color: #161B22 !important;
        color: #FFFFFF !important;
        border: 2px solid #005FB8 !important;
        border-radius: 10px !important;
    }
    .stChatMessage { background-color: #161B22 !important; border: 1px solid #30363D !important; border-radius: 15px !important; }
    [data-testid="stChatMessageUser"] { border-left: 5px solid #005FB8 !important; }
    h1, h2, h3 { color: #58A6FF !important; }
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
        if response.status_code == 200:
            return response.text
        return "Não consegui acessar o clima agora."
    except:
        return "Erro ao buscar clima."

def transcribe_audio_free(audio_bytes):
    try:
        # Converter bytes para formato que o SpeechRecognition entende
        audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
        wav_io = io.BytesIO()
        audio_segment.export(wav_io, format="wav")
        wav_io.seek(0)
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="pt-BR")
            return text
    except Exception as e:
        return f"[Erro na transcrição gratuita: {e}]"

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>🤖 ChatSS IA</h1>", unsafe_allow_html=True)
    model_option = st.selectbox("🚀 Modelo", list(AVAILABLE_MODELS.keys()), index=0)
    model_full_id = AVAILABLE_MODELS[model_option]
    provider, model_id = model_full_id.split(":")
    
    if provider == "openai":
        st.session_state.openai_key = st.text_input("🔑 Chave OpenAI", value=st.session_state.openai_key, type="password")
        api_key = st.session_state.openai_key
        base_url = None
    else:
        st.session_state.groq_key = st.text_input("🔑 Chave Groq", value=st.session_state.groq_key, type="password")
        api_key = st.session_state.groq_key
        base_url = "https://api.groq.com/openai/v1"
    
    st.session_state.voice_enabled = st.toggle("🔊 Voz Ativa", value=st.session_state.voice_enabled)
    
    if st.button("➕ Novo Chat", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()

# --- ÁREA PRINCIPAL ---
st.markdown("<h2 style='text-align: center;'>Voz & Clima Grátis</h2>", unsafe_allow_html=True)

# Entrada de Áudio
st.write("🎤 Fale com a IA (Grátis):")
audio_record = mic_recorder(start_prompt="🔴 Gravar", stop_prompt="🟢 Enviar", just_once=True, key='recorder')

# Processar Áudio se houver
user_input = st.chat_input("Ou digite aqui...")
if audio_record and audio_record.get('id') != st.session_state.last_audio_id:
    st.session_state.last_audio_id = audio_record.get('id')
    with st.spinner("Traduzindo sua voz..."):
        user_input = transcribe_audio_free(audio_record['bytes'])

# Lógica de Chat
if user_input:
    if not api_key:
        st.error("⚠️ Insira sua chave na barra lateral!")
    else:
        if "tempo" in user_input.lower() or "temperatura" in user_input.lower():
            city = "Caraguatatuba"
            weather_info = get_weather(city)
            user_input += f"\n\n[INFO CLIMA: Em {city} está {weather_info}]"

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

# Exibir Histórico
for message in st.session_state.messages[:-1]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
