"""
Détection 3D Secure sur un site web.
Combine plusieurs méthodes pour produire un score de probabilité (0-100).
"""
import json
import re
import os
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# Chargement de la base des passerelles
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GATEWAYS_PATH = os.path.join(_BASE_DIR, "data", "payment_gateways.json")

with open(_GATEWAYS_PATH, "r", encoding="utf-8") as f:
    PAYMENT_GATEWAYS = json.load(f)

# Mots-clés indiquant 3DS dans le texte
KEYWORDS_3DS = [
    "3d secure", "3-d secure", "3ds", "3d-secure",
    "authentification forte", "sca", "psd2",
    "strong customer authentication",
    "authentification du porteur", "secure code",
    "verified by visa", "mastercard securecode", "mastercard identity check",
    "american express safekey"
]

# Signatures techniques 3DS universelles (présentes sur les sites avec 3DS actif,
# indépendamment de la passerelle). Très forte corrélation avec 3DS v2 activé.
THREE_DS_TECHNICAL_SIGNATURES = [
    "cardinalcommerce.com",        # Visa Cardinal Commerce, fournisseur 3DS leader
    "centinelapi",                  # Cardinal Centinel API (3DS)
    "ds.netcetera.com",             # Netcetera Directory Server (3DS v2)
    "3dsecure2", "3ds2.",
    "threeds2",
    "threedsserver", "threeds-server",
    "acs.modirum.com",              # Modirum ACS (3DS v2)
    "acs.acculynk", "acs.cybersource",
    "challengewindowsize",          # JS variable 3DS v2 challenge
    "threedsmethodurl", "threedsmethoddata",
    "cb_3ds", "_3ds_", "three_d_secure",
    "stripe3ds",                    # Stripe 3DS JS
    "stripe.js/v3",                 # Stripe v3 = 3DS v2 obligatoire
    "adyen3ds2",
    "checkout-3ds",
    "mpi.scellius", "mpi.systempay",
    "directoryserver",
    "cybersource.com/3ds",
]

# Pages susceptibles de mentionner 3DS (CGV / légales)
LEGAL_PAGES = [
    "/cgv", "/cgu", "/mentions-legales", "/conditions-generales",
    "/conditions-de-vente", "/securite", "/security", "/faq", "/aide", "/help",
    "/conditions", "/legal", "/terms", "/privacy",
    "/politique-confidentialite", "/cookies"
]

# Pages de tunnel d'achat (où le 3DS est techniquement visible)
CHECKOUT_PAGES = [
    "/cart", "/panier", "/checkout", "/commande", "/paiement", "/payment",
    "/caisse", "/order", "/finaliser", "/validate-order",
    "/cart.html", "/checkout.html", "/index.php?controller=cart",
    "/index.php?controller=order", "/?page_id=cart",
]

# E-commerce indicators
ECOMMERCE_INDICATORS = [
    "add-to-cart", "add_to_cart", "addtocart", "ajouter au panier",
    "panier", "cart", "checkout", "commander", "shop", "boutique",
    "produit", "product", "buy now", "acheter", "woocommerce",
    "shopify", "prestashop", "magento", "wp-content/plugins/woo"
]


def _get_session():
    ua = UserAgent()
    s = requests.Session()
    s.headers.update({
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    return s


def _fetch(url, session=None, timeout=12):
    """Récupère le HTML d'une page, retourne (html, status_code, final_url)."""
    if session is None:
        session = _get_session()
    try:
        if not url.startswith("http"):
            url = "https://" + url
        r = session.get(url, timeout=timeout, allow_redirects=True, verify=True)
        return r.text, r.status_code, r.url
    except requests.exceptions.SSLError:
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True, verify=False)
            return r.text, r.status_code, r.url
        except Exception:
            return None, None, url
    except Exception:
        return None, None, url


def detect_payment_gateways(html):
    """Retourne la liste des passerelles détectées dans le HTML."""
    detected = []
    if not html:
        return detected
    html_lower = html.lower()
    for gw_id, gw in PAYMENT_GATEWAYS.items():
        for sig in gw["signatures"]:
            if sig.lower() in html_lower:
                detected.append({
                    "id": gw_id,
                    "name": gw["name"],
                    "supports_3ds": gw["supports_3ds"],
                    "3ds_default": gw["3ds_default"],
                    "notes": gw["notes"],
                    "matched_signature": sig
                })
                break
    return detected


def detect_3ds_keywords(html):
    """Cherche des mentions explicites de 3DS dans le texte."""
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True).lower()
    found = []
    for kw in KEYWORDS_3DS:
        if kw in text:
            found.append(kw)
    return found


