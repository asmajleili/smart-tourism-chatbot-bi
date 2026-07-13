import json
import os
import sqlite3
import re
from datetime import datetime
import gradio as gr
from groq import Groq

# ==========================================
# CONFIGURATION : CLÉ API GROQ
# ==========================================
# ⚠️ Remplace par ta vraie clé API Groq (ex: "gsk_xxxx...")
GROQ_API_KEY = "key"

try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"⚠️ Erreur d'initialisation Groq : {e}")
    client = None

DATA_FILE = "users_data.json"
DB_FILE = "tourisme_analytics.db"  # 📂 Base de données exploitée par Power BI

# ==========================================
# INITIALISATION DE LA BASE BI (AUTOMATIQUE)
# ==========================================
def initialiser_base_bi():
    """Crée la table de suivi analytique si elle n'existe pas encore."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions_tourisme (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                date_heure TEXT,
                style_voyage TEXT,
                budget TEXT,
                destination_detectee TEXT,
                message_utilisateur TEXT,
                document_utilise INTEGER
            )
        """)
        conn.commit()
        conn.close()
        print(f"✔️ Base de données SQLite BI initialisée avec succès ({DB_FILE})")
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la base BI : {e}")

# Lancement de l'initialisation au démarrage de l'application
initialiser_base_bi()

# ==========================================
# GESTION DES UTILISATEURS & PERSISTANCE JSON
# ==========================================
def charger_donnees():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def sauvegarder_donnees(donnees):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=4)

def obtenir_ou_creer_profil(username):
    donnees = charger_donnees()
    username = username.strip() or "Explorateur Anonyme"
    if username not in donnees:
        donnees[username] = {"preferences": {"style": "Culture", "budget": "Moyen"}, "historique": []}
        sauvegarder_donnees(donnees)
    return donnees[username], username

def enregistrer_preferences_globales(username, style, budget):
    donnees = charger_donnees()
    _, username_propre = obtenir_ou_creer_profil(username)
    
    donnees[username_propre]["preferences"] = {"style": style, "budget": budget}
    sauvegarder_donnees(donnees)
    return f"ℹ️ Préférences enregistrées pour {username_propre} !"

def analyser_document(file):
    if file is None:
        return "ℹ️ Aucun document chargé", ""
    try:
        with open(file.name, "r", encoding="utf-8") as f:
            contenu = f.read()
        nom_fichier = os.path.basename(file.name)
        return f"✔️ Document chargé : {nom_fichier}", contenu
    except Exception as e:
        return f"❌ Erreur de lecture : {str(e)}", ""

# ==========================================
# ENREGISTREMENT AUTOMATIQUE DES MÉTRIQUES BI
# ==========================================
def extraire_destination(message):
    """Petite logique regex pour tenter de capter un lieu (ex: à Paris, au Japon, vers Rome)."""
    match = re.search(r"(?:à|au|aux|en|vers|pour|visiter)\s+([A-Z][a-zA-ZÀ-ÿ\-]+)", message)
    if match:
        return match.group(1)
    return "Non spécifiée"

def enregistrer_metrique_bi(username, style, budget, message, doc_charge):
    """Enregistre de manière structurée chaque interaction dans la base SQLite."""
    try:
        destination = extraire_destination(message)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interactions_tourisme (username, date_heure, style_voyage, budget, destination_detectee, message_utilisateur, document_utilise)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            username, 
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
            style, 
            budget,
            destination,
            message[:250],  # On stocke un extrait de la question
            1 if doc_charge else 0
        ))
        conn.commit()
        conn.close()
        print("✔️ Métriques BI enregistrées dans SQLite.")
    except Exception as e:
        print(f"⚠️ Erreur lors de la sauvegarde des métriques BI : {e}")

# ==========================================
# INTELLIGENCE ARTIFICIELLE VIA GROQ
# ==========================================
def interroger_groq(prompt_systeme, message_utilisateur, historique_conversation):
    if not client or GROQ_API_KEY == "METS_TA_CLE_GROQ_ICI":
        return "⚠️ L'API Groq n'est pas configurée. Veuillez ajouter une clé API valide dans le code."
    
    messages = [{"role": "system", "content": prompt_systeme}]
    for echange in historique_conversation[-6:]:
        messages.append({"role": echange["role"], "content": echange["content"]})
    messages.append({"role": "user", "content": message_utilisateur})
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=1024
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"❌ Erreur API Groq : {str(e)}"

# ==========================================
# LOGIQUE PRINCIPALE DU CHATBOT (AVEC INJECTION BI)
# ==========================================
def repondre_chatbot(message, historique, username, style, budget, contenu_doc):
    if not message.strip():
        return "", historique

    profil, username_propre = obtenir_ou_creer_profil(username)
    contexte_document = f"\nInformations complémentaires issues du document chargé :\n{contenu_doc}" if contenu_doc else ""

    prompt_systeme = f"""
    Tu es 'Guide Touristique Virtuel IA 🗺️', un conseiller expert pour les voyages partout dans le monde.
    L'utilisateur s'appelle {username_propre}.
    
    CRITÈRES À RESPECTER :
    - Style de voyage : {style}
    - Budget : {budget}
    {contexte_document}
    
    Consignes :
    1. Réponds en Français de manière structurée avec des puces Markdown.
    2. Utilise des emojis pour rendre le chat vivant.
    3. Adapte tes suggestions mondiales au profil de {username_propre}.
    """
    
    reponse = interroger_groq(prompt_systeme, message, profil["historique"])
    
    # 1. Sauvegarde pour l'historique de conversation (JSON)
    donnees = charger_donnees()
    if username_propre in donnees:
        donnees[username_propre]["historique"].append({"role": "user", "content": message})
        donnees[username_propre]["historique"].append({"role": "assistant", "content": reponse})
        sauvegarder_donnees(donnees)

    # 2. 🚀 ENREGISTREMENT AUTOMATIQUE DANS LA BASE SQLITE POUR POWER BI
    enregistrer_metrique_bi(username_propre, style, budget, message, doc_charge=bool(contenu_doc))

    historique.append({"role": "user", "content": message})
    historique.append({"role": "assistant", "content": reponse})
    
    return "", historique

