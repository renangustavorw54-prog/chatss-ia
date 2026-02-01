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
    .model-info {
        font-size: 0.8em;
        color: #888;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar Estado da Sessão
if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "api_key" not in st.session_state:
    st.session_state.api_key = os.environ.get("OPENAI_API_KEY", "")

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.title("🤖 ChatSS IA")
    st.subheader("Configurações de Elite")
    
    # Configuração de API
    api_key = st.text_input("Chave de API OpenAI", value=st.session_state.api_key, type="password", help="Sua chave é usada apenas localmente e não é salva no servidor.")
    if api_key:
        st.session_state.api_key = api_key
        os.environ["OPENAI_API_KEY"] = api_key
    
    # Seleção de Modelo e Agente
    model_option = st.selectbox("Modelo de IA", list(AVAILABLE_MODELS.keys()), index=0)
    model_id = AVAILABLE_MODELS[model_option]
    
    agent_option = st.selectbox("Perfil do Agente", list(AGENT_TEMPLATES.keys()), index=0)
    agent_config = AGENT_TEMPLATES[agent_option]
    
    # Parâmetros Avançados
    with st.expander("Ajustes Avançados"):
        temp = st.slider("Criatividade (Temperatura)", 0.0, 2.0, agent_config["temperature"], 0.1)
        max_tokens = st.number_input("Limite de Resposta (Tokens)", 100, 128000, 4000)
    
    st.divider()
    
    # Histórico de Conversas
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

    st.divider()
    
    # Estatísticas
    stats = db.get_statistics()
    st.info(f"📊 **Uso Total:**\n- Tokens: {stats['total_tokens']:,}\n- Custo Est.: ${stats['total_cost']:.4f}")

# --- ÁREA PRINCIPAL ---

# Título da Conversa Atual
if st.session_state.current_conversation_id:
    conv_data = next((c for c in conversations if c['id'] == st.session_state.current_conversation_id), None)
    title = conv_data['title'] if conv_data else "Conversa"
    st.title(f"💬 {title}")
else:
    st.title("🤖 ChatSS IA: Seu Agente Ilimitado")
    st.info("Inicie uma nova conversa ou selecione uma do histórico na barra lateral.")

# Upload de Arquivos
uploaded_file = st.file_uploader("Anexar arquivo para análise (PDF, DOCX, TXT, etc.)", type=["pdf", "docx", "txt", "md", "py"])

# Exibir Mensagens
for message in st.session_state.messages:
    role_label = "user" if message["role"] == "user" else "assistant"
    with st.chat_message(role_label):
        st.markdown(message["content"])

# Lógica de Chat
if prompt := st.chat_input("O que vamos construir hoje?"):
    if not st.session_state.api_key:
        st.error("Por favor, insira sua chave de API na barra lateral para começar.")
    else:
        # Processar arquivo se houver
        file_content = ""
        if uploaded_file:
            with st.spinner("Processando arquivo..."):
                file_content = process_uploaded_file(uploaded_file.name, uploaded_file.read())
                prompt = f"--- CONTEÚDO DO ARQUIVO ({uploaded_file.name}) ---\n{file_content}\n\n--- PERGUNTA DO USUÁRIO ---\n{prompt}"

        # Criar conversa no DB se for nova
        if st.session_state.current_conversation_id is None:
            title = prompt[:30] + "..."
            st.session_state.current_conversation_id = db.create_conversation(title, model_id, agent_option)
        
        # Adicionar mensagem do usuário
        st.session_state.messages.append({"role": "user", "content": prompt})
        db.add_message(st.session_state.current_conversation_id, "user", prompt)
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Resposta da IA
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                client = OpenAI(api_key=st.session_state.api_key)
                
                # Preparar mensagens para a API (incluindo System Prompt)
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
                
                # Salvar resposta no DB
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                db.add_message(st.session_state.current_conversation_id, "assistant", full_response)
                
                # Atualizar custo estimado (simplificado)
                tokens_est = (len(prompt) + len(full_response)) // 4
                cost_rate = MODEL_COSTS.get(model_id, {"input": 0.0001, "output": 0.0004})
                est_cost = (tokens_est / 1000) * cost_rate["output"]
                db.update_conversation_cost(st.session_state.current_conversation_id, est_cost)
                
            except Exception as e:
                st.error(f"Erro na chamada da API: {str(e)}")

# Rodapé e Exportação
if st.session_state.current_conversation_id and st.session_state.messages:
    st.divider()
    col_exp1, col_exp2, _ = st.columns([0.2, 0.2, 0.6])
    
    conv_data = next((c for c in conversations if c['id'] == st.session_state.current_conversation_id), {"title": "conversa"})
    
    json_data = export_conversation_to_json(conv_data, st.session_state.messages)
    col_exp1.download_button("📥 Exportar JSON", json_data, file_name=f"chatss_{st.session_state.current_conversation_id}.json")
    
    txt_data = export_conversation_to_text(conv_data, st.session_state.messages)
    col_exp2.download_button("📄 Exportar TXT", txt_data, file_name=f"chatss_{st.session_state.current_conversation_id}.txt")
