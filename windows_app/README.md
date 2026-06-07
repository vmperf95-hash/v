# 🛡️ 3DS Hunter — Logiciel Windows de prospection 3D Secure

**Outil desktop pour identifier automatiquement les sites e-commerce dépourvus de 3D Secure** et exporter leurs coordonnées pour ta prospection B2B.

---

## ✨ Fonctionnalités

- 🤖 **Découverte automatique** de sites e-commerce via DuckDuckGo (aucune clé API requise)
- ✍️ **Saisie manuelle** ou import d'une liste d'URLs (.txt / .csv)
- 🛡️ **Détection 3DS multi-méthodes** avec score de probabilité 0-100 :
  - Identification de la passerelle de paiement (Stripe, PayPlug, Mollie, Adyen, PayPal, Lyra/SystemPay, Monetico, Atos SIPS, Stancer, Checkout.com, Shopify Payments, Klarna...)
  - Recherche de mots-clés 3DS / SCA dans CGV et mentions légales
  - Détection de site e-commerce vs vitrine
- 📧 **Extraction automatique des contacts** : emails, téléphones, formulaire de contact, réseaux sociaux
- 📊 **Export CSV / Excel** multi-onglets (Tous / Prospects / Avec 3DS)
- 🎨 Interface graphique moderne (CustomTkinter, thème sombre)
- 🚀 **100% gratuit / open-source**, aucun service tiers payant

---

## 🚀 Démarrage rapide (sur ton PC Windows)

### Option 1 — Lancer directement en Python

```bat
cd windows_app
pip install -r requirements.txt
python main.py
```

### Option 2 — Compiler en `.exe` autonome (recommandé)

Double-clique sur **`build.bat`** dans le dossier `windows_app`.

PyInstaller va générer un fichier unique `dist\3DS_Hunter.exe` que tu peux :
- Distribuer à n'importe quel PC Windows (pas besoin de Python installé)
- Lancer par double-clic
- Mettre dans une clé USB ou sur le bureau

---

## 📖 Comment utiliser

### 1. Onglet "🔎 Découverte / Scan"

#### A. Découverte automatique
- Saisis des **mots-clés** ciblant ton marché : `bijoux artisanaux, cosmétiques bio, vêtements enfants`
- Règle le nombre max de sites par requête (15 = bon compromis)
- Active "Analyser après découverte" → le scan démarre automatiquement
- Clique sur **"🤖 Lancer la découverte"**

#### B. Saisie manuelle
- Colle une ou plusieurs URLs (une par ligne)
- Ou importe un fichier `.txt`/`.csv`
- Clique sur **"🚀 Lancer le scan"**

### 2. Onglet "📊 Résultats"

Visualise chaque site avec :
- 🎯 **PROSPECT** (rouge) = site e-commerce sans 3DS → à contacter !
- ⚠️ **INCERTAIN** (orange) = à vérifier manuellement
- ✅ **AVEC 3DS** (vert) = pas un prospect
- 🚫 **PAS E-COMMERCE** (gris) = ignoré

Utilise les filtres pour ne voir que les prospects.

### 3. Onglet "💾 Export"

Exporte en CSV ou Excel (3 onglets : Tous, Prospects, Déjà 3DS).
Le fichier contient : URL, Nom entreprise, Verdict, Score, Passerelles, **Emails**, **Téléphones**, Pages contact, Réseaux sociaux, etc.

---

## 🧠 Comment fonctionne la détection ?

Le score 3DS est calculé à partir de plusieurs signaux :

| Signal | Points |
|---|---|
| Passerelle moderne (Stripe, PayPlug, Mollie, Adyen, Lyra...) avec 3DS par défaut | +60 |
| Passerelle supportant 3DS mais activation manuelle | +20 |
| Mentions « 3D Secure », « SCA », « authentification forte » dans CGV | +25 |
| HTTPS actif | +5 |
| Aucune passerelle reconnue sur un e-commerce | −20 |
| Aucune mention 3DS dans pages légales | −5 |

- **≥ 70** → 3DS Probable ✅
- **40-69** → Incertain ⚠️
- **< 40** → Sans 3DS Probable 🎯

> ⚠️ Le score est une **estimation** basée sur des heuristiques (le seul moyen 100% sûr est de tenter un paiement réel). Les sites « Incertain » et « Sans 3DS » sont tes meilleurs prospects.

---

## 🛠️ Stack technique

- **Python 3.10+**
- **CustomTkinter** pour l'interface (moderne, thème sombre)
- **Requests + BeautifulSoup4 + lxml** pour le scraping
- **fake-useragent** pour rotation d'UA
- **Pandas + openpyxl** pour les exports
- **PyInstaller** pour compiler en `.exe`

---

## 📁 Structure du projet

```
windows_app/
├── main.py                       # Entrée GUI
├── requirements.txt
├── build.bat                     # Compilation .exe
├── core/
│   ├── detector.py               # Détection 3DS
│   ├── scraper.py                # Découverte DuckDuckGo
│   ├── contact_extractor.py      # Emails/tel/réseaux sociaux
│   └── exporter.py               # CSV / Excel
├── gui/
├── data/
│   └── payment_gateways.json     # Base des passerelles
└── exports/                      # Fichiers générés
```

---

## 💡 Conseils de prospection

1. **Cible géographique** : ajoute des mots-clés régionaux (`bijoux paris`, `cosmétiques lyon`)
2. **Niche** : préfère les petites boutiques indépendantes (les gros e-commerce ont déjà 3DS)
3. **Approche** : propose un **audit gratuit** dans ton 1er email pour engager
4. **Argument clé PSD2** : depuis 2021, la 3DS est **obligatoire** en Europe pour la majorité des paiements → tu peux légitimement les sensibiliser au risque de fraude et de chargebacks
5. **Volume** : lance 1 découverte = ~50-150 prospects qualifiés par jour

---

## ⚖️ Légal / Éthique

- Le scraping respecte les délais (1.2s entre requêtes)
- N'utilise pas l'outil pour spammer — respecte le RGPD pour la prospection B2B (mention dans email, opt-out facile)
- Les données extraites sont publiques (présentes sur les sites)

---

## 🐛 Problèmes courants

**"DuckDuckGo ne renvoie rien"** → Vérifie ta connexion, ou attends 1-2 min (anti-bot temporaire). Réessaie avec d'autres mots-clés.

**Site inaccessible** → Certains sites bloquent les bots. Tu peux les ajouter manuellement après vérification.

**Compilation lente** → PyInstaller prend 2-5 min, c'est normal. L'.exe final fait ~50-80 MB.

---

Bonne prospection ! 🚀
