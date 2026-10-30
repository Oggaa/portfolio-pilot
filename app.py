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


# --- FONCTION DE CALCUL DES FRAIS FORTENEO STARTER ---
def calculer_frais_fortuneo(montant_brut, ordre_gratuit):
  """Calcule les frais de courtage selon la grille Fortuneo Starter et l'option ordre gratuit"""
  if ordre_gratuit:
    return 0.0
  if montant_brut <= 500:
    return 0.35
  else:
    return round(montant_brut * 0.005, 2)


# --- CHARGEMENT ET SYNCHRONISATION DES DONNÉES DU GOOGLE SHEET ---
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
    st.warning(f"Mode hors-ligne actif (synchronisation impossible : {e})")

  cursor = conn.cursor()
  cursor.execute(
      "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE"
      " 'sqlite_%';"
  )
  tables = [row[0] for row in cursor.fetchall()]

  portefeuille = (
      pd.read_sql("SELECT * FROM portefeuille", conn)
      if "portefeuille" in tables
      else pd.DataFrame()
  )
  versements = (
      pd.read_sql("SELECT * FROM versements", conn)
      if "versements" in tables
      else pd.DataFrame()
  )

  # Recherche intelligente de la table des ordres
  ordres = pd.DataFrame()
  for t in tables:
    if "ordre" in t or "historique" in t or "transaction" in t:
      ordres = pd.read_sql(f"SELECT * FROM {t}", conn)
      break

  conn.close()
  return portefeuille, versements, ordres, tables


portefeuille_df, versements_df, ordres_df, tables_disponibles = load_data()

# --- TITRE & NAVIGATION ---
st.title("🚀 Portfolio Pilot PEA")
st.markdown("Pilotez vos actifs, vos ordres et vos frais Fortuneo Starter.")

st.sidebar.header("🧭 Navigation")
menu = st.sidebar.selectbox(
    "Aller à",
    [
        "📊 Dashboard & Courbes",
        "📋 Portefeuille & Versements",
        "➕ Saisir un Achat / Vente",
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
    st.metric(label="Capital Global", value="4 224,93 €", delta="+196,93 €")
  with col2:
    st.metric(label="Évaluation Titres", value="3 722,61 €", delta="+66,20 €")
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
        "Montant": [2300, 1422],
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
    if not portefeuille_df.empty:
      fig_line = px.line(
          title="Tendance globale du portefeuille",
          labels={"x": "Période", "y": "Valeur (€)"},
      )
      st.plotly_chart(fig_line, use_container_width=True)
    else:
      st.info("Chargement des courbes...")

# ==========================================
# 2. PORTEFEUILLE & VERSEMENTS
# ==========================================
elif menu == "📋 Portefeuille & Versements":
  st.subheader("💼 Lignes Actives de votre Portefeuille")
  if not portefeuille_df.empty:
    st.dataframe(portefeuille_df, use_container_width=True, hide_index=True)
  else:
    st.warning("Aucune ligne trouvée dans l'onglet Portefeuille.")

  st.markdown("---")
  st.subheader("💰 Suivi des Versements")
  if not versements_df.empty:
    st.dataframe(versements_df, use_container_width=True, hide_index=True)
  else:
    st.info("Aucun versement enregistré.")

# ==========================================
# 3. SAISIR UN ACHAT / VENTE (AVEC FRAIS)
# ==========================================
elif menu == "➕ Saisir un Achat / Vente":
  st.subheader("📝 Enregistrement d'une Transaction (Fortuneo Starter)")

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
        ordre_gratuit_achat = st.checkbox(
            "🎁 Utiliser l'ordre gratuit du mois (0 € de frais)"
        )

      montant_brut = quantite * prix
      frais_estimes = calculer_frais_fortuneo(
          montant_brut, ordre_gratuit_achat
      )
      montant_total = montant_brut + frais_estimes

      st.info(
          f"💡 **Calcul Fortuneo** — Brut : {montant_brut:.2f} € | Frais :"
          f" **{frais_estimes:.2f} €** | Total débité : **{montant_total:.2f} €**"
      )

      if st.form_submit_button("Valider l'Achat"):
        st.success(
            f"Achat de {quantite} x {ticker} pris en compte avec"
            f" {frais_estimes:.2f} € de frais."
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
        ordre_gratuit_vente = st.checkbox(
            "🎁 Utiliser l'ordre gratuit pour cette vente (0 € de frais)"
        )

      montant_vente_brut = qte_vente * prix_vente
      frais_vente = calculer_frais_fortuneo(
          montant_vente_brut, ordre_gratuit_vente
      )
      montant_nette = montant_vente_brut - frais_vente

      st.info(
          f"💡 **Calcul Fortuneo** — Vente brute : {montant_vente_brut:.2f} € |"
          f" Frais : **{frais_vente:.2f} €** | Net crédité :"
          f" **{montant_nette:.2f} €**"
      )

      if st.form_submit_button("Valider la Vente"):
        st.success(
            f"Vente de {qte_vente} x {ticker_vente} enregistrée avec"
            f" {frais_vente:.2f} € de frais."
        )

# ==========================================
# 4. HISTORIQUE DES ORDRES
# ==========================================
elif menu == "📜 Historique des Ordres":
  st.subheader("📊 Registre complet des ordres (Google Sheet)")
  st.caption(f"Tables détectées : {tables_disponibles}")

  if not ordres_df.empty:
    st.dataframe(ordres_df, use_container_width=True, hide_index=True)
  else:
    st.warning("Aucun historique d'ordres trouvé dans le fichier.")
      
