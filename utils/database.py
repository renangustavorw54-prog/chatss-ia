"""
Gerenciamento de banco de dados para ChatSS IA
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from config.settings import DATABASE_PATH


class DatabaseManager:
    """Gerencia o banco de dados SQLite para histórico de conversas"""
    
    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializa o banco de dados com as tabelas necessárias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela de conversas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                model TEXT,
                agent_template TEXT,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost REAL DEFAULT 0.0
            )
        """)
        
        # Tabela de mensagens
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tokens INTEGER DEFAULT 0,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        """)
        
        # Tabela de configurações
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def create_conversation(self, title: str, model: str, agent_template: str) -> int:
        """Cria uma nova conversa e retorna o ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO conversations (title, model, agent_template)
            VALUES (?, ?, ?)
        """, (title, model, agent_template))
        
        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return conversation_id
    
    def add_message(self, conversation_id: int, role: str, content: str, tokens: int = 0):
        """Adiciona uma mensagem a uma conversa"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO messages (conversation_id, role, content, tokens)
            VALUES (?, ?, ?, ?)
        """, (conversation_id, role, content, tokens))
        
        # Atualizar timestamp da conversa
        cursor.execute("""
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP,
                total_tokens = total_tokens + ?
            WHERE id = ?
        """, (tokens, conversation_id))
        
        conn.commit()
        conn.close()
    
    def get_conversations(self, limit: int = 50) -> List[Dict]:
        """Retorna lista de conversas ordenadas por data de atualização"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, created_at, updated_at, model, agent_template, 
                   total_tokens, estimated_cost
            FROM conversations
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))
        
        conversations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return conversations
    
    def get_messages(self, conversation_id: int) -> List[Dict]:
        """Retorna todas as mensagens de uma conversa"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, role, content, timestamp, tokens
            FROM messages
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        """, (conversation_id,))
        
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return messages
    
    def delete_conversation(self, conversation_id: int):
        """Deleta uma conversa e todas as suas mensagens"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        
        conn.commit()
        conn.close()
    
    def update_conversation_title(self, conversation_id: int, title: str):
        """Atualiza o título de uma conversa"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE conversations
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (title, conversation_id))
        
        conn.commit()
        conn.close()
    
    def update_conversation_cost(self, conversation_id: int, cost: float):
        """Atualiza o custo estimado de uma conversa"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE conversations
            SET estimated_cost = estimated_cost + ?
            WHERE id = ?
        """, (cost, conversation_id))
        
        conn.commit()
        conn.close()
    
    def search_messages(self, query: str, limit: int = 20) -> List[Dict]:
        """Busca mensagens por conteúdo"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT m.*, c.title as conversation_title
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.content LIKE ?
            ORDER BY m.timestamp DESC
            LIMIT ?
        """, (f"%{query}%", limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas gerais de uso"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_conversations = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(total_tokens) FROM conversations")
        total_tokens = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(estimated_cost) FROM conversations")
        total_cost = cursor.fetchone()[0] or 0.0
        
        conn.close()
        
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
        }
    
    def save_setting(self, key: str, value: str):
        """Salva uma configuração"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (key, value))
        
        conn.commit()
        conn.close()
    
    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Recupera uma configuração"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        
        conn.close()
        
        return result[0] if result else default
