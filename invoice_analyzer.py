import os
import re
import pandas as pd
import fitz  # PyMuPDF
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json
from pathlib import Path
import numpy as np

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
            print(f"Erreur lors de la lecture du PDF {pdf_path}: {e}")
            return ""
    
    def identify_supplier(self, text: str) -> Optional[str]:
        """Identifie le fournisseur à partir du texte"""
        for supplier, patterns in self.suppliers_patterns.items():
            for identifier in patterns['identifier']:
                if identifier.lower() in text.lower():
                    return supplier
        return None
    
    def parse_volume(self, description: str) -> Tuple[float, str]:
        """
        Extrait le volume/contenance d'une description de produit
        Ex: "COCA COLA 6x1L" -> (6.0, "L")
        """
        # Patterns pour différents formats de volume
        patterns = [
            # Format 6x1L, 12x33CL, etc.
            r'(\d+)[xX\*](\d+(?:[,\.]\d+)?)\s*([LlCcMm][Ll]?)',
            # Format 1.5L, 75CL, etc.
            r'(\d+(?:[,\.]\d+)?)\s*([LlCcMm][Ll])',
            # Format 6X1,5L
            r'(\d+)[xX\*](\d+[,\.]\d+)\s*([LlCcMm][Ll]?)',
            # Format avec KG
            r'(\d+(?:[,\.]\d+)?)\s*(KG|kg|Kg)',
            # Format bouteille unique (70CL, 100CL)
            r'(\d+)\s*(CL|cl)',
            # Format pack (6P, 12P)
            r'(\d+)\s*P(?:\s|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, description)
            if match:
                groups = match.groups()
                if len(groups) == 3:  # Format multiplicateur
                    try:
                        multiplier = float(groups[0].replace(',', '.'))
                        volume = float(groups[1].replace(',', '.'))
                        unit = groups[2].upper()
                        
                        # Conversion en litres
                        if 'CL' in unit.upper():
                            total_volume = multiplier * volume / 100
                        elif 'ML' in unit.upper():
                            total_volume = multiplier * volume / 1000
                        else:
                            total_volume = multiplier * volume
                        
                        return total_volume, 'L'
                    except:
                        pass
                elif len(groups) == 2:  # Format simple
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
        # Supprime les codes produits au début
        product_name = re.sub(r'^\d+\s+', '', product_name)
        
        # Supprime les informations de volume/contenance
        product_name = re.sub(r'\d+[xX\*]\d+[,\.]?\d*\s*[LlCcMm][Ll]?', '', product_name)
        product_name = re.sub(r'\d+[,\.]?\d*\s*[LlCcMm][Ll]', '', product_name)
        product_name = re.sub(r'\d+[,\.]?\d*\s*KG', '', product_name, flags=re.IGNORECASE)
        product_name = re.sub(r'\d+%', '', product_name)
        product_name = re.sub(r'\d+P\s', '', product_name)
        
        # Supprime les codes entre parenthèses
        product_name = re.sub(r'\([^)]*\)', '', product_name)
        
        # Nettoie les espaces multiples
        product_name = ' '.join(product_name.split())
        
        return product_name.strip()
    
    def parse_invoice(self, text: str, supplier: str) -> Dict:
        """Parse une facture selon le fournisseur"""
        patterns = self.suppliers_patterns[supplier]
        
        # Extraction des informations générales
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
            # Conversion en format uniforme
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
        
        # Parsing des lignes de produits selon le fournisseur
        lines = text.split('\n')
        
        if supplier == 'TERRE AZUR':
            self._parse_terre_azur_products(lines, invoice_data)
        elif supplier == 'METRO':
            self._parse_metro_products(lines, invoice_data)
        elif supplier == 'COLIN RHD':
            self._parse_colin_products(lines, invoice_data)
        elif supplier == 'EPISAVEURS':
            self._parse_episaveurs_products(lines, invoice_data)
        elif supplier == 'FOUGERES BOISSONS':
            self._parse_fougeres_products(lines, invoice_data)
        elif supplier == 'CAVE LES 3B':
            self._parse_cave3b_products(lines, invoice_data)
        else:
            # Parsing générique
            self._parse_generic_products(lines, invoice_data, patterns)
        
        return invoice_data
    
    def _parse_terre_azur_products(self, lines: List[str], invoice_data: Dict):
        """Parse spécifique pour Terre Azur"""
        for line in lines:
            # Pattern: 340/ 102946 Mangue joue 5G 1KX6 Api 2,000 PCH 2,000 KG 14,990 E 1 29,98
            match = re.match(r'^\d+/\s+(\d+)\s+(.*?)\s+(\d+[,\.]\d+)\s+(PCH|KG|COL|SAC|PU|FLT|BQT)\s+.*?\s+([\d,\.]+)$', line)
            if match:
                product = {
                    'code': match.group(1),
                    'name': self.clean_product_name(match.group(2)),
                    'quantity': float(match.group(3).replace(',', '.')),
                    'unit': match.group(4),
                    'price': float(match.group(5).replace(',', '.')),
                    'volume': 0.0,
                    'volume_unit': ''
                }
                
                # Extraction du volume
                volume, unit = self.parse_volume(match.group(2))
                product['volume'] = volume
                product['volume_unit'] = unit
                
                invoice_data['products'].append(product)
    
    def _parse_metro_products(self, lines: List[str], invoice_data: Dict):
        """Parse spécifique pour Metro"""
        for line in lines:
            # Pattern Metro avec codes barres
            match = re.match(r'^(\d{11})\s+(\d+)\s+(.*?)\s+([SI])\s+.*?\s+([\d,\.]+)\s+([DB])', line)
            if match:
                product = {
                    'code': match.group(1),
                    'name': self.clean_product_name(match.group(3)),
                    'quantity': float(match.group(2)),
                    'unit': 'UN',
                    'price': float(match.group(5).replace(',', '.')),
                    'volume': 0.0,
                    'volume_unit': ''
                }
                
                # Extraction du volume depuis le nom
                volume, unit = self.parse_volume(match.group(3))
                product['volume'] = volume
                product['volume_unit'] = unit
                
                invoice_data['products'].append(product)
    
    def _parse_colin_products(self, lines: List[str], invoice_data: Dict):
        """Parse spécifique pour Colin RHD"""
        for line in lines:
            # Pattern Colin: T2304905 1 CAR GNOCCHI DE POMME DE TERRE 30,78
            match = re.match(r'^(T\d+)\s+(\d+)\s+(CAR|UN)\s+(.*?)\s+([\d,\.]+)\s+([\d,\.]+)\s+\d+', line)
            if match:
                product = {
                    'code': match.group(1),
                    'name': self.clean_product_name(match.group(4)),
                    'quantity': float(match.group(2)),
                    'unit': match.group(3),
                    'price': float(match.group(6).replace(',', '.')),
                    'volume': 0.0,
                    'volume_unit': ''
                }
                
                invoice_data['products'].append(product)
    
    def _parse_episaveurs_products(self, lines: List[str], invoice_data: Dict):
        """Parse spécifique pour Episaveurs"""
        for line in lines:
            # Pattern similaire à Terre Azur
            match = re.match(r'^\d+/\s+(\d+)\s+(.*?)\s+(\d+[,\.]\d+)\s+(BID|PCH|COL|BTL|SAC)\s+.*?\s+([\d,\.]+)', line)
            if match:
                product = {
                    'code': match.group(1),
                    'name': self.clean_product_name(match.group(2)),
                    'quantity': float(match.group(3).replace(',', '.')),
                    'unit': match.group(4),
                    'price': float(match.group(5).replace(',', '.')),
                    'volume': 0.0,
                    'volume_unit': ''
                }
                
                volume, unit = self.parse_volume(match.group(2))
                product['volume'] = volume
                product['volume_unit'] = unit
                
                invoice_data['products'].append(product)
    
    def _parse_fougeres_products(self, lines: List[str], invoice_data: Dict):
        """Parse spécifique pour Fougères Boissons"""
        for line in lines:
            # Pattern: 0024100 CREME CASSIS GIFFARD 16% 100CL 1 BTL 1 BTL 6.5130
            match = re.match(r'^(\d{7})\s+(.*?)\s+(\d+)\s+(BTL|CAR|CAI|FAR)\s+.*?\s+([\d,\.]+)', line)
            if match:
                product = {
                    'code': match.group(1),
                    'name': self.clean_product_name(match.group(2)),
                    'quantity': float(match.group(3)),
                    'unit': match.group(4),
                    'price': 0.0,  # À calculer
                    'volume': 0.0,
                    'volume_unit': ''
                }
                
                volume, unit = self.parse_volume(match.group(2))
                product['volume'] = volume
                product['volume_unit'] = unit
                
                invoice_data['products'].append(product)
    
    def _parse_cave3b_products(self, lines: List[str], invoice_data: Dict):
        """Parse spécifique pour Cave Les 3B"""
        for line in lines:
            # Pattern: LAB20 COTES DE THAU... 6.00 4.75 4.75 28.50 C20
            match = re.match(r'^([A-Z]+\d+)\s+(.*?)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+([\d,\.]+)\s+(C\d+)', line)
            if match:
                product = {
                    'code': match.group(1),
                    'name': self.clean_product_name(match.group(2)),
                    'quantity': float(match.group(3).replace(',', '.')),
                    'unit': 'BTL',
                    'price': float(match.group(6).replace(',', '.')),
                    'unit_price': float(match.group(4).replace(',', '.')),
                    'volume': 0.75,  # Défaut pour les vins
                    'volume_unit': 'L'
                }
                
                # Tentative d'extraction du volume depuis le nom
                volume, unit = self.parse_volume(match.group(2))
                if volume > 0:
                    product['volume'] = volume
                    product['volume_unit'] = unit
                
                invoice_data['products'].append(product)
    
    def _parse_generic_products(self, lines: List[str], invoice_data: Dict, patterns: Dict):
        """Parsing générique pour les fournisseurs non spécifiques"""
        product_pattern = patterns.get('product_line', '')
        if not product_pattern:
            return
        
        for line in lines:
            match = re.match(product_pattern, line)
            if match:
                groups = match.groups()
                if len(groups) >= 4:
                    product = {
                        'code': groups[0] if len(groups) > 0 else '',
                        'name': self.clean_product_name(groups[1] if len(groups) > 1 else ''),
                        'quantity': float((groups[2] if len(groups) > 2 else '1').replace(',', '.')),
                        'unit': groups[3] if len(groups) > 3 else 'UN',
                        'price': float((groups[4] if len(groups) > 4 else '0').replace(',', '.')),
                        'volume': 0.0,
                        'volume_unit': ''
                    }
                    
                    # Extraction du volume
                    volume, unit = self.parse_volume(groups[1] if len(groups) > 1 else '')
                    product['volume'] = volume
                    product['volume_unit'] = unit
                    
                    invoice_data['products'].append(product)
    
    def process_invoices(self, input_folder: str, output_file: str = 'analyse_factures.xlsx'):
        """Traite toutes les factures d'un dossier"""
        all_invoices = []
        all_products = []
        
        # Parcours des fichiers PDF
        for filename in os.listdir(input_folder):
            if filename.lower().endswith('.pdf'):
                pdf_path = os.path.join(input_folder, filename)
                print(f"Traitement de {filename}...")
                
                # Extraction du texte
                text = self.extract_text_from_pdf(pdf_path)
                if not text:
                    print(f"  ⚠️ Impossible de lire le fichier")
                    continue
                
                # Identification du fournisseur
                supplier = self.identify_supplier(text)
                if not supplier:
                    print(f"  ⚠️ Fournisseur non reconnu")
                    continue
                
                print(f"  ✅ Fournisseur identifié: {supplier}")
                
                # Parsing de la facture
                invoice_data = self.parse_invoice(text, supplier)
                invoice_data['filename'] = filename
                
                # Ajout aux résultats
                all_invoices.append({
                    'Fichier': filename,
                    'Fournisseur': invoice_data['supplier'],
                    'N° Facture': invoice_data['invoice_number'],
                    'Date': invoice_data['date'],
                    'Total HT': invoice_data['total_amount'] - invoice_data['total_vat'],
                    'TVA': invoice_data['total_vat'],
                    'Total TTC': invoice_data['total_amount'],
                    'Nb Produits': len(invoice_data['products'])
                })
                
                # Ajout des produits
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
                        'Prix Unitaire': product.get('unit_price', product['price'] / product['quantity'] if product['quantity'] > 0 else 0),
                        'Prix Total': product['price']
                    })
        
        # Création du fichier Excel
        self.create_excel_report(all_invoices, all_products, output_file)
        
        return all_invoices, all_products
    
    def create_excel_report(self, invoices: List[Dict], products: List[Dict], output_file: str):
        """Crée un rapport Excel avec plusieurs onglets"""
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Onglet 1: Résumé des factures
            df_invoices = pd.DataFrame(invoices)
            if not df_invoices.empty:
                df_invoices.to_excel(writer, sheet_name='Résumé Factures', index=False)
            
            # Onglet 2: Détail des produits
            df_products = pd.DataFrame(products)
            if not df_products.empty:
                df_products.to_excel(writer, sheet_name='Détail Produits', index=False)
            
            # Onglet 3: Analyse par fournisseur
            if not df_invoices.empty:
                supplier_summary = df_invoices.groupby('Fournisseur').agg({
                    'N° Facture': 'count',
                    'Total HT': 'sum',
                    'TVA': 'sum',
                    'Total TTC': 'sum'
                }).rename(columns={'N° Facture': 'Nb Factures'})
                supplier_summary.to_excel(writer, sheet_name='Analyse Fournisseurs')
            
            # Onglet 4: Top produits
            if not df_products.empty:
                # Regroupement par produit
                product_summary = df_products.groupby('Produit').agg({
                    'Quantité': 'sum',
                    'Prix Total': 'sum',
                    'Fournisseur': 'first',
                    'Volume': 'mean'
                }).sort_values('Prix Total', ascending=False).head(20)
                product_summary.to_excel(writer, sheet_name='Top 20 Produits')
        
        print(f"\n✅ Rapport Excel créé: {output_file}")
        print(f"   - {len(invoices)} factures analysées")
        print(f"   - {len(products)} lignes de produits extraites")

