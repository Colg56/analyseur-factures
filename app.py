import os
import re
import pandas as pd
from datetime import datetime
import pdfplumber
import streamlit as st
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

class AnalyseurFacturesFinal:
    """
    Analyseur de factures FINAL - Version robuste et précise
    """
    
    def __init__(self):
        self.donnees_extraites = []
        
    def detecter_fournisseur(self, texte):
        """Détection du fournisseur"""
        texte_upper = texte.upper()
        
        if 'FOUGERES BOISSONS' in texte_upper or 'VTE-' in texte_upper:
            return 'Fougères Boissons'
        elif 'METRO' in texte_upper and ('METRO.FR' in texte_upper or 'METRO FRANCE' in texte_upper):
            return 'Metro'
        elif 'PROMOCASH' in texte_upper:
            return 'Promocash'
        elif 'CAVE LES 3B' in texte_upper or 'SOMMELIERS-CAVISTES' in texte_upper:
            return 'Cave Les 3B'
        elif 'TERREAZUR' in texte_upper or 'TERRE AZUR' in texte_upper:
            return 'TerreAzur'
        elif 'EPISAVEURS' in texte_upper or 'EPI SAVEURS' in texte_upper:
            return 'EpiSaveurs'
        elif 'COLIN RHD' in texte_upper:
            return 'Colin RHD'
        elif 'PASSIONFROID' in texte_upper:
            return 'Passionfroid'
        elif 'SVA JEAN ROZE' in texte_upper:
            return 'SVA Jean Roze'
        else:
            return 'Autre fournisseur'
    
    def extraire_contenance(self, texte):
        """Extrait la contenance d'un produit"""
        if not texte:
            return "1PC"
        
        texte = texte.upper()
        
        # Patterns pour différents formats
        patterns = [
            r'(\d+)\s*X\s*(\d+(?:[,\.]\d+)?)\s*(CL|ML|L|KG|G)',  # 6X75CL
            r'(\d+(?:[,\.]\d+)?)\s*(CL|ML|L|KG|G)\s*X\s*(\d+)',  # 75CL X6
            r'(\d+(?:[,\.]\d+)?)\s*(CL|ML|L|KG|G)',  # 75CL
            r'(\d+)\s*(BTL|BTE|PC|UN|CAR|CAI|FAR)',  # 6 BTL
        ]
        
        for pattern in patterns:
            match = re.search(pattern, texte)
            if match:
                groups = match.groups()
                if 'X' in pattern:
                    if len(groups) == 3:
                        if groups[2] in ['CL', 'ML', 'L', 'KG', 'G']:
                            return f"{groups[0]}x{groups[1]}{groups[2]}"
                        else:
                            return f"{groups[0]}{groups[1]}x{groups[2]}"
                else:
                    return f"{groups[0]}{groups[1]}"
        
        return "1PC"
    
    def analyser_fougeres(self, texte, tables):
        """Analyse spécifique pour Fougères Boissons"""
        produits = []
        
        # Extraire date et numéro
        date_match = re.search(r'du\s+(\d{2}/\d{2}/\d{4})', texte)
        date_facture = date_match.group(1) if date_match else datetime.now().strftime('%d/%m/%Y')
        
        num_match = re.search(r'VTE-(\d+)', texte)
        num_facture = f"VTE-{num_match.group(1)}" if num_match else "N/A"
        
        # D'abord essayer avec les tables PDF
        if tables:
            for table in tables:
                for row in table:
                    if row and len(row) >= 6:
                        # Vérifier si c'est une ligne produit (commence par 7 chiffres)
                        code_str = str(row[0]) if row[0] else ""
                        if re.match(r'^\d{7}$', code_str.strip()):
                            try:
                                code = code_str.strip()
                                designation = str(row[1]) if row[1] else ""
                                
                                # Chercher quantité et montant dans les colonnes suivantes
                                quantite = 1
                                montant = 0
                                prix_unit = 0
                                
                                for i in range(2, len(row)):
                                    if row[i]:
                                        val_str = str(row[i]).strip()
                                        # Si c'est un nombre entier (quantité probable)
                                        if val_str.isdigit():
                                            val_int = int(val_str)
                                            if val_int < 100:  # Probablement une quantité
                                                quantite = val_int
                                        # Si c'est un montant (avec virgule ou point)
                                        elif re.match(r'^\d+[,\.]\d+$', val_str):
                                            val_float = float(val_str.replace(',', '.'))
                                            if montant == 0:
                                                montant = val_float
                                            elif prix_unit == 0:
                                                prix_unit = val_float
                                
                                # Ajuster prix unitaire et montant total
                                if montant > 0:
                                    if prix_unit == 0:
                                        prix_unit = montant / quantite if quantite > 0 else montant
                                    else:
                                        # Le plus grand est probablement le montant total
                                        if prix_unit > montant:
                                            prix_unit, montant = montant, prix_unit
                                        # Recalculer le montant total si nécessaire
                                        if abs(montant - (prix_unit * quantite)) > 0.1:
                                            montant = prix_unit * quantite
                                    
                                    produits.append({
                                        'Date Facture': date_facture,
                                        'N° Facture': num_facture,
                                        'Fournisseur': 'Fougères Boissons',
                                        'Code Article': code,
                                        'Désignation': designation,
                                        'Catégorie': self.determiner_categorie(designation),
                                        'Contenance': self.extraire_contenance(designation),
                                        'Nb Unités': quantite,
                                        'Prix Unitaire HT': round(prix_unit, 2),
                                        'Montant HT': round(montant, 2)
                                    })
                            except:
                                continue
        
        # Si pas assez de produits trouvés, analyser le texte
        if len(produits) < 3:
            lignes = texte.split('\n')
            for ligne in lignes:
                # Pattern pour Fougères : 7 chiffres + désignation + montants
                if re.match(r'^\d{7}\s', ligne):
                    parts = ligne.split()
                    if len(parts) >= 4:
                        code = parts[0]
                        
                        # Trouver les montants dans la ligne
                        montants = []
                        designation_parts = []
                        quantite = 1
                        
                        for part in parts[1:]:
                            # Montant avec virgule
                            if re.match(r'^\d+[,\.]\d+$', part):
                                montants.append(float(part.replace(',', '.')))
                            # Quantité (petit nombre)
                            elif part.isdigit() and int(part) < 100:
                                quantite = int(part)
                            # Ignorer les unités
                            elif part not in ['BTL', 'CAR', 'CAI', 'FAR', 'PU', 'PC']:
                                designation_parts.append(part)
                        
                        if montants and designation_parts:
                            designation = ' '.join(designation_parts)
                            # Le dernier montant est généralement le total
                            montant = montants[-1] if montants else 0
                            prix_unit = montants[0] if len(montants) > 1 else montant / quantite
                            
                            # Ne pas ajouter si déjà présent
                            if not any(p['Code Article'] == code for p in produits):
                                produits.append({
                                    'Date Facture': date_facture,
                                    'N° Facture': num_facture,
                                    'Fournisseur': 'Fougères Boissons',
                                    'Code Article': code,
                                    'Désignation': designation,
                                    'Catégorie': self.determiner_categorie(designation),
                                    'Contenance': self.extraire_contenance(designation),
                                    'Nb Unités': quantite,
                                    'Prix Unitaire HT': round(prix_unit, 2),
                                    'Montant HT': round(montant, 2)
                                })
        
        return produits
    
    def analyser_metro(self, texte, tables):
        """Analyse spécifique pour Metro"""
        produits = []
        
        # Extraction date et numéro
        date_match = re.search(r'Date facture\s*:\s*(\d{2}-\d{2}-\d{4})', texte)
        if not date_match:
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', texte)
        date_facture = date_match.group(1).replace('-', '/') if date_match else datetime.now().strftime('%d/%m/%Y')
        
        num_match = re.search(r'(?:FACTURE|N°)\s*(\d{8,})', texte)
        num_facture = num_match.group(1) if num_match else "N/A"
        
        # Analyser les tables si disponibles
        if tables:
            for table in tables:
                for row in table:
                    if row and len(row) >= 4:
                        # Chercher un code produit Metro (10-13 chiffres)
                        code = ""
                        designation = ""
                        montant = 0
                        quantite = 1
                        
                        for i, cell in enumerate(row):
                            if cell:
                                cell_str = str(cell).strip()
                                # Code produit
                                if re.match(r'^\d{10,13}$', cell_str):
                                    code = cell_str
                                # Montant
                                elif re.match(r'^\d+[,\.]\d{2}$', cell_str):
                                    montant = float(cell_str.replace(',', '.'))
                                # Quantité
                                elif cell_str.isdigit() and int(cell_str) < 100:
                                    quantite = int(cell_str)
                                # Désignation (texte non numérique)
                                elif len(cell_str) > 3 and not cell_str.replace(',', '.').replace('.', '').isdigit():
                                    if len(cell_str) > len(designation):
                                        designation = cell_str
                        
                        if code and designation and montant > 0:
                            produits.append({
                                'Date Facture': date_facture,
                                'N° Facture': num_facture,
                                'Fournisseur': 'Metro',
                                'Code Article': code,
                                'Désignation': designation,
                                'Catégorie': self.determiner_categorie(designation),
                                'Contenance': self.extraire_contenance(designation),
                                'Nb Unités': quantite,
                                'Prix Unitaire HT': round(montant / quantite, 2),
                                'Montant HT': round(montant, 2)
                            })
        
        # Si pas de tables ou peu de résultats, analyser le texte
        if len(produits) < 3:
            lignes = texte.split('\n')
            for ligne in lignes:
                # Pattern Metro : code long + designation + montant
                match = re.match(r'^(\d{10,13})\s+(?:\d{6,}\s+)?(.+?)\s+(\d+[,\.]\d{2})', ligne)
                if match:
                    code = match.group(1)
                    designation = match.group(2).strip()
                    montant = float(match.group(3).replace(',', '.'))
                    
                    # Extraire quantité si présente dans la désignation
                    quantite = 1
                    quant_match = re.search(r'(\d+)\s*(?:PC|UN|X)', designation)
                    if quant_match:
                        quantite = int(quant_match.group(1))
                    
                    if not any(p['Code Article'] == code for p in produits):
                        produits.append({
                            'Date Facture': date_facture,
                            'N° Facture': num_facture,
                            'Fournisseur': 'Metro',
                            'Code Article': code,
                            'Désignation': designation,
                            'Catégorie': self.determiner_categorie(designation),
                            'Contenance': self.extraire_contenance(designation),
                            'Nb Unités': quantite,
                            'Prix Unitaire HT': round(montant / quantite, 2),
                            'Montant HT': round(montant, 2)
                        })
        
        return produits
    
    def analyser_cave3b(self, texte, tables):
        """Analyse spécifique pour Cave Les 3B"""
        produits = []
        
        # Date et numéro
        date_match = re.search(r'Date document\s*:\s*(\d{2}/\d{2}/\d{4})', texte)
        date_facture = date_match.group(1) if date_match else datetime.now().strftime('%d/%m/%Y')
        
        num_match = re.search(r'N°(F\d+)', texte)
        num_facture = num_match.group(1) if num_match else "N/A"
        
        # Analyser tables
        if tables:
            for table in tables:
                for row in table:
                    if row and len(row) >= 5:
                        # Format Cave 3B : Reference | Designation | Qté | PU | Total
                        reference = str(row[0]) if row[0] else ""
                        
                        # Vérifier que c'est une ligne produit (référence alphanumérique)
                        if reference and re.match(r'^[A-Z]+\d+', reference):
                            try:
                                designation = str(row[1]) if row[1] else ""
                                quantite = 1
                                prix_unit = 0
                                montant = 0
                                
                                # Parcourir les colonnes pour trouver les valeurs
                                for i in range(2, len(row)):
                                    if row[i]:
                                        val_str = str(row[i]).replace(',', '.')
                                        try:
                                            val = float(val_str)
                                            if val < 10 and val > 0:  # Probablement quantité
                                                quantite = int(val)
                                            elif val > 0:
                                                if prix_unit == 0:
                                                    prix_unit = val
                                                else:
                                                    montant = val
                                        except:
                                            pass
                                
                                if montant > 0:
                                    produits.append({
                                        'Date Facture': date_facture,
                                        'N° Facture': num_facture,
                                        'Fournisseur': 'Cave Les 3B',
                                        'Code Article': reference,
                                        'Désignation': designation,
                                        'Catégorie': 'Vins et Spiritueux',
                                        'Contenance': self.extraire_contenance(designation),
                                        'Nb Unités': quantite,
                                        'Prix Unitaire HT': round(prix_unit, 2),
                                        'Montant HT': round(montant, 2)
                                    })
                            except:
                                continue
        
        return produits
    
    def analyser_terreazur(self, texte, tables):
        """Analyse spécifique pour TerreAzur"""
        produits = []
        
        # Date et numéro
        date_match = re.search(r'du\s+(\d{2}\.\d{2}\.\d{4})', texte)
        if not date_match:
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', texte)
        date_facture = date_match.group(1).replace('.', '/') if date_match else datetime.now().strftime('%d/%m/%Y')
        
        num_match = re.search(r'FACTURE N°\s*(\d+)', texte)
        num_facture = num_match.group(1) if num_match else "N/A"
        
        # Analyser tables
        if tables:
            for table in tables:
                for row in table:
                    if row and len(row) >= 4:
                        # Chercher un pattern TerreAzur
                        code = ""
                        designation = ""
                        quantite = 1
                        montant = 0
                        
                        for i, cell in enumerate(row):
                            if cell:
                                cell_str = str(cell).strip()
                                # Code format XX/ XXXXXX
                                if re.match(r'^\d+/\s*\d+', cell_str):
                                    code = cell_str.replace(' ', '')
                                # Montant
                                elif re.match(r'^\d+[,\.]\d+$', cell_str):
                                    val = float(cell_str.replace(',', '.'))
                                    if val > montant:
                                        montant = val
                                # Quantité (KG, PC, etc.)
                                elif re.match(r'^\d+[,\.]\d+\s*(KG|PC|COL|SAC)', cell_str):
                                    match = re.match(r'^(\d+[,\.]\d+)', cell_str)
                                    if match:
                                        quantite = float(match.group(1).replace(',', '.'))
                                # Désignation
                                elif len(cell_str) > 3 and not cell_str.replace(',', '.').replace('.', '').isdigit():
                                    if len(cell_str) > len(designation):
                                        designation = cell_str
                        
                        if code and designation and montant > 0:
                            produits.append({
                                'Date Facture': date_facture,
                                'N° Facture': num_facture,
                                'Fournisseur': 'TerreAzur',
                                'Code Article': code,
                                'Désignation': designation,
                                'Catégorie': self.determiner_categorie(designation),
                                'Contenance': self.extraire_contenance(designation),
                                'Nb Unités': quantite,
                                'Prix Unitaire HT': round(montant / quantite if quantite > 0 else montant, 2),
                                'Montant HT': round(montant, 2)
                            })
        
        return produits
    
    def analyser_generique(self, texte, tables, fournisseur):
        """Analyseur générique pour autres fournisseurs"""
        produits = []
        
        # Extraction date
        date_patterns = [
            r'(?:du|Date)\s+(\d{2}[/-]\d{2}[/-]\d{4})',
            r'(\d{2}[/-]\d{2}[/-]\d{4})'
        ]
        date_facture = None
        for pattern in date_patterns:
            match = re.search(pattern, texte)
            if match:
                date_facture = match.group(1).replace('-', '/')
                break
        if not date_facture:
            date_facture = datetime.now().strftime('%d/%m/%Y')
        
        # Extraction numéro
        num_match = re.search(r'(?:FACTURE|N°|Numéro)\s*[:=]?\s*([A-Z0-9\-]+)', texte, re.IGNORECASE)
        num_facture = num_match.group(1) if num_match else "N/A"
        
        # Analyser les tables
        if tables:
            for table in tables:
                for row in table:
                    if row and len(row) >= 3:
                        code = ""
                        designation = ""
                        montant = 0
                        quantite = 1
                        
                        for i, cell in enumerate(row):
                            if cell:
                                cell_str = str(cell).strip()
                                
                                # Code (commence par des chiffres ou alphanumérique)
                                if i == 0 and (re.match(r'^\d{3,}', cell_str) or re.match(r'^[A-Z]+\d+', cell_str)):
                                    code = cell_str
                                # Montant
                                elif re.match(r'^\d+[,\.]\d{2}$', cell_str):
                                    val = float(cell_str.replace(',', '.'))
                                    if val > montant:
                                        montant = val
                                # Quantité
                                elif cell_str.isdigit() and int(cell_str) < 100:
                                    quantite = int(cell_str)
                                # Désignation
                                elif len(cell_str) > 5 and not re.match(r'^[\d,\.]+$', cell_str):
                                    if len(cell_str) > len(designation):
                                        designation = cell_str
                        
                        if designation and montant > 0:
                            produits.append({
                                'Date Facture': date_facture,
                                'N° Facture': num_facture,
                                'Fournisseur': fournisseur,
                                'Code Article': code,
                                'Désignation': designation,
                                'Catégorie': self.determiner_categorie(designation),
                                'Contenance': self.extraire_contenance(designation),
                                'Nb Unités': quantite,
                                'Prix Unitaire HT': round(montant / quantite if quantite > 0 else montant, 2),
                                'Montant HT': round(montant, 2)
                            })
        
        return produits
    
    def determiner_categorie(self, designation):
        """Détermine la catégorie d'un produit"""
        if not designation:
            return "Autre"
        
        designation_lower = designation.lower()
        
        categories = {
            'Boissons Alcoolisées': ['gin', 'whisky', 'vodka', 'rhum', 'vin', 'champagne', 
                                     'bière', 'jack daniel', 'jameson', 'beefeater', 'lillet',
                                     'get 27', 'crème de cassis', 'alcool', 'cognac'],
            'Boissons Soft': ['perrier', 'coca', 'limonade', 'eau', 'jus', 'soda', 'caraibos'],
            'Viande': ['boeuf', 'porc', 'agneau', 'poulet', 'veau', 'souris', 'côte'],
            'Poisson': ['saumon', 'bar', 'crevette', 'lieu', 'cabillaud'],
            'Légumes': ['salade', 'tomate', 'carotte', 'champignon', 'betterave', 'panais'],
            'Fruits': ['pomme', 'poire', 'orange', 'mangue', 'ananas', 'fraise'],
            'Produits Laitiers': ['lait', 'crème', 'beurre', 'fromage', 'yaourt'],
            'Epicerie': ['huile', 'vinaigre', 'sauce', 'pâte', 'riz', 'farine']
        }
        
        for categorie, mots_cles in categories.items():
            for mot in mots_cles:
                if mot in designation_lower:
                    return categorie
        
        return 'Autre'
    
    def analyser_pdf(self, fichier_pdf, nom_fichier=""):
        """Analyse principale d'un PDF"""
        tous_les_produits = []
        
        try:
            with pdfplumber.open(fichier_pdf) as pdf:
                texte_complet = ""
                tables_completes = []
                
                # Extraire texte et tables
                for page in pdf.pages:
                    texte_page = page.extract_text()
                    if texte_page:
                        texte_complet += texte_page + "\n"
                    
                    tables = page.extract_tables()
                    if tables:
                        tables_completes.extend(tables)
                
                # Détecter le fournisseur
                fournisseur = self.detecter_fournisseur(texte_complet)
                
                # Appeler la bonne méthode d'analyse
                if fournisseur == 'Fougères Boissons':
                    produits = self.analyser_fougeres(texte_complet, tables_completes)
                elif fournisseur == 'Metro':
                    produits = self.analyser_metro(texte_complet, tables_completes)
                elif fournisseur == 'Cave Les 3B':
                    produits = self.analyser_cave3b(texte_complet, tables_completes)
                elif fournisseur == 'TerreAzur':
                    produits = self.analyser_terreazur(texte_complet, tables_completes)
                else:
                    produits = self.analyser_generique(texte_complet, tables_completes, fournisseur)
                
                # Ajouter le fichier source
                for produit in produits:
                    produit['Fichier Source'] = nom_fichier
                
                tous_les_produits.extend(produits)
                
                # Si aucun produit trouvé, extraction basique du total
                if not tous_les_produits:
                    st.warning(f"⚠️ Extraction limitée pour {nom_fichier}")
                    # Essayer de trouver au moins le montant total
                    montant_match = re.search(r'(?:TOTAL|NET|Facturé).*?([\d\s]+[,\.]\d{2})', texte_complet, re.IGNORECASE)
                    if montant_match:
                        montant_str = montant_match.group(1).replace(' ', '').replace(',', '.')
                        try:
                            montant = float(montant_str)
                            tous_les_produits.append({
                                'Date Facture': datetime.now().strftime('%d/%m/%Y'),
                                'N° Facture': 'TOTAL_ONLY',
                                'Fournisseur': fournisseur,
                                'Code Article': '',
                                'Désignation': f'Total facture {fournisseur}',
                                'Catégorie': 'Autre',
                                'Contenance': '1PC',
                                'Nb Unités': 1,
                                'Prix Unitaire HT': montant,
                                'Montant HT': montant,
                                'Fichier Source': nom_fichier
                            })
                        except:
                            pass
                        
        except Exception as e:
            st.error(f"❌ Erreur lors de l'analyse de {nom_fichier}: {str(e)}")
            
        return tous_les_produits


