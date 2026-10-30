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


# --- FONCTION DE CHARGEMENT DES DONNÉES ---
@st.cache_data(ttl=600)
def load_data():
  export_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"
  try:
    response = requests.get(export_url)
    if response.status_code == 200:
      excel_data = io.BytesIO(response.content)
      xls = pd.ExcelFile(excel_data)
      conn = sqlite3.connect(DB_NAME)
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
      conn.close()
  except Exception as e:
    st.warning(
        f"Synchronisation Google Sheets hors-ligne. Erreur : {e}"
    )

  conn = sqlite3.connect(DB_NAME)
  try:
    portefeuille = pd.read_sql("SELECT * FROM portefeuille", conn)
    versements = pd.read_sql("SELECT * FROM versements", conn)
    ordres = pd.read_sql("SELECT * FROM ordres", conn)
  except Exception:
    portefeuille, versements, ordres = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
  conn.close()
  return portefeuille, versements, ordres


portefeuille_df, versements_df, ordres_df = load_data()

st.title("🚀 Portfolio Pilot PEA")
st.markdown("Pilotez votre portefeuille boursier facilement.")

st.sidebar.header("🧭 Navigation")
menu = st.sidebar.selectbox(
    "Aller à",
    [
        "📊 Dashboard Principal",
        "📋 Détail du Portefeuille",
        "➕ Saisir un Ordre / Versement",
        "📜 Historique des Transactions",
    ],
)

if st.sidebar.button("🔄 Rafraîchir"):
  st.cache_data.clear()
  st.rerun()

if menu == "📊 Dashboard Principal":
  st.subheader("Vue d'ensemble de votre capital")
  col1, col2, col3, col4 = st.columns(4)
  with col1:
    st.metric(label="Capital Actuel", value="4 209,07 €", delta="+181,07 €")
  with col2:
    st.metric(label="Évaluation Titres", value="3 706,75 €", delta="+50,47 €")
  with col3:
    st.metric(label="Liquidités (Cash)", value="502,32 €")
  with col4:
    st.metric(label="Performance Globale", value="+4,50%")

  st.markdown("---")
  col_g1, col_g2 = st.columns(2)
  with col_g1:
    st.subheader("⚖️ Répartition Stratégique")
    strategie_data = {
        "Type": ["Passif (ETF / Conviction)", "Dynamique (Stock Picking)"],
        "Montant": [2300, 1406],
    }
    fig_pie = px.pie(
        names=strategie_data["Type"],
        values=strategie_data["Montant"],
        hole=0.4,
        color_discrete_sequence=["#2ea043", "#1f6feb"],
    )
    st.plotly_chart(fig_pie, use_container_width=True)

elif menu == "📋 Détail du Portefeuille":
  st.subheader("💼 Lignes Actives")
  if not portefeuille_df.empty:
    st.dataframe(portefeuille_df, use_container_width=True)
  else:
    st.warning("Aucune donnée.")

elif menu == "➕ Saisir un Ordre / Versement":
  st.subheader("📝 Ajouter une transaction")
  tab1, tab2 = st.tabs(["🛒 Nouvel Ordre", "💰 Nouveau Versement"])
  with tab1:
    with st.form("form_ordre"):
      ticker = st.text_input("Ticker (ex: EPA:AI)")
      quantite = st.number_input("Quantité", value=1.0)
      prix = st.number_input("Prix Unitaire (€)", value=10.0)
      if st.form_submit_button("Enregistrer"):
        st.success("Ordre pris en compte !")
  with tab2:
    with st.form("form_versement"):
      montant = st.number_input("Montant (€)", value=500.0)
      if st.form_submit_button("Enregistrer"):
        st.success("Versement pris en compte !")

elif menu == "📜 Historique des Transactions":
  st.subheader("📊 Registre complet")
  if not ordres_df.empty:
    st.dataframe(ordres_df, use_container_width=True)
  else:
    st.info("Aucun ordre.")
    
