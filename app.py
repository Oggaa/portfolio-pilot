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


def lire_indicateurs(portefeuille_brut):
    """Lit les indicateurs dans les cellules du tableau de bord du Google Sheet."""
    # Dans le fichier fourni : libellés en colonne B, valeurs en colonne C.
    resultats = {}
    for ligne in range(len(portefeuille_brut)):
        libelle = portefeuille_brut.iat[ligne, 1] if portefeuille_brut.shape[1] > 1 else None
        valeur = portefeuille_brut.iat[ligne, 2] if portefeuille_brut.shape[1] > 2 else None
        if isinstance(libelle, str) and pd.notna(valeur):
            texte = libelle.lower()
            if "capital actuel" in texte:
                resultats["capital"] = nombre(valeur)
            elif "liquidités" in texte:
                resultats["liquidites"] = nombre(valeur)
            elif "évaluation titres" in texte:
                resultats["titres"] = nombre(valeur)
            elif "total versé" in texte:
                resultats["verse"] = nombre(valeur)
            elif "gain/perte total" in texte:
                resultats["gain_total"] = nombre(valeur)
            elif "gain/perte en cours" in texte:
                resultats["gain_latent"] = nombre(valeur)
            elif "perfo globale" in texte:
                resultats["performance"] = nombre(valeur)

    # Le gain latent est affiché à côté de son libellé : valeur en colonne M,
    # libellé en colonne N (contrairement aux autres indicateurs en B/C).
    if portefeuille_brut.shape[1] > 13:
        libelle_latent = portefeuille_brut.iat[1, 13]
        valeur_latent = portefeuille_brut.iat[1, 12]
        if isinstance(libelle_latent, str) and "gain/perte en cours" in libelle_latent.lower():
            resultats["gain_latent"] = nombre(valeur_latent)

    # Historique en colonnes Z (date), AA (valorisation), AB (total versé).
    historique = portefeuille_brut.iloc[:, 25:28].copy() if portefeuille_brut.shape[1] >= 28 else pd.DataFrame()
    if not historique.empty:
        historique.columns = ["Date", "Valorisation", "Total versé"]
        historique = historique.dropna(subset=["Date"])
        historique["Date"] = pd.to_datetime(historique["Date"], errors="coerce")
        historique["Valorisation"] = pd.to_numeric(historique["Valorisation"], errors="coerce")
        historique["Total versé"] = pd.to_numeric(historique["Total versé"], errors="coerce")
        historique = historique.dropna(subset=["Date", "Valorisation"])
        historique = historique[
            (historique["Valorisation"] > 0)
            | (historique["Total versé"].fillna(0) > 0)
        ].sort_values("Date")
    else:
        historique = pd.DataFrame(columns=["Date", "Valorisation", "Total versé"])

    return resultats, historique


def preparer_versements(df):
    df = df.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    if "Versement" in df.columns:
        df["Versement (€)"] = pd.to_numeric(df["Versement"], errors="coerce")
    return df