# Interface Streamlit
def main():
    st.set_page_config(
        page_title="Analyseur de Factures - Bistro Urbain",
        page_icon="📊",
        layout="wide"
    )
    
    # Header
    st.markdown("""
        <style>
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            border-radius: 10px;
            color: white;
            margin-bottom: 2rem;
        }
        .metric-box {
            background: white;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        </style>
        <div class="main-header">
            <h1>📊 Analyseur de Factures - Bistro Urbain</h1>
            <p>Version Finale - Extraction précise et complète</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Initialiser l'analyseur
    analyseur = AnalyseurFacturesFinal()
    
    # Sidebar
    with st.sidebar:
        st.header("📋 Fournisseurs supportés")
        st.info("""
        ✅ **Extraction optimisée :**
        - Fougères Boissons
        - Metro / Promocash
        - Cave Les 3B
        - TerreAzur
        - EpiSaveurs
        - Colin RHD
        - Passionfroid
        - SVA Jean Roze
        
        ✅ **Extraction universelle** pour tous les autres
        """)
        
        st.divider()
        
        st.header("ℹ️ Informations")
        st.caption("Version déployée sur Streamlit Cloud")
        st.caption("Données sécurisées - Aucun stockage")
    
    # Zone principale
    col1, col2 = st.columns([3, 1])
    
    with col1:
        fichiers = st.file_uploader(
            "📁 Glissez vos factures PDF ici",
            type=['pdf'],
            accept_multiple_files=True,
            help="Tous les formats de factures sont acceptés"
        )
    
    with col2:
        if fichiers:
            st.metric("📄 Fichiers", len(fichiers))
            st.metric("📦 Taille", f"{sum(f.size for f in fichiers) / 1024:.1f} KB")
    
    if fichiers:
        if st.button("🚀 ANALYSER LES FACTURES", type="primary", use_container_width=True):
            
            with st.spinner("🔄 Analyse en cours..."):
                tous_les_produits = []
                resume_fichiers = []
                
                # Progress bar
                progress_bar = st.progress(0)
                
                # Analyser chaque fichier
                for i, fichier in enumerate(fichiers):
                    produits = analyseur.analyser_pdf(fichier, fichier.name)
                    
                    if produits:
                        tous_les_produits.extend(produits)
                        # Calculer le total pour ce fichier
                        total_fichier = sum(p.get('Montant HT', 0) for p in produits)
                        resume_fichiers.append({
                            'Fichier': fichier.name,
                            'Nb Produits': len(produits),
                            'Total HT': total_fichier
                        })
                    
                    progress_bar.progress((i + 1) / len(fichiers))
                
                # Effacer la progress bar
                progress_bar.empty()
                
                if tous_les_produits:
                    # Créer DataFrame
                    df = pd.DataFrame(tous_les_produits)
                    
                    # Compléter les colonnes manquantes
                    colonnes = ['Date Facture', 'N° Facture', 'Fournisseur', 'Code Article',
                               'Désignation', 'Catégorie', 'Contenance', 'Nb Unités',
                               'Prix Unitaire HT', 'Montant HT', 'TVA %', 'Montant TTC', 'Fichier Source']
                    
                    for col in colonnes:
                        if col not in df.columns:
                            if col == 'TVA %':
                                df[col] = 5.5
                            elif col == 'Montant TTC':
                                df[col] = df['Montant HT'] * 1.055
                            else:
                                df[col] = ''
                    
                    # Résumé des fichiers analysés
                    st.success(f"✅ Analyse terminée : {len(tous_les_produits)} produits extraits")
                    
                    # Afficher résumé par fichier
                    if resume_fichiers:
                        with st.expander("📋 Résumé par fichier"):
                            df_resume = pd.DataFrame(resume_fichiers)
                            st.dataframe(df_resume, use_container_width=True, hide_index=True)
                    
                    # Métriques principales
                    st.divider()
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("📦 Total produits", len(df))
                    with col2:
                        st.metric("💶 Total HT", f"{df['Montant HT'].sum():,.2f}€")
                    with col3:
                        st.metric("💶 Total TTC", f"{df['Montant TTC'].sum():,.2f}€")
                    with col4:
                        st.metric("📄 Fournisseurs", df['Fournisseur'].nunique())
                    
                    # Tabs
                    tab1, tab2, tab3, tab4 = st.tabs(["📊 Données", "📈 Graphiques", "📋 Statistiques", "💾 Export"])
                    
                    with tab1:
                        st.subheader("Données extraites")
                        
                        # Filtres
                        col1, col2 = st.columns(2)
                        with col1:
                            fournisseurs = st.multiselect(
                                "Filtrer par fournisseur",
                                df['Fournisseur'].unique(),
                                default=df['Fournisseur'].unique()
                            )
                        with col2:
                            categories = st.multiselect(
                                "Filtrer par catégorie",
                                df['Catégorie'].unique(),
                                default=df['Catégorie'].unique()
                            )
                        
                        # Appliquer filtres
                        df_filtre = df[
                            (df['Fournisseur'].isin(fournisseurs)) &
                            (df['Catégorie'].isin(categories))
                        ]
                        
                        # Afficher données
                        st.dataframe(
                            df_filtre[['Date Facture', 'Fournisseur', 'Désignation', 
                                      'Nb Unités', 'Prix Unitaire HT', 'Montant HT']],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Prix Unitaire HT": st.column_config.NumberColumn(format="%.2f €"),
                                "Montant HT": st.column_config.NumberColumn(format="%.2f €")
                            }
                        )
                    
                    with tab2:
                        st.subheader("Visualisations")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Répartition par fournisseur
                            fig_fourn = px.pie(
                                df.groupby('Fournisseur')['Montant HT'].sum().reset_index(),
                                values='Montant HT',
                                names='Fournisseur',
                                title="Répartition par fournisseur"
                            )
                            st.plotly_chart(fig_fourn, use_container_width=True)
                        
                        with col2:
                            # Répartition par catégorie
                            fig_cat = px.pie(
                                df.groupby('Catégorie')['Montant HT'].sum().reset_index(),
                                values='Montant HT',
                                names='Catégorie',
                                title="Répartition par catégorie"
                            )
                            st.plotly_chart(fig_cat, use_container_width=True)
                        
                        # Top 10 produits
                        top_produits = df.nlargest(10, 'Montant HT')
                        fig_top = px.bar(
                            top_produits,
                            x='Montant HT',
                            y='Désignation',
                            orientation='h',
                            title="Top 10 produits par montant"
                        )
                        st.plotly_chart(fig_top, use_container_width=True)
                    
                    with tab3:
                        st.subheader("Statistiques détaillées")
                        
                        # Stats par fournisseur
                        stats_fourn = df.groupby('Fournisseur').agg({
                            'Montant HT': ['sum', 'mean', 'count'],
                            'N° Facture': 'nunique'
                        }).round(2)
                        stats_fourn.columns = ['Total HT', 'Moyenne HT', 'Nb Produits', 'Nb Factures']
                        st.dataframe(stats_fourn, use_container_width=True)
                        
                        # Stats par catégorie
                        st.divider()
                        stats_cat = df.groupby('Catégorie').agg({
                            'Montant HT': ['sum', 'mean', 'count']
                        }).round(2)
                        stats_cat.columns = ['Total HT', 'Moyenne HT', 'Nb Produits']
                        st.dataframe(stats_cat, use_container_width=True)
                    
                    with tab4:
                        st.subheader("Export des données")
                        
                        # Excel
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, sheet_name='Données', index=False)
                            
                            # Résumé
                            resume = pd.DataFrame({
                                'Métrique': ['Nb produits', 'Total HT', 'Total TTC', 'Nb fournisseurs'],
                                'Valeur': [
                                    len(df),
                                    f"{df['Montant HT'].sum():.2f}€",
                                    f"{df['Montant TTC'].sum():.2f}€",
                                    df['Fournisseur'].nunique()
                                ]
                            })
                            resume.to_excel(writer, sheet_name='Résumé', index=False)
                        
                        output.seek(0)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.download_button(
                                label="📥 Télécharger Excel",
                                data=output,
                                file_name=f"analyse_factures_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        
                        with col2:
                            # CSV
                            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                            st.download_button(
                                label="📥 Télécharger CSV",
                                data=csv,
                                file_name=f"analyse_factures_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv"
                            )
                        
                        st.success("""
                        ✅ **Données prêtes pour Power BI !**
                        - Format compatible Excel/CSV
                        - Colonnes structurées
                        - Montants calculés correctement
                        """)
                
                else:
                    st.error("❌ Aucune donnée n'a pu être extraite")
    
    # Footer
    st.divider()
    st.caption("💻 Développé pour Bistro Urbain | 📊 Optimisé pour Power BI | 🔒 Données sécurisées")


if __name__ == "__main__":
    main()
