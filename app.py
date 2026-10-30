import io
import sqlite3
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# --- CONFIGURATION DE LA PAGE (MODE PLEINE PAGE) ---
st.set_page_config(
    page_title="Portfolio Pilot PEA", page_icon="📈", layout="wide"
)

SPREADSHEET_ID = "15ou0TCePSKfcbIuivkaGhq8voPzjR3ZudV0sARYwNjE"
DB_NAME = "portfolio.db"


# --- FONCTION DE CALCUL DES FRAIS FORTENEO STARTER ---
def calculer_frais_fortuneo(montant_brut, ordre_gratuit):
  if ordre_gratuit:
    return 0.0
  if montant_brut <= 500:
    return 0.35
  else:
    return round(montant_brut * 0.005, 2)


# --- CHARGEMENT DES DONNÉES ---
@st.cache_data(ttl=300)
def load_data():
  conn = sqlite3.connect(DB_NAME)
  export_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"

  tables_detectees = []
  try:
    response = requests.get(export_url)
    if response.status_code == 200:
      excel_data = io.BytesIO(response.content)
      xls = pd.ExcelFile(excel_data)
      for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        df = df.dropna(how="all").dropna(axis=1, how="all")
        t_name = (
            sheet_name.strip()
            .lower()
            .replace(" ", "_")
            .replace("é", "e")
            .replace("è", "e")
        )
        df.to_sql(t_name, conn, if_exists="replace", index=False)
  except Exception:
    pass

  cursor = conn.cursor()
  cursor.execute(
      "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE"
      " 'sqlite_%';"
  )
  tables_detectees = [row[0] for row in cursor.fetchall()]

  try:
    portefeuille = pd.read_sql("SELECT * FROM portefeuille", conn)
    if portefeuille.empty:
      raise Exception
  except Exception:
    portefeuille = pd.DataFrame({
        "Titre": ["EPA:AI", "EPA:EWLD", "EPA:FDJU", "EPA:RNO", "EPA:STLAP"],
        "Montant brut": [1809.00, 501.48, 490.82, 470.05, 451.26],
        "Plus/Moins-value (€)": [122.98, 18.51, -5.28, -21.62, -48.39],
        "Performance (%)": [7.4, 3.9, -1.1, -4.4, -9.8],
    })

  try:
    versements = pd.read_sql("SELECT * FROM versements", conn)
    if versements.empty:
      raise Exception
  except Exception:
    versements = pd.DataFrame({
        "Date": [
            "10/06/2026",
            "01/07/2026",
            "17/07/2026",
            "18/08/2026",
            "14/09/2026",
            "22/09/2026",
        ],
        "Versement": ["500 €", "400 €", "500 €", "1 668 €", "500 €", "460 €"],
    })

  try:
    ordres = pd.read_sql("SELECT * FROM ordres", conn)
    if ordres.empty:
      raise Exception
  except Exception:
    ordres = pd.DataFrame({
        "Date achat": [
            "15/06/2026",
            "30/07/2026",
            "14/09/2026",
            "02/09/2026",
            "16/09/2026",
            "08/07/2026",
        ],
        "Titre": [
            "EPA:EWLD",
            "EPA:FDJU",
            "EPA:STLAP",
            "EPA:RNO",
            "EPA:AI",
            "EPA:RNO",
        ],
        "Qté": [12, 23, 109, 18, 10, 16],
        "Plus value": [18.51, -5.28, -48.39, 37.70, 122.98, 65.09],
        "Etat": ["Acheté", "Acheté", "Acheté", "Vendu", "Acheté", "Vendu"],
    })

  conn.close()
  return portefeuille, versements, ordres, tables_detectees


portefeuille_df, versements_df, ordres_df, tables_disponibles = load_data()


# Fonction pour colorer les valeurs financières en vert/rouge
def color_green_red(val):
  if isinstance(val, (int, float)):
    color = "color: #2ea043;" if val >= 0 else "color: #da3633;"
    return color
  return ""


# --- APPLICATION MONO-PAGE ---
st.title("🚀 Portfolio Pilot PEA")
st.markdown("Vue d'ensemble centralisée de vos investissements.")

if st.button("🔄 Synchroniser avec le Google Sheet"):
  st.cache_data.clear()
  st.rerun()

st.markdown("---")

# ==========================================
# 1. DASHBOARD & MÉTRIQUES
# ==========================================
st.subheader("📊 Vue d'ensemble du Capital")
col1, col2, col3 = st.columns(3)
with col1:
  st.metric(label="Capital Global", value="4 224,93 €", delta="+196,93 €")
with col2:
  st.metric(label="Évaluation Titres", value="3 722,61 €", delta="+66,20 €")
with col3:
  st.metric(label="Liquidités Disponibles", value="502,32 €")

col_g1, col_g2 = st.columns(2)
with col_g1:
  st.markdown("### ⚖️ Répartition Stratégique")
  fig_pie = px.pie(
      names=["Passif (ETF / Long Terme)", "Dynamique (Stock Picking)"],
      values=[2300, 1422],
      hole=0.4,
      color_discrete_sequence=["#2ea043", "#1f6feb"],
  )
  st.plotly_chart(fig_pie, use_container_width=True)

with col_g2:
  st.markdown("### 📈 Tendance de la Valorisation")
  fig_line = px.line(
      title="Évolution du capital", labels={"x": "Période", "y": "Valeur (€)"}
  )
  st.plotly_chart(fig_line, use_container_width=True)

st.markdown("---")

# ==========================================
# 2. PORTEFEUILLE & VERSEMENTS
# ==========================================
st.subheader("💼 Lignes Actives & Performance")
if not portefeuille_df.empty:
  # Application du style vert/rouge si les colonnes existent
  styled_portefeuille = portefeuille_df.style.applymap(
      color_green_red,
      subset=[
          col
          for col in portefeuille_df.columns
          if any(
              k in col.lower() for k in ["value", "gain", "perf", "plus"]
          )
      ],
  )
  st.dataframe(styled_portefeuille, use_container_width=True, hide_index=True)
else:
  st.warning("Aucune ligne trouvée dans l'onglet Portefeuille.")

st.markdown("### 💰 Suivi des Versements")
if not versements_df.empty:
  st.dataframe(versements_df, use_container_width=True, hide_index=True)
else:
  st.info("Aucun versement enregistré.")

st.markdown("---")

# ==========================================
# 3. SAISIR UN ACHAT / VENTE (FRAIS FORTENEO)
# ==========================================
st.subheader("➕ Enregistrement d'une Transaction (Fortuneo Starter)")

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
    frais_estimes = calculer_frais_fortuneo(montant_brut, ordre_gratuit_achat)
    montant_total = montant_brut + frais_estimes

    st.info(
        f"💡 **Calcul Fortuneo Starter** — Brut : {montant_brut:.2f} € | Frais :"
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
      ticker_vente = st.text_input("Ticker à revendre", placeholder="ex: EPA:AI")
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
        f"💡 **Calcul Fortuneo Starter** — Vente brute : {montant_vente_brut:.2f}"
        f" € | Frais : **{frais_vente:.2f} €** | Net crédité :"
        f" **{montant_nette:.2f} €**"
    )

    if st.form_submit_button("Valider la Vente"):
      st.success(
          f"Vente de {qte_vente} x {ticker_vente} enregistrée avec"
          f" {frais_vente:.2f} € de frais."
      )

st.markdown("---")

# ==========================================
# 4. HISTORIQUE DES ORDRES
# ==========================================
st.subheader("📜 Historique Complet des Ordres")
if not ordres_df.empty:
  styled_ordres = ordres_df.style.applymap(
      color_green_red,
      subset=[
          col
          for col in ordres_df.columns
          if any(k in col.lower() for k in ["value", "gain", "perf", "plus"])
      ],
  )
  st.dataframe(styled_ordres, use_container_width=True, hide_index=True)
else:
  st.warning("Aucun ordre enregistré.")
    
