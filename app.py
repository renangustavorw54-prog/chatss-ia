import streamlit as st
import os
import base64
from openai import OpenAI
from config.settings import AVAILABLE_MODELS, AGENT_TEMPLATES
from utils.database import DatabaseManager
from utils.file_handler import process_uploaded_file, export_conversation_to_json, export_conversation_to_text
from streamlit_mic_recorder import mic_recorder
from gtts import gTTS
import io

# Configuração da Página
st.set_page_config(
    page_title="ChatSS IA - Elite Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inicializar Banco de Dados
db = DatabaseManager()

# --- DESIGN MODERNO (PRETO, CINZA, AZUL) - SEM VERMELHO ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; color: #E0E0E0; }
    [data-testid="stSidebar"] { background-color: #161B22; border-right: 1px solid #30363D; }
    
    /* Mensagens */
    .stChatMessage {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 15px;
    }
    [data-testid="stChatMessageUser"] {
        background-color: #0D1117;
        border-left: 4px solid #005FB8; /* Azul Escuro */
    }
    
    /* Barra de Digitação - Sem Vermelho */
    .stChatInputContainer textarea {
        background-color: #161B22 !important;
        color: #E0E0E0 !important;
        border: 1px solid #005FB8 !important;
    }
    
    /* Botões */
    .stButton>button {
        background-color: #21262D;
        color: #58A6FF;
        border: 1px solid #30363D;
        border-radius: 8px;
    }
    
    h1, h2, h3 { color: #58A6FF !important; }
    
    /* Estilo para o gravador */
    .mic-container {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar Estado
if "messages" not in st.session_state: st.session_state.messages = []
if "current_conversation_id" not in st.session_state: st.session_state.current_conversation_id = None
if "openai_key" not in st.session_state: st.session_state.openai_key = ""
if "groq_key" not in st.session_state: st.session_state.groq_key = ""
if "voice_enabled" not in st.session_state: st.session_state.voice_enabled = False

def text_to_speech(text):
    tts = gTTS(text=text, lang='pt', tld='com.br')
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    return fp

# --- SIDEBAR ---
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
        st.session_state.groq_key = st.text_input("🔑 Chave Groq (Grátis)", value=st.session_state.groq_key, type="password")
        api_key = st.session_state.groq_key
        base_url = "https://api.groq.com/openai/v1"
    
    st.session_state.voice_enabled = st.toggle("🔊 Resposta em Voz", value=st.session_state.voice_enabled)
    
    st.divider()
    if st.button("➕ Novo Chat", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()
    
    conversations = db.get_conversations()
    for conv in conversations:
        if st.button(f"💬 {conv['title'][:20]}", key=f"c_{conv['id']}", use_container_width=True):
            st.session_state.current_conversation_id = conv['id']
            st.session_state.messages = db.get_messages(conv['id'])
            st.rerun()

# --- ÁREA PRINCIPAL ---
st.markdown("<h1 style='text-align: center;'>Multimídia & Voz</h1>", unsafe_allow_html=True)

# Upload de Arquivos e Imagens
uploaded_files = st.file_uploader("📁 Enviar Imagens, Áudios ou Documentos", accept_multiple_files=True)

# Gravador de Voz
st.write("🎤 Gravar Áudio:")
audio_record = mic_recorder(start_prompt="Começar Gravação", stop_prompt="Parar e Enviar", key='recorder')

# Exibir Mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Lógica de Processamento
prompt = st.chat_input("O que vamos construir hoje?")

# Se houver áudio gravado, processar como prompt
if audio_record:
    # Nota: Em um ambiente real, usaríamos Whisper para transcrever. 
    # Aqui vamos simular o recebimento do áudio.
    prompt = "[Áudio Gravado Enviado]"

if prompt:
    if not api_key:
        st.error("Insira sua chave na barra lateral!")
    else:
        if st.session_state.current_conversation_id is None:
            st.session_state.current_conversation_id = db.create_conversation(prompt[:30], model_id, "Assistente")
        
        # Processar arquivos anexados
        context_files = ""
        if uploaded_files:
            for f in uploaded_files:
                if f.type.startswith("image/"):
                    context_files += f"\n[Imagem Anexada: {f.name}]"
                else:
                    content = process_uploaded_file(f.name, f.read())
                    context_files += f"\n[Arquivo: {f.name}]\n{content}"
        
        full_prompt = prompt + context_files
        st.session_state.messages.append({"role": "user", "content": full_prompt})
        db.add_message(st.session_state.current_conversation_id, "user", full_prompt)
        
        with st.chat_message("user"):
            st.markdown(full_prompt)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                client = OpenAI(api_key=api_key, base_url=base_url)
                response = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                    stream=True,
                )
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                        message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                db.add_message(st.session_state.current_conversation_id, "assistant", full_response)
                
                # Se voz estiver ativa, gerar áudio
                if st.session_state.voice_enabled:
                    audio_fp = text_to_speech(full_response)
                    st.audio(audio_fp, format='audio/mp3', autoplay=True)
                    
            except Exception as e:
                st.error(f"Erro: {str(e)}")
