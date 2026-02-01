import streamlit as st
import os
import time
from openai import OpenAI
from config.settings import AVAILABLE_MODELS, AGENT_TEMPLATES, DEFAULT_SETTINGS, MODEL_COSTS
from utils.database import DatabaseManager
from utils.file_handler import process_uploaded_file, export_conversation_to_json, export_conversation_to_text

# Configuração da Página
st.set_page_config(
    page_title="ChatSS IA - Elite Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Injeção de Meta Tags para PWA e Mobile
st.markdown(f"""
    <link rel="manifest" href="https://raw.githubusercontent.com/renangustavorw54-prog/chatss-ia/master/static/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/1698/1698535.png">
""", unsafe_allow_html=True)

# Inicializar Banco de Dados
db = DatabaseManager()

# --- DESIGN MODERNO (PRETO, CINZA, AZUL) ---
st.markdown("""
<style>
    /* Fundo e Cores Base */
    .stApp {
        background-color: #0E1117;
        color: #E0E0E0;
    }
    
    /* Sidebar Customizada */
    [data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
    }
    
    /* Mensagens de Chat */
    .stChatMessage {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* Mensagem do Usuário (Destaque Azul) */
    [data-testid="stChatMessageUser"] {
        background-color: #0D1117;
        border-left: 4px solid #58A6FF;
    }
    
    /* Botões Customizados */
    .stButton>button {
        background-color: #21262D;
        color: #58A6FF;
        border: 1px solid #30363D;
        border-radius: 8px;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: #30363D;
        border-color: #58A6FF;
        color: #58A6FF;
    }
    
    /* Input de Chat */
    .stChatInputContainer {
        background-color: #0E1117;
        padding-bottom: 20px;
    }
    
    /* Títulos e Textos */
    h1, h2, h3 {
        color: #58A6FF !important;
        font-family: 'Inter', sans-serif;
    }
    
    /* Esconder elementos desnecessários */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Inicializar Estado da Sessão
if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "openai_key" not in st.session_state:
    st.session_state.openai_key = ""
if "groq_key" not in st.session_state:
    st.session_state.groq_key = ""

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.markdown("<h1 style='text-align: center;'>🤖 ChatSS IA</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #8B949E;'>Elite Agent v2.0</p>", unsafe_allow_html=True)
    
    st.divider()
    
    # Seleção de Modelo e Agente
    model_option = st.selectbox("🚀 Modelo de IA", list(AVAILABLE_MODELS.keys()), index=0)
    model_full_id = AVAILABLE_MODELS[model_option]
    provider, model_id = model_full_id.split(":")
    
    # Configuração de API
    if provider == "openai":
        api_key = st.text_input("🔑 Chave OpenAI", value=st.session_state.openai_key, type="password")
        st.session_state.openai_key = api_key
        base_url = None
    else:
        api_key = st.text_input("🔑 Chave Groq (Grátis)", value=st.session_state.groq_key, type="password")
        st.session_state.groq_key = api_key
        base_url = "https://api.groq.com/openai/v1"
    
    agent_option = st.selectbox("👤 Perfil do Agente", list(AGENT_TEMPLATES.keys()), index=0)
    agent_config = AGENT_TEMPLATES[agent_option]
    
    st.divider()
    
    # Histórico
    st.subheader("📜 Conversas Recentes")
    if st.button("➕ Iniciar Novo Chat", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()
    
    conversations = db.get_conversations()
    for conv in conversations:
        col1, col2 = st.columns([0.85, 0.15])
        if col1.button(f"💬 {conv['title'][:18]}...", key=f"conv_{conv['id']}", use_container_width=True):
            st.session_state.current_conversation_id = conv['id']
            st.session_state.messages = db.get_messages(conv['id'])
            st.rerun()
        if col2.button("×", key=f"del_{conv['id']}"):
            db.delete_conversation(conv['id'])
            if st.session_state.current_conversation_id == conv['id']:
                st.session_state.current_conversation_id = None
                st.session_state.messages = []
            st.rerun()

# --- ÁREA PRINCIPAL ---

if st.session_state.current_conversation_id:
    conv_data = next((c for c in conversations if c['id'] == st.session_state.current_conversation_id), None)
    title = conv_data['title'] if conv_data else "Conversa"
    st.markdown(f"<h2>{title}</h2>", unsafe_allow_html=True)
else:
    st.markdown("<h1 style='text-align: center;'>Como posso ajudar você hoje?</h1>", unsafe_allow_html=True)
    if not api_key:
        st.warning(f"⚠️ Configure sua chave do **{provider.upper()}** na barra lateral.")

# Exibir Mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Lógica de Chat
if prompt := st.chat_input("Digite sua mensagem..."):
    if not api_key:
        st.error(f"Chave do {provider.upper()} necessária!")
    else:
        # Criar conversa no DB se for nova
        if st.session_state.current_conversation_id is None:
            st.session_state.current_conversation_id = db.create_conversation(prompt[:30], model_id, agent_option)
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        db.add_message(st.session_state.current_conversation_id, "user", prompt)
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                client = OpenAI(api_key=api_key, base_url=base_url)
                
                # Prompt de Sistema Aprimorado (Estilo ChatGPT)
                system_msg = agent_config["system_prompt"] + " Você tem acesso a conhecimentos atualizados até 2024 e deve agir como um assistente de elite, adaptando-se ao tom do usuário. Se o usuário perguntar sobre o tempo ou fatos em tempo real, explique que você busca ser o mais preciso possível com base nos dados disponíveis."
                
                api_messages = [{"role": "system", "content": system_msg}]
                # Incluir histórico para adaptação de contexto
                for m in st.session_state.messages[-10:]: # Últimas 10 mensagens para contexto
                    api_messages.append({"role": m["role"], "content": m["content"]})
                
                response = client.chat.completions.create(
                    model=model_id,
                    messages=api_messages,
                    temperature=0.7,
                    stream=True,
                )
                
                for chunk in response:
                    if chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                        message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                db.add_message(st.session_state.current_conversation_id, "assistant", full_response)
                
            except Exception as e:
                st.error(f"Erro na IA: {str(e)}")

# Rodapé de Ações
if st.session_state.current_conversation_id and st.session_state.messages:
    with st.expander("📂 Opções da Conversa"):
        col_exp1, col_exp2, col_exp3 = st.columns([1, 1, 1])
        conv_data = next((c for c in conversations if c['id'] == st.session_state.current_conversation_id), {})
        col_exp1.download_button("📥 Exportar JSON", export_conversation_to_json(conv_data, st.session_state.messages), f"chat_{st.session_state.current_conversation_id}.json", use_container_width=True)
        col_exp2.download_button("📄 Exportar Texto", export_conversation_to_text(conv_data, st.session_state.messages), f"chat_{st.session_state.current_conversation_id}.txt", use_container_width=True)
        if col_exp3.button("🗑️ Apagar Chat", use_container_width=True):
            db.delete_conversation(st.session_state.current_conversation_id)
            st.session_state.current_conversation_id = None
            st.session_state.messages = []
            st.rerun()
