"""
Scraping / découverte automatique de sites e-commerce via DuckDuckGo HTML
(pas de clé API requise).
"""
import re
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

DUCK_HTML = "https://html.duckduckgo.com/html/"

# Domaines à exclure (marketplaces, gros sites institutionnels...)
EXCLUDED_DOMAINS = {
    "amazon.fr", "amazon.com", "amazon.de", "amazon.co.uk",
    "ebay.fr", "ebay.com", "cdiscount.com", "fnac.com",
    "darty.com", "boulanger.com", "leclerc.com",
    "google.com", "google.fr", "youtube.com", "facebook.com",
    "linkedin.com", "instagram.com", "twitter.com", "x.com",
    "wikipedia.org", "wikipédia.org", "lemonde.fr", "lefigaro.fr",
    "leboncoin.fr", "manomano.fr", "rueducommerce.fr",
    "aliexpress.com", "wish.com", "shein.com", "temu.com",
    "carrefour.fr", "auchan.fr",
    "societe.com", "pagesjaunes.fr", "verif.com", "infogreffe.fr",
    "service-public.fr", "impots.gouv.fr",
    "pinterest.fr", "pinterest.com",
    "trustpilot.com", "avis-verifies.com",
}


def _session():
    ua = UserAgent()
    s = requests.Session()
    s.headers.update({
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "fr-FR,fr;q=0.9",
    })
    return s


def _extract_domain(url):
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        host = p.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return url


def search_duckduckgo(query, max_results=30):
    """
    Recherche DuckDuckGo HTML version (sans API).
    Retourne une liste d'URLs uniques (domaines).
    """
    session = _session()
    results = []
    seen_domains = set()

    try:
        params = {"q": query, "kl": "fr-fr"}
        r = session.post(DUCK_HTML, data=params, timeout=15)
        if r.status_code != 200:
            return results

        # 1) Récupère les URLs uddg= (résultats de recherche)
        uddg_links = re.findall(r'uddg=([^&"]+)', r.text)
        all_urls = []
        for u in uddg_links:
            try:
                decoded = urllib.parse.unquote(u)
                if decoded.startswith("http"):
                    all_urls.append(decoded)
            except Exception:
                continue

        # 2) Fallback : extrait tous les liens http(s) directs
        if not all_urls:
            all_urls = re.findall(r'<a[^>]*href="(https?://[^"]+)"', r.text)

        for href in all_urls:
            domain = _extract_domain(href)
            if not domain or domain in seen_domains:
                continue
            # Filtre les domaines DDG/internes
            if "duckduckgo" in domain or "ddg.gg" in domain:
                continue
            if any(domain == ex or domain.endswith("." + ex) for ex in EXCLUDED_DOMAINS):
                continue

            seen_domains.add(domain)
            results.append("https://" + domain)
            if len(results) >= max_results:
                break
    except Exception as e:
        print(f"[scraper] Erreur DDG: {e}")

    return results


def discover_ecommerce_sites(keywords, country="fr", max_per_query=20, progress_cb=None):
    """
    Découvre des sites e-commerce via plusieurs requêtes ciblées.
    keywords: liste de mots-clés (ex: ['bijoux', 'vetement enfant'])
    Retourne liste d'URLs uniques.
    """
    if isinstance(keywords, str):
        keywords = [keywords]

    all_results = []
    seen = set()

    # Modificateurs pour cibler des e-commerces
    modifiers = [
        "boutique en ligne",
        "acheter en ligne",
        "site e-commerce",
        "achat en ligne",
    ]

    queries = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        for mod in modifiers:
            queries.append(f"{kw} {mod}")
        # Aussi version simple
        queries.append(f"{kw} site:.{country}")

    total = len(queries)
    for i, q in enumerate(queries):
        if progress_cb:
            progress_cb(i + 1, total, q)
        urls = search_duckduckgo(q, max_results=max_per_query)
        for u in urls:
            d = _extract_domain(u)
            if d not in seen:
                seen.add(d)
                all_results.append(u)
        time.sleep(1.2)  # Politesse

    return all_results
