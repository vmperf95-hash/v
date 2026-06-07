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

# Pages susceptibles de mentionner 3DS
LEGAL_PAGES = [
    "/cgv", "/cgu", "/mentions-legales", "/conditions-generales",
    "/conditions-de-vente", "/paiement", "/payment", "/checkout",
    "/securite", "/security", "/faq", "/aide", "/help",
    "/conditions", "/legal", "/terms", "/privacy",
    "/politique-confidentialite", "/cookies"
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
    # Limit
    return list(links)[:6]


def analyze_site(url, deep=True, max_legal_pages=4):
    """
    Analyse un site et retourne un dictionnaire détaillé :
    {
      url, final_url, status, is_ecommerce,
      gateways: [...],
      keywords_found: [...],
      legal_pages_checked: [...],
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
        "legal_pages_checked": [],
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

    # E-commerce ?
    ecom = is_ecommerce(html)
    result["is_ecommerce"] = ecom

    # Passerelles sur homepage
    gateways = detect_payment_gateways(html)

    # Keywords sur homepage
    kws = detect_3ds_keywords(html)

    # Aller chercher dans pages légales / checkout
    if deep:
        legal_links = find_legal_links(html, final_url)
        for link in legal_links[:max_legal_pages]:
            sub_html, sub_status, _ = _fetch(link, session, timeout=8)
            if sub_html:
                result["legal_pages_checked"].append(link)
                # Plus de passerelles ?
                for gw in detect_payment_gateways(sub_html):
                    if not any(g["id"] == gw["id"] for g in gateways):
                        gateways.append(gw)
                # Plus de keywords ?
                for kw in detect_3ds_keywords(sub_html):
                    if kw not in kws:
                        kws.append(kw)

    result["gateways"] = gateways
    result["keywords_found"] = kws

    # Scoring
    score = 0
    reasons = []

    if not ecom:
        result["verdict"] = "Pas e-commerce"
        result["reason"] = "Aucun indicateur d'e-commerce détecté (pas de panier, produits, etc.)"
        return result

    # Passerelles modernes avec 3DS par défaut
    modern_gw = [g for g in gateways if g["3ds_default"]]
    legacy_gw = [g for g in gateways if not g["3ds_default"] and g["supports_3ds"]]
    no_3ds_gw = [g for g in gateways if not g["supports_3ds"]]

    if modern_gw:
        score += 60
        reasons.append(f"Passerelle moderne avec 3DS par défaut: {', '.join(g['name'] for g in modern_gw)}")
    if legacy_gw:
        score += 20
        reasons.append(f"Passerelle supportant 3DS (config requise): {', '.join(g['name'] for g in legacy_gw)}")
    if no_3ds_gw:
        score -= 10
        reasons.append(f"Passerelle sans 3DS par défaut: {', '.join(g['name'] for g in no_3ds_gw)}")

    if kws:
        score += 25
        reasons.append(f"Mentions 3DS trouvées: {', '.join(kws[:3])}")
    else:
        score -= 5
        reasons.append("Aucune mention 3DS dans CGV/mentions légales")

    # HTTPS bonus
    if final_url.startswith("https://"):
        score += 5

    # Si aucune passerelle détectée du tout sur e-commerce -> suspect
    if not gateways:
        score -= 20
        reasons.append("Aucune passerelle de paiement reconnue (custom/obsolète ?)")

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
