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
from PIL import Image, ImageEnhance
import moviepy.editor as mp

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

def improve_image_quality(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    # Melhorar Nitidez
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)
    # Melhorar Contraste
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)
    # Melhorar Cor
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.1)
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def process_video_reels(video_bytes):
    # Salvar temporariamente
    with open("temp_video.mp4", "wb") as f:
        f.write(video_bytes)
    
    clip = mp.VideoFileClip("temp_video.mp4")
    # Cortar para 9:16 (Reels) se necessário
    w, h = clip.size
    target_ratio = 9/16
    current_ratio = w/h
    
    if current_ratio > target_ratio:
        new_w = h * target_ratio
        clip = clip.crop(x_center=w/2, width=new_w)
    
    # Limitar a 60 segundos para Reels
    if clip.duration > 60:
        clip = clip.subclip(0, 60)
        
    clip.write_videofile("reels_output.mp4", codec="libx264")
    with open("reels_output.mp4", "rb") as f:
        return f.read()

def encode_image(image_file):
    return base64.b64encode(image_file.read()).decode('utf-8')

# --- BARRA LATERAL ---
with st.sidebar:
    if os.path.exists("static/logo.png"):
        st.image("static/logo.png", use_container_width=True)
    
    st.subheader("⚙️ Configurações")
    model_option = st.selectbox("Modelo de IA", list(AVAILABLE_MODELS.keys()), index=3)
    model_full_id = AVAILABLE_MODELS[model_option]
    provider, model_id = model_full_id.split(":")
    
    if provider == "openai":
        st.session_state.openai_key = st.text_input("Chave OpenAI", value=st.session_state.openai_key, type="password")
        api_key = st.session_state.openai_key
    else:
        st.session_state.groq_key = st.text_input("Chave Groq", value=st.session_state.groq_key, type="password")
        api_key = st.session_state.groq_key
    
    with st.expander("🔗 Conexões Externas"):
        st.session_state.github_token = st.text_input("Token GitHub", value=st.session_state.github_token, type="password")
        st.session_state.gmail_token = st.text_input("Token Gmail", value=st.session_state.gmail_token, type="password")

    st.session_state.voice_enabled = st.toggle("🔊 Resposta em Voz", value=st.session_state.voice_enabled)
    
    st.divider()
    if st.button("➕ Nova Conversa", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()

# --- ÁREA PRINCIPAL ---
st.title("🤖 ChatSS IA: Estúdio de Elite")

# Ferramentas Multimídia
with st.expander("🎨 Ferramentas de Edição (Imagem e Vídeo)"):
    col_img, col_vid = st.columns(2)
    with col_img:
        img_file = st.file_uploader("Melhorar Qualidade de Foto", type=['png', 'jpg', 'jpeg'])
        if img_file and st.button("✨ Melhorar Foto"):
            with st.spinner("Processando imagem..."):
                improved_img = improve_image_quality(img_file.read())
                st.image(improved_img, caption="Imagem Melhorada")
                st.download_button("Baixar Foto HD", improved_img, "foto_hd.png")
    
    with col_vid:
        vid_file = st.file_uploader("Criar Reels (Corte 9:16)", type=['mp4', 'mov'])
        if vid_file and st.button("🎬 Gerar Reels"):
            with st.spinner("Editando vídeo para Reels..."):
                reels_vid = process_video_reels(vid_file.read())
                st.video(reels_vid)
                st.download_button("Baixar Reels", reels_vid, "meu_reels.mp4")

# Chat Principal
uploaded_files = st.file_uploader("📁 Enviar para Análise", accept_multiple_files=True)
audio_record = mic_recorder(start_prompt="🎤 Gravar", stop_prompt="Enviar", just_once=True, key='recorder')

# Exibir Mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], list):
            for item in message["content"]:
                if item["type"] == "text": st.markdown(item["text"])
                elif item["type"] == "image_url": st.image(item["image_url"]["url"])
        else: st.markdown(message["content"])

user_input = st.chat_input("O que vamos criar hoje?")

if audio_record and audio_record.get('id') != st.session_state.last_audio_id:
    st.session_state.last_audio_id = audio_record.get('id')
    with st.spinner("Ouvindo..."):
        user_input = transcribe_audio_free(audio_record['bytes'])

if user_input:
    if not api_key:
        st.error("⚠️ Insira sua chave na barra lateral!")
    else:
        if st.session_state.current_conversation_id is None:
            st.session_state.current_conversation_id = db.create_conversation(user_input[:30], model_id, "Assistente")
        
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
            client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1" if "groq" in model_id else None)
            
            sys_msg = f"Você é o ChatSS IA Estúdio. Você pode editar imagens e vídeos. GitHub: {st.session_state.github_token}, Gmail: {st.session_state.gmail_token}. Responda em português."
            
            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "system", "content": sys_msg}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]],
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
