# 🤖 ChatSS IA - Elite Agent GPT

O **ChatSS IA** é um aplicativo de chat avançado e exclusivo, desenvolvido para oferecer uma experiência de inteligência artificial ilimitada e profissional. Ele combina a potência dos modelos GPT da OpenAI com funcionalidades de elite para desenvolvedores, analistas e escritores.

## 🚀 Funcionalidades Principais

- **Acesso Ilimitado**: Utilize sua própria chave de API da OpenAI para ter controle total sobre o uso e custos.
- **Histórico Persistente**: Todas as suas conversas são salvas automaticamente em um banco de dados local (SQLite), permitindo que você nunca perca uma ideia.
- **Múltiplos Modelos**: Suporte para GPT-4o, GPT-4.1 Mini/Nano, Gemini 2.5 Flash e outros.
- **Templates de Agentes**: Escolha entre perfis especializados como Desenvolvedor Elite, Analista de Dados, Escritor Criativo e mais.
- **Análise de Arquivos**: Faça upload de PDFs, documentos Word (.docx) e arquivos de código para análise imediata pela IA.
- **Exportação Flexível**: Exporte suas conversas importantes para formatos JSON ou TXT com um clique.
- **Estatísticas de Uso**: Acompanhe o consumo de tokens e o custo estimado das suas interações.

## 🛠️ Como Instalar e Rodar

1. **Clone o repositório**:
   ```bash
   git clone <link-do-seu-repositorio>
   cd chatss-ia
   ```

2. **Instale as dependências**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Execute o aplicativo**:
   ```bash
   streamlit run app.py
   ```

4. **Configure sua API**:
   Insira sua chave de API da OpenAI na barra lateral do aplicativo para começar a usar.

## 📂 Estrutura do Projeto

- `app.py`: Aplicativo principal Streamlit.
- `config/`: Configurações de modelos e templates.
- `utils/`: Módulos de banco de dados, processamento de arquivos e exportação.
- `data/`: Local onde o histórico de conversas é armazenado com segurança.

## 🛡️ Privacidade
O ChatSS IA foi projetado para ser privado. Suas conversas e chaves de API são armazenadas apenas localmente no seu dispositivo.

---
Desenvolvido com foco em performance e produtividade.