def detect_3ds_technical(html):
    """Cherche des signatures techniques 3DS universelles (cardinalcommerce, etc.)."""
    if not html:
        return []
    html_lower = html.lower()
    found = []
    for sig in THREE_DS_TECHNICAL_SIGNATURES:
        if sig.lower() in html_lower:
            found.append(sig)
    return found


def detect_payment_iframes(html, base_url):
    """Détecte les iframes de paiement chargées (forte indication de PSP utilisée)."""
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    iframes = []
    psp_hosts = [
        "stripe.com", "paypal.com", "payplug", "mollie", "adyen",
        "systempay", "lyra", "payzen", "scellius", "sogecommerce",
        "monetico", "worldline", "mercanet", "atos",
        "checkout.com", "braintree", "vivapayments", "stancer",
        "shopify.com", "klarna", "amazonpay", "applepay", "googlepay",
        "cardinalcommerce", "netcetera",
    ]
    for ifr in soup.find_all("iframe", src=True):
        src = ifr["src"].lower()
        for host in psp_hosts:
            if host in src:
                iframes.append({"host": host, "src": ifr["src"][:200]})
                break
    return iframes


def is_ecommerce(html):
    """Détermine si le site est un e-commerce."""
    if not html:
        return False
    html_lower = html.lower()
    score = sum(1 for kw in ECOMMERCE_INDICATORS if kw in html_lower)
    return score >= 2


def find_legal_links(html, base_url):
    """Trouve les liens vers pages légales/CGV."""
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text(" ", strip=True).lower()
        for marker in LEGAL_PAGES:
            if marker in href or marker.replace("/", "") in text:
                full = urljoin(base_url, a["href"])
                links.add(full)
                break
    return list(links)[:6]


def build_checkout_urls(base_url):
    """Génère des URLs candidates pour les pages de tunnel d'achat."""
    urls = []
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    for path in CHECKOUT_PAGES:
        urls.append(root + path)
    return urls


