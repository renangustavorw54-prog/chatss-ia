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
    initial_sidebar_state="expanded"
)

# Inicializar Banco de Dados
try:
    db = DatabaseManager()
except Exception as e:
    st.error(f"Erro ao iniciar banco de dados: {e}")
    st.stop()

# --- DESIGN INICIAL MELHORADO (ARREDONDADO, AZUL E PRETO) ---
st.markdown("""
<style>
    /* Fundo e Cores Base */
    .stApp {
        background-color: #0E1117 !important;
        color: #E0E0E0 !important;
    }
    
    /* Sidebar Arredondada */
    [data-testid="stSidebar"] {
        background-color: #161B22 !important;
        border-right: 1px solid #30363D !important;
    }
    
    /* Mensagens de Chat Arredondadas */
    .stChatMessage {
        background-color: #161B22 !important;
        border: 1px solid #30363D !important;
        border-radius: 25px !important; /* Super Arredondado */
        padding: 15px !important;
        margin-bottom: 15px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
    }
    
    /* Mensagem do Usuário (Destaque Azul Escuro) */
    [data-testid="stChatMessageUser"] {
        background-color: #0D1117 !important;
        border-left: 6px solid #005FB8 !important;
        border-radius: 25px !important;
    }
    
    /* Barra de Digitação Arredondada - Azul Escuro */
    .stChatInputContainer textarea {
        background-color: #161B22 !important;
        color: #FFFFFF !important;
        border: 2px solid #005FB8 !important;
        border-radius: 30px !important; /* Estilo Pílula */
        padding: 12px 20px !important;
    }
    
    /* Botões Arredondados */
    .stButton>button {
        background-color: #21262D !important;
        color: #58A6FF !important;
        border: 1px solid #30363D !important;
        border-radius: 15px !important;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        border-color: #58A6FF !important;
        background-color: #30363D !important;
    }
    
    /* Títulos */
    h1, h2, h3 {
        color: #58A6FF !important;
        font-family: 'Inter', sans-serif;
    }

    /* Inputs e Selects Arredondados */
    .stTextInput input, .stSelectbox div {
        border-radius: 12px !important;
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

# --- BARRA LATERAL (ESTRUTURA INICIAL) ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>🤖 ChatSS IA</h1>", unsafe_allow_html=True)
    
    st.subheader("⚙️ Configurações")
    model_option = st.selectbox("Modelo de IA", list(AVAILABLE_MODELS.keys()), index=0)
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
    
    st.session_state.voice_enabled = st.toggle("🔊 Resposta em Voz", value=st.session_state.voice_enabled)
    
    st.divider()
    
    st.subheader("📜 Histórico")
    if st.button("➕ Nova Conversa", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()
    
    try:
        conversations = db.get_conversations()
        for conv in conversations:
            if st.button(f"💬 {conv['title'][:20]}", key=f"c_{conv['id']}", use_container_width=True):
                st.session_state.current_conversation_id = conv['id']
                st.session_state.messages = db.get_messages(conv['id'])
                st.rerun()
    except: pass

# --- ÁREA PRINCIPAL ---
st.title("🤖 ChatSS IA: Agente de Elite")

# Ferramentas (Microfone e Upload)
col1, col2 = st.columns([0.7, 0.3])
with col1:
    uploaded_files = st.file_uploader("📁 Enviar Arquivos/Imagens", accept_multiple_files=True)
with col2:
    st.write("🎤 Gravar Voz:")
    audio_record = mic_recorder(start_prompt="Gravar", stop_prompt="Enviar", just_once=True, key='recorder')

# Exibir Mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input de Chat
user_input = st.chat_input("O que vamos construir hoje?")

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
