import streamlit as st
import os
import base64
import time
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

# Inicializar Banco de Dados com tratamento de erro para estabilidade
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
    
    /* Estilo para o botão de áudio */
    .audio-btn-container {
        display: flex;
        justify-content: center;
        padding: 10px;
        background: #161B22;
        border-radius: 10px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar Estado da Sessão com segurança
def init_session():
    if "messages" not in st.session_state: st.session_state.messages = []
    if "current_conversation_id" not in st.session_state: st.session_state.current_conversation_id = None
    if "openai_key" not in st.session_state: st.session_state.openai_key = ""
    if "groq_key" not in st.session_state: st.session_state.groq_key = ""
    if "voice_enabled" not in st.session_state: st.session_state.voice_enabled = True # Padrão ligado
    if "last_audio_id" not in st.session_state: st.session_state.last_audio_id = None

init_session()

def text_to_speech(text):
    try:
        tts = gTTS(text=text, lang='pt', tld='com.br', slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        return fp
    except Exception as e:
        st.warning(f"Erro na síntese de voz: {e}")
        return None

def encode_image(image_file):
    return base64.b64encode(image_file.read()).decode('utf-8')

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>🤖 ChatSS IA</h1>", unsafe_allow_html=True)
    
    model_option = st.selectbox("🚀 Escolha o Modelo", list(AVAILABLE_MODELS.keys()), index=0)
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
    
    st.session_state.voice_enabled = st.toggle("🔊 Voz Ativa", value=st.session_state.voice_enabled)
    
    st.divider()
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
    except:
        st.write("Sem histórico disponível.")

# --- ÁREA PRINCIPAL ---
st.markdown("<h2 style='text-align: center;'>Central de Voz e Inteligência</h2>", unsafe_allow_html=True)

# Container de Entrada Multimídia
with st.container():
    col1, col2 = st.columns([0.7, 0.3])
    with col1:
        uploaded_files = st.file_uploader("📁 Enviar Imagens/Arquivos", accept_multiple_files=True)
    with col2:
        st.write("🎤 Falar agora:")
        audio_record = mic_recorder(
            start_prompt="🔴 Gravar",
            stop_prompt="🟢 Enviar",
            just_once=True,
            key='recorder'
        )

# Exibir Mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if isinstance(message["content"], list):
            for item in message["content"]:
                if item["type"] == "text": st.markdown(item["text"])
                elif item["type"] == "image_url": st.image(item["image_url"]["url"])
        else:
            st.markdown(message["content"])

# Lógica de Processamento de Entrada
user_input = st.chat_input("O que vamos construir hoje?")
audio_prompt = None

# Se houver áudio gravado e for novo
if audio_record and audio_record.get('id') != st.session_state.last_audio_id:
    st.session_state.last_audio_id = audio_record.get('id')
    audio_prompt = "O usuário enviou uma mensagem de voz. Por favor, responda de forma amigável e suave."
    # Em um cenário ideal aqui transcreveríamos o áudio. 
    # Como estamos focando na resposta de voz da IA:
    user_input = audio_prompt

if user_input:
    if not api_key:
        st.error("⚠️ Por favor, insira sua chave na barra lateral!")
    else:
        try:
            if st.session_state.current_conversation_id is None:
                st.session_state.current_conversation_id = db.create_conversation(user_input[:30], model_id, "Assistente")
            
            # Preparar conteúdo
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
                
                # Contexto de voz e visão
                sys_prompt = "Você é um assistente de elite. Se o usuário falar com você, responda de forma clara e natural. Você pode ver imagens. Responda sempre em português brasileiro."
                
                api_messages = [{"role": "system", "content": sys_prompt}]
                for m in st.session_state.messages[-10:]:
                    api_messages.append({"role": m["role"], "content": m["content"]})
                
                response = client.chat.completions.create(
                    model=model_id,
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
                
                # Resposta em Voz Automática
                if st.session_state.voice_enabled:
                    audio_fp = text_to_speech(full_response)
                    if audio_fp:
                        st.audio(audio_fp, format='audio/mp3', autoplay=True)
                        
        except Exception as e:
            st.error(f"Ocorreu um erro: {str(e)}")
            st.info("Dica: Verifique se sua chave de API é válida e se você selecionou o modelo correto.")
