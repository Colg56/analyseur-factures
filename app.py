import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from invoice_analyzer import InvoiceAnalyzer
import tempfile
import os
from datetime import datetime, timedelta
import base64
from io import BytesIO

# Configuration de la page
st.set_page_config(
    page_title="📊 Analyseur de Factures Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé pour un design moderne
st.markdown("""
<style>
    /* Thème principal */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Cards */
    .metric-card {
        background: rgba(255, 255, 255, 0.95);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        backdrop-filter: blur(4px);
        border: 1px solid rgba(255, 255, 255, 0.18);
        margin-bottom: 20px;
    }
    
    /* Titres */
    h1 {
        color: white !important;
        text-align: center;
        font-size: 3em !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        margin-bottom: 30px;
    }
    
    h2 {
        color: #764ba2 !important;
        border-bottom: 2px solid #667eea;
        padding-bottom: 10px;
    }
    
    /* Boutons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 30px;
        border-radius: 25px;
        font-weight: bold;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px 0 rgba(31, 38, 135, 0.2);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px 0 rgba(31, 38, 135, 0.4);
    }
    
    /* Upload zone */
    .uploadedFile {
        background: rgba(255, 255, 255, 0.9) !important;
        border-radius: 10px;
        padding: 20px;
    }
    
    /* Métriques */
    [data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.95);
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 15px 0 rgba(31, 38, 135, 0.1);
    }
    
    /* Tables */
    .dataframe {
        background: white !important;
        border-radius: 10px;
        overflow: hidden;
    }
    
    /* Progress bar */
    .stProgress > div > div > div {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Sidebar */
    .css-1d391kg {
        background: rgba(255, 255, 255, 0.95);
    }
    
    /* Success/Error messages */
    .stSuccess {
        background: rgba(52, 211, 153, 0.1);
        border: 1px solid #34D399;
        border-radius: 10px;
        padding: 15px;
    }
    
    .stError {
        background: rgba(248, 113, 113, 0.1);
        border: 1px solid #F87171;
        border-radius: 10px;
        padding: 15px;
    }
</style>
""", unsafe_allow_html=True)

# Fonction pour télécharger le fichier Excel
def get_download_link(df_dict, filename="analyse_factures.xlsx"):
    """Génère un lien de téléchargement pour le fichier Excel"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in df_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">📥 Télécharger le rapport Excel</a>'

# Initialisation de l'analyseur
@st.cache_resource
def get_analyzer():
    return InvoiceAnalyzer()

# Header avec animation
st.markdown("""
<h1>📊 Analyseur de Factures Professionnel</h1>
<p style='text-align: center; color: white; font-size: 1.2em; margin-bottom: 30px;'>
    Uploadez vos factures PDF et obtenez une analyse détaillée instantanément
</p>
""", unsafe_allow_html=True)

# Sidebar pour les options
with st.sidebar:
    st.markdown("### ⚙️ Options d'analyse")
    
    # Sélection des fournisseurs à analyser
    suppliers = ['Tous'] + list(get_analyzer().suppliers_patterns.keys())
    selected_suppliers = st.multiselect(
        "Fournisseurs à analyser",
        suppliers,
        default=['Tous']
    )
    
    # Période d'analyse
    st.markdown("### 📅 Période d'analyse")
    date_range = st.date_input(
        "Sélectionnez la période",
        value=(datetime.now() - timedelta(days=30), datetime.now()),
        max_value=datetime.now()
    )
    
    # Options d'export
    st.markdown("### 💾 Options d'export")
    include_charts = st.checkbox("Inclure les graphiques", value=True)
    include_summary = st.checkbox("Inclure le résumé", value=True)
    
    # Informations
    st.markdown("---")
    st.markdown("### ℹ️ Informations")
    st.info("""
    **Fournisseurs supportés:**
    - Terre Azur
    - Metro
    - Colin RHD
    - Episaveurs
    - PassionFroid
    - Fougères Boissons
    - Cave Les 3B
    """)

# Zone principale
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
    st.markdown("## 📤 Upload des factures")
    
    uploaded_files = st.file_uploader(
        "Glissez-déposez vos factures PDF ou cliquez pour sélectionner",
        type=['pdf'],
        accept_multiple_files=True,
        help="Formats supportés: PDF. Vous pouvez sélectionner plusieurs fichiers."
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} fichier(s) uploadé(s)")
        
        # Affichage des fichiers uploadés
        with st.expander("📁 Fichiers uploadés", expanded=True):
            for i, file in enumerate(uploaded_files, 1):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.text(f"{i}. {file.name}")
                with col_b:
                    st.text(f"{file.size / 1024:.1f} KB")
    
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
    st.markdown("## 📊 Statistiques rapides")
    
    if uploaded_files:
        metric1, metric2 = st.columns(2)
        with metric1:
            st.metric("Fichiers", len(uploaded_files), "PDF")
        with metric2:
            total_size = sum(f.size for f in uploaded_files) / 1024
            st.metric("Taille totale", f"{total_size:.1f}", "KB")
    else:
        st.info("Uploadez des fichiers pour voir les statistiques")
    
    st.markdown("</div>", unsafe_allow_html=True)

# Bouton d'analyse
if uploaded_files:
    st.markdown("---")
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        if st.button("🚀 Lancer l'analyse", use_container_width=True):
            with st.spinner("🔄 Analyse en cours..."):
                # Création d'un dossier temporaire
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Sauvegarde des fichiers uploadés
                    for uploaded_file in uploaded_files:
                        file_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                    
                    # Analyse
                    analyzer = get_analyzer()
                    
                    # Progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    all_invoices = []
                    all_products = []
                    
                    for i, uploaded_file in enumerate(uploaded_files):
                        progress = (i + 1) / len(uploaded_files)
                        progress_bar.progress(progress)
                        status_text.text(f"Analyse de {uploaded_file.name}...")
                        
                        file_path = os.path.join(temp_dir, uploaded_file.name)
                        
                        # Extraction du texte
                        text = analyzer.extract_text_from_pdf(file_path)
                        if text:
                            supplier = analyzer.identify_supplier(text)
                            if supplier:
                                if 'Tous' in selected_suppliers or supplier in selected_suppliers:
                                    invoice_data = analyzer.parse_invoice(text, supplier)
                                    invoice_data['filename'] = uploaded_file.name
                                    
                                    # Ajout aux résultats
                                    all_invoices.append({
                                        'Fichier': uploaded_file.name,
                                        'Fournisseur': invoice_data['supplier'],
                                        'N° Facture': invoice_data['invoice_number'],
                                        'Date': invoice_data['date'],
                                        'Total HT': invoice_data['total_amount'] - invoice_data['total_vat'],
                                        'TVA': invoice_data['total_vat'],
                                        'Total TTC': invoice_data['total_amount'],
                                        'Nb Produits': len(invoice_data['products'])
                                    })
                                    
                                    for product in invoice_data['products']:
                                        all_products.append({
                                            'Fournisseur': supplier,
                                            'Date': invoice_data['date'],
                                            'N° Facture': invoice_data['invoice_number'],
                                            'Code': product.get('code', ''),
                                            'Produit': product['name'],
                                            'Quantité': product['quantity'],
                                            'Unité': product['unit'],
                                            'Volume': product.get('volume', 0),
                                            'Volume Unit': product.get('volume_unit', ''),
                                            'Prix Total': product['price']
                                        })
                    
                    progress_bar.progress(1.0)
                    status_text.text("✅ Analyse terminée!")
                    
                    # Stockage dans session state
                    st.session_state['invoices'] = all_invoices
                    st.session_state['products'] = all_products
                    st.session_state['analysis_done'] = True

# Affichage des résultats
if 'analysis_done' in st.session_state and st.session_state['analysis_done']:
    st.markdown("---")
    st.markdown("# 📈 Résultats de l'analyse")
    
    invoices = st.session_state['invoices']
    products = st.session_state['products']
    
    if invoices:
        # Métriques principales
        st.markdown("## 💰 Synthèse financière")
        
        df_invoices = pd.DataFrame(invoices)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Total HT",
                f"{df_invoices['Total HT'].sum():,.2f} €",
                f"{len(invoices)} factures"
            )
        with col2:
            st.metric(
                "TVA totale",
                f"{df_invoices['TVA'].sum():,.2f} €",
                f"{(df_invoices['TVA'].sum() / df_invoices['Total HT'].sum() * 100):.1f}%"
            )
        with col3:
            st.metric(
                "Total TTC",
                f"{df_invoices['Total TTC'].sum():,.2f} €",
                delta=None
            )
        with col4:
            st.metric(
                "Produits",
                f"{len(products)}",
                f"{len(products) / len(invoices):.0f} par facture"
            )
        
        # Graphiques
        if include_charts:
            st.markdown("## 📊 Visualisations")
            
            tab1, tab2, tab3, tab4 = st.tabs(["Par fournisseur", "Évolution temporelle", "Top produits", "Répartition"])
            
            with tab1:
                # Graphique par fournisseur
                supplier_data = df_invoices.groupby('Fournisseur')['Total TTC'].sum().reset_index()
                fig1 = px.bar(
                    supplier_data, 
                    x='Fournisseur', 
                    y='Total TTC',
                    title="Montant total par fournisseur",
                    color='Total TTC',
                    color_continuous_scale='Viridis'
                )
                fig1.update_layout(height=400)
                st.plotly_chart(fig1, use_container_width=True)
            
            with tab2:
                # Évolution temporelle
                if 'Date' in df_invoices.columns and df_invoices['Date'].notna().any():
                    df_invoices['Date'] = pd.to_datetime(df_invoices['Date'])
                    temporal_data = df_invoices.groupby('Date')['Total TTC'].sum().reset_index()
                    fig2 = px.line(
                        temporal_data,
                        x='Date',
                        y='Total TTC',
                        title="Évolution des achats dans le temps",
                        markers=True
                    )
                    fig2.update_layout(height=400)
                    st.plotly_chart(fig2, use_container_width=True)
            
            with tab3:
                # Top produits
                df_products = pd.DataFrame(products)
                if not df_products.empty:
                    top_products = df_products.groupby('Produit')['Prix Total'].sum().nlargest(10).reset_index()
                    fig3 = px.bar(
                        top_products,
                        x='Prix Total',
                        y='Produit',
                        orientation='h',
                        title="Top 10 des produits par valeur",
                        color='Prix Total',
                        color_continuous_scale='Reds'
                    )
                    fig3.update_layout(height=400)
                    st.plotly_chart(fig3, use_container_width=True)
            
            with tab4:
                # Camembert de répartition
                fig4 = px.pie(
                    supplier_data,
                    values='Total TTC',
                    names='Fournisseur',
                    title="Répartition des achats par fournisseur"
                )
                fig4.update_layout(height=400)
                st.plotly_chart(fig4, use_container_width=True)
        
        # Tables de données
        st.markdown("## 📋 Données détaillées")
        
        tab_invoices, tab_products, tab_summary = st.tabs(["Factures", "Produits", "Résumé par fournisseur"])
        
        with tab_invoices:
            st.dataframe(
                df_invoices.style.format({
                    'Total HT': '{:.2f} €',
                    'TVA': '{:.2f} €',
                    'Total TTC': '{:.2f} €'
                }),
                use_container_width=True
            )
        
        with tab_products:
            if products:
                df_products = pd.DataFrame(products)
                st.dataframe(
                    df_products.style.format({
                        'Prix Total': '{:.2f} €',
                        'Volume': '{:.2f}'
                    }),
                    use_container_width=True
                )
        
        with tab_summary:
            supplier_summary = df_invoices.groupby('Fournisseur').agg({
                'N° Facture': 'count',
                'Total HT': 'sum',
                'TVA': 'sum',
                'Total TTC': 'sum',
                'Nb Produits': 'sum'
            }).rename(columns={'N° Facture': 'Nb Factures'})
            
            st.dataframe(
                supplier_summary.style.format({
                    'Total HT': '{:.2f} €',
                    'TVA': '{:.2f} €',
                    'Total TTC': '{:.2f} €'
                }),
                use_container_width=True
            )
        
        # Téléchargement Excel
        st.markdown("---")
        st.markdown("## 💾 Export des données")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # Préparation des données pour l'export
            export_data = {
                'Résumé Factures': df_invoices,
                'Détail Produits': pd.DataFrame(products) if products else pd.DataFrame(),
                'Analyse Fournisseurs': supplier_summary
            }
            
            # Génération du lien de téléchargement
            excel_link = get_download_link(export_data, f"analyse_factures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
            st.markdown(excel_link, unsafe_allow_html=True)
            
            st.success("✅ Analyse complète ! Cliquez ci-dessus pour télécharger le rapport Excel.")
    else:
        st.warning("⚠️ Aucune facture n'a pu être analysée. Vérifiez que les fichiers sont bien des factures des fournisseurs supportés.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: white; padding: 20px;'>
    <p>Développé avec ❤️ pour automatiser votre gestion de factures</p>
    <p style='font-size: 0.9em; opacity: 0.8;'>
        Support technique : Uploadez vos factures PDF et laissez la magie opérer ✨
    </p>
</div>
""", unsafe_allow_html=True)
