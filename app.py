import io
import re
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# ============================================================
# CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Gestion PEA",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# TEST TEMPORAIRE
st.title("TEST PORTFOLIO PILOT")
st.success("Le script Streamlit démarre correctement.")

SPREADSHEET_ID = "15ou0TCePSKfcbIuivkaGhq8voPzjR3ZudV0sARYwNjE"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=xlsx"

# ============================================================
# OUTILS
# ============================================================
def euro(value):
    """Format monétaire français."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    return f"{value:,.2f} €".replace(",", " ").replace(".", ",")


def pourcentage(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0.0
    return f"{value * 100:+.2f} %".replace(".", ",")


def nombre(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def calculer_frais_fortuneo(montant_brut, ordre_gratuit):
    """Estimation des frais Fortuneo Starter selon la règle utilisée dans l'app."""
    if ordre_gratuit:
        return 0.0
    if montant_brut <= 500:
        return 0.35
    return round(montant_brut * 0.005, 2)


def normaliser_ticker(value):
    if pd.isna(value):
        return ""
    return str(value).strip().upper()


# ============================================================
# LECTURE GOOGLE SHEETS
# ============================================================
@st.cache_data(ttl=300, show_spinner=False)
def charger_classeur():
    response = requests.get(EXPORT_URL, timeout=30)
    response.raise_for_status()
    if not response.content[:2] == b"PK":
        raise ValueError(
            "Google Sheets n'a pas renvoyé un fichier Excel. Vérifie que le fichier "
            "est accessible en lecture via le lien de partage."
        )
    contenu = io.BytesIO(response.content)
    xls = pd.ExcelFile(contenu)
    feuilles = {nom.strip(): nom for nom in xls.sheet_names}

    requis = ["Porte feuille", "Versements", "Ordres"]
    absentes = [nom for nom in requis if nom not in feuilles]
    if absentes:
        raise ValueError(
            "Onglet(s) introuvable(s) dans le Google Sheet : " + ", ".join(absentes)
        )

    # Le premier onglet a une mise en page de tableau de bord, sans ligne d'en-tête classique.
    portefeuille_brut = pd.read_excel(xls, sheet_name=feuilles["Porte feuille"], header=None)
    versements = pd.read_excel(xls, sheet_name=feuilles["Versements"])
    ordres = pd.read_excel(xls, sheet_name=feuilles["Ordres"])

    return portefeuille_brut, versements, ordres, xls.sheet_names

