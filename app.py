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

class AnalyseurFacturesPro:
    """
    Analyseur professionnel de factures - Version 4.0
    Compatible avec tous les fournisseurs du Bistro Urbain
    """
    
    def __init__(self):
        self.donnees_extraites = []
        self.stats_extraction = {
            'total_lignes': 0,
            'lignes_extraites': 0,
            'methode_utilisee': ''
        }
        
    def detecter_fournisseur(self, texte):
        """Détection intelligente du fournisseur"""
        texte_upper = texte.upper()
        
        fournisseurs = {
            'Fougères Boissons': ['FOUGERES BOISSONS', 'VTE-20', 'LANDE DU BAS'],
            'Metro': ['METRO.FR', 'METRO FRANCE', 'N° FACTURE'],
            'Promocash': ['PROMOCASH', 'PROMO CASH'],
            'Cave Les 3B': ['CAVE LES 3B', 'SOMMELIERS-CAVISTES', 'F99'],
            'TerreAzur': ['TERREAZUR', 'TERRE AZUR', 'POMONA'],
            'EpiSaveurs': ['EPISAVEURS', 'EPI SAVEURS'],
            'Colin RHD': ['COLIN RHD', 'TOQUE D\'AZUR'],
            'Passionfroid': ['PASSIONFROID', 'PASSION FROID'],
            'SVA Jean Roze': ['SVA JEAN ROZE', 'JEAN ROZE', 'SVA']
        }
        
        for fournisseur, patterns in fournisseurs.items():
            for pattern in patterns:
                if pattern in texte_upper:
                    return fournisseur
        
        return 'Autre fournisseur'
    
    def extraire_contenance_avancee(self, texte):
        """Extraction avancée de la contenance avec tous les formats possibles"""
        if not texte:
            return "1PC", 1, "PC"
        
        texte = texte.upper()
        
        # Patterns complets pour toutes les contenances
        patterns = [
            # Format multiplicateur (6x75CL, 12x100CL, etc.)
            (r'(\d+)\s*[X×]\s*(\d+(?:[,\.]\d+)?)\s*(CL|ML|L|KG|G)', lambda m: (f"{m.group(1)}x{m.group(2)}{m.group(3)}", float(m.group(1)) * float(m.group(2).replace(',', '.')), m.group(3))),
            
            # Format simple avec unité (75CL, 1.5L, 500G, etc.)
            (r'(\d+(?:[,\.]\d+)?)\s*(CL|ML|L|KG|G)\b', lambda m: (f"{m.group(1)}{m.group(2)}", float(m.group(1).replace(',', '.')), m.group(2))),
            
            # Format pack (PACK DE 6, 6 PACK, etc.)
            (r'(?:PACK\s+DE\s+)?(\d+)\s+(?:PACK|PC|UN|BTL|BTE)', lambda m: (f"{m.group(1)}PC", float(m.group(1)), "PC")),
            
            # Format carton/caisse (CAR 6, CAISSE 12, etc.)
            (r'(?:CAR|CAISSE|CAI|FAR)\s*(\d+)', lambda m: (f"{m.group(1)}PC", float(m.group(1)), "PC")),
            
            # Format bouteille seule
            (r'(\d+)\s*(?:BOUTEILLE|BTL|BTE)', lambda m: (f"{m.group(1)}BTL", float(m.group(1)), "BTL")),
            
            # Format poids (2.5KG, 500G, etc.)
            (r'(\d+(?:[,\.]\d+)?)\s*(KG|G)', lambda m: (f"{m.group(1)}{m.group(2)}", float(m.group(1).replace(',', '.')), m.group(2)))
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, texte)
            if match:
                return formatter(match)
        
        # Si aucun pattern ne correspond, retourner 1PC par défaut
        return "1PC", 1, "PC"
    
    def calculer_volume_total(self, quantite, contenance_str):
        """Calcule le volume/poids total en tenant compte de la quantité et de la contenance"""
        contenance_format, contenance_val, unite = self.extraire_contenance_avancee(contenance_str)
        
        # Convertir en unité standard (L pour liquides, KG pour solides)
        if unite == "CL":
            volume_unitaire = contenance_val / 100  # Convertir en litres
            unite_finale = "L"
        elif unite == "ML":
            volume_unitaire = contenance_val / 1000  # Convertir en litres
            unite_finale = "L"
        elif unite == "L":
            volume_unitaire = contenance_val
            unite_finale = "L"
        elif unite == "G":
            volume_unitaire = contenance_val / 1000  # Convertir en kg
            unite_finale = "KG"
        elif unite == "KG":
            volume_unitaire = contenance_val
            unite_finale = "KG"
        else:
            volume_unitaire = contenance_val
            unite_finale = unite
        
        volume_total = quantite * volume_unitaire
        
        return {
            'contenance_format': contenance_format,
            'volume_unitaire': volume_unitaire,
            'volume_total': volume_total,
            'unite': unite_finale
        }
    
    def analyser_fougeres_avance(self, texte, tables):
        """Analyse avancée pour Fougères Boissons avec extraction complète"""
        produits = []
        
        # Extraction des métadonnées
        date_match = re.search(r'du\s+(\d{2}/\d{2}/\d{4})', texte)
        date_facture = date_match.group(1) if date_match else datetime.now().strftime('%d/%m/%Y')
        
        num_match = re.search(r'VTE-(\d+)', texte)
        num_facture = f"VTE-{num_match.group(1)}" if num_match else "N/A"
        
        # Stratégie 1: Utiliser les tables si disponibles
        if tables:
            for table in tables:
                for row in table:
                    if row and len(row) >= 5 and row[0]:
                        # Vérifier si c'est un code produit (7 chiffres)
                        if re.match(r'^\d{7}$', str(row[0])):
                            code = str(row[0])
                            designation = str(row[1]) if row[1] else ""
                            
                            # Extraction intelligente des valeurs numériques
                            quantite = 1
                            prix_unitaire = 0
                            montant = 0
                            
                            for i, cell in enumerate(row[2:], 2):
                                if cell:
                                    cell_str = str(cell).strip()
                                    # Détecter les quantités
                                    if cell_str.isdigit() and int(cell_str) < 1000:
                                        quantite = int(cell_str)
                                    # Détecter les prix (format XX.XX ou XX,XX)
                                    elif re.match(r'^\d+[,\.]\d{2,4}$', cell_str):
                                        val = float(cell_str.replace(',', '.'))
                                        if prix_unitaire == 0:
                                            prix_unitaire = val
                                        else:
                                            montant = val
                            
                            if montant == 0 and prix_unitaire > 0:
                                montant = prix_unitaire * quantite
                            
                            # Extraction avancée de la contenance
                            contenance_info = self.calculer_volume_total(quantite, designation)
                            
                            produits.append({
                                'Date Facture': date_facture,
                                'N° Facture': num_facture,
                                'Fournisseur': 'Fougères Boissons',
                                'Code Article': code,
                                'Désignation': designation,
                                'Désignation Simplifiée': self.simplifier_designation(designation),
                                'Catégorie': self.determiner_categorie_avancee(designation),
                                'Contenance Unitaire': contenance_info['contenance_format'],
                                'Nb Unités': quantite,
                                'Volume Unitaire': contenance_info['volume_unitaire'],
                                'Volume Total': contenance_info['volume_total'],
                                'Unité': contenance_info['unite'],
                                'Prix Unitaire HT': prix_unitaire,
                                'Montant HT': montant,
                                'Prix/Litre ou Prix/Kg': prix_unitaire / contenance_info['volume_unitaire'] if contenance_info['volume_unitaire'] > 0 else 0
                            })
        
        # Stratégie 2: Parser le texte ligne par ligne
        if not produits:
            lignes = texte.split('\n')
            for ligne in lignes:
                # Pattern amélioré pour Fougères
                match = re.match(r'^(\d{7})\s+(.+?)(?:\s+(\d+)\s+)?(?:\w{2,3}\s+)?(\d+[,\.]\d+)\s+(\d+[,\.]\d+)?', ligne)
                if match:
                    code = match.group(1)
                    designation = match.group(2).strip()
                    quantite = int(match.group(3)) if match.group(3) else 1
                    prix_unitaire = float(match.group(4).replace(',', '.'))
                    montant = float(match.group(5).replace(',', '.')) if match.group(5) else prix_unitaire * quantite
                    
                    contenance_info = self.calculer_volume_total(quantite, designation)
                    
                    produits.append({
                        'Date Facture': date_facture,
                        'N° Facture': num_facture,
                        'Fournisseur': 'Fougères Boissons',
                        'Code Article': code,
                        'Désignation': designation,
                        'Désignation Simplifiée': self.simplifier_designation(designation),
                        'Catégorie': self.determiner_categorie_avancee(designation),
                        'Contenance Unitaire': contenance_info['contenance_format'],
                        'Nb Unités': quantite,
                        'Volume Unitaire': contenance_info['volume_unitaire'],
                        'Volume Total': contenance_info['volume_total'],
                        'Unité': contenance_info['unite'],
                        'Prix Unitaire HT': prix_unitaire,
                        'Montant HT': montant,
                        'Prix/Litre ou Prix/Kg': prix_unitaire / contenance_info['volume_unitaire'] if contenance_info['volume_unitaire'] > 0 else 0
                    })
        
        return produits
    
    def analyser_metro_avance(self, texte, tables):
        """Analyse avancée pour Metro/Promocash"""
        produits = []
        
        # Métadonnées
        date_match = re.search(r'Date facture\s*:\s*(\d{2}-\d{2}-\d{4})', texte)
        if not date_match:
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', texte)
        date_facture = date_match.group(1).replace('-', '/') if date_match else datetime.now().strftime('%d/%m/%Y')
        
        num_match = re.search(r'(?:N°\s*FACTURE|FACTURE N°).*?(\d{8,})', texte)
        num_facture = num_match.group(1) if num_match else "N/A"
        
        # Parser le texte
        lignes = texte.split('\n')
        for ligne in lignes:
            # Pattern Metro amélioré
            patterns = [
                r'^(\d{10,13})\s+(\d{6,})\s+(.+?)\s+(\d+[,\.]\d{2})',  # Format standard
                r'^(\d{10,13})\s+(.+?)\s+(\d+[,\.]\d{2})\s+(\d+)',  # Format alternatif
                r'^(\d{6,})\s+(.+?)\s+(\d+)\s+(\d+[,\.]\d{2})'  # Format court
            ]
            
            for pattern in patterns:
                match = re.match(pattern, ligne)
                if match:
                    groups = match.groups()
                    code = groups[0]
                    
                    # Identifier la désignation et les valeurs
                    if len(groups) == 4:
                        if re.match(r'^\d{6,}$', groups[1]):
                            designation = groups[2]
                            prix = float(groups[3].replace(',', '.'))
                        else:
                            designation = groups[1]
                            prix = float(groups[2].replace(',', '.'))
                    else:
                        designation = groups[1]
                        prix = float(groups[-1].replace(',', '.'))
                    
                    # Extraction de la quantité depuis la désignation
                    quantite = 1
                    quant_match = re.search(r'(\d+)\s*(?:PC|UN|X)', designation)
                    if quant_match:
                        quantite = int(quant_match.group(1))
                    
                    contenance_info = self.calculer_volume_total(quantite, designation)
                    
                    produits.append({
                        'Date Facture': date_facture,
                        'N° Facture': num_facture,
                        'Fournisseur': self.detecter_fournisseur(texte),
                        'Code Article': code,
                        'Désignation': designation,
                        'Désignation Simplifiée': self.simplifier_designation(designation),
                        'Catégorie': self.determiner_categorie_avancee(designation),
                        'Contenance Unitaire': contenance_info['contenance_format'],
                        'Nb Unités': quantite,
                        'Volume Unitaire': contenance_info['volume_unitaire'],
                        'Volume Total': contenance_info['volume_total'],
                        'Unité': contenance_info['unite'],
                        'Prix Unitaire HT': prix / quantite if quantite > 0 else prix,
                        'Montant HT': prix,
                        'Prix/Litre ou Prix/Kg': (prix / quantite) / contenance_info['volume_unitaire'] if contenance_info['volume_unitaire'] > 0 and quantite > 0 else 0
                    })
                    break
        
        return produits
    
    def analyser_universel(self, texte, tables, fournisseur):
        """Analyseur universel pour tous types de factures"""
        produits = []
        
        # Extraction de la date (patterns multiples)
        date_patterns = [
            r'(?:du|le|Date)\s+(\d{2}[/-]\d{2}[/-]\d{4})',
            r'(\d{2}[/-]\d{2}[/-]\d{4})',
            r'(\d{2}\.\d{2}\.\d{4})'
        ]
        
        date_facture = None
        for pattern in date_patterns:
            match = re.search(pattern, texte, re.IGNORECASE)
            if match:
                date_facture = match.group(1).replace('-', '/').replace('.', '/')
                break
        
        if not date_facture:
            date_facture = datetime.now().strftime('%d/%m/%Y')
        
        # Extraction du numéro de facture
        num_patterns = [
            r'(?:FACTURE|N°|NUM)\s*(?:N°)?\s*[:=]?\s*([A-Z0-9\-]+)',
            r'([A-Z]{1,3}\d{6,})',
            r'(\d{8,})'
        ]
        
        num_facture = None
        for pattern in num_patterns:
            match = re.search(pattern, texte)
            if match:
                num_facture = match.group(1)
                break
        
        if not num_facture:
            num_facture = f"AUTO_{datetime.now().strftime('%Y%m%d%H%M')}"
        
        # Stratégie 1: Utiliser les tables
        if tables:
            for table in tables:
                for row in table:
                    if row and len(row) >= 3:
                        # Identifier les colonnes pertinentes
                        designation = None
                        prix = None
                        quantite = 1
                        code = ""
                        
                        for i, cell in enumerate(row):
                            if cell:
                                cell_str = str(cell).strip()
                                
                                # Code produit (commence par des chiffres)
                                if i == 0 and re.match(r'^\d{3,}', cell_str):
                                    code = cell_str
                                # Désignation (texte non numérique)
                                elif not re.match(r'^[\d,\.]+$', cell_str) and len(cell_str) > 3:
                                    if not designation or len(cell_str) > len(designation):
                                        designation = cell_str
                                # Prix (format monétaire)
                                elif re.match(r'^\d+[,\.]\d{2}$', cell_str):
                                    prix = float(cell_str.replace(',', '.'))
                                # Quantité (petit nombre entier)
                                elif cell_str.isdigit() and int(cell_str) < 100:
                                    quantite = int(cell_str)
                        
                        if designation and prix:
                            contenance_info = self.calculer_volume_total(quantite, designation)
                            
                            produits.append({
                                'Date Facture': date_facture,
                                'N° Facture': num_facture,
                                'Fournisseur': fournisseur,
                                'Code Article': code,
                                'Désignation': designation,
                                'Désignation Simplifiée': self.simplifier_designation(designation),
                                'Catégorie': self.determiner_categorie_avancee(designation),
                                'Contenance Unitaire': contenance_info['contenance_format'],
                                'Nb Unités': quantite,
                                'Volume Unitaire': contenance_info['volume_unitaire'],
                                'Volume Total': contenance_info['volume_total'],
                                'Unité': contenance_info['unite'],
                                'Prix Unitaire HT': prix / quantite if quantite > 0 else prix,
                                'Montant HT': prix,
                                'Prix/Litre ou Prix/Kg': (prix / quantite) / contenance_info['volume_unitaire'] if contenance_info['volume_unitaire'] > 0 and quantite > 0 else 0
                            })
        
        # Stratégie 2: Parser le texte avec des patterns génériques
        if not produits:
            lignes = texte.split('\n')
            for ligne in lignes:
                # Pattern générique pour détecter les lignes de produits
                # Format: [code optionnel] designation quantité prix
                match = re.match(r'^(?:(\d{3,})\s+)?(.+?)\s+(\d{1,3})\s+(\d+[,\.]\d{2})', ligne)
                if match:
                    code = match.group(1) if match.group(1) else ""
                    designation = match.group(2).strip()
                    quantite = int(match.group(3))
                    prix = float(match.group(4).replace(',', '.'))
                    
                    contenance_info = self.calculer_volume_total(quantite, designation)
                    
                    produits.append({
                        'Date Facture': date_facture,
                        'N° Facture': num_facture,
                        'Fournisseur': fournisseur,
                        'Code Article': code,
                        'Désignation': designation,
                        'Désignation Simplifiée': self.simplifier_designation(designation),
                        'Catégorie': self.determiner_categorie_avancee(designation),
                        'Contenance Unitaire': contenance_info['contenance_format'],
                        'Nb Unités': quantite,
                        'Volume Unitaire': contenance_info['volume_unitaire'],
                        'Volume Total': contenance_info['volume_total'],
                        'Unité': contenance_info['unite'],
                        'Prix Unitaire HT': prix / quantite if quantite > 0 else prix,
                        'Montant HT': prix,
                        'Prix/Litre ou Prix/Kg': (prix / quantite) / contenance_info['volume_unitaire'] if contenance_info['volume_unitaire'] > 0 and quantite > 0 else 0
                    })
        
        return produits
    
    def simplifier_designation(self, designation):
        """Simplification intelligente de la désignation"""
        if not designation:
            return ""
        
        # Supprimer les codes et références
        designation = re.sub(r'\([^)]*\)', '', designation)
        designation = re.sub(r'\b\d{6,}\b', '', designation)
        designation = re.sub(r'REF[:\s]\S+', '', designation)
        
        # Supprimer les volumes à la fin
        designation = re.sub(r'\d+[,\.]\d*\s*(CL|ML|L|KG|G)$', '', designation)
        
        # Nettoyer les espaces
        designation = ' '.join(designation.split())
        
        return designation.strip()
    
    def determiner_categorie_avancee(self, designation):
        """Catégorisation avancée avec plus de précision"""
        if not designation:
            return "Autre"
        
        designation_lower = designation.lower()
        
        categories_detaillees = {
            'Spiritueux': ['gin', 'whisky', 'vodka', 'rhum', 'cognac', 'armagnac', 'get 27', 'jack daniel', 'jameson', 'beefeater'],
            'Vins': ['vin', 'bordeaux', 'bourgogne', 'champagne', 'crémant', 'prosecco', 'cava', 'muscadet', 'côtes'],
            'Bières': ['bière', 'beer', 'lager', 'ale', 'ipa', 'stout'],
            'Liqueurs & Apéritifs': ['liqueur', 'cassis', 'lillet', 'martini', 'campari', 'aperol', 'pastis', 'ricard'],
            'Boissons Soft': ['coca', 'pepsi', 'limonade', 'orangina', 'schweppes', 'perrier', 'eau', 'jus', 'soda'],
            'Viande Rouge': ['boeuf', 'veau', 'agneau', 'mouton', 'entrecôte', 'filet', 'côte', 'bavette'],
            'Viande Blanche': ['poulet', 'dinde', 'porc', 'lapin', 'canard'],
            'Poissons': ['saumon', 'bar', 'dorade', 'cabillaud', 'lieu', 'sole', 'turbot'],
            'Fruits de Mer': ['crevette', 'homard', 'huître', 'moule', 'coquille', 'langoustine'],
            'Légumes Frais': ['salade', 'tomate', 'carotte', 'courgette', 'aubergine', 'poivron', 'concombre'],
            'Féculents': ['pomme de terre', 'pâte', 'riz', 'semoule', 'quinoa', 'blé'],
            'Produits Laitiers': ['lait', 'crème', 'beurre', 'yaourt', 'fromage', 'comté', 'camembert', 'roquefort'],
            'Epicerie': ['huile', 'vinaigre', 'sel', 'poivre', 'épice', 'sauce', 'moutarde', 'mayonnaise'],
            'Desserts': ['glace', 'sorbet', 'tarte', 'gâteau', 'chocolat', 'bonbon']
        }
        
        for categorie, mots_cles in categories_detaillees.items():
            for mot in mots_cles:
                if mot in designation_lower:
                    return categorie
        
        return 'Autre'
    
    def analyser_pdf(self, fichier_pdf, nom_fichier=""):
        """Analyse principale d'un PDF avec détection automatique du format"""
        tous_les_produits = []
        
        try:
            with pdfplumber.open(fichier_pdf) as pdf:
                texte_complet = ""
                tables_completes = []
                
                # Extraire texte et tables de toutes les pages
                for page in pdf.pages:
                    texte_page = page.extract_text()
                    if texte_page:
                        texte_complet += texte_page + "\n"
                    
                    tables = page.extract_tables()
                    if tables:
                        tables_completes.extend(tables)
                
                # Détecter le fournisseur
                fournisseur = self.detecter_fournisseur(texte_complet)
                
                # Appliquer la stratégie d'analyse appropriée
                if fournisseur == 'Fougères Boissons':
                    produits = self.analyser_fougeres_avance(texte_complet, tables_completes)
                elif fournisseur in ['Metro', 'Promocash']:
                    produits = self.analyser_metro_avance(texte_complet, tables_completes)
                else:
                    produits = self.analyser_universel(texte_complet, tables_completes, fournisseur)
                
                # Ajouter le nom du fichier source et enrichir les données
                for produit in produits:
                    produit['Fichier Source'] = nom_fichier
                    
                    # Calculer des métriques supplémentaires
                    if produit.get('Volume Total', 0) > 0:
                        produit['Coût par unité de volume'] = produit['Montant HT'] / produit['Volume Total']
                    else:
                        produit['Coût par unité de volume'] = 0
                
                tous_les_produits.extend(produits)
                
                # Si aucun produit trouvé, extraction de secours
                if not tous_les_produits:
                    st.warning(f"⚠️ Extraction basique pour {nom_fichier}")
                    # Essayer d'extraire au moins le montant total
                    montant_match = re.search(r'(?:TOTAL|NET|TTC).*?([\d\s]+[,\.]\d{2})', texte_complet, re.IGNORECASE)
                    if montant_match:
                        montant = float(montant_match.group(1).replace(' ', '').replace(',', '.'))
                        tous_les_produits.append({
                            'Date Facture': datetime.now().strftime('%d/%m/%Y'),
                            'N° Facture': 'EXTRACTION_BASIQUE',
                            'Fournisseur': fournisseur,
                            'Code Article': '',
                            'Désignation': f'Montant total facture - {fournisseur}',
                            'Désignation Simplifiée': 'Total facture',
                            'Catégorie': 'Autre',
                            'Contenance Unitaire': '1PC',
                            'Nb Unités': 1,
                            'Volume Unitaire': 1,
                            'Volume Total': 1,
                            'Unité': 'PC',
                            'Prix Unitaire HT': montant,
                            'Montant HT': montant,
                            'Prix/Litre ou Prix/Kg': 0,
                            'Fichier Source': nom_fichier,
                            'Coût par unité de volume': 0
                        })
                        
        except Exception as e:
            st.error(f"❌ Erreur lors de l'analyse de {nom_fichier}: {str(e)}")
            
        return tous_les_produits


