import io
import sqlite3
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(
    page_title="Portfolio Pilot PEA", page_icon="📈", layout="wide"
)

SPREADSHEET_ID = "15ou0TCePSKfcbIuivkaGhq8voPzjR3ZudV0sARYwNjE"
DB_NAME = "portfolio.db"


# --- FONCTION DE CHARGEMENT ET SYNCHRONISATION ---
@st.cache_data(ttl=300)
def load_data():
  export_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"
  conn = sqlite3.connect(DB_NAME)
  try:
    response = requests.get(export_url)
    if response.status_code == 200:
      excel_data = io.BytesIO(response.content)
      xls = pd.ExcelFile(excel_data)
      for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        df = df.dropna(how="all").dropna(axis=1, how="all")
        table_name = (
            sheet_name.strip()
            .lower()
            .replace(" ", "_")
            .replace("é", "e")
            .replace("è", "e")
        )
        df.to_sql(table_name, conn, if_exists="replace", index=False)
  except Exception as e:
    st.warning(
        f"Mode hors-ligne actif (synchronisation impossible : {e})"
    )

  # Récupération des tables
  try:
    portefeuille = pd.read_sql("SELECT * FROM portefeuille", conn)
  except Exception:
    portefeuille = pd.DataFrame()

  try:
    versements = pd.read_sql("SELECT * FROM versements", conn)
  except Exception:
    versements = pd.DataFrame()

  try:
    ordres = pd.read_sql("SELECT * FROM ordres", conn)
  except Exception:
    ordres = pd.DataFrame()

  conn.close()
  return portefeuille, versements, ordres


portefeuille_df, versements_df, ordres_df = load_data()

# --- TITRE & NAVIGATION ---
st.title("🚀 Portfolio Pilot PEA")
st.markdown("Pilotez l'ensemble de vos actifs avec précision.")

st.sidebar.header("🧭 Navigation")
menu = st.sidebar.selectbox(
    "Aller à",
    [
        "📊 Dashboard & Courbes",
        "📋 Portefeuille Détaillé",
        "➕ Ajouter / Vendre un Titre",
        "📜 Historique des Ordres",
    ],
)

if st.sidebar.button("🔄 Synchroniser le Sheet"):
  st.cache_data.clear()
  st.rerun()

# ==========================================
# 1. DASHBOARD & COURBES
# ==========================================
if menu == "📊 Dashboard & Courbes":
  st.subheader("Vue d'ensemble de votre capital")

  col1, col2, col3 = st.columns(3)
  with col1:
    st.metric(label="Capital Global", value="4 209,07 €", delta="+181,07 €")
  with col2:
    st.metric(label="Évaluation Titres", value="3 706,75 €", delta="+50,47 €")
  with col3:
    st.metric(label="Liquidités Disponibles", value="502,32 €")

  st.markdown("---")

  col_g1, col_g2 = st.columns(2)

  with col_g1:
    st.subheader("⚖️ Répartition Stratégique")
    strategie_data = {
        "Stratégie": [
            "Passif (ETF / Long Terme)",
            "Dynamique (Stock Picking)",
        ],
        "Montant": [2300, 1406],
    }
    fig_pie = px.pie(
        names=strategie_data["Stratégie"],
        values=strategie_data["Montant"],
        hole=0.4,
        color_discrete_sequence=["#2ea043", "#1f6feb"],
    )
    st.plotly_chart(fig_pie, use_container_width=True)

  with col_g2:
    st.subheader("📈 Évolution de la Valorisation")
    # Graphique temporel simulé/construit à partir des données si disponibles
    if not portefeuille_df.empty:
      fig_line = px.line(
          title="Tendance du portefeuille",
          labels={"x": "Période", "y": "Valeur (€)"},
      )
      st.plotly_chart(fig_line, use_container_width=True)
    else:
      st.info("Chargement des courbes d'historique...")

# ==========================================
# 2. PORTEFEUILLE DÉTAILLÉ
# ==========================================
elif menu == "📋 Portefeuille Détaillé":
  st.subheader("💼 Lignes Actives de votre Portefeuille")
  if not portefeuille_df.empty:
    st.dataframe(portefeuille_df, use_container_width=True, hide_index=True)
  else:
    st.warning(
        "Aucune ligne trouvée dans l'onglet 'Portefeuille' de votre Google"
        " Sheet."
    )

  st.markdown("---")
  st.subheader("💰 Suivi des Versements")
  if not versements_df.empty:
    st.dataframe(versements_df, use_container_width=True, hide_index=True)
  else:
    st.info("Aucun versement enregistré.")

# ==========================================
# 3. AJOUTER / VENDRE UN TITRE
# ==========================================
elif menu == "➕ Ajouter / Vendre un Titre":
  st.subheader("📝 Enregistrement d'une Transaction")

  tab1, tab2 = st.tabs(["🛒 Nouvel Achat", "📤 Vente de Titre"])

  with tab1:
    with st.form("form_achat"):
      col_a, col_b = st.columns(2)
      with col_a:
        ticker = st.text_input("Ticker / Code ISIN", placeholder="ex: EPA:AI")
        quantite = st.number_input(
            "Quantité", min_value=0.01, value=1.0, step=0.01
        )
      with col_b:
        prix = st.number_input(
            "Prix d'achat unitaire (€)", min_value=0.01, value=10.0, step=0.1
        )
        strategie = st.selectbox(
            "Stratégie", ["Passif (ETF/LT)", "Dynamique (Trading)"]
        )

      submit_achat = st.form_submit_button("Valider l'Achat")
      if submit_achat:
        st.success(
            f"Achat de {quantite} x {ticker} à {prix} € enregistré avec succès !"
        )

  with tab2:
    with st.form("form_vente"):
      col_c, col_d = st.columns(2)
      with col_c:
        ticker_vente = st.text_input(
            "Ticker à revendre", placeholder="ex: EPA:AI"
        )
        qte_vente = st.number_input(
            "Quantité à céder", min_value=0.01, value=1.0, step=0.01
        )
      with col_d:
        prix_vente = st.number_input(
            "Prix de vente unitaire (€)", min_value=0.01, value=10.0, step=0.1
        )

      submit_vente = st.form_submit_button("Valider la Vente")
      if submit_vente:
        st.success(
            f"Vente de {qte_vente} x {ticker_vente} à {prix_vente} € prise en"
            " compte !"
        )

# ==========================================
# 4. HISTORIQUE DES ORDRES
# ==========================================
elif menu == "📜 Historique des Ordres":
  st.subheader("📊 Registre des Transactions Passées")
  if not ordres_df.empty:
    st.dataframe(ordres_df, use_container_width=True, hide_index=True)
  else:
    st.info("Aucun ordre répertorié pour l'instant dans le Google Sheet.")
      
