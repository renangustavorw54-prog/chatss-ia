"""
Configurações do ChatSS IA
"""
import os
from pathlib import Path

# Diretórios
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"

# Criar diretórios se não existirem
DATA_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)

# Banco de dados
DATABASE_PATH = DATA_DIR / "chatss_ia.db"

# Modelos disponíveis
AVAILABLE_MODELS = {
    "GPT-4.1 Mini": "gpt-4.1-mini",
    "GPT-4.1 Nano": "gpt-4.1-nano",
    "Gemini 2.5 Flash": "gemini-2.5-flash",
    "GPT-4o": "gpt-4o",
    "GPT-4o Mini": "gpt-4o-mini",
    "GPT-3.5 Turbo": "gpt-3.5-turbo",
}

# Templates de agentes
AGENT_TEMPLATES = {
    "Assistente Geral": {
        "system_prompt": "Você é um assistente útil, criativo e inteligente.",
        "temperature": 0.7,
    },
    "Desenvolvedor Elite": {
        "system_prompt": "Você é um engenheiro de software sênior especializado em desenvolvimento full-stack. Você escreve código limpo, eficiente e bem documentado. Você sempre fornece soluções completas e funcionais.",
        "temperature": 0.3,
    },
    "Analista de Dados": {
        "system_prompt": "Você é um cientista de dados experiente. Você analisa dados, cria visualizações e fornece insights acionáveis baseados em evidências.",
        "temperature": 0.2,
    },
    "Escritor Criativo": {
        "system_prompt": "Você é um escritor talentoso e criativo. Você cria conteúdo envolvente, bem estruturado e adaptado ao público-alvo.",
        "temperature": 0.9,
    },
    "Tutor Educacional": {
        "system_prompt": "Você é um professor paciente e experiente. Você explica conceitos complexos de forma clara e didática, adaptando-se ao nível de conhecimento do aluno.",
        "temperature": 0.5,
    },
    "Consultor de Negócios": {
        "system_prompt": "Você é um consultor de negócios estratégico. Você fornece análises de mercado, estratégias de crescimento e soluções práticas para desafios empresariais.",
        "temperature": 0.6,
    },
}

# Configurações padrão
DEFAULT_SETTINGS = {
    "model": "gpt-4.1-mini",
    "temperature": 0.7,
    "max_tokens": 4000,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "stream": True,
}

# Limites de arquivo
MAX_FILE_SIZE_MB = 10
SUPPORTED_FILE_TYPES = {
    "text": [".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml"],
    "document": [".pdf", ".docx", ".doc"],
    "image": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
}

# Estimativa de custos (USD por 1K tokens)
MODEL_COSTS = {
    "gpt-4.1-mini": {"input": 0.0001, "output": 0.0004},
    "gpt-4.1-nano": {"input": 0.00005, "output": 0.0002},
    "gemini-2.5-flash": {"input": 0.00005, "output": 0.0002},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}
