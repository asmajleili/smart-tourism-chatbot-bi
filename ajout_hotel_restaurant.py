
import json
import os
import gradio as gr
from groq import Groq
import psycopg2
from psycopg2 import sql
import random
from datetime import datetime
import re

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
# CONFIGURATION : PARAMÈTRES POSTGRESQL
# ==========================================
DB_CONFIG = {
    "host": "localhost",
    "database": "chatbot_tourisme",
    "user": "postgres",
    "password": "admin",
    "port": "5432"
}

def initialiser_base_postgres():
    """Crée les tables nécessaires si elles n'existent pas."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding('utf8')
        cur = conn.cursor()
        
        # Table bi_logs mise à jour avec hotel
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bi_logs (
                id SERIAL PRIMARY KEY,
                date_heure TIMESTAMP,
                utilisateur TEXT,
                ville TEXT,
                restaurant TEXT,
                hotel TEXT,
                style TEXT,
                budget TEXT,
                satisfaction INTEGER
            );
        """)
        
        # Nouvelle table pour les hôtels
        cur.execute("""
            CREATE TABLE IF NOT EXISTS hotels (
                id SERIAL PRIMARY KEY,
                nom TEXT NOT NULL,
                ville TEXT NOT NULL,
                categorie TEXT,
                prix_nuit_min INTEGER,
                prix_nuit_max INTEGER,
                note DECIMAL(3,1),
                nb_etoiles INTEGER,
                equipements TEXT[],
                description TEXT,
                date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("✔️ Base PostgreSQL connectée avec succès. Tables mises à jour.")
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de PostgreSQL : {e}")

initialiser_base_postgres()

# ==========================================
# FONCTION DE NETTOYAGE AVANCÉ
# ==========================================
def nettoyer_nom_etablissement(nom):
    """Nettoie le nom d'un établissement en supprimant les mots parasites."""
    if not nom or nom == "Inconnu":
        return "Inconnu"
    
    # Liste des mots parasites à supprimer
    mots_parasites = [
        'comment', 'faire', 'réserver', 'reserver', 'pour', 'avec', 'sans',
        'près', 'de', 'du', 'des', 'à', 'en', 'dans', 'sur', 'sous',
        'est', 'et', 'ou', 'mais', 'donc', 'car', 'ni', 'que', 'qui',
        'hotel', 'hôtel', 'restaurant', 'auberge', 'pension', 'logis', 'resort',
        'magnifique', 'superbe', 'excellent', 'parfait', 'formidable'
    ]
    
    # Nettoyer le nom
    nom_clean = nom.lower()
    
    # Supprimer les mots parasites
    for mot in mots_parasites:
        if nom_clean.startswith(mot + ' '):
            nom_clean = nom_clean[len(mot) + 1:]
        if nom_clean.endswith(' ' + mot):
            nom_clean = nom_clean[:-len(mot) - 1]
        nom_clean = re.sub(r'\s+' + mot + r'\s+', ' ', nom_clean)
    
    # Supprimer les mots "hôtel" ou "hotel" s'ils sont au début
    nom_clean = re.sub(r'^(hôtel|hotel)\s+', '', nom_clean, flags=re.IGNORECASE)
    nom_clean = re.sub(r'^restaurant\s+', '', nom_clean, flags=re.IGNORECASE)
    
    # Nettoyer les espaces multiples
    nom_clean = re.sub(r'\s+', ' ', nom_clean).strip()
    
    # Remettre en majuscule la première lettre de chaque mot
    mots = nom_clean.split()
    nom_clean = ' '.join([mot.capitalize() if len(mot) > 2 else mot for mot in mots])
    
    return nom_clean if nom_clean else "Inconnu"

# ==========================================
# EXTRACTION INTELLIGENTE AVEC NETTOYAGE AVANCÉ
# ==========================================
def extraire_entites_bi(message_utilisateur):
    """Analyse le message pour extraire la ville, le restaurant et l'hôtel avec nettoyage."""
    if not client:
        return "Monde", "Inconnu", "Inconnu"
    
    ville_trouvee = None
    restaurant_trouve = None
    hotel_trouve = None
    
    message_clean = message_utilisateur
    
    # ===== 1. Détection des HÔTELS =====
    patterns_hotel = [
        r'(?:hôtel|hotel)\s+([\w\s\-\']+?)(?:\s+à|\s+en|\s+dans|\s+près|\s+de|,|\.|$|;|\s+pour|\s+comment)',
        r'([\w\s\-\']+?)\s+(?:hôtel|hotel)(?:\s+à|\s+en|\s+dans|,|\.|$|;|\s+pour|\s+comment)',
        r'séjourner\s+à\s+l\'?hôtel\s+([\w\s\-\']+?)(?:\s+à|\s+dans|,|\.|$|;|\s+pour|\s+comment)',
        r'loger\s+à\s+([\w\s\-\']+?)\s+(?:hôtel|hotel)',
        r'réserver\s+chez\s+([\w\s\-\']+?)(?:\s+à|\s+dans|,|\.|$|;|\s+pour|\s+comment)',
        r'séjour\s+au\s+([\w\s\-\']+?)(?:\s+à|\s+dans|,|\.|$|;|\s+pour|\s+comment)',
        r'(?i)(?:Novotel|Ibis|Mercure|Sofitel|Pullman|Hilton|Marriott|Sheraton|Holiday Inn|Best Western|Radisson|Ritz|Four Seasons|Shangri-La|Bristol|Meurice|Negresco|Carlton|Majestic|Palace)\s+[\w\s]+?(?:\s+à|\s+dans|,|\.|$|;|\s+pour|\s+comment|\s+à\s+Paris)',
        r'(?i)(?:Le\s+)?(?:Meurice|Ritz|Bristol|Negresco|Carlton|Majestic|Plaza|Athénée|Crillon|George V|Novotel|Ibis|Mercure|Sofitel|Pullman)(?:\s+[\w\s]+?)?(?:\s+à|\s+dans|,|\.|$|;|\s+pour|\s+comment)',
    ]
    
    for pattern in patterns_hotel:
        match = re.search(pattern, message_clean, re.IGNORECASE)
        if match:
            hotel_trouve = match.group(1).strip() if len(match.groups()) > 0 else match.group(0).strip()
            hotel_trouve = nettoyer_nom_etablissement(hotel_trouve)
            if hotel_trouve and hotel_trouve != "Inconnu" and len(hotel_trouve) > 2:
                break
    
    # ===== 2. Détection spécifique : "Novotel Paris Tour Eiffel" =====
    if not hotel_trouve or hotel_trouve == "Inconnu":
        patterns_novotel = [
            r'(?i)(Novotel\s+Paris\s+Tour\s+Eiffel)',
            r'(?i)(Novotel\s+Paris\s+Tour\s+Eiffel)\s+comment',
            r'(?i)(Novotel\s+Paris\s+Tour\s+Eiffel)\s+faire',
            r'(?i)(Novotel\s+Paris\s+Tour\s+Eiffel)\s+réserver',
        ]
        for pattern in patterns_novotel:
            match = re.search(pattern, message_clean, re.IGNORECASE)
            if match:
                hotel_trouve = "Novotel Paris Tour Eiffel"
                if not ville_trouvee:
                    ville_trouvee = "Paris"
                break
    
    # ===== 3. Détection des RESTAURANTS =====
    patterns_restaurant = [
        r'(?:restaurant|chez)\s+([\w\s\-\']+?)(?:\s+à|\s+en|\s+dans|,|\.|$|;|\s+pour|\s+comment)',
        r'([\w\s\-\']+?)\s+est\s+un\s+restaurant',
        r'le\s+([\w\s\-\']+?)(?:\s+à|\s+à\s+Paris|\s+dans|,|\.|$|;|\s+pour|\s+comment)',
        r'([\w\s\-\']+?)\s+est\s+le\s+restaurant',
        r'dîner\s+au\s+([\w\s\-\']+?)(?:\s+à|\s+dans|,|\.|$|;|\s+pour|\s+comment)',
        r'manger\s+au\s+([\w\s\-\']+?)(?:\s+à|\s+dans|,|\.|$|;|\s+pour|\s+comment)',
    ]
    
    for pattern in patterns_restaurant:
        match = re.search(pattern, message_clean, re.IGNORECASE)
        if match:
            restaurant_trouve = match.group(1).strip() if len(match.groups()) > 0 else match.group(0).strip()
            restaurant_trouve = nettoyer_nom_etablissement(restaurant_trouve)
            if restaurant_trouve and restaurant_trouve != "Inconnu" and len(restaurant_trouve) > 2:
                break
    
    # ===== 4. Détection des VILLES =====
    patterns_ville = [
        r'(?:à|en|au|aux|dans|vers|près\s+de)\s+([A-Z][a-zéèêëïîôûùçâäàéèêëïîôûùÿñ\-\s]+?)(?:\s+avec|\s+et|\s+pour|,|\.|$|;|\s+près|\s+à\s+Paris|\s+en\s+France|\))',
        r'(?:ville\s+de\s+)([A-Z][a-zéèêëïîôûùçâäàéèêëïîôûùÿñ\-\s]+?)(?:\s+avec|\s+et|,|\.|$|;)',
        r'([A-Z][a-zéèêëïîôûùçâäàéèêëïîôûùÿñ\-\s]+?)(?:,|\s+en\s+France|\s+en\s+Europe)',
    ]
    
    mots_ignores = ['avec', 'et', 'pour', 'sans', 'contre', 'pendant', 'depuis', 'sur', 'sous', 'comment', 'faire']
    
    for pattern in patterns_ville:
        match = re.search(pattern, message_clean, re.IGNORECASE)
        if match:
            ville_candidate = match.group(1).strip()
            if ville_candidate.lower() not in [m.lower() for m in mots_ignores]:
                ville_candidate = re.sub(r'\s+(?:avec|et|pour|sans|comment|faire)$', '', ville_candidate, flags=re.IGNORECASE)
                if len(ville_candidate) > 2:
                    ville_trouvee = ville_candidate
                    break
    
    # ===== 5. Extraction de la ville depuis le nom de l'hôtel =====
    if hotel_trouve and hotel_trouve != "Inconnu" and not ville_trouvee:
        match_ville_dans_hotel = re.search(r'(?i)(?:à\s+)?([A-Z][a-zéèêëïîôûùç\-]+)(?:\s+Tour\s+Eiffel|\s+Centre|\s+Opéra|\s+Louvre|\s+Champs)?$', hotel_trouve)
        if match_ville_dans_hotel:
            ville_trouvee = match_ville_dans_hotel.group(1)
    
    # ===== 6. Utiliser l'IA si nécessaire =====
    if (restaurant_trouve or hotel_trouve) and not ville_trouvee:
        try:
            prompt_ville = f"""
            Les établissements mentionnés sont : 
            Restaurant: {restaurant_trouve if restaurant_trouve else 'Aucun'}
            Hôtel: {hotel_trouve if hotel_trouve else 'Aucun'}
            Dans quelle ville se trouve(nt)-ils ? Réponds UNIQUEMENT par le nom de la ville.
            """
            completion = client.chat.completions.create(
                model="llama-3-8b-instant",
                messages=[
                    {"role": "system", "content": "Tu es un assistant qui donne UNIQUEMENT le nom de la ville."},
                    {"role": "user", "content": prompt_ville}
                ],
                temperature=0
            )
            ville_trouvee = completion.choices[0].message.content.strip()
            if ville_trouvee.lower() in ['monde', 'inconnu', 'aucune', 'non spécifié', '']:
                ville_trouvee = None
        except Exception:
            pass
    
    # ===== 7. Extraction complète via API Groq =====
    if not (ville_trouvee or restaurant_trouve or hotel_trouve):
        prompt_extraction = f"""
        Extrais UNIQUEMENT ces informations du message utilisateur :
        1. La ville ou pays - si non mentionné: "Monde"
        2. Le nom du restaurant - si non mentionné: "Inconnu"
        3. Le nom de l'hôtel - si non mentionné: "Inconnu"
        
        IMPORTANT : 
        - Si le message contient "Novotel Paris Tour Eiffel", l'hôtel est "Novotel Paris Tour Eiffel" et la ville est "Paris"
        - Nettoie les noms : supprime "comment faire", "réserver", etc.
        
        Message : "{message_utilisateur}"
        
        Réponds UNIQUEMENT sous ce format strict :
        VILLE | RESTAURANT | HOTEL
        """
        
        try:
            completion = client.chat.completions.create(
                model="llama-3-8b-instant",
                messages=[
                    {"role": "system", "content": "Réponds UNIQUEMENT au format : Ville | Restaurant | Hotel"},
                    {"role": "user", "content": prompt_extraction}
                ],
                temperature=0
            )
            reponse = completion.choices[0].message.content.strip()
            
            if "|" in reponse:
                parts = reponse.split("|")
                ville = parts[0].strip() if len(parts) > 0 else "Monde"
                resto = parts[1].strip() if len(parts) > 1 else "Inconnu"
                hotel = parts[2].strip() if len(parts) > 2 else "Inconnu"
                
                ville = nettoyer_nom_etablissement(ville)
                resto = nettoyer_nom_etablissement(resto)
                hotel = nettoyer_nom_etablissement(hotel)
                
                if ville.lower() in ["monde", "inconnu", "aucune", "non spécifié", ""]:
                    ville = None
                if resto.lower() in ["inconnu", "aucun", "non spécifié", ""]:
                    resto = None
                if hotel.lower() in ["inconnu", "aucun", "non spécifié", ""]:
                    hotel = None
                    
                return (ville or "Monde"), (resto or "Inconnu"), (hotel or "Inconnu")
        except Exception as e:
            print(f"⚠️ Erreur d'extraction IA : {e}")
    
    # Nettoyage final
    if ville_trouvee:
        ville_trouvee = nettoyer_nom_etablissement(ville_trouvee)
        if ville_trouvee.lower() in ["monde", "inconnu", "aucune", "non spécifié", ""]:
            ville_trouvee = "Monde"
    else:
        ville_trouvee = "Monde"
    
    if restaurant_trouve:
        restaurant_trouve = nettoyer_nom_etablissement(restaurant_trouve)
        if restaurant_trouve.lower() in ["inconnu", "aucun", "non spécifié", ""]:
            restaurant_trouve = "Inconnu"
    else:
        restaurant_trouve = "Inconnu"
    
    if hotel_trouve:
        hotel_trouve = nettoyer_nom_etablissement(hotel_trouve)
        if hotel_trouve.lower() in ["inconnu", "aucun", "non spécifié", ""]:
            hotel_trouve = "Inconnu"
    else:
        hotel_trouve = "Inconnu"
    
    return ville_trouvee, restaurant_trouve, hotel_trouve

# ==========================================
# GESTION DES UTILISATEURS & PERSISTANCE LOCAL
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

def supprimer_historique(username):
    if not username or username.strip() == "":
        return [], "⚠️ Veuillez entrer un nom d'utilisateur valide."
    
    username_propre = username.strip()
    donnees = charger_donnees()
    
    if username_propre in donnees:
        donnees[username_propre]["historique"] = []
        sauvegarder_donnees(donnees)
        return [], f"✅ L'historique de '{username_propre}' a été supprimé avec succès !"
    else:
        return [], f"⚠️ Aucun profil trouvé pour '{username_propre}'."

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
# ENREGISTREMENT BI AVEC HÔTEL
# ==========================================
def logger_interaction_postgres(username, ville_detectee, resto_detecte, hotel_detecte, style, budget):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding('utf8')
        cur = conn.cursor()
        
        print(f"📝 Insertion BI - Utilisateur: {username}, Ville: {ville_detectee}, Restaurant: {resto_detecte}, Hôtel: {hotel_detecte}")
        
        cur.execute(
            """INSERT INTO bi_logs (date_heure, utilisateur, ville, restaurant, hotel, style, budget, satisfaction) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (datetime.now(), username, ville_detectee, resto_detecte, hotel_detecte, style, budget, random.randint(4, 5))
        )
        
        if hotel_detecte and hotel_detecte != "Inconnu" and ville_detectee and ville_detectee != "Monde":
            inserer_hotel_dans_table(hotel_detecte, ville_detectee)
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Données BI insérées avec succès !")
        print(f"   📍 Destination: {ville_detectee}")
        print(f"   🍽️ Restaurant: {resto_detecte}")
        print(f"   🏨 Hôtel: {hotel_detecte}")
    except Exception as e:
        print(f"❌ Erreur lors de l'insertion des métriques dans PostgreSQL : {e}")

def inserer_hotel_dans_table(nom_hotel, ville):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM hotels WHERE nom = %s AND ville = %s", (nom_hotel, ville))
        resultat = cur.fetchone()
        
        if not resultat:
            categories = ["Luxe", "Confort", "Standard", "Économique", "Boutique", "Resort", "Design"]
            equipements_possibles = ["WiFi", "Piscine", "Spa", "Restaurant", "Parking", "Climatisation", 
                                   "Salle de sport", "Petit-déjeuner", "Service d'étage", "Conciergerie", 
                                   "Terrasse", "Jacuzzi", "Sauna", "Hammam", "Salon de beauté"]
            nb_equipements = random.randint(3, 7)
            equipements = random.sample(equipements_possibles, min(nb_equipements, len(equipements_possibles)))
            
            prix_min = random.randint(60, 350)
            prix_max = prix_min + random.randint(50, 400)
            nb_etoiles = random.randint(2, 5)
            note = round(random.uniform(3.5, 4.9), 1)
            
            cur.execute("""
                INSERT INTO hotels 
                (nom, ville, categorie, prix_nuit_min, prix_nuit_max, note, nb_etoiles, equipements, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                nom_hotel,
                ville,
                random.choice(categories),
                prix_min,
                prix_max,
                note,
                nb_etoiles,
                equipements,
                f"Magnifique hôtel situé à {ville}, offrant un séjour confortable et agréable. {nb_etoiles} étoiles pour un service de qualité."
            ))
            
            print(f"   🏨 Nouvel hôtel ajouté : {nom_hotel} à {ville} ({nb_etoiles}⭐)")
        else:
            print(f"   🏨 L'hôtel '{nom_hotel}' existe déjà dans la base.")
        
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"⚠️ Erreur lors de l'insertion de l'hôtel : {e}")

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

    ville_detectee, resto_detecte, hotel_detecte = extraire_entites_bi(message)
    
    print(f"🔍 Extraction - Message: '{message}'")
    print(f"   Ville détectée: '{ville_detectee}'")
    print(f"   Restaurant détecté: '{resto_detecte}'")
    print(f"   Hôtel détecté: '{hotel_detecte}'")

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
    4. Si l'utilisateur mentionne un hôtel, donne des informations sur cet hôtel.
    """
    
    reponse = interroger_groq(prompt_systeme, message, profil["historique"])

    logger_interaction_postgres(username_propre, ville_detectee, resto_detecte, hotel_detecte, style, budget)

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
# INTERFACE GRAPHIQUE (GRADIO)
# ==========================================
with gr.Blocks(title="Guide Touristique Virtuel IA", css=".gradio-container {background-color: #fdfdfd}") as demo:
    
    gr.Markdown("""
    # 🧭 Guide Touristique Virtuel IA
    ### Explorez le monde entier et alimentez votre Dashboard BI !
    """)
    
    document_text_storage = gr.State(value="")
    
    with gr.Tabs():
        with gr.TabItem("💬 Chat"):
            with gr.Row():
                
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
                        gr.Markdown("---")
                        btn_supprimer_history = gr.Button("🗑️ Supprimer tout l'historique", variant="stop")
                        status_suppression = gr.Markdown("")
                    
                    suppression_state = gr.State(value="")

                with gr.Column(scale=3):
                    chatbot_ui = gr.Chatbot(label="🤖 Chatbot", height=650)
                    
                    with gr.Row():
                        txt_input = gr.Textbox(
                            show_label=False,
                            label=None,
                            placeholder="Ex: Quels hôtels et restaurants recommandez-vous à Paris ?",
                            lines=1,
                            scale=5
                        )
                        btn_envoyer = gr.Button("Envoyer", variant="primary", scale=1)

        with gr.TabItem("🏨 Hôtels"):
            gr.Markdown("""
            ### 🏨 Hôtels détectés dans les conversations
            Les hôtels mentionnés par les utilisateurs sont automatiquement enregistrés ici.
            """)
            
            def afficher_hotels():
                try:
                    conn = psycopg2.connect(**DB_CONFIG)
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT nom, ville, nb_etoiles, note, prix_nuit_min, prix_nuit_max, equipements, date_ajout
                        FROM hotels 
                        ORDER BY date_ajout DESC 
                        LIMIT 15
                    """)
                    resultats = cur.fetchall()
                    cur.close()
                    conn.close()
                    
                    if not resultats:
                        return "ℹ️ Aucun hôtel enregistré pour le moment."
                    
                    html = "<div style='font-family: sans-serif;'>"
                    for hotel in resultats:
                        nom, ville, etoiles, note, prix_min, prix_max, equipements, date_ajout = hotel
                        etoiles_str = "⭐" * (etoiles if etoiles else 0)
                        equipements_str = ", ".join(equipements[:4]) if equipements else "Non spécifié"
                        date_str = date_ajout.strftime("%d/%m/%Y") if date_ajout else "N/A"
                        
                        html += f"""
                        <div style='border:1px solid #e0e0e0; padding:12px; margin:8px 0; border-radius:8px; background:#f9f9f9;'>
                            <div style='display:flex; justify-content:space-between; align-items:center;'>
                                <div>
                                    <strong style='font-size:16px;'>🏨 {nom}</strong>
                                    <span style='margin-left:10px; color:#666;'>{ville}</span>
                                    <span style='margin-left:10px;'>{etoiles_str}</span>
                                </div>
                                <div>
                                    <span style='background:#4CAF50; color:white; padding:2px 8px; border-radius:12px;'>
                                        {note}/5
                                    </span>
                                </div>
                            </div>
                            <div style='margin-top:6px;'>
                                <span style='color:#555;'>💰 {prix_min}€ - {prix_max}€/nuit</span>
                                <span style='margin-left:15px; color:#555;'>🔧 {equipements_str}</span>
                            </div>
                            <div style='margin-top:4px; font-size:12px; color:#999;'>
                                Ajouté le {date_str}
                            </div>
                        </div>
                        """
                    html += "</div>"
                    return html
                except Exception as e:
                    return f"❌ Erreur: {str(e)}"
            
            with gr.Row():
                with gr.Column(scale=3):
                    hotels_display = gr.HTML(value="🔄 Chargement des hôtels...")
                    btn_rafraichir = gr.Button("🔄 Rafraîchir la liste")
                    btn_rafraichir.click(afficher_hotels, outputs=[hotels_display])
                    demo.load(afficher_hotels, outputs=[hotels_display])
                
                with gr.Column(scale=1):
                    gr.Markdown("#### 📊 Statistiques")
                    
                    def afficher_stats():
                        try:
                            conn = psycopg2.connect(**DB_CONFIG)
                            cur = conn.cursor()
                            
                            cur.execute("SELECT COUNT(*) FROM hotels")
                            total = cur.fetchone()[0]
                            
                            cur.execute("SELECT AVG(note) FROM hotels WHERE note IS NOT NULL")
                            note_moyenne = cur.fetchone()[0] or 0
                            
                            cur.execute("SELECT COUNT(DISTINCT ville) FROM hotels")
                            villes = cur.fetchone()[0] or 0
                            
                            cur.execute("SELECT AVG(nb_etoiles) FROM hotels WHERE nb_etoiles IS NOT NULL")
                            etoiles_moyennes = cur.fetchone()[0] or 0
                            
                            cur.close()
                            conn.close()
                            
                            return f"""
                            <div style='background:#f0f4f8; padding:15px; border-radius:10px;'>
                                <p style='font-size:18px;'>🏨 <strong>{total}</strong> hôtels</p>
                                <p>⭐ Note moyenne: <strong>{round(note_moyenne, 1)}/5</strong></p>
                                <p>🌟 Étoiles moyennes: <strong>{round(etoiles_moyennes, 1)}</strong></p>
                                <p>📍 <strong>{villes}</strong> villes différentes</p>
                            </div>
                            """
                        except Exception as e:
                            return f"❌ Erreur: {str(e)}"
                    
                    stats_hotels = gr.HTML(value="🔄 Chargement des statistiques...")
                    btn_stats = gr.Button("📊 Actualiser")
                    btn_stats.click(afficher_stats, outputs=[stats_hotels])
                    demo.load(afficher_stats, outputs=[stats_hotels])

    # --- LIAISONS D'ÉVÉNEMENTS ---
    btn_charger_profil.click(charger_profil_utilisateur, inputs=[username_input], outputs=[chatbot_ui, status_user, style_input, budget_input])
    username_input.submit(charger_profil_utilisateur, inputs=[username_input], outputs=[chatbot_ui, status_user, style_input, budget_input])
    btn_reload_history.click(charger_profil_utilisateur, inputs=[username_input], outputs=[chatbot_ui, status_user, style_input, budget_input])
    
    btn_charger_doc.click(analyser_document, inputs=[file_input], outputs=[status_doc, document_text_storage])
    btn_save_prefs.click(enregistrer_preferences_globales, inputs=[username_input, style_input, budget_input], outputs=[status_prefs])
    
    btn_supprimer_history.click(
        supprimer_historique, 
        inputs=[username_input], 
        outputs=[chatbot_ui, status_suppression]
    )
    
    inputs_chat = [txt_input, chatbot_ui, username_input, style_input, budget_input, document_text_storage]
    outputs_chat = [txt_input, chatbot_ui]
    
    btn_envoyer.click(repondre_chatbot, inputs=inputs_chat, outputs=outputs_chat)
    txt_input.submit(repondre_chatbot, inputs=inputs_chat, outputs=outputs_chat)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", theme="soft")