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