def preparer_positions(ordres):
    """Reconstruit les positions actuelles à partir des lignes dont l'état est Acheté."""
    df = ordres.copy()
    df.columns = [str(c).strip() for c in df.columns]

    colonnes = ["Titre", "Qté", "prix vente", "Montant brut vente", "Coût total achat", "Plus value", "%", "Type", "Etat"]
    for col in colonnes:
        if col not in df.columns:
            df[col] = pd.NA

    df["Etat_nettoye"] = df["Etat"].astype(str).str.strip().str.lower()
    df["Titre_nettoye"] = df["Titre"].apply(normaliser_ticker)
    actifs = df[(df["Etat_nettoye"] == "acheté") & (df["Titre_nettoye"] != "")].copy()

    if actifs.empty:
        return pd.DataFrame(columns=["Titre", "Type", "Quantité", "Cours", "Valorisation", "Coût d'achat", "Gain latent", "Performance"])

    for col in ["Qté", "prix vente", "Montant brut vente", "Coût total achat", "Plus value", "%"]:
        actifs[col] = pd.to_numeric(actifs[col], errors="coerce").fillna(0)

    # On regroupe les éventuels achats successifs d'un même titre.
    lignes = []
    for ticker, groupe in actifs.groupby("Titre_nettoye", sort=False):
        quantite = groupe["Qté"].sum()
        valorisation = groupe["Montant brut vente"].sum()
        cout = groupe["Coût total achat"].sum()
        gain = groupe["Plus value"].sum()
        cours = valorisation / quantite if quantite else 0
        perf = gain / cout if cout else 0
        types = groupe["Type"].dropna().astype(str).str.strip()
        type_titre = types.iloc[-1] if not types.empty else "Non renseigné"
        lignes.append({
            "Titre": ticker,
            "Type": type_titre,
            "Quantité": quantite,
            "Cours": cours,
            "Valorisation": valorisation,
            "Coût d'achat": cout,
            "Gain latent": gain,
            "Performance": perf,
        })

    positions = pd.DataFrame(lignes)
    return positions.sort_values("Valorisation", ascending=False)


# ============================================================
# CHARGEMENT ET CONTRÔLE
# ============================================================
st.title("📈 Gestion PEA")
st.caption("Vue d'ensemble centralisée de tes investissements")

