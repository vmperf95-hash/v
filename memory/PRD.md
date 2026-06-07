# PRD - 3DS Hunter

## Problème
Créer un logiciel Windows desktop qui détecte automatiquement les sites e-commerce sans 3D Secure pour proposer des services d'installation 3DS aux propriétaires.

## Utilisateur cible
Prestataire freelance / consultant qui vend des services d'installation 3D Secure (PSD2/SCA) aux e-commerçants.

## Stack technique
- **Langage** : Python 3.10+
- **GUI** : CustomTkinter (thème sombre moderne)
- **Scraping** : requests + BeautifulSoup4 + lxml + fake-useragent
- **Découverte** : DuckDuckGo HTML (pas d'API key)
- **Export** : pandas + openpyxl (CSV + Excel)
- **Packaging** : PyInstaller (.exe Windows autonome)
- **100% gratuit / open-source** (aucune API payante)

## Architecture
```
windows_app/
├── main.py                    # GUI (CustomTkinter, 4 pages)
├── requirements.txt
├── build.bat                  # Compilation .exe
├── README.md
├── core/
│   ├── detector.py            # Analyse 3DS + scoring
│   ├── scraper.py             # Découverte DuckDuckGo
│   ├── contact_extractor.py   # Emails/tel/réseaux
│   └── exporter.py            # CSV / Excel
├── data/
│   └── payment_gateways.json  # 24 passerelles connues
└── exports/                   # Fichiers générés
```

## Fonctionnalités livrées (v1.0.0) - 2026-01

### Découverte/Scan
- ✅ Saisie manuelle d'URLs (textarea, une par ligne)
- ✅ Import fichier .txt/.csv
- ✅ Découverte automatique via mots-clés (DuckDuckGo HTML scraping)
- ✅ Slider de configuration (max sites/requête)
- ✅ Scan multi-threadé non bloquant (UI réactive)
- ✅ Console de log avec horodatage
- ✅ Bouton "Arrêter" pour interrompre

### Détection 3DS
- ✅ Base de 24 passerelles de paiement (Stripe, PayPlug, Mollie, Adyen, PayPal,
     Lyra/SystemPay, Atos SIPS, Monetico, Stancer, Checkout.com, Shopify Payments,
     Wix Payments, Squarespace, Klarna, Apple Pay, Google Pay, Amazon Pay,
     Braintree, Viva Wallet, PrestaShop, Magento, Razorpay, Elavon)
- ✅ Détection sur homepage + pages CGV/légales (deep scan)
- ✅ Recherche de mots-clés 3DS / SCA / PSD2
- ✅ Détection e-commerce vs vitrine
- ✅ Scoring 0-100 avec verdict : 3DS Probable / Incertain / Sans 3DS Probable / Pas e-commerce

### Extraction contacts
- ✅ Emails (filtrés : exclusion sentry/wixpress/exemples/hashes)
- ✅ Téléphones FR stricts (format 10 chiffres)
- ✅ Formulaire de contact détecté
- ✅ Réseaux sociaux (Facebook, Instagram, LinkedIn, Twitter, YouTube)
- ✅ Crawl pages contact / mentions légales

### Résultats & Export
- ✅ Page Résultats avec cartes visuelles + filtres (Tous / Prospects / Sans 3DS / Incertain / Avec 3DS)
- ✅ Stats temps réel dans sidebar
- ✅ Export CSV (encodage utf-8-sig, séparateur `;` pour Excel FR)
- ✅ Export Excel multi-onglets (Tous / Prospects / Déjà 3DS)
- ✅ Choix du dossier de destination
- ✅ Ouverture auto du dossier après export

### UI/UX
- ✅ Thème sombre moderne (palette personnalisée GitHub-like)
- ✅ Sidebar de navigation 4 pages
- ✅ Accent vert turquoise (#00d4aa)
- ✅ Badges colorés selon verdict
- ✅ Progress bar de scan
- ✅ Aucun problème de contraste

### Build & Distribution
- ✅ Script `build.bat` (PyInstaller --onefile --windowed)
- ✅ Génère un `.exe` Windows autonome distribuable
- ✅ README complet avec instructions

## Tests fonctionnels validés
- ✅ Détection sur Shopify (90/100, ✓ 3DS)
- ✅ Détection sur boutique Wix (Wix Payments détectée, Incertain)
- ✅ Détection sur PrestaShop (à vérifier - Sans 3DS Probable)
- ✅ Extraction emails pro réels (contact@laruee.fr, etc.)
- ✅ Découverte DuckDuckGo : 10+ boutiques bijoux françaises par requête
- ✅ Export CSV / XLSX vérifiés
- ✅ GUI rendu visuel correct (contraste, alignement OK)
- ✅ Lint Python clean (ruff)

## Backlog / Améliorations possibles
- P1 : Sauvegarde session (résultats persistants entre lancements)
- P1 : Génération automatique d'email de prospection personnalisé par IA
- P2 : Suivi CRM (statut prospect : contacté/répondu/converti)
- P2 : Détection en parallèle (multithreading) pour accélérer
- P2 : Plus de moteurs de recherche (Bing, Brave Search)
- P2 : Export PDF avec rapport par site
- P3 : Mode "audit" : génère un rapport client complet
- P3 : Détection des CMS WordPress vulnérables (WooCommerce sans Stripe)
- P3 : Intégration LinkedIn pour trouver le décideur (CEO/CTO)

## Dates
- 2026-01-07 : MVP v1.0.0 livré