# Interface Streamlit professionnelle
def main():
    st.set_page_config(
        page_title="Analyseur de Factures PRO - Bistro Urbain",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # CSS personnalisé
    st.markdown("""
        <style>
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            border-radius: 15px;
            color: white;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .metric-card {
            background: white;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .success-message {
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            padding: 1rem;
            border-radius: 5px;
        }
        </style>
        <div class="main-header">
            <h1>📊 Analyseur de Factures Professionnel</h1>
            <p>Version 4.0 - Compatible tous fournisseurs | Export Power BI optimisé</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Sidebar avec options
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Options d'analyse
        st.subheader("Options d'analyse")
        extract_contenance = st.checkbox("Extraire les contenances détaillées", value=True)
        calculate_volumes = st.checkbox("Calculer les volumes totaux", value=True)
        group_by_category = st.checkbox("Grouper par catégorie", value=False)
        
        st.divider()
        
        # Informations
        st.subheader("📋 Fournisseurs supportés")
        st.info("""
        ✅ **Optimisés:**
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
        
        # Guide d'hébergement
        st.subheader("🌐 Hébergement")
        with st.expander("Comment partager cet outil ?"):
            st.markdown("""
            **Option 1: Streamlit Cloud (Gratuit)**
            1. Créez un compte GitHub
            2. Uploadez le code
            3. Connectez à share.streamlit.io
            4. Obtenez votre URL publique
            
            **Option 2: Heroku**
            ```bash
            heroku create votre-app
            git push heroku main
            ```
            
            **Option 3: Local (réseau)**
            ```bash
            streamlit run app.py --server.address 0.0.0.0
            ```
            """)
    
    # Zone principale
    analyseur = AnalyseurFacturesPro()
    
    # Upload de fichiers
    col1, col2 = st.columns([3, 1])
    
    with col1:
        fichiers = st.file_uploader(
            "📁 Glissez vos factures PDF ici (tous fournisseurs acceptés)",
            type=['pdf'],
            accept_multiple_files=True,
            help="L'outil détecte automatiquement le format et extrait toutes les données"
        )
    
    with col2:
        if fichiers:
            st.metric("Fichiers chargés", len(fichiers))
            taille_totale = sum(f.size for f in fichiers) / 1024
            st.metric("Taille totale", f"{taille_totale:.1f} KB")
    
    if fichiers:
        # Bouton d'analyse principal
        if st.button("🚀 ANALYSER LES FACTURES", type="primary", use_container_width=True):
            
            with st.spinner("🔄 Analyse en cours... Extraction des données, contenances et calcul des volumes..."):
                tous_les_produits = []
                stats_analyse = {
                    'total_fichiers': len(fichiers),
                    'fichiers_reussis': 0,
                    'total_produits': 0,
                    'montant_total': 0
                }
                
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Container pour les résultats par fichier
                resultats_container = st.container()
                
                # Analyser chaque fichier
                for i, fichier in enumerate(fichiers):
                    status_text.text(f"📄 Analyse de {fichier.name}...")
                    
                    produits = analyseur.analyser_pdf(fichier, fichier.name)
                    
                    if produits:
                        tous_les_produits.extend(produits)
                        stats_analyse['fichiers_reussis'] += 1
                        stats_analyse['total_produits'] += len(produits)
                        stats_analyse['montant_total'] += sum(p.get('Montant HT', 0) for p in produits)
                        
                        # Afficher un mini-résumé
                        with resultats_container:
                            st.success(f"✅ {fichier.name}: {len(produits)} produits extraits - {sum(p.get('Montant HT', 0) for p in produits):.2f}€ HT")
                    else:
                        with resultats_container:
                            st.warning(f"⚠️ {fichier.name}: Aucune donnée extraite")
                    
                    progress_bar.progress((i + 1) / len(fichiers))
                
                # Clear status
                status_text.empty()
                progress_bar.empty()
                
                if tous_les_produits:
                    st.divider()
                    
                    # Créer le DataFrame enrichi
                    df = pd.DataFrame(tous_les_produits)
                    
                    # Ajouter les colonnes manquantes avec valeurs par défaut
                    colonnes_completes = [
                        'Date Facture', 'N° Facture', 'Fournisseur', 'Code Article',
                        'Désignation', 'Désignation Simplifiée', 'Catégorie',
                        'Contenance Unitaire', 'Nb Unités', 'Volume Unitaire',
                        'Volume Total', 'Unité', 'Prix Unitaire HT', 'Montant HT',
                        'Prix/Litre ou Prix/Kg', 'Coût par unité de volume',
                        'TVA %', 'Montant TTC', 'Origine', 'Fichier Source'
                    ]
                    
                    for col in colonnes_completes:
                        if col not in df.columns:
                            if col == 'TVA %':
                                df[col] = 5.5
                            elif col == 'Montant TTC':
                                df[col] = df['Montant HT'] * 1.055  # Avec TVA à 5.5%
                            elif col == 'Origine':
                                df[col] = 'France'
                            else:
                                df[col] = 0 if col.startswith(('Prix', 'Montant', 'Volume', 'Coût')) else ''
                    
                    # Affichage des résultats en tabs
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "📊 Données complètes", 
                        "📈 Analyses visuelles", 
                        "📋 Statistiques", 
                        "💰 Analyse financière",
                        "💾 Export Power BI"
                    ])
                    
                    with tab1:
                        st.subheader("📊 Données extraites avec contenances et volumes")
                        
                        # Métriques principales
                        col1, col2, col3, col4, col5 = st.columns(5)
                        with col1:
                            st.metric("📦 Total produits", f"{len(df):,}")
                        with col2:
                            st.metric("💶 Montant HT", f"{df['Montant HT'].sum():,.2f}€")
                        with col3:
                            st.metric("💶 Montant TTC", f"{df['Montant TTC'].sum():,.2f}€")
                        with col4:
                            volume_total = df[df['Unité'] == 'L']['Volume Total'].sum()
                            st.metric("🍾 Volume liquides", f"{volume_total:.1f}L")
                        with col5:
                            poids_total = df[df['Unité'] == 'KG']['Volume Total'].sum()
                            st.metric("⚖️ Poids solides", f"{poids_total:.1f}KG")
                        
                        # Filtres dynamiques
                        st.subheader("🔍 Filtres")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            fournisseurs = st.multiselect(
                                "Fournisseurs",
                                df['Fournisseur'].unique(),
                                default=df['Fournisseur'].unique()
                            )
                        with col2:
                            categories = st.multiselect(
                                "Catégories",
                                df['Catégorie'].unique(),
                                default=df['Catégorie'].unique()
                            )
                        with col3:
                            montant_min = st.number_input("Montant HT min", value=0.0)
                        with col4:
                            montant_max = st.number_input("Montant HT max", value=float(df['Montant HT'].max()))
                        
                        # Appliquer les filtres
                        df_filtre = df[
                            (df['Fournisseur'].isin(fournisseurs)) &
                            (df['Catégorie'].isin(categories)) &
                            (df['Montant HT'] >= montant_min) &
                            (df['Montant HT'] <= montant_max)
                        ]
                        
                        # Affichage du dataframe
                        colonnes_affichage = [
                            'Date Facture', 'Fournisseur', 'Désignation', 
                            'Nb Unités', 'Contenance Unitaire', 'Volume Total',
                            'Unité', 'Prix Unitaire HT', 'Montant HT', 'Catégorie'
                        ]
                        
                        st.dataframe(
                            df_filtre[colonnes_affichage],
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "Prix Unitaire HT": st.column_config.NumberColumn(format="%.2f €"),
                                "Montant HT": st.column_config.NumberColumn(format="%.2f €"),
                                "Volume Total": st.column_config.NumberColumn(format="%.2f"),
                                "Nb Unités": st.column_config.NumberColumn(format="%d")
                            }
                        )
                    
                    with tab2:
                        st.subheader("📈 Analyses visuelles")
                        
                        # Graphiques en colonnes
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Répartition par fournisseur
                            fig_fourn = px.pie(
                                df.groupby('Fournisseur')['Montant HT'].sum().reset_index(),
                                values='Montant HT',
                                names='Fournisseur',
                                title="💼 Répartition des achats par fournisseur",
                                color_discrete_sequence=px.colors.qualitative.Set3
                            )
                            st.plotly_chart(fig_fourn, use_container_width=True)
                            
                            # Top 10 produits par montant
                            top_produits = df.nlargest(10, 'Montant HT')[['Désignation Simplifiée', 'Montant HT']]
                            fig_top = px.bar(
                                top_produits,
                                x='Montant HT',
                                y='Désignation Simplifiée',
                                orientation='h',
                                title="🏆 Top 10 produits par montant",
                                color='Montant HT',
                                color_continuous_scale='Viridis'
                            )
                            st.plotly_chart(fig_top, use_container_width=True)
                        
                        with col2:
                            # Répartition par catégorie
                            fig_cat = px.pie(
                                df.groupby('Catégorie')['Montant HT'].sum().reset_index(),
                                values='Montant HT',
                                names='Catégorie',
                                title="📦 Répartition par catégorie",
                                hole=0.4
                            )
                            st.plotly_chart(fig_cat, use_container_width=True)
                            
                            # Analyse des volumes par catégorie
                            volumes_cat = df.groupby(['Catégorie', 'Unité'])['Volume Total'].sum().reset_index()
                            fig_vol = px.bar(
                                volumes_cat,
                                x='Catégorie',
                                y='Volume Total',
                                color='Unité',
                                title="📊 Volumes par catégorie et unité",
                                barmode='group'
                            )
                            fig_vol.update_xaxes(tickangle=45)
                            st.plotly_chart(fig_vol, use_container_width=True)
                    
                    with tab3:
                        st.subheader("📋 Statistiques détaillées")
                        
                        # Statistiques par fournisseur
                        st.markdown("### 🏢 Analyse par fournisseur")
                        stats_fournisseur = df.groupby('Fournisseur').agg({
                            'Montant HT': ['sum', 'mean', 'count'],
                            'Volume Total': 'sum',
                            'N° Facture': 'nunique'
                        }).round(2)
                        stats_fournisseur.columns = ['Total HT', 'Moyenne HT', 'Nb Produits', 'Volume Total', 'Nb Factures']
                        st.dataframe(stats_fournisseur, use_container_width=True)
                        
                        # Statistiques par catégorie
                        st.markdown("### 📦 Analyse par catégorie")
                        stats_categorie = df.groupby('Catégorie').agg({
                            'Montant HT': ['sum', 'mean'],
                            'Volume Total': 'sum',
                            'Prix/Litre ou Prix/Kg': 'mean'
                        }).round(2)
                        stats_categorie.columns = ['Total HT', 'Moyenne HT', 'Volume Total', 'Prix moyen/unité']
                        st.dataframe(stats_categorie, use_container_width=True)
                        
                        # Top produits par volume
                        st.markdown("### 🥇 Top 10 produits par volume")
                        top_volumes = df.nlargest(10, 'Volume Total')[['Désignation', 'Volume Total', 'Unité', 'Fournisseur']]
                        st.dataframe(top_volumes, use_container_width=True, hide_index=True)
                    
                    with tab4:
                        st.subheader("💰 Analyse financière approfondie")
                        
                        # Analyse des marges potentielles
                        st.markdown("### 📊 Indicateurs financiers clés")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            total_ht = df['Montant HT'].sum()
                            total_ttc = df['Montant TTC'].sum()
                            tva_totale = total_ttc - total_ht
                            st.metric("TVA totale", f"{tva_totale:.2f}€")
                        with col2:
                            prix_moyen = df['Prix Unitaire HT'].mean()
                            st.metric("Prix unitaire moyen", f"{prix_moyen:.2f}€")
                        with col3:
                            if df['Volume Total'].sum() > 0:
                                cout_moyen_volume = df['Montant HT'].sum() / df['Volume Total'].sum()
                                st.metric("Coût moyen/unité volume", f"{cout_moyen_volume:.2f}€")
                        
                        # Évolution temporelle si plusieurs dates
                        if df['Date Facture'].nunique() > 1:
                            st.markdown("### 📈 Évolution temporelle")
                            df['Date'] = pd.to_datetime(df['Date Facture'], format='%d/%m/%Y', errors='coerce')
                            evolution = df.groupby('Date')['Montant HT'].sum().reset_index()
                            fig_temps = px.line(
                                evolution,
                                x='Date',
                                y='Montant HT',
                                title="Evolution des achats dans le temps",
                                markers=True
                            )
                            st.plotly_chart(fig_temps, use_container_width=True)
                        
                        # Analyse ABC (Pareto)
                        st.markdown("### 📊 Analyse ABC (Principe de Pareto)")
                        df_pareto = df.groupby('Désignation')['Montant HT'].sum().sort_values(ascending=False).reset_index()
                        df_pareto['Cumul %'] = (df_pareto['Montant HT'].cumsum() / df_pareto['Montant HT'].sum() * 100).round(1)
                        df_pareto['Classe'] = pd.cut(df_pareto['Cumul %'], bins=[0, 80, 95, 100], labels=['A', 'B', 'C'])
                        
                        # Afficher les produits classe A (80% du CA)
                        produits_a = df_pareto[df_pareto['Classe'] == 'A']
                        st.info(f"📌 {len(produits_a)} produits représentent 80% de vos achats (Classe A)")
                        st.dataframe(produits_a[['Désignation', 'Montant HT', 'Cumul %']], use_container_width=True, hide_index=True)
                    
                    with tab5:
                        st.subheader("💾 Export optimisé pour Power BI")
                        
                        st.success("""
                        ✅ **Données enrichies prêtes pour Power BI:**
                        - Toutes les contenances extraites et formatées
                        - Volumes totaux calculés
                        - Catégorisation automatique
                        - Prix par unité de volume
                        - Format compatible avec les tableaux croisés dynamiques
                        """)
                        
                        # Préparer l'export Excel multi-feuilles
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            # Feuille 1: Données complètes
                            df.to_excel(writer, sheet_name='Données_Complètes', index=False)
                            
                            # Feuille 2: Résumé par fournisseur
                            resume_fournisseur = df.groupby('Fournisseur').agg({
                                'Montant HT': 'sum',
                                'Montant TTC': 'sum',
                                'Volume Total': 'sum',
                                'N° Facture': 'nunique',
                                'Code Article': 'count'
                            }).round(2)
                            resume_fournisseur.columns = ['Total HT', 'Total TTC', 'Volume Total', 'Nb Factures', 'Nb Produits']
                            resume_fournisseur.to_excel(writer, sheet_name='Résumé_Fournisseurs')
                            
                            # Feuille 3: Résumé par catégorie
                            resume_categorie = df.groupby('Catégorie').agg({
                                'Montant HT': 'sum',
                                'Volume Total': 'sum',
                                'Code Article': 'count'
                            }).round(2)
                            resume_categorie.columns = ['Total HT', 'Volume Total', 'Nb Produits']
                            resume_categorie.to_excel(writer, sheet_name='Résumé_Catégories')
                            
                            # Feuille 4: Analyse ABC
                            if 'df_pareto' in locals():
                                df_pareto.to_excel(writer, sheet_name='Analyse_ABC', index=False)
                            
                            # Feuille 5: Métadonnées
                            metadata = pd.DataFrame({
                                'Information': [
                                    'Date extraction',
                                    'Nombre de fichiers analysés',
                                    'Nombre total de produits',
                                    'Montant total HT',
                                    'Montant total TTC',
                                    'Volume total liquides (L)',
                                    'Poids total solides (KG)',
                                    'Nombre de fournisseurs',
                                    'Période',
                                    'Version outil'
                                ],
                                'Valeur': [
                                    datetime.now().strftime('%d/%m/%Y %H:%M'),
                                    stats_analyse['total_fichiers'],
                                    len(df),
                                    f"{df['Montant HT'].sum():.2f}€",
                                    f"{df['Montant TTC'].sum():.2f}€",
                                    f"{df[df['Unité'] == 'L']['Volume Total'].sum():.2f}",
                                    f"{df[df['Unité'] == 'KG']['Volume Total'].sum():.2f}",
                                    df['Fournisseur'].nunique(),
                                    f"Du {df['Date Facture'].min()} au {df['Date Facture'].max()}",
                                    '4.0 PRO'
                                ]
                            })
                            metadata.to_excel(writer, sheet_name='Métadonnées', index=False)
                        
                        output.seek(0)
                        
                        # Boutons de téléchargement
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.download_button(
                                label="📥 EXCEL COMPLET POWER BI",
                                data=output,
                                file_name=f"analyse_complete_bistro_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                type="primary"
                            )
                        
                        with col2:
                            # CSV pour compatibilité universelle
                            csv = df.to_csv(index=False, sep=';', encoding='utf-8-sig', decimal=',')
                            st.download_button(
                                label="📥 CSV (Format FR)",
                                data=csv,
                                file_name=f"donnees_bistro_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                                mime="text/csv"
                            )
                        
                        with col3:
                            # JSON pour intégrations API
                            json_data = df.to_json(orient='records', force_ascii=False, indent=2, date_format='iso')
                            st.download_button(
                                label="📥 JSON (API)",
                                data=json_data,
                                file_name=f"donnees_bistro_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                                mime="application/json"
                            )
                        
                        # Instructions Power BI
                        with st.expander("📚 Guide d'import dans Power BI"):
                            st.markdown("""
                            ### 🚀 Import dans Power BI Desktop
                            
                            1. **Ouvrez Power BI Desktop**
                            2. **Obtenir les données > Excel**
                            3. **Sélectionnez le fichier téléchargé**
                            4. **Cochez toutes les feuilles** pour import
                            5. **Transformez les données** si nécessaire
                            
                            ### 📊 Visualisations recommandées
                            
                            **Dashboard KPI:**
                            - Carte: Montant total HT/TTC
                            - Jauge: Volume total
                            - Graphique en secteurs: Répartition fournisseurs
                            
                            **Analyse détaillée:**
                            - Tableau croisé: Catégorie × Fournisseur
                            - Graphique en cascade: Top produits
                            - Carte de chaleur: Prix/volume par catégorie
                            
                            **Mesures DAX suggérées:**
                            ```dax
                            Marge Brute = SUM('Données'[Montant HT]) * 0.3
                            Prix Moyen Litre = DIVIDE(SUM('Données'[Montant HT]), SUM('Données'[Volume Total]))
                            Rotation Stock = COUNTROWS('Données') / DISTINCTCOUNT('Données'[Code Article])
                            ```
                            """)
                
                else:
                    st.error("❌ Aucune donnée n'a pu être extraite des factures uploadées.")
                    st.info("""
                    💡 **Conseils:**
                    - Vérifiez que les PDF ne sont pas scannés (texte sélectionnable)
                    - Assurez-vous qu'ils ne sont pas protégés par mot de passe
                    - Essayez avec un seul fichier pour identifier le problème
                    """)
    
    # Footer avec informations
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption("🔧 Version 4.0 PRO - Extraction avancée")
    with col2:
        st.caption("📊 Optimisé pour Power BI")
    with col3:
        st.caption("🌐 Hébergeable sur Streamlit Cloud")


if __name__ == "__main__":
    main()