import json
import os
import gradio as gr
from groq import Groq
import csv
import random
from datetime import datetime

# ==========================================
# CONFIGURATION : CLÉ API GROQ
# ==========================================
GROQ_API_KEY = "key"

try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"⚠️ Erreur d'initialisation Groq : {e}")
    client = None

DATA_FILE = "users_data.json"

# ==========================================
# GESTION DES UTILISATEURS & PERSISTANCE
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
# ENREGISTREMENT BI (BUSINESS INTELLIGENCE)
# ==========================================
def logger_interaction_bi(username, ville_detectee, style, budget):
    """Force l'écriture dans le fichier CSV au bon emplacement."""
    chemin_dossier = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
    nom_fichier = os.path.join(chemin_dossier, 'logs_tourisme.csv')
    
    # Si le fichier n'existe pas, on écrit l'en-tête d'abord
    fichier_existe = os.path.exists(nom_fichier)
    
    with open(nom_fichier, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not fichier_existe:
            writer.writerow(["Date", "Utilisateur", "Ville", "Style", "Budget", "Satisfaction"])
            
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            username,
            ville_detectee,
            style,
            budget,
            random.randint(4, 5)  # Simulation note de satisfaction élevée
        ])

# ==========================================
# INTELLIGENCE ARTIFICIELLE VIA GROQ
# ==========================================
def interroger_groq(prompt_systeme, message_utilisateur, historique_conversation):
    if not client:
        return "⚠️ L'API Groq n'est pas configurée."
    
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
# LOGIQUE PRINCIPALE DU CHATBOT
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
    3. Adapte tes suggestions au profil de {username_propre} (style et budget).
    """
    
    reponse = interroger_groq(prompt_systeme, message, profil["historique"])
    
    # 🕵️ Tentative simple d'extraction de la destination dans le message
    ville_detectee = "Monde"
    mots = message.replace(",", " ").replace(".", " ").split()
    for m in mots:
        if m[0].isupper() and m.lower() not in ["je", "tu", "il", "nous", "vous", "le", "la", "les", "un", "une", "pour"]:
            ville_detectee = m
            break

    # 🌟 ICI : APPEL DE LA FONCTION POUR ENREGISTRER DANS LE CSV BI !
    logger_interaction_bi(username_propre, ville_detectee, style, budget)

    donnees = charger_donnees()
    if username_propre in donnees:
        donnees[username_propre]["historique"].append({"role": "user", "content": message})
        donnees[username_propre]["historique"].append({"role": "assistant", "content": reponse})
        sauvegarder_donnees(donnees)

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
# INTERFACE GRAPHIQUE (AGRANDIE & NETTOYÉE)
# ==========================================
with gr.Blocks(title="Guide Touristique Virtuel IA", css=".gradio-container {background-color: #fdfdfd}") as demo:
    
    gr.Markdown("""
    # 🧭 Guide Touristique Virtuel IA
    ### Explorez le monde entier !
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

                # --- COLONNE CHATBOT (DROITE - ÉLARGIE ET NETTOYÉE) ---
                with gr.Column(scale=3):
                    chatbot_ui = gr.Chatbot(label="🤖 Chatbot", height=650) # Hauteur augmentée
                    
                    with gr.Row():
                        txt_input = gr.Textbox(
                            show_label=False,             # Supprime le texte "zone de texte" ou "Textbox"
                            label=None,
                            placeholder="Posser une question...", # Placeholder modifié
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