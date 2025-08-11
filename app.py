import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import tempfile
import os
import re
import fitz  # PyMuPDF
from datetime import datetime, timedelta
import base64
from io import BytesIO
from typing import Dict, List, Tuple, Optional
import numpy as np

# ================================
# PARTIE 1: ANALYSEUR DE FACTURES
# ================================

class InvoiceAnalyzer:
    """Analyseur intelligent de factures multi-fournisseurs"""
    
    def __init__(self):
        self.suppliers_patterns = {
            'TERRE AZUR': {
                'identifier': ['TERRE AZUR', 'TA BRETAGNE', 'terreazur.fr'],
                'invoice_number': r'FACTURE\s+N°\s*(\d+)',
                'date': r'du\s+(\d{2}\.\d{2}\.\d{4})',
                'product_line': r'^\d+/\s+(\d+)\s+(.*?)\s+(\d+[,\.]\d+)\s+(PCH|KG|COL|SAC|PU|FLT|BQT)',
                'total': r'Net à payer\s*:\s*([\d\s,\.]+)\s*EUR'
            },
            'METRO': {
                'identifier': ['METRO', 'METRO France'],
                'invoice_number': r'N°\s*FACTURE.*?(\d+/\d+)',
                'date': r'Date facture\s*:\s*(\d{2}-\d{2}-\d{4})',
                'product_line': r'(\d{11})\s+(\d+)\s+(.*?)\s+(\d+[,\.]\d+)\s+(S|I|M)',
                'total': r'Total à payer\s*([\d\s,\.]+)'
            },
            'COLIN RHD': {
                'identifier': ['Colin RHD', 'COLIN RHD SAS', 'colinrhd.com'],
                'invoice_number': r'FACTURE\s+(\w+)',
                'date': r'Date.*?(\d{2}/\d{2}/\d{4})',
                'product_line': r'^(T\d+)\s+(\d+)\s+(CAR|UN)\s+(.*?)\s+([\d,\.]+)\s+([\d,\.]+)',
                'total': r'NET À PAYER\s*:\s*\*+([\d,\.]+)'
            },
            'EPISAVEURS': {
                'identifier': ['EpiSaveurs', 'EPISAVEURS', 'episaveurs'],
                'invoice_number': r'FACTURE\s+N°\s*(\d+)',
                'date': r'du\s+(\d{2}\.\d{2}\.\d{4})',
                'product_line': r'^\d+/\s+(\d+)\s+(.*?)\s+(\d+[,\.]\d+)\s+(BID|PCH|COL|BTL|SAC)',
                'total': r'Net à payer\s*:\s*([\d\s,\.]+)\s*EUR'
            },
            'PASSIONFROID': {
                'identifier': ['PassionFroid', 'PASSIONFROID', 'passionfroid.fr'],
                'invoice_number': r'FACTURE\s+N°\s*(\d+)',
                'date': r'du\s+(\d{2}\.\d{2}\.\d{4})',
                'product_line': r'^\d+/\s+(\d+)\s+(.*?)\s+(\d+[,\.]\d+)\s+(COL|PU|KG)',
                'total': r'Net à payer\s*:\s*([\d\s,\.]+)\s*EUR'
            },
            'FOUGERES BOISSONS': {
                'identifier': ['FOUGERES BOISSONS', 'OUEST BOISSONS'],
                'invoice_number': r'FACTURE\s+(\w+-\d+)',
                'date': r'du\s+(\d{2}/\d{2}/\d{4})',
                'product_line': r'(\d{7})\s+(.*?)\s+(\d+)\s+(BTL|CAR|CAI|FAR)\s+([\d,\.]+)',
                'total': r'Net facture\s*([\d\s,\.]+)\s*€'
            },
            'CAVE LES 3B': {
                'identifier': ['CAVE LES 3B', 'sommeliers-cavistes'],
                'invoice_number': r'N°(\w+)',
                'date': r'Date document\s*:\s*(\d{2}/\d{2}/\d{4})',
                'product_line': r'^([A-Z]+\d+)\s+(.*?)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+(C\d+)',
                'total': r'NET A PAYER\s*([\d\s,\.]+)\s*€'
            }
        }
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extrait le texte d'un PDF avec PyMuPDF"""
        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            st.error(f"Erreur lors de la lecture du PDF {pdf_path}: {e}")
            return ""
    
    def identify_supplier(self, text: str) -> Optional[str]:
        """Identifie le fournisseur à partir du texte"""
        for supplier, patterns in self.suppliers_patterns.items():
            for identifier in patterns['identifier']:
                if identifier.lower() in text.lower():
                    return supplier
        return None
    
    def parse_volume(self, description: str) -> Tuple[float, str]:
        """Extrait le volume/contenance d'une description de produit"""
        patterns = [
            r'(\d+)[xX\*](\d+(?:[,\.]\d+)?)\s*([LlCcMm][Ll]?)',
            r'(\d+(?:[,\.]\d+)?)\s*([LlCcMm][Ll])',
            r'(\d+)[xX\*](\d+[,\.]\d+)\s*([LlCcMm][Ll]?)',
            r'(\d+(?:[,\.]\d+)?)\s*(KG|kg|Kg)',
            r'(\d+)\s*(CL|cl)',
            r'(\d+)\s*P(?:\s|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    try:
                        multiplier = float(groups[0].replace(',', '.'))
                        volume = float(groups[1].replace(',', '.'))
                        unit = groups[2].upper()
                        
                        if 'CL' in unit.upper():
                            total_volume = multiplier * volume / 100
                        elif 'ML' in unit.upper():
                            total_volume = multiplier * volume / 1000
                        else:
                            total_volume = multiplier * volume
                        
                        return total_volume, 'L'
                    except:
                        pass
                elif len(groups) == 2:
                    try:
                        volume = float(groups[0].replace(',', '.'))
                        unit = groups[1].upper()
                        
                        if 'CL' in unit:
                            return volume / 100, 'L'
                        elif 'ML' in unit:
                            return volume / 1000, 'L'
                        elif 'KG' in unit:
                            return volume, 'KG'
                        else:
                            return volume, unit
                    except:
                        pass
        
        return 0.0, ''
    
    def clean_product_name(self, product_name: str) -> str:
        """Nettoie le nom du produit"""
        product_name = re.sub(r'^\d+\s+', '', product_name)
        product_name = re.sub(r'\d+[xX\*]\d+[,\.]?\d*\s*[LlCcMm][Ll]?', '', product_name)
        product_name = re.sub(r'\d+[,\.]?\d*\s*[LlCcMm][Ll]', '', product_name)
        product_name = re.sub(r'\d+[,\.]?\d*\s*KG', '', product_name, flags=re.IGNORECASE)
        product_name = re.sub(r'\d+%', '', product_name)
        product_name = re.sub(r'\d+P\s', '', product_name)
        product_name = re.sub(r'\([^)]*\)', '', product_name)
        product_name = ' '.join(product_name.split())
        
        return product_name.strip()
    
    def parse_invoice(self, text: str, supplier: str) -> Dict:
        """Parse une facture selon le fournisseur"""
        patterns = self.suppliers_patterns[supplier]
        
        invoice_data = {
            'supplier': supplier,
            'invoice_number': '',
            'date': '',
            'total_amount': 0.0,
            'total_vat': 0.0,
            'products': []
        }
        
        # Numéro de facture
        invoice_match = re.search(patterns['invoice_number'], text)
        if invoice_match:
            invoice_data['invoice_number'] = invoice_match.group(1)
        
        # Date
        date_match = re.search(patterns['date'], text)
        if date_match:
            date_str = date_match.group(1)
            for fmt in ['%d.%m.%Y', '%d-%m-%Y', '%d/%m/%Y']:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    invoice_data['date'] = date_obj.strftime('%Y-%m-%d')
                    break
                except:
                    continue
        
        # Total
        total_match = re.search(patterns['total'], text)
        if total_match:
            total_str = total_match.group(1).replace(' ', '').replace(',', '.')
            try:
                invoice_data['total_amount'] = float(total_str)
            except:
                pass
        
        # TVA
        vat_patterns = [
            r'TOTAL TVA\s*([\d\s,\.]+)',
            r'Montant TVA\s*([\d\s,\.]+)',
            r'TVA.*?:\s*([\d\s,\.]+)\s*€'
        ]
        for vat_pattern in vat_patterns:
            vat_match = re.search(vat_pattern, text)
            if vat_match:
                vat_str = vat_match.group(1).replace(' ', '').replace(',', '.')
                try:
                    invoice_data['total_vat'] = float(vat_str)
                    break
                except:
                    pass
        
        # Parsing des produits
        lines = text.split('\n')
        
        for line in lines:
            # Pattern générique pour essayer d'extraire des produits
            product_patterns = [
                # Pattern type Terre Azur
                r'^\d+/\s+(\d+)\s+(.*?)\s+(\d+[,\.]\d+)\s+(PCH|KG|COL|SAC|PU|FLT|BQT)\s+.*?\s+([\d,\.]+)$',
                # Pattern type Metro
                r'^(\d{11})\s+(\d+)\s+(.*?)\s+([SI])\s+.*?\s+([\d,\.]+)',
                # Pattern type Colin
                r'^(T\d+)\s+(\d+)\s+(CAR|UN)\s+(.*?)\s+([\d,\.]+)\s+([\d,\.]+)',
                # Pattern générique
                r'^([A-Z0-9]+)\s+(.*?)\s+(\d+[,\.]\d+)\s+.*?\s+([\d,\.]+)'
            ]
            
            for pattern in product_patterns:
                match = re.match(pattern, line)
                if match:
                    groups = match.groups()
                    try:
                        product = {
                            'code': groups[0] if len(groups) > 0 else '',
                            'name': self.clean_product_name(groups[1] if len(groups) > 1 else groups[2] if len(groups) > 2 else ''),
                            'quantity': float((groups[2] if len(groups) > 2 else '1').replace(',', '.')),
                            'unit': groups[3] if len(groups) > 3 else 'UN',
                            'price': float((groups[4] if len(groups) > 4 else groups[-1]).replace(',', '.')),
                            'volume': 0.0,
                            'volume_unit': ''
                        }
                        
                        # Extraction du volume
                        volume, unit = self.parse_volume(product['name'])
                        product['volume'] = volume
                        product['volume_unit'] = unit
                        
                        if product['name'] and product['price'] > 0:
                            invoice_data['products'].append(product)
                            break
                    except:
                        continue
        
        return invoice_data

# ================================
# PARTIE 2: INTERFACE WEB
# ================================

# Configuration de la page
st.set_page_config(
    page_title="📊 Analyseur de Factures Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .metric-card {
        background: rgba(255, 255, 255, 0.95);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        margin-bottom: 20px;
    }
    
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
    
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 30px;
        border-radius: 25px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    
    [data-testid="metric-container"] {
        background: rgba(255, 255, 255, 0.95);
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 15px 0 rgba(31, 38, 135, 0.1);
    }
</style>
""", unsafe_allow_html=True)

# Fonction pour créer le fichier Excel
def create_excel_download(invoices, products):
    """Crée un fichier Excel téléchargeable"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Onglet 1: Résumé des factures
        if invoices:
            df_invoices = pd.DataFrame(invoices)
            df_invoices.to_excel(writer, sheet_name='Résumé Factures', index=False)
            
            # Onglet 2: Détail des produits
            if products:
                df_products = pd.DataFrame(products)
                df_products.to_excel(writer, sheet_name='Détail Produits', index=False)
            
            # Onglet 3: Analyse par fournisseur
            supplier_summary = df_invoices.groupby('Fournisseur').agg({
                'N° Facture': 'count',
                'Total HT': 'sum',
                'TVA': 'sum',
                'Total TTC': 'sum'
            }).rename(columns={'N° Facture': 'Nb Factures'})
            supplier_summary.to_excel(writer, sheet_name='Analyse Fournisseurs')
            
            # Onglet 4: Top produits
            if products:
                df_products = pd.DataFrame(products)
                product_summary = df_products.groupby('Produit').agg({
                    'Quantité': 'sum',
                    'Prix Total': 'sum'
                }).sort_values('Prix Total', ascending=False).head(20)
                product_summary.to_excel(writer, sheet_name='Top 20 Produits')
    
    return output.getvalue()

# Header
st.markdown("""
<h1>📊 Analyseur de Factures Professionnel</h1>
<p style='text-align: center; color: white; font-size: 1.2em; margin-bottom: 30px;'>
    Uploadez vos factures PDF et obtenez une analyse détaillée instantanément
</p>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Options")
    
    st.markdown("### ℹ️ Fournisseurs supportés")
    st.info("""
    • Terre Azur
    • Metro
    • Colin RHD
    • Episaveurs
    • PassionFroid
    • Fougères Boissons
    • Cave Les 3B
    """)
    
    st.markdown("### 📊 Instructions")
    st.success("""
    1. Uploadez vos PDFs
    2. Cliquez sur 'Analyser'
    3. Téléchargez l'Excel
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
        help="Vous pouvez sélectionner plusieurs fichiers PDF"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} fichier(s) uploadé(s)")
        
        with st.expander("📁 Fichiers uploadés", expanded=True):
            for i, file in enumerate(uploaded_files, 1):
                st.text(f"{i}. {file.name} ({file.size / 1024:.1f} KB)")
    
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
    st.markdown("## 📊 Statistiques")
    
    if uploaded_files:
        st.metric("Fichiers", len(uploaded_files), "PDF")
        total_size = sum(f.size for f in uploaded_files) / 1024
        st.metric("Taille totale", f"{total_size:.1f}", "KB")
    else:
        st.info("Uploadez des fichiers pour voir les stats")
    
    st.markdown("</div>", unsafe_allow_html=True)

# Bouton d'analyse
if uploaded_files:
    st.markdown("---")
    
    if st.button("🚀 ANALYSER LES FACTURES", use_container_width=True):
        with st.spinner("🔄 Analyse en cours..."):
            analyzer = InvoiceAnalyzer()
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_invoices = []
            all_products = []
            
            # Création d'un dossier temporaire
            with tempfile.TemporaryDirectory() as temp_dir:
                for i, uploaded_file in enumerate(uploaded_files):
                    progress = (i + 1) / len(uploaded_files)
                    progress_bar.progress(progress)
                    status_text.text(f"Analyse de {uploaded_file.name}...")
                    
                    # Sauvegarde du fichier
                    file_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    # Extraction et analyse
                    text = analyzer.extract_text_from_pdf(file_path)
                    if text:
                        supplier = analyzer.identify_supplier(text)
                        if supplier:
                            invoice_data = analyzer.parse_invoice(text, supplier)
                            
                            # Ajout aux résultats
                            all_invoices.append({
                                'Fichier': uploaded_file.name,
                                'Fournisseur': supplier,
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
                                    'Produit': product['name'],
                                    'Quantité': product['quantity'],
                                    'Volume': product.get('volume', 0),
                                    'Prix Total': product['price']
                                })
                        else:
                            st.warning(f"⚠️ Fournisseur non reconnu dans {uploaded_file.name}")
                    else:
                        st.error(f"❌ Impossible de lire {uploaded_file.name}")
            
            progress_bar.progress(1.0)
            status_text.text("✅ Analyse terminée!")
            
            # Affichage des résultats
            if all_invoices:
                st.markdown("---")
                st.markdown("# 📈 Résultats de l'analyse")
                
                df_invoices = pd.DataFrame(all_invoices)
                
                # Métriques
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total HT", f"{df_invoices['Total HT'].sum():,.2f} €")
                with col2:
                    st.metric("TVA", f"{df_invoices['TVA'].sum():,.2f} €")
                with col3:
                    st.metric("Total TTC", f"{df_invoices['Total TTC'].sum():,.2f} €")
                with col4:
                    st.metric("Produits", len(all_products))
                
                # Graphiques
                st.markdown("## 📊 Visualisations")
                
                tab1, tab2, tab3 = st.tabs(["Par fournisseur", "Top produits", "Données"])
                
                with tab1:
                    supplier_data = df_invoices.groupby('Fournisseur')['Total TTC'].sum().reset_index()
                    fig = px.bar(
                        supplier_data, 
                        x='Fournisseur', 
                        y='Total TTC',
                        title="Montant total par fournisseur",
                        color='Total TTC',
                        color_continuous_scale='Viridis'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with tab2:
                    if all_products:
                        df_products = pd.DataFrame(all_products)
                        top_products = df_products.groupby('Produit')['Prix Total'].sum().nlargest(10).reset_index()
                        fig2 = px.bar(
                            top_products,
                            x='Prix Total',
                            y='Produit',
                            orientation='h',
                            title="Top 10 des produits",
                            color='Prix Total',
                            color_continuous_scale='Reds'
                        )
                        st.plotly_chart(fig2, use_container_width=True)
                
                with tab3:
                    st.subheader("📋 Tableau des factures")
                    st.dataframe(df_invoices, use_container_width=True)
                    
                    if all_products:
                        st.subheader("📦 Tableau des produits")
                        st.dataframe(pd.DataFrame(all_products), use_container_width=True)
                
                # Téléchargement Excel
                st.markdown("---")
                st.markdown("## 💾 Télécharger le rapport Excel")
                
                excel_data = create_excel_download(all_invoices, all_products)
                
                st.download_button(
                    label="📥 TÉLÉCHARGER LE FICHIER EXCEL",
                    data=excel_data,
                    file_name=f"analyse_factures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
                st.success("✅ Analyse complète ! Cliquez ci-dessus pour télécharger.")
            else:
                st.error("❌ Aucune facture n'a pu être analysée.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: white; padding: 20px;'>
    <p>💡 Développé pour automatiser votre gestion de factures</p>
</div>
""", unsafe_allow_html=True)