def analyze_site(url, deep=True, max_legal_pages=4, scan_checkout=True):
    """
    Analyse un site et retourne un dictionnaire détaillé :
    {
      url, final_url, status, is_ecommerce,
      gateways: [...],
      keywords_found: [...],
      tech_signatures: [...],     # signatures techniques 3DS
      iframes: [...],              # iframes paiement
      legal_pages_checked: [...],
      checkout_pages_checked: [...],
      score_3ds: int 0-100,
      verdict: '3DS Probable' | 'Sans 3DS Probable' | 'Incertain' | 'Pas e-commerce',
      reason: str
    }
    """
    result = {
        "url": url,
        "final_url": url,
        "status": None,
        "is_ecommerce": False,
        "gateways": [],
        "keywords_found": [],
        "tech_signatures": [],
        "iframes": [],
        "legal_pages_checked": [],
        "checkout_pages_checked": [],
        "score_3ds": 0,
        "verdict": "Erreur",
        "reason": ""
    }

    session = _get_session()
    html, status, final_url = _fetch(url, session)
    result["status"] = status
    result["final_url"] = final_url

    if not html or (status and status >= 400):
        result["verdict"] = "Site inaccessible"
        result["reason"] = f"Code HTTP: {status}"
        return result

    ecom = is_ecommerce(html)
    result["is_ecommerce"] = ecom

    # Analyse homepage
    gateways = detect_payment_gateways(html)
    kws = detect_3ds_keywords(html)
    tech_sigs = detect_3ds_technical(html)
    iframes = detect_payment_iframes(html, final_url)

    # Deep scan : pages légales (CGV)
    if deep:
        legal_links = find_legal_links(html, final_url)
        for link in legal_links[:max_legal_pages]:
            sub_html, sub_status, _ = _fetch(link, session, timeout=8)
            if sub_html:
                result["legal_pages_checked"].append(link)
                for gw in detect_payment_gateways(sub_html):
                    if not any(g["id"] == gw["id"] for g in gateways):
                        gateways.append(gw)
                for kw in detect_3ds_keywords(sub_html):
                    if kw not in kws:
                        kws.append(kw)
                for sig in detect_3ds_technical(sub_html):
                    if sig not in tech_sigs:
                        tech_sigs.append(sig)

    # Scan des pages de tunnel d'achat (cart, checkout, panier...)
    if scan_checkout and ecom:
        checkout_urls = build_checkout_urls(final_url)
        # Limite à 4 pour rester rapide
        for c_url in checkout_urls[:4]:
            c_html, c_status, c_final = _fetch(c_url, session, timeout=8)
            if c_html and c_status == 200 and len(c_html) > 500:
                result["checkout_pages_checked"].append(c_final)
                for gw in detect_payment_gateways(c_html):
                    if not any(g["id"] == gw["id"] for g in gateways):
                        gateways.append(gw)
                for sig in detect_3ds_technical(c_html):
                    if sig not in tech_sigs:
                        tech_sigs.append(sig)
                for ifr in detect_payment_iframes(c_html, c_final):
                    if not any(i["host"] == ifr["host"] for i in iframes):
                        iframes.append(ifr)

    result["gateways"] = gateways
    result["keywords_found"] = kws
    result["tech_signatures"] = tech_sigs
    result["iframes"] = iframes

    # Scoring
    score = 0
    reasons = []

    if not ecom:
        result["verdict"] = "Pas e-commerce"
        result["reason"] = "Aucun indicateur d'e-commerce détecté"
        return result

    modern_gw = [g for g in gateways if g["3ds_default"]]
    legacy_gw = [g for g in gateways if not g["3ds_default"] and g["supports_3ds"]]
    no_3ds_gw = [g for g in gateways if not g["supports_3ds"]]

    if modern_gw:
        score += 55
        reasons.append(f"Passerelle moderne 3DS par défaut: {', '.join(g['name'] for g in modern_gw[:3])}")
    if legacy_gw:
        score += 20
        reasons.append(f"Passerelle 3DS optionnel: {', '.join(g['name'] for g in legacy_gw[:2])}")
    if no_3ds_gw:
        score -= 10

    # 🆕 BOOST : signatures techniques 3DS universelles (très forte preuve)
    if tech_sigs:
        score += 25
        reasons.append(f"Signatures techniques 3DS v2 détectées: {', '.join(tech_sigs[:3])}")

    # 🆕 BOOST : iframes PSP chargées sur checkout
    if iframes:
        score += 10
        reasons.append(f"Iframes paiement chargées: {', '.join(i['host'] for i in iframes[:3])}")

    if kws:
        score += 15
        reasons.append(f"Mentions 3DS dans CGV: {', '.join(kws[:3])}")
    else:
        score -= 5

    if final_url.startswith("https://"):
        score += 5

    if not gateways and not iframes:
        score -= 20
        reasons.append("Aucune passerelle ni iframe paiement détectée (custom/obsolète ?)")

    # 🆕 Si checkout scanné mais aucune trace 3DS → suspect (sauf si passerelle moderne déjà détectée)
    if scan_checkout and result["checkout_pages_checked"] and not tech_sigs and not iframes:
        if not modern_gw:
            score -= 10
            reasons.append("Pages checkout accessibles mais aucune trace technique 3DS")
        # Si passerelle moderne déjà détectée → léger doute, mais pas de pénalité majeure
        # (le 3DS est chargé via JS dynamique, invisible au scan statique)

    score = max(0, min(100, score))
    result["score_3ds"] = score

    if score >= 70:
        result["verdict"] = "3DS Probable"
    elif score >= 40:
        result["verdict"] = "Incertain"
    else:
        result["verdict"] = "Sans 3DS Probable"

    result["reason"] = " | ".join(reasons)
    return result