# Fonction principale pour utilisation directe
def main():
    """Fonction principale pour tester l'analyseur"""
    analyzer = InvoiceAnalyzer()
    
    # Dossier contenant les factures
    input_folder = 'factures'
    
    # Créer le dossier s'il n'existe pas
    if not os.path.exists(input_folder):
        os.makedirs(input_folder)
        print(f"📁 Dossier '{input_folder}' créé. Placez vos factures PDF dedans.")
        return
    
    # Traitement des factures
    invoices, products = analyzer.process_invoices(input_folder)
    
    # Affichage des statistiques
    if invoices:
        df_invoices = pd.DataFrame(invoices)
        print("\n📊 Statistiques globales:")
        print(f"   - Total HT: {df_invoices['Total HT'].sum():.2f} €")
        print(f"   - Total TVA: {df_invoices['TVA'].sum():.2f} €")
        print(f"   - Total TTC: {df_invoices['Total TTC'].sum():.2f} €")
        
        print("\n📈 Par fournisseur:")
        for supplier in df_invoices['Fournisseur'].unique():
            supplier_data = df_invoices[df_invoices['Fournisseur'] == supplier]
            print(f"   {supplier}: {supplier_data['Total TTC'].sum():.2f} € ({len(supplier_data)} factures)")

if __name__ == "__main__":
    main()
