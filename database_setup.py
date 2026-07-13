# database_setup.py
import psycopg2
from psycopg2.extras import Json
import os
from dotenv import load_dotenv

load_dotenv()

def creer_base_donnees():
    """Crée la base de données et les tables nécessaires"""
    
    # Connexion à PostgreSQL (sans base spécifique)
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '')
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Créer la base si elle n'existe pas
    db_name = os.getenv('DB_NAME', 'chatbot_tourisme')
    cursor.execute(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
    if not cursor.fetchone():
        cursor.execute(f"CREATE DATABASE {db_name}")
        print(f"✅ Base de données '{db_name}' créée")
    
    cursor.close()
    conn.close()
    
    # Connexion à la nouvelle base pour créer les tables
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=db_name,
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '')
    )
    cursor = conn.cursor()
    
    # Créer la table users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            preferences JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Créer la table conversations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            message TEXT,
            reponse TEXT,
            role VARCHAR(50),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Créer la table logs_bi
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs_bi (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            ville VARCHAR(255),
            style VARCHAR(100),
            budget VARCHAR(50),
            satisfaction INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Créer les index pour les performances
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_user_id 
        ON conversations(user_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_logs_bi_user_id 
        ON logs_bi(user_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_logs_bi_timestamp 
        ON logs_bi(timestamp)
    """)
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("✅ Tables créées avec succès")

if __name__ == "__main__":
    creer_base_donnees()