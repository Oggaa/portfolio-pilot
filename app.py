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


# --- FONCTION DE CALCUL DES FRAIS FORTENEO (AVEC OPTION ORDRE GRATUIT) ---
def calculer_frais_fortuneo(montant_brut, ordre_gratuit):
  """Calcule les frais de courtage selon la grille Fortuneo Starter et l'ordre gratuit mensuel"""
  if ordre_gratuit:
    return 0.0
  if montant_brut <= 500:
    return 0.35
  else:
    return round(montant_brut * 0.005, 2)  # 0.50%


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
    st.warning(f"Mode hors-ligne actif (synchronisation impossible : {e})")

  cursor = conn.cursor()
  cursor.execute(
      "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE"
      " 'sqlite_%';"
  )
  tables = [row[0] for row in cursor.fetchall()]