col_sync, col_info = st.columns([1, 4])
with col_sync:
    if st.button("🔄 Synchroniser le Google Sheet", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with col_info:
    st.caption("Synchronisation automatique toutes les 5 minutes. Les données affichées proviennent du Google Sheet.")

try:
    portefeuille_brut, versements_df, ordres_df, feuilles = charger_classeur()
    indicateurs, historique_df = lire_indicateurs(portefeuille_brut)
    versements_df = preparer_versements(versements_df)
    positions_df = preparer_positions(ordres_df)
    erreur_chargement = None
except Exception as exc:
    erreur_chargement = str(exc)
    indicateurs, historique_df = {}, pd.DataFrame()
    versements_df, ordres_df, positions_df = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

if erreur_chargement:
    st.error("Impossible de lire le Google Sheet. Aucune donnée fictive n'est affichée.")
    st.code(erreur_chargement)
    st.info(
        "Vérifie le partage du Google Sheet : l'application doit pouvoir accéder au fichier en lecture. "
        "Tu peux aussi vérifier que les trois onglets s'appellent exactement « Porte feuille », « Versements » et « Ordres »."
    )
    st.stop()

# ============================================================
# DASHBOARD - INDICATEURS
# ============================================================
st.divider()
st.subheader("📊 1. Vue d'ensemble du capital")

capital = indicateurs.get("capital")
liquidites = indicateurs.get("liquidites")
valeur_titres = indicateurs.get("titres")
total_verse = indicateurs.get("verse")
gain_total = indicateurs.get("gain_total")
gain_latent = indicateurs.get("gain_latent")
performance = indicateurs.get("performance")

if capital is None:
    st.warning("La cellule du capital actuel n'a pas été trouvée dans l'onglet « Porte feuille ».")

metriques = st.columns(4)
with metriques[0]:
    st.metric("💰 Capital actuel", euro(capital) if capital is not None else "—")
with metriques[1]:
    st.metric("🏦 Valeur des titres", euro(valeur_titres) if valeur_titres is not None else "—")
with metriques[2]:
    st.metric("💶 Liquidités", euro(liquidites) if liquidites is not None else "—")
with metriques[3]:
    st.metric("💵 Total versé", euro(total_verse) if total_verse is not None else "—")

metriques2 = st.columns(3)
with metriques2[0]:
    st.metric("🏆 Gain/perte total", euro(gain_total) if gain_total is not None else "—")
with metriques2[1]:
    st.metric("📈 Gain/perte en cours", euro(gain_latent) if gain_latent is not None else "—")
with metriques2[2]:
    st.metric("📊 Performance globale", pourcentage(performance) if performance is not None else "—")

# ============================================================
# HISTORIQUE
# ============================================================
st.divider()
st.subheader("📉 2. Évolution du portefeuille")
if not historique_df.empty:
    historique_long = historique_df.melt(
        id_vars="Date",
        value_vars=["Valorisation", "Total versé"],
        var_name="Indicateur",
        value_name="Montant (€)",
    )
    fig_historique = px.line(
        historique_long,
        x="Date",
        y="Montant (€)",
        color="Indicateur",
        markers=True,
        title="Valorisation du portefeuille et cumul des versements",
        color_discrete_map={"Valorisation": "#2E86DE", "Total versé": "#16A085"},
    )
    fig_historique.update_layout(
        hovermode="x unified",
        legend_title_text="",
        margin=dict(l=10, r=10, t=55, b=10),
        yaxis_tickformat=".0f",
    )
    st.plotly_chart(fig_historique, use_container_width=True)
    st.caption("Historique repris des colonnes Date, Portefeuille et Total versé de l'onglet « Porte feuille ».")
else:
    st.info("Aucune donnée historique exploitable n'a été trouvée dans l'onglet « Porte feuille ».")

# ============================================================
# POSITIONS ACTUELLES
# ============================================================
st.divider()
st.subheader("💼 3. Positions actuellement détenues")
if not positions_df.empty:
    total_valo_positions = positions_df["Valorisation"].sum()
    positions_affichage = positions_df.copy()
    positions_affichage["Quantité"] = positions_affichage["Quantité"].map(lambda x: f"{x:g}")
    for col in ["Cours", "Valorisation", "Coût d'achat", "Gain latent"]:
        positions_affichage[col] = positions_affichage[col].map(euro)
    positions_affichage["Performance"] = positions_affichage["Performance"].map(pourcentage)
    positions_affichage["Poids"] = positions_df["Valorisation"].apply(
        lambda x: pourcentage(x / total_valo_positions) if total_valo_positions else "—"
    )
    st.dataframe(
        positions_affichage[["Titre", "Type", "Quantité", "Cours", "Valorisation", "Coût d'achat", "Gain latent", "Performance", "Poids"]],
        use_container_width=True,
        hide_index=True,
    )

    col_repartition, col_performance = st.columns(2)
    with col_repartition:
        st.markdown("#### ⚖️ Répartition par titre")
        fig_repartition = px.pie(
            positions_df,
            names="Titre",
            values="Valorisation",
            hole=0.48,
        )
        fig_repartition.update_traces(textposition="inside", textinfo="percent+label")
        fig_repartition.update_layout(showlegend=False, margin=dict(l=5, r=5, t=15, b=5))
        st.plotly_chart(fig_repartition, use_container_width=True)
    with col_performance:
        st.markdown("#### 📊 Répartition stratégique")
        strategie = positions_df.groupby("Type", as_index=False)["Valorisation"].sum()
        fig_strategie = px.pie(strategie, names="Type", values="Valorisation", hole=0.48)
        fig_strategie.update_traces(textposition="inside", textinfo="percent+label")
        fig_strategie.update_layout(showlegend=False, margin=dict(l=5, r=5, t=15, b=5))
        st.plotly_chart(fig_strategie, use_container_width=True)
else:
    st.info("Aucune position avec l'état « Acheté » n'a été trouvée dans l'onglet « Ordres ».")

# ============================================================
# VERSEMENTS
# ============================================================
st.divider()
st.subheader("💰 4. Historique des versements")
if not versements_df.empty:
    colonnes_disponibles = [c for c in ["Date", "Versement", "Versement (€)"] if c in versements_df.columns]
    tableau_versements = versements_df[colonnes_disponibles].copy()
    if "Date" in tableau_versements.columns:
        tableau_versements["Date"] = pd.to_datetime(tableau_versements["Date"], errors="coerce").dt.strftime("%d/%m/%Y")
    if "Versement (€)" in tableau_versements.columns:
        tableau_versements["Versement (€)"] = tableau_versements["Versement (€)"].map(euro)
    st.dataframe(tableau_versements, use_container_width=True, hide_index=True)
else:
    st.info("Aucun versement enregistré dans l'onglet « Versements ».")

# ============================================================
# HISTORIQUE DES ORDRES
# ============================================================
st.divider()
st.subheader("📜 5. Historique des ordres")
if not ordres_df.empty:
    ordres_visibles = ordres_df.copy()
    ordres_visibles = ordres_visibles.dropna(how="all")
    if "Titre" in ordres_visibles.columns:
        ordres_visibles = ordres_visibles[ordres_visibles["Titre"].notna()]
    if "Date achat" in ordres_visibles.columns:
        ordres_visibles["Date achat"] = pd.to_datetime(ordres_visibles["Date achat"], errors="coerce").dt.strftime("%d/%m/%Y")
    if "Date vente" in ordres_visibles.columns:
        ordres_visibles["Date vente"] = pd.to_datetime(ordres_visibles["Date vente"], errors="coerce").dt.strftime("%d/%m/%Y")
    colonnes_ordre = [c for c in ["Date achat", "Titre", "Type", "Qté", "Coût total achat", "prix vente", "Plus value", "%", "Date vente", "Etat"] if c in ordres_visibles.columns]
    st.dataframe(ordres_visibles[colonnes_ordre], use_container_width=True, hide_index=True)
else:
    st.info("Aucun ordre n'a été trouvé.")

# ============================================================
# SIMULATEURS DE FRAIS - NE MODIFIENT PAS LE GOOGLE SHEET
# ============================================================
st.divider()
st.subheader("🧮 6. Simulateur de frais Fortuneo Starter")
st.caption("Ces calculateurs servent à estimer les frais. Ils n'enregistrent pas d'ordre dans ton Google Sheet.")

onglet_achat, onglet_vente = st.tabs(["🛒 Simulation d'achat", "📤 Simulation de vente"])
with onglet_achat:
    c1, c2, c3 = st.columns(3)
    with c1:
        qte_achat = st.number_input("Quantité à acheter", min_value=0.01, value=1.0, step=1.0, key="sim_qte_achat")
    with c2:
        prix_achat = st.number_input("Prix unitaire (€)", min_value=0.01, value=10.0, step=0.1, key="sim_prix_achat")
    with c3:
        gratuit_achat = st.checkbox("Utiliser l'ordre gratuit", key="sim_gratuit_achat")
    brut_achat = qte_achat * prix_achat
    frais_achat = calculer_frais_fortuneo(brut_achat, gratuit_achat)
    st.info(f"Montant brut : **{euro(brut_achat)}**  |  Frais estimés : **{euro(frais_achat)}**  |  Total débité : **{euro(brut_achat + frais_achat)}**")

with onglet_vente:
    c1, c2, c3 = st.columns(3)
    with c1:
        qte_vente = st.number_input("Quantité à vendre", min_value=0.01, value=1.0, step=1.0, key="sim_qte_vente")
    with c2:
        prix_vente = st.number_input("Prix unitaire de vente (€)", min_value=0.01, value=10.0, step=0.1, key="sim_prix_vente")
    with c3:
        gratuit_vente = st.checkbox("Utiliser l'ordre gratuit", key="sim_gratuit_vente")
    brut_vente = qte_vente * prix_vente
    frais_vente = calculer_frais_fortuneo(brut_vente, gratuit_vente)
    st.info(f"Montant brut : **{euro(brut_vente)}**  |  Frais estimés : **{euro(frais_vente)}**  |  Net crédité : **{euro(brut_vente - frais_vente)}**")

st.divider()
st.caption("Gestion PEA — données synchronisées depuis Google Sheets. Dernière lecture à la demande ou lors du rafraîchissement automatique du cache (5 min).")
