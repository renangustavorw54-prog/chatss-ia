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
if "voice_enabled" not in st.session_state: st.session_state.voice_enabled = False

def text_to_speech(text):
    try:
        # gTTS com sotaque brasileiro suave
        tts = gTTS(text=text, lang='pt', tld='com.br', slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp
    except:
        return None

def encode_image(image_file):
    return base64.b64encode(image_file.read()).decode('utf-8')

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>🤖 ChatSS IA</h1>", unsafe_allow_html=True)
    
    model_option = st.selectbox("🚀 Escolha o Modelo", list(AVAILABLE_MODELS.keys()), index=3) # Default para GPT-4o
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
    
    st.session_state.voice_enabled = st.toggle("🔊 Voz Suave (Estilo Siri)", value=st.session_state.voice_enabled)
    
    st.divider()
    if st.button("➕ Nova Conversa", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()

# --- ÁREA PRINCIPAL ---
st.markdown("<h2 style='text-align: center;'>Visão & Voz Inteligente</h2>", unsafe_allow_html=True)

# Container de Multimídia
with st.container():
    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        uploaded_files = st.file_uploader("📁 Enviar Imagens ou Documentos", accept_multiple_files=True)
    with col2:
        st.write("🎤 Gravar Voz:")
        audio_record = mic_recorder(start_prompt="Gravar", stop_prompt="Enviar", key='recorder')

# Exibir Mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], list):
            for item in message["content"]:
                if item["type"] == "text":
                    st.markdown(item["text"])
                elif item["type"] == "image_url":
                    st.image(item["image_url"]["url"])
        else:
            st.markdown(message["content"])

# Lógica de Chat
if prompt := st.chat_input("O que vamos construir hoje?"):
    if not api_key:
        st.error("Por favor, insira sua chave na barra lateral!")
    else:
        if st.session_state.current_conversation_id is None:
            st.session_state.current_conversation_id = db.create_conversation(prompt[:30], model_id, "Assistente")
        
        # Preparar conteúdo da mensagem (Texto + Imagens)
        message_content = [{"type": "text", "text": prompt}]
        
        if uploaded_files:
            for f in uploaded_files:
                if f.type.startswith("image/"):
                    base64_image = encode_image(f)
                    message_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{f.type};base64,{base64_image}"}
                    })
                else:
                    content = process_uploaded_file(f.name, f.read())
                    message_content[0]["text"] += f"\n\n[Arquivo: {f.name}]\n{content}"
        
        st.session_state.messages.append({"role": "user", "content": message_content})
        db.add_message(st.session_state.current_conversation_id, "user", str(message_content))
        
        with st.chat_message("user"):
            if len(message_content) > 1:
                st.markdown(prompt)
                for item in message_content[1:]:
                    st.image(item["image_url"]["url"])
            else:
                st.markdown(prompt)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                client = OpenAI(api_key=api_key, base_url=base_url)
                
                # Ajustar mensagens para o formato da API
                api_messages = [{"role": "system", "content": "Você é um assistente de elite com visão computacional. Você pode ver imagens e descrevê-las com precisão. Sua voz é suave e amigável. Responda sempre em português."}]
                for m in st.session_state.messages[-10:]:
                    api_messages.append({"role": m["role"], "content": m["content"]})
                
                response = client.chat.completions.create(
                    model=model_id if provider == "openai" else model_id,
                    messages=api_messages,
                    max_tokens=1000,
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
                    if audio_fp:
                        st.audio(audio_fp, format='audio/mp3', autoplay=True)
                    
            except Exception as e:
                st.error(f"Erro: {str(e)}")