def charger_profil_utilisateur(username):
    profil, username_propre = obtenir_ou_creer_profil(username)
    
    historique_gradio = []
    for echange in profil.get("historique", []):
        historique_gradio.append({"role": echange["role"], "content": echange["content"]})
        
    prefs = profil.get("preferences", {"style": "Culture", "budget": "Moyen"})
    
    if isinstance(prefs, list):
        style_sauvegarde = "Culture"
        budget_sauvegarde = "Moyen"
    else:
        style_sauvegarde = prefs.get("style", "Culture")
        budget_sauvegarde = prefs.get("budget", "Moyen")
    
    return (
        historique_gradio, 
        f"👤 Connecté en tant que : {username_propre}", 
        gr.update(value=style_sauvegarde), 
        gr.update(value=budget_sauvegarde)
    )

# ==========================================
# INTERFACE GRAPHIQUE GRADIO
# ==========================================
with gr.Blocks(title="Guide Touristique Virtuel IA", css=".gradio-container {background-color: #fdfdfd}") as demo:
    
    gr.Markdown("""
    # 🧭 Guide Touristique Virtuel IA
    ### Explorez le monde entier avec l'intelligence de Llama 3 & Groq et suivez l'activité en temps réel sur Power BI !
    """)
    
    document_text_storage = gr.State(value="")
    
    with gr.Tabs():
        with gr.TabItem("💬 Chat"):
            with gr.Row():
                
                # --- COLONNE PARAMÈTRES (GAUCHE) ---
                with gr.Column(scale=1):
                    
                    gr.Markdown("### 👤 Session Utilisateur")
                    username_input = gr.Textbox(
                        value="Explorateur Anonyme", 
                        label="Nom d'utilisateur / Prénom", 
                        placeholder="Tapez votre nom...",
                        max_lines=1
                    )
                    btn_charger_profil = gr.Button("🔄 Se connecter / Charger le profil", variant="secondary")
                    status_user = gr.HTML(value="👤 Mode invité : Explorateur Anonyme")
                    
                    gr.Markdown("---")
                    
                    gr.Markdown("📄 **Document touristique (optionnel)**")
                    file_input = gr.File(label=None, file_types=[".txt", ".md", ".json"], interactive=True)
                    btn_charger_doc = gr.Button("📂 Charger le document", variant="primary")
                    status_doc = gr.HTML(value="ℹ️ Aucun document chargé")
                    
                    gr.Markdown("---")
                    
                    style_input = gr.Dropdown(
                        choices=["Culture", "Nature & Randonnée", "Gastronomie", "Aventure", "Détente"], 
                        label="Style de voyage", 
                        value="Culture"
                    )
                    budget_input = gr.Dropdown(
                        choices=["Économique", "Moyen", "Luxe"], 
                        label="Budget", 
                        value="Moyen"
                    )
                    
                    btn_save_prefs = gr.Button("💾 Enregistrer les préférences")
                    status_prefs = gr.Markdown("")
                    
                    gr.Markdown("---")
                    
                    with gr.Accordion("📁 Historique des conversations", open=False):
                        btn_reload_history = gr.Button("🔄 Recharger mes données de session")

                # --- COLONNE CHATBOT (DROITE) ---
                with gr.Column(scale=3):
                    chatbot_ui = gr.Chatbot(label="🤖 Chatbot", height=650, type="messages")
                    
                    with gr.Row():
                        txt_input = gr.Textbox(
                            show_label=False,        
                            label=None,              
                            placeholder="Posez une question...", 
                            lines=1,
                            scale=5                  
                        )
                        btn_envoyer = gr.Button("Envoyer", variant="primary", scale=1)

    # --- LIAISONS D'ÉVÉNEMENTS ---
    btn_charger_profil.click(charger_profil_utilisateur, inputs=[username_input], outputs=[chatbot_ui, status_user, style_input, budget_input])
    username_input.submit(charger_profil_utilisateur, inputs=[username_input], outputs=[chatbot_ui, status_user, style_input, budget_input])
    btn_reload_history.click(charger_profil_utilisateur, inputs=[username_input], outputs=[chatbot_ui, status_user, style_input, budget_input])
    
    btn_charger_doc.click(analyser_document, inputs=[file_input], outputs=[status_doc, document_text_storage])
    btn_save_prefs.click(enregistrer_preferences_globales, inputs=[username_input, style_input, budget_input], outputs=[status_prefs])
    
    inputs_chat = [txt_input, chatbot_ui, username_input, style_input, budget_input, document_text_storage]
    outputs_chat = [txt_input, chatbot_ui]
    
    btn_envoyer.click(repondre_chatbot, inputs=inputs_chat, outputs=outputs_chat)
    txt_input.submit(repondre_chatbot, inputs=inputs_chat, outputs=outputs_chat)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", theme="soft")