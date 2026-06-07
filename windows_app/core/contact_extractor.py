"""
Extraction des coordonnées de contact (email, téléphone, formulaire) depuis un site.
"""
import re
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}(?:\.[a-zA-Z]{2,6})?"
)

# Téléphones français stricts : 10 chiffres commençant par 0, séparateurs cohérents
# Format international : +33 X XX XX XX XX
PHONE_REGEX = re.compile(
    r"(?:\+33|0033)\s?[1-9](?:[\s.-]\d{2}){4}"  # +33 X XX XX XX XX
    r"|\b0[1-9](?:[\s.-]?\d{2}){4}\b"  # 0X XX XX XX XX
)

CONTACT_PAGES = [
    "/contact", "/contactez-nous", "/nous-contacter", "/contact-us",
    "/about", "/a-propos", "/qui-sommes-nous", "/mentions-legales",
    "/contact.html", "/contact.php", "/contacter", "/support",
    "/aide", "/help", "/sav"
]

# Emails à exclure (génériques, exemples, images, monitoring)
EMAIL_BLACKLIST_SUFFIX = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")
EMAIL_BLACKLIST_PREFIX = ("sentry@", "wixpress", "example@", "test@", "user@", "name@", "email@",
                          "johndoe@", "john.doe@", "jane.doe@", "prenom.nom@", "nom.prenom@",
                          "votre@", "votreemail@", "monemail@", "yourname@", "votremail@",
                          "contact@example", "info@example", "admin@example")
EMAIL_BLACKLIST_DOMAINS = (
    "sentry.io", "sentry.wixpress.com", "sentry-next.wixpress.com",
    "wixpress.com", "sentry-cdn", "rollbar", "bugsnag",
    "datadoghq.com", "newrelic.com",
    "example.com", "example.fr", "domain.com", "domaine.com", "domaine.fr",
    "votresite.com", "votresite.fr", "monsite.fr", "monsite.com",
    "votre-site.fr", "votre-site.com",
)


def _session():
    ua = UserAgent()
    s = requests.Session()
    s.headers.update({
        "User-Agent": ua.random,
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    })
    return s


def _fetch(url, session, timeout=10):
    try:
        if not url.startswith("http"):
            url = "https://" + url
        r = session.get(url, timeout=timeout, allow_redirects=True, verify=True)
        return r.text, r.url
    except requests.exceptions.SSLError:
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True, verify=False)
            return r.text, r.url
        except Exception:
            return None, url
    except Exception:
        return None, url


def _clean_emails(emails):
    cleaned = set()
    # TLDs courants valides
    VALID_TLDS = {"com", "fr", "org", "net", "io", "co", "eu", "de", "uk", "be", "ch", "ca",
                  "info", "biz", "store", "shop", "online", "tech", "app", "dev", "es", "it",
                  "nl", "pl", "pt", "se", "no", "fi", "dk", "ie", "lu", "ma", "tn", "dz",
                  "us", "ai", "me", "gg", "tv", "agency", "company", "club", "boutique",
                  "paris", "lyon", "bzh", "alsace", "corsica"}
    for e in emails:
        e = e.strip().lower().rstrip(".,;:)")
        if any(e.endswith(suf) for suf in EMAIL_BLACKLIST_SUFFIX):
            continue
        if any(e.startswith(pref) for pref in EMAIL_BLACKLIST_PREFIX):
            continue
        if any(dom in e for dom in EMAIL_BLACKLIST_DOMAINS):
            continue
        local = e.split("@")[0]
        domain = e.split("@", 1)[1] if "@" in e else ""
        # Exclut version package : @1.2.3 ou @x.y.z
        if re.fullmatch(r"\d+(\.\d+)+", domain):
            continue
        # TLD valide ?
        tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
        if tld not in VALID_TLDS:
            continue
        # Exclut les hash (>=24 hex chars dans la partie locale)
        if len(local) >= 24 and all(c in "0123456789abcdef" for c in local):
            continue
        if len(e) > 80:
            continue
        cleaned.add(e)
    return sorted(cleaned)


def _clean_phones(phones):
    cleaned = set()
    for p in phones:
        p = p.strip()
        digits = re.sub(r"[^\d+]", "", p)
        # FR: 10 chiffres si commence par 0, ou 11-12 si +33
        if digits.startswith("+33"):
            if len(digits) != 12:
                continue
        elif digits.startswith("0033"):
            if len(digits) != 13:
                continue
        elif digits.startswith("0"):
            if len(digits) != 10:
                continue
        else:
            continue
        # Exclut séparateurs incohérents (mélange . et chiffres décimaux genre "12.3289")
        # Si on a un groupe de 4 chiffres après un point, c'est suspect (vrai téléphone = groupes de 2)
        if re.search(r"\.\d{3,}", p):
            continue
        cleaned.add(p.strip())
    return sorted(cleaned)


def _find_social_links(soup):
    socials = {}
    patterns = {
        "facebook": r"facebook\.com/[^/\"'? ]+",
        "instagram": r"instagram\.com/[^/\"'? ]+",
        "linkedin": r"linkedin\.com/(?:company|in)/[^/\"'? ]+",
        "twitter": r"(?:twitter|x)\.com/[^/\"'? ]+",
        "youtube": r"youtube\.com/(?:c|channel|user|@)[^/\"'? ]+",
    }
    html = str(soup)
    for net, pat in patterns.items():
        m = re.search(pat, html)
        if m:
            socials[net] = "https://" + m.group(0)
    return socials


def _find_contact_links(html, base_url):
    soup = BeautifulSoup(html, "lxml")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text(" ", strip=True).lower()
        for marker in CONTACT_PAGES:
            if marker in href or marker.replace("/", "") in text:
                full = urljoin(base_url, a["href"])
                links.add(full)
                break
        if "contact" in text and len(text) < 30:
            full = urljoin(base_url, a["href"])
            links.add(full)
    return list(links)[:5]


def _has_contact_form(html):
    if not html:
        return False
    soup = BeautifulSoup(html, "lxml")
    forms = soup.find_all("form")
    for form in forms:
        text = str(form).lower()
        if any(x in text for x in ["contact", "message", "nom", "email", "name"]):
            return True
    return False


def extract_contacts(url):
    """
    Extrait emails, téléphones, formulaire, réseaux sociaux d'un site.
    Cherche sur homepage + pages contact.
    """
    result = {
        "url": url,
        "emails": [],
        "phones": [],
        "has_contact_form": False,
        "contact_pages": [],
        "socials": {},
        "company_name": None,
    }

    session = _session()
    html, final_url = _fetch(url, session)
    if not html:
        return result

    # Homepage
    emails = set(EMAIL_REGEX.findall(html))
    phones = set(PHONE_REGEX.findall(html))

    # mailto: tags
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            emails.add(href.replace("mailto:", "").split("?")[0])
        elif href.startswith("tel:"):
            phones.add(href.replace("tel:", ""))

    # Title / company name
    title = soup.find("title")
    if title:
        result["company_name"] = title.get_text(strip=True)[:120]

    # Socials
    result["socials"] = _find_social_links(soup)

    # Form on homepage?
    if _has_contact_form(html):
        result["has_contact_form"] = True

    # Pages contact
    contact_links = _find_contact_links(html, final_url)
    for link in contact_links:
        sub_html, _ = _fetch(link, session, timeout=8)
        if not sub_html:
            continue
        result["contact_pages"].append(link)
        emails |= set(EMAIL_REGEX.findall(sub_html))
        phones |= set(PHONE_REGEX.findall(sub_html))
        sub_soup = BeautifulSoup(sub_html, "lxml")
        for a in sub_soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                emails.add(href.replace("mailto:", "").split("?")[0])
            elif href.startswith("tel:"):
                phones.add(href.replace("tel:", ""))
        if _has_contact_form(sub_html):
            result["has_contact_form"] = True

    result["emails"] = _clean_emails(emails)
    result["phones"] = _clean_phones(phones)
    return result
