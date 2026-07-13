# dashboard_bi_postgres.py
import streamlit as st
import pandas as pd
import plotly.express as px
from db_manager import db_manager
import psycopg2

st.set_page_config(
    page_title="Dashboard Tourisme BI - PostgreSQL",
    page_icon="📊",
    layout="wide"
)

def charger_donnees_bi():
    """Charge les données BI depuis PostgreSQL"""
    conn = db_manager.get_connection()
    
    try:
        # Requête pour les utilisateurs
        users_df = pd.read_sql("""
            SELECT 
                id,
                username,
                preferences->>'style' as style,
                preferences->>'budget' as budget,
                created_at
            FROM users
        """, conn)
        
        # Requête pour les conversations
        conversations_df = pd.read_sql("""
            SELECT 
                u.username,
                c.message,
                c.timestamp
            FROM conversations c
            JOIN users u ON c.user_id = u.id
        """, conn)
        
        # Requête pour les logs BI
        bi_df = pd.read_sql("""
            SELECT 
                u.username,
                l.ville,
                l.style,
                l.budget,
                l.satisfaction,
                l.timestamp
            FROM logs_bi l
            JOIN users u ON l.user_id = u.id
        """, conn)
        
        return users_df, conversations_df, bi_df
    finally:
        conn.close()

# Titre
st.title("📊 Tableau de Bord Touristique - PostgreSQL Analytics")
st.markdown("---")

# Chargement des données
try:
    users_df, conversations_df, bi_df = charger_donnees_bi()
except Exception as e:
    st.error(f"❌ Erreur de chargement des données : {e}")
    st.stop()

# Métriques
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("👥 Utilisateurs", len(users_df))
with col2:
    if not users_df.empty and 'style' in users_df.columns:
        style_pop = users_df['style'].mode()[0] if not users_df['style'].mode().empty else "Aucun"
        st.metric("🏆 Style préféré", style_pop)
    else:
        st.metric("🏆 Style préféré", "Aucun")
with col3:
    st.metric("💬 Messages", len(conversations_df))
with col4:
    if not bi_df.empty:
        satisfaction = bi_df['satisfaction'].mean()
        st.metric("⭐ Satisfaction moyenne", f"{satisfaction:.2f}/5")
    else:
        st.metric("⭐ Satisfaction moyenne", "N/A")

st.markdown("---")

# Graphiques
col1, col2 = st.columns(2)

with col1:
    st.subheader("🎨 Styles de voyage")
    if not users_df.empty:
        fig = px.pie(users_df, names='style', title='Répartition des styles',
                     color_discrete_sequence=px.colors.qualitative.Set3)
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("💰 Budgets")
    if not users_df.empty:
        fig = px.bar(users_df, x='budget', title='Distribution des budgets',
                     color='budget', color_discrete_sequence=px.colors.sequential.Greens)
        st.plotly_chart(fig, use_container_width=True)

# Destinations
st.markdown("---")
st.subheader("🌍 Destinations populaires")

if not bi_df.empty:
    col1, col2 = st.columns(2)
    
    with col1:
        villes = bi_df['ville'].value_counts().head(10)
        fig = px.bar(villes, title='Top 10 des destinations')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Satisfaction par destination
        satisfaction_ville = bi_df.groupby('ville')['satisfaction'].mean().sort_values(ascending=False).head(10)
        fig = px.bar(satisfaction_ville, title='Satisfaction par destination')
        st.plotly_chart(fig, use_container_width=True)

# Données brutes
st.markdown("---")
with st.expander("📋 Voir les données brutes"):
    tab1, tab2, tab3 = st.tabs(["👥 Utilisateurs", "💬 Conversations", "📊 Logs BI"])
    
    with tab1:
        st.dataframe(users_df, use_container_width=True)
    with tab2:
        st.dataframe(conversations_df.head(100), use_container_width=True)
    with tab3:
        st.dataframe(bi_df, use_container_width=True)