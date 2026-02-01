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
    page_title="ChatSS IA - Agente de Elite",
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
    .stApp { background-color: #0E1117 !important; color: #E0E0E0 !important; }
    [data-testid="stSidebar"] { background-color: #161B22 !important; border-right: 1px solid #30363D !important; }
    .stChatMessage {
        background-color: #161B22 !important;
        border: 1px solid #30363D !important;
        border-radius: 25px !important;
        padding: 15px !important;
        margin-bottom: 15px !important;
    }
    [data-testid="stChatMessageUser"] {
        background-color: #0D1117 !important;
        border-left: 6px solid #005FB8 !important;
        border-radius: 25px !important;
    }
    .stChatInputContainer textarea {
        background-color: #161B22 !important;
        color: #FFFFFF !important;
        border: 2px solid #005FB8 !important;
        border-radius: 30px !important;
        padding: 12px 20px !important;
    }
    .stButton>button {
        background-color: #21262D !important;
        color: #58A6FF !important;
        border: 1px solid #30363D !important;
        border-radius: 15px !important;
    }
    h1, h2, h3 { color: #58A6FF !important; }
</style>
""", unsafe_allow_html=True)

# Inicializar Estado
if "messages" not in st.session_state: st.session_state.messages = []
if "current_conversation_id" not in st.session_state: st.session_state.current_conversation_id = None
if "openai_key" not in st.session_state: st.session_state.openai_key = ""
if "groq_key" not in st.session_state: st.session_state.groq_key = ""
if "github_token" not in st.session_state: st.session_state.github_token = ""
if "gmail_token" not in st.session_state: st.session_state.gmail_token = ""
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

def generate_image_dalle(prompt, api_key):
    try:
        client = OpenAI(api_key=api_key)
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url
    except Exception as e:
        return f"Erro ao gerar imagem: {e}"

def encode_image(image_file):
    return base64.b64encode(image_file.read()).decode('utf-8')

# --- BARRA LATERAL ---
with st.sidebar:
    # Exibir Logo se existir
    if os.path.exists("static/logo.png"):
        st.image("static/logo.png", use_container_width=True)
    else:
        st.markdown("<h1 style='text-align: center;'>🤖 ChatSS IA</h1>", unsafe_allow_html=True)
    
    st.subheader("⚙️ Configurações")
    model_option = st.selectbox("Modelo de IA", list(AVAILABLE_MODELS.keys()), index=3) # GPT-4o como padrão para visão
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
    
    with st.expander("🔗 Conexões Externas"):
        st.session_state.github_token = st.text_input("Token GitHub", value=st.session_state.github_token, type="password")
        st.session_state.gmail_token = st.text_input("Token Gmail/App Password", value=st.session_state.gmail_token, type="password")
        st.info("Esses tokens permitem que a IA gerencie seus repositórios e e-mails.")

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
    uploaded_files = st.file_uploader("📁 Enviar Arquivos/Imagens para Análise", accept_multiple_files=True)
with col2:
    st.write("🎤 Gravar Voz:")
    audio_record = mic_recorder(start_prompt="Gravar", stop_prompt="Enviar", just_once=True, key='recorder')

# Exibir Mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], list):
            for item in message["content"]:
                if item["type"] == "text": st.markdown(item["text"])
                elif item["type"] == "image_url": st.image(item["image_url"]["url"])
        else:
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
        # Lógica de Criação de Imagem
        if "crie uma imagem" in user_input.lower() or "gerar imagem" in user_input.lower():
            if provider != "openai":
                st.warning("A geração de imagens requer uma chave da OpenAI.")
            else:
                with st.spinner("Gerando sua imagem com DALL-E 3..."):
                    img_url = generate_image_dalle(user_input, api_key)
                    if img_url.startswith("http"):
                        st.session_state.messages.append({"role": "user", "content": user_input})
                        st.session_state.messages.append({"role": "assistant", "content": f"Aqui está a imagem que você pediu: [Imagem]({img_url})"})
                        st.image(img_url)
                        st.rerun()
                    else:
                        st.error(img_url)

        if st.session_state.current_conversation_id is None:
            st.session_state.current_conversation_id = db.create_conversation(user_input[:30], model_id, "Assistente")
        
        # Preparar conteúdo (Texto + Imagens)
        message_content = [{"type": "text", "text": user_input}]
        if uploaded_files:
            for f in uploaded_files:
                if f.type.startswith("image/"):
                    base64_image = encode_image(f)
                    message_content.append({"type": "image_url", "image_url": {"url": f"data:{f.type};base64,{base64_image}"}})
                else:
                    content = process_uploaded_file(f.name, f.read())
                    message_content[0]["text"] += f"\n\n[Arquivo: {f.name}]\n{content}"
        
        st.session_state.messages.append({"role": "user", "content": message_content})
        db.add_message(st.session_state.current_conversation_id, "user", str(message_content))
        
        with st.chat_message("user"):
            st.markdown(user_input)
            if len(message_content) > 1:
                for item in message_content[1:]: st.image(item["image_url"]["url"])
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            client = OpenAI(api_key=api_key, base_url=base_url)
            
            # System Prompt com instruções de GitHub/Gmail
            sys_msg = f"Você é o ChatSS IA, um agente de elite. Você pode ver imagens, criar imagens e gerenciar conexões. GitHub Token: {st.session_state.github_token}, Gmail Token: {st.session_state.gmail_token}. Use essas informações se o usuário pedir para mexer em repositórios ou e-mails. Responda sempre em português brasileiro."
            
            api_messages = [{"role": "system", "content": sys_msg}]
            for m in st.session_state.messages[-10:]:
                api_messages.append({"role": m["role"], "content": m["content"]})
            
            response = client.chat.completions.create(
                model=model_id,
                messages=api_messages,
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
