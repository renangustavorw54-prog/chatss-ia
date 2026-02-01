import streamlit as st
import os
import time
from openai import OpenAI
from config.settings import AVAILABLE_MODELS, AGENT_TEMPLATES, DEFAULT_SETTINGS, MODEL_COSTS
from utils.database import DatabaseManager
from utils.file_handler import process_uploaded_file, export_conversation_to_json, export_conversation_to_text

# Configuração da Página
st.set_page_config(
    page_title="ChatSS IA - Agente de Elite",
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

# Estilos Customizados
st.markdown("""
<style>
    .stChatMessage {
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 10px;
    }
    .stChatInputContainer {
        padding-bottom: 20px;
    }
    .sidebar-content {
        padding: 10px;
    }
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
    st.title("🤖 ChatSS IA")
    st.subheader("Configurações de Elite")
    
    # Seleção de Modelo e Agente
    model_option = st.selectbox("Modelo de IA", list(AVAILABLE_MODELS.keys()), index=0)
    model_full_id = AVAILABLE_MODELS[model_option]
    provider, model_id = model_full_id.split(":")
    
    # Configuração de API baseada no provedor
    if provider == "openai":
        api_key = st.text_input("Chave OpenAI (sk-...)", value=st.session_state.openai_key, type="password")
        st.session_state.openai_key = api_key
        base_url = None
    else:
        st.info("💡 **Dica:** Use o Groq para acesso gratuito!")
        api_key = st.text_input("Chave Groq (gsk-...)", value=st.session_state.groq_key, type="password", help="Pegue grátis em console.groq.com")
        st.session_state.groq_key = api_key
        base_url = "https://api.groq.com/openai/v1"
    
    agent_option = st.selectbox("Perfil do Agente", list(AGENT_TEMPLATES.keys()), index=0)
    agent_config = AGENT_TEMPLATES[agent_option]
    
    # Parâmetros Avançados
    with st.expander("Ajustes Avançados"):
        temp = st.slider("Criatividade", 0.0, 2.0, agent_config["temperature"], 0.1)
        max_tokens = st.number_input("Limite de Tokens", 100, 32000, 4000)
    
    st.divider()
    
    # Histórico
    st.subheader("📜 Histórico")
    if st.button("➕ Nova Conversa", use_container_width=True):
        st.session_state.current_conversation_id = None
        st.session_state.messages = []
        st.rerun()
    
    conversations = db.get_conversations()
    for conv in conversations:
        col1, col2 = st.columns([0.8, 0.2])
        if col1.button(f"💬 {conv['title'][:20]}...", key=f"conv_{conv['id']}", use_container_width=True):
            st.session_state.current_conversation_id = conv['id']
            st.session_state.messages = db.get_messages(conv['id'])
            st.rerun()
        if col2.button("🗑️", key=f"del_{conv['id']}"):
            db.delete_conversation(conv['id'])
            if st.session_state.current_conversation_id == conv['id']:
                st.session_state.current_conversation_id = None
                st.session_state.messages = []
            st.rerun()

# --- ÁREA PRINCIPAL ---

if st.session_state.current_conversation_id:
    conv_data = next((c for c in conversations if c['id'] == st.session_state.current_conversation_id), None)
    title = conv_data['title'] if conv_data else "Conversa"
    st.title(f"💬 {title}")
else:
    st.title("🤖 ChatSS IA: Seu Agente Ilimitado")
    if not api_key:
        st.warning(f"⚠️ Por favor, insira sua chave do **{provider.upper()}** na barra lateral para começar.")
        if provider == "groq":
            st.markdown("1. Vá para [console.groq.com](https://console.groq.com/keys)\n2. Crie uma chave grátis\n3. Cole no campo ao lado")

# Upload de Arquivos
uploaded_file = st.file_uploader("Anexar arquivo (PDF, DOCX, TXT)", type=["pdf", "docx", "txt", "md", "py"])

# Exibir Mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Lógica de Chat
if prompt := st.chat_input("O que vamos construir hoje?"):
    if not api_key:
        st.error(f"Erro: Chave do {provider.upper()} não encontrada!")
    else:
        if uploaded_file:
            with st.spinner("Lendo arquivo..."):
                file_content = process_uploaded_file(uploaded_file.name, uploaded_file.read())
                prompt = f"--- ARQUIVO: {uploaded_file.name} ---\n{file_content}\n\n--- PERGUNTA ---\n{prompt}"

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
                api_messages = [{"role": "system", "content": agent_config["system_prompt"]}]
                for m in st.session_state.messages:
                    api_messages.append({"role": m["role"], "content": m["content"]})
                
                response = client.chat.completions.create(
                    model=model_id,
                    messages=api_messages,
                    temperature=temp,
                    max_tokens=max_tokens,
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

# Exportação
if st.session_state.current_conversation_id and st.session_state.messages:
    st.divider()
    conv_data = next((c for c in conversations if c['id'] == st.session_state.current_conversation_id), {})
    col_exp1, col_exp2, _ = st.columns([0.2, 0.2, 0.6])
    col_exp1.download_button("📥 JSON", export_conversation_to_json(conv_data, st.session_state.messages), f"chat_{st.session_state.current_conversation_id}.json")
    col_exp2.download_button("📄 TXT", export_conversation_to_text(conv_data, st.session_state.messages), f"chat_{st.session_state.current_conversation_id}.txt")
