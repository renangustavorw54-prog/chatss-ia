"""
Processamento de arquivos e exportação para ChatSS IA
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Optional
import PyPDF2
from docx import Document
from PIL import Image
import io

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extrai texto de um arquivo PDF"""
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extrai texto de um arquivo DOCX"""
    doc = Document(io.BytesIO(file_bytes))
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text

def process_uploaded_file(file_name: str, file_bytes: bytes) -> str:
    """Processa o arquivo enviado e retorna seu conteúdo de texto"""
    ext = Path(file_name).suffix.lower()
    
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(file_bytes)
    elif ext in [".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml"]:
        return file_bytes.decode("utf-8", errors="ignore")
    else:
        return f"[Arquivo {file_name} enviado, mas o formato não suporta extração direta de texto]"

def export_conversation_to_json(conversation: Dict, messages: List[Dict]) -> str:
    """Exporta a conversa para formato JSON"""
    data = {
        "conversation": conversation,
        "messages": messages
    }
    return json.dumps(data, indent=4, ensure_ascii=False)

def export_conversation_to_text(conversation: Dict, messages: List[Dict]) -> str:
    """Exporta a conversa para formato de texto legível"""
    output = f"Conversa: {conversation['title']}\n"
    output += f"Modelo: {conversation['model']}\n"
    output += f"Data: {conversation['created_at']}\n"
    output += "="*50 + "\n\n"
    
    for msg in messages:
        role = "VOCÊ" if msg['role'] == "user" else "IA"
        output += f"[{role}]:\n{msg['content']}\n\n"
        output += "-"*30 + "\n\n"
    
    return output
