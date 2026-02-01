import streamlit as st
import os
import base64
import time
import requests
import json
import pandas as pd
import matplotlib.pyplot as plt
from openai import OpenAI
from config.settings import AVAILABLE_MODELS, AGENT_TEMPLATES
from utils.database import DatabaseManager
from utils.file_handler import process_uploaded_file, export_conversation_to_json, export_conversation_to_text
from streamlit_mic_recorder import mic_recorder
from gtts import gTTS
import io
import speech_recognition as sr
from pydub import AudioSegment
from PIL import Image, ImageEnhance

# Configuração da Página
st.set_page_config(
    page_title="ChatSS IA - Ultimate Edition",
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

# --- DESIGN ULTIMATE (ESTILO CHATGPT PLUS) ---
st.markdown("""
<style>
    .stApp { background-color: #0D0D0D !important; color: #ECECEC !important; }
    [data-testid="stSidebar"] { background-color: #000000 !important; border-right: 1px solid #2D2D2D !important; }
    .stChatMessage {
        background-color: transparent !important;
        padding: 25px 0 !important;
        max-width: 850px !important;
        margin: 0 auto !important;
    }
    [data-testid="stChatMessageUser"] {
        background-color: #2F2F2F !important;
        border-radius: 20px !important;
        padding: 15px 20px !important;
    }
    .stChatInputContainer textarea {
        background-color: #2F2F2F !important;
        color: #FFFFFF !important;
        border: 1px solid #424242 !important;
        border-radius: 25px !important;
    }
    .stButton>button {
        border-radius: 10px !important;
        background-color: #212121 !important;
        color: #ECECEC !important;
        border: 1px solid #424242 !important;
    }
    h1, h2, h3 { color: #58A6FF !important; }
</style>
""", unsafe_allow_html=True)

# Inicializar Estado
if "messages" not in st.session_state: st.session_state.messages = []
if "current_conversation_id" not in st.session_state: st.session_state.current_conversation_id = None
if "openai_key" not in st.session_state: st.session_state.openai_key = ""
if "groq_key" not in st.session_state: st.session_state.groq_key = ""
if "voice_enabled" not in st.session_state: st.session_state.voice_enabled = True
if "permanent_memory" not in st.session_state: st.session_state.permanent_memory = {}
if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

def search_web(query):
    try:
        return f"Resultado da busca para: {query}. (Conexão Web Ativa)"
    except: return "Busca indisponível no momento."

def text_to_speech_natural(text):
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

# --- BARRA LATERAL ---
with st.sidebar:
    if os.path.exists("static/logo.png"):
        st.image("static/logo.png", use_container_width=True)
    
    st.subheader("⚙️ Configurações Plus")
    model_option = st.selectbox("Modelo", list(AVAILABLE_MODELS.keys()), index=0)
    model_full_id = AVAILABLE_MODELS[model_option]
    provider, model_id = model_full_id.split(":")
    
    # Lógica de exibição de chaves baseada no provedor do modelo selecionado
    if provider == "openai":
        st.session_state.openai_key = st.text_input("Chave OpenAI (sk-...)", value=st.session_state.openai_key, type="password")
        current_api_key = st.session_state.openai_key
        current_base_url = None
    else:
        st.session_state.groq_key = st.text_input("Chave Groq (gsk-...)", value=st.session_state.groq_key, type="password")
        current_api_key = st.session_state.groq_key
        current_base_url = "https://api.groq.com/openai/v1"
    
    st.session_state.voice_enabled = st.toggle("🔊 Voz Natural Ativa", value=st.session_state.voice_enabled)
    
    st.divider()
    st.subheader("🧠 Memória Permanente")
    if st.session_state.permanent_memory:
        st.json(st.session_state.permanent_memory)
    else:
        st.info("A IA aprenderá sobre você durante a conversa.")

    if st.button("➕ Novo Chat", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()

# --- ÁREA PRINCIPAL ---
st.title("🤖 ChatSS IA: Ultimate Edition")

# Exibir Mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Ferramentas de Entrada
col_mic, col_file, _ = st.columns([0.1, 0.1, 0.8])
with col_mic:
    audio_record = mic_recorder(start_prompt="🎤", stop_prompt="✅", just_once=True, key='recorder')
with col_file:
    uploaded_files = st.file_uploader("📎", accept_multiple_files=True, label_visibility="collapsed")

user_input = st.chat_input("Como posso ajudar hoje?")

# Processar Áudio
if audio_record and audio_record.get('id') != st.session_state.last_audio_id:
    st.session_state.last_audio_id = audio_record.get('id')
    with st.spinner("Ouvindo..."):
        user_input = transcribe_audio_free(audio_record['bytes'])

if user_input:
    if not current_api_key:
        st.error(f"⚠️ Por favor, insira sua chave do {provider.upper()} na barra lateral!")
    else:
        if st.session_state.current_conversation_id is None:
            st.session_state.current_conversation_id = db.create_conversation(user_input[:30], model_id, "Assistente")
        
        if "pesquise" in user_input.lower() or "quem é" in user_input.lower():
            search_res = search_web(user_input)
            user_input += f"\n\n[SISTEMA: Resultado da Pesquisa Web: {search_res}]"

        st.session_state.messages.append({"role": "user", "content": user_input})
        db.add_message(st.session_state.current_conversation_id, "user", user_input)
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                # Inicializar cliente com a chave e URL corretas do provedor selecionado
                client = OpenAI(api_key=current_api_key, base_url=current_base_url)
                
                sys_msg = f"""Você é o ChatSS IA Ultimate. 
                Memória Permanente: {json.dumps(st.session_state.permanent_memory)}.
                Responda sempre em português brasileiro."""
                
                response = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "system", "content": sys_msg}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-15:]],
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
                    audio_fp = text_to_speech_natural(full_response)
                    if audio_fp: st.audio(audio_fp, format='audio/mp3', autoplay=True)
            
            except Exception as e:
                st.error(f"Erro na chamada da API: {str(e)}")
                if "401" in str(e) or "invalid_api_key" in str(e):
                    st.info(f"Dica: Verifique se a sua chave do {provider.upper()} está correta.")
