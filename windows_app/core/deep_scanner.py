"""
Deep Scan via Playwright (Chromium headless).
Ouvre vraiment le site dans un navigateur, capture les requêtes réseau et le DOM
pour identifier précisément les endpoints 3DS et les iframes de paiement.
"""
import os
import sys
from urllib.parse import urlparse, urljoin

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


THREE_DS_NETWORK_PATTERNS = [
    "cardinalcommerce.com", "centinelapi", "centinel-",
    "ds.netcetera.com", "acs.netcetera",
    "3dsecure", "3ds2.", "threeds2", "three_d_secure",
    "challengeurl", "challenge_url",
    "acsurl", "acs_url", "/acs/",
    "stripe.com/v1/payment_intents", "stripe.com/v1/sources",
    "stripe.com/v1/3d_secure",
    "stripe3ds", "stripe-3ds",
    "checkoutshopper-live.adyen", "live.adyen.com",
    "secure.payplug.com", "api.payplug",
    "api.mollie.com",
    "systempay.fr", "payzen.eu", "scellius",
    "monetico-paiement", "p.monetico",
    "mercanet", "worldline",
    "checkout.com/sessions",
    "directoryserver", "directoryservers",
    "mpi.scellius", "mpi.systempay",
    "cybersource.com",
    "braintreegateway", "braintree-api",
]

PAYMENT_IFRAME_HOSTS = [
    "stripe.com", "js.stripe", "checkout.stripe",
    "paypal.com", "paypalobjects",
    "payplug.com",
    "mollie.com",
    "adyen.com",
    "systempay.fr", "lyra-collect", "payzen.eu", "scellius.fr",
    "monetico-paiement",
    "worldline.com", "mercanet",
    "checkout.com", "cko.com",
    "braintreegateway",
    "vivapayments.com", "viva.com",
    "stancer.com",
    "shopify.com", "shop.app",
    "klarna.com",
    "amazonpay", "payments.amazon",
    "applepay", "googlepay", "pay.google.com",
    "cardinalcommerce.com",
]

# Hosts JS / scripts indiquant un SDK paiement chargé (forte indication 3DS-ready)
PAYMENT_SDK_HOSTS = [
    "js.stripe.com", "checkout.stripe.com",
    "www.paypal.com/sdk", "paypalobjects.com",
    "secure.payplug.com",
    "js.mollie.com",
    "checkoutshopper-live.adyen.com",
    "static.payzen.eu", "static.systempay.fr",
    "p.monetico-services.com",
    "static.lyra-collect.com",
    "frames.checkout.com",
    "js.braintreegateway.com",
    "vivapayments.com",
    "cdn.shopify.com", "shop.app",
    "x.klarnacdn.net",
    "static-na.payments-amazon.com",
    "cardinalcommerce.com", "centinelapi",
]

PRODUCT_LINK_SELECTORS = [
    "a[href*='/product/']", "a[href*='/produit/']",
    "a[href*='/products/']", "a[href*='/produits/']",
    "a.product-link", "a.product-item-link",
    "a.woocommerce-LoopProduct-link",
    "a[href*='/shop/']", "a[href*='/boutique/']",
    ".product a", ".product-card a", ".product-tile a",
    "[class*='product'] a[href]",
    "a[class*='product']",
]

ADD_TO_CART_SELECTORS = [
    "button[name='add-to-cart']",
    "button.single_add_to_cart_button",
    "button.add_to_cart_button",
    "button#add-to-cart-button",
    "button[data-action='add-to-cart']",
    "button[data-testid*='cart']",
    "button.btn-cart",
    "form.cart button[type='submit']",
    "input[name='add-to-cart']",
    "button:has-text('Ajouter au panier')",
    "button:has-text('Ajouter')",
    "button:has-text('Add to cart')",
    "button:has-text('Add to bag')",
    "button:has-text('Acheter')",
    "button:has-text('Buy now')",
]


def is_playwright_installed():
    if not PLAYWRIGHT_AVAILABLE:
        return False, "Module 'playwright' non installé. Lance: pip install playwright"
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                return True, "OK"
            except Exception as e:
                msg = str(e)
                if "Executable doesn't exist" in msg or "playwright install" in msg:
                    return False, "Chromium non installé. Lance: playwright install chromium"
                return False, f"Erreur Chromium: {msg[:200]}"
    except Exception as e:
        return False, f"Erreur Playwright: {str(e)[:200]}"


def install_chromium(progress_cb=None):
    import subprocess
    try:
        if progress_cb:
            progress_cb("Téléchargement de Chromium (~150 MB, 2-5 min)...")
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            return True, "Chromium installé avec succès."
        return False, f"Échec install: {result.stderr[:300]}"
    except subprocess.TimeoutExpired:
        return False, "Timeout (>10 min). Réessaie."
    except Exception as e:
        return False, f"Erreur: {str(e)[:200]}"


def _analyze_current_page(page, result, log):
    """Analyse la page courante : iframes + signatures DOM. Mutate result."""
    try:
        content = page.content().lower()

        # Iframes
        try:
            for ifr in page.locator("iframe").all():
                try:
                    src = (ifr.get_attribute("src") or "").lower()
                    if src:
                        for host in PAYMENT_IFRAME_HOSTS:
                            if host in src:
                                if not any(i["host"] == host for i in result["iframes_found"]):
                                    result["iframes_found"].append({"host": host, "src": src[:200]})
                                break
                except Exception:
                    continue
        except Exception:
            pass

        # Signatures dans le DOM rendu
        try:
            from core.detector import THREE_DS_TECHNICAL_SIGNATURES
        except ImportError:
            THREE_DS_TECHNICAL_SIGNATURES = []
        for sig in THREE_DS_TECHNICAL_SIGNATURES:
            if sig.lower() in content and sig not in result["page_content_signatures"]:
                result["page_content_signatures"].append(sig)
    except Exception as e:
        log(f"⚠ Erreur analyse page: {str(e)[:80]}")


def deep_scan_site(url, timeout_sec=45, progress_cb=None):
    """
    Deep scan en plusieurs étapes :
      1. Homepage (avec JS rendu) → analyse
      2. Page produit (tentative) → analyse
      3. Add-to-cart → analyse
      4. Tentatives directes /cart, /checkout → analyse à chaque étape
      5. Aggregation network + iframes + signatures + SDK chargés
    """
    result = {
        "url": url,
        "playwright_available": PLAYWRIGHT_AVAILABLE,
        "reached_checkout": False,
        "checkout_url": None,
        "added_to_cart": False,
        "network_3ds_hits": [],
        "iframes_found": [],
        "page_content_signatures": [],
        "payment_sdks_loaded": [],
        "page_titles": [],
        "navigation_log": [],
        "errors": [],
        "deep_score": 0,
        "deep_verdict": "Erreur",
        "deep_reason": "",
        "confidence": "Faible",
    }

    if not PLAYWRIGHT_AVAILABLE:
        result["errors"].append("Playwright non installé")
        result["deep_reason"] = "Playwright requis"
        return result

    def log(msg):
        result["navigation_log"].append(msg)
        if progress_cb:
            progress_cb(msg)

    network_urls = []

    try:
        with sync_playwright() as p:
            log(f"🌐 Lancement Chromium pour {url}...")
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled",
                      "--disable-features=IsolateOrigins,site-per-process"],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 800},
                locale="fr-FR",
                ignore_https_errors=True,
            )
            page = context.new_page()
            page.set_default_timeout(15000)

            def on_request(req):
                network_urls.append(req.url)
            page.on("request", on_request)

            # === ÉTAPE 1 : Homepage ===
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
                page.wait_for_timeout(2500)
                result["page_titles"].append(page.title()[:100])
                log(f"✓ Homepage chargée: {page.title()[:60]}")
                _analyze_current_page(page, result, log)
            except PWTimeout:
                result["errors"].append("Timeout sur homepage")
                log("⚠ Timeout homepage")
            except Exception as e:
                result["errors"].append(f"Erreur homepage: {str(e)[:120]}")
                log(f"⚠ Erreur homepage: {str(e)[:80]}")

            # === ÉTAPE 2 : Page produit ===
            product_url = None
            for sel in PRODUCT_LINK_SELECTORS:
                try:
                    links = page.locator(sel).all()
                    if links:
                        href = links[0].get_attribute("href")
                        if href and not href.startswith("#"):
                            product_url = urljoin(page.url, href)
                            break
                except Exception:
                    continue

            if product_url:
                log(f"🛍️  Produit trouvé: {product_url[:80]}")
                try:
                    page.goto(product_url, wait_until="domcontentloaded", timeout=15000)
                    page.wait_for_timeout(2500)
                    result["page_titles"].append(page.title()[:100])
                    _analyze_current_page(page, result, log)

                    # === ÉTAPE 3 : Add to cart ===
                    for sel in ADD_TO_CART_SELECTORS:
                        try:
                            btn = page.locator(sel).first
                            if btn.count() > 0:
                                try:
                                    btn.scroll_into_view_if_needed(timeout=2000)
                                except Exception:
                                    pass
                                try:
                                    btn.click(timeout=4000, force=False)
                                except Exception:
                                    try:
                                        btn.click(timeout=2000, force=True)
                                    except Exception:
                                        continue
                                page.wait_for_timeout(3000)
                                result["added_to_cart"] = True
                                log("🛒 Ajout au panier OK")
                                _analyze_current_page(page, result, log)
                                break
                        except Exception:
                            continue
                    if not result["added_to_cart"]:
                        log("⚠ Impossible d'ajouter au panier (variantes/captcha ?)")
                except Exception as e:
                    log(f"⚠ Erreur page produit: {str(e)[:80]}")
            else:
                log("⚠ Aucun lien produit détecté sur la homepage")

            # === ÉTAPE 4 : Tentative checkout directe ===
            parsed = urlparse(page.url)
            root = f"{parsed.scheme}://{parsed.netloc}"
            checkout_candidates = [
                root + "/checkout", root + "/commande", root + "/paiement",
                root + "/cart", root + "/panier", root + "/caisse",
                root + "/index.php?controller=order",
                root + "/index.php?controller=cart",
            ]

            for ck_url in checkout_candidates:
                try:
                    resp = page.goto(ck_url, wait_until="domcontentloaded", timeout=10000)
                    if resp and resp.status < 400:
                        page.wait_for_timeout(2500)
                        cur = page.url.lower()
                        if any(p in cur for p in ["/cart", "/checkout", "/panier",
                                                   "/commande", "/paiement", "/caisse",
                                                   "controller=cart", "controller=order"]):
                            result["reached_checkout"] = True
                            result["checkout_url"] = page.url
                            result["page_titles"].append(page.title()[:100])
                            log(f"💳 Checkout: {page.url[:80]}")
                            _analyze_current_page(page, result, log)
                            break
                except Exception:
                    continue

            browser.close()

    except Exception as e:
        result["errors"].append(f"Erreur Playwright: {str(e)[:200]}")
        log(f"❌ Erreur Playwright: {str(e)[:100]}")
        return result

    # === ÉTAPE 5 : Analyse réseau capturée ===
    for url_seen in network_urls:
        url_low = url_seen.lower()
        # 3DS patterns
        for pattern in THREE_DS_NETWORK_PATTERNS:
            if pattern in url_low:
                if not any(h["pattern"] == pattern for h in result["network_3ds_hits"]):
                    result["network_3ds_hits"].append({"pattern": pattern, "url": url_seen[:200]})
        # SDK paiement chargés
        for sdk in PAYMENT_SDK_HOSTS:
            if sdk in url_low and sdk not in result["payment_sdks_loaded"]:
                result["payment_sdks_loaded"].append(sdk)

    # === SCORING ===
    score = 0
    reasons = []
    real_checkout = result["added_to_cart"] and result["reached_checkout"]

    if result["network_3ds_hits"]:
        score += 50
        patterns = list(set(h["pattern"] for h in result["network_3ds_hits"]))
        reasons.append(f"Requêtes réseau 3DS détectées: {', '.join(patterns[:5])}")

    if result["iframes_found"]:
        score += 30
        hosts = list(set(i["host"] for i in result["iframes_found"]))
        reasons.append(f"Iframes paiement chargées: {', '.join(hosts[:3])}")

    if result["payment_sdks_loaded"]:
        score += 25
        sdks_short = [s.replace("www.", "").split(".com")[0] + ".com" if ".com" in s else s
                      for s in result["payment_sdks_loaded"][:3]]
        reasons.append(f"SDK paiement chargés: {', '.join(sdks_short)}")

    if result["page_content_signatures"]:
        score += 20
        reasons.append(f"Signatures techniques 3DS: {', '.join(result['page_content_signatures'][:3])}")

    if real_checkout:
        score += 10
        reasons.append("✓ Tunnel d'achat traversé (panier rempli)")
    elif result["reached_checkout"]:
        reasons.append("Page panier atteinte mais panier vide")
    else:
        reasons.append("Page checkout non atteinte (anti-bot ou structure inhabituelle)")

    # Cas crucial : tunnel d'achat traversé sans AUCUN signal paiement
    if real_checkout and not result["network_3ds_hits"] and not result["iframes_found"] \
            and not result["payment_sdks_loaded"]:
        score -= 30
        reasons.append("⚠️ Aucune trace de système de paiement standard → SANS 3DS très probable")

    score = max(0, min(100, score))
    result["deep_score"] = score

    # Verdict
    if score >= 70:
        result["deep_verdict"] = "3DS Confirmé"
        result["confidence"] = "Élevée (~95%)" if real_checkout else "Bonne (~85%)"
    elif score >= 40:
        result["deep_verdict"] = "3DS Probable"
        result["confidence"] = "Bonne (~80%)" if real_checkout else "Moyenne (~70%)"
    elif real_checkout and not result["payment_sdks_loaded"] and not result["iframes_found"]:
        result["deep_verdict"] = "Sans 3DS Confirmé"
        result["confidence"] = "Élevée (~90%)"
    elif result["payment_sdks_loaded"] or result["iframes_found"]:
        result["deep_verdict"] = "Incertain"
        result["confidence"] = "Moyenne — test paiement réel recommandé"
    elif result["errors"]:
        result["deep_verdict"] = "Bloqué (anti-bot)"
        result["confidence"] = "Site inaccessible au scan automatique"
    else:
        result["deep_verdict"] = "Inconcluant"
        result["confidence"] = "Faible — paiement custom ou rare"

    result["deep_reason"] = " | ".join(reasons)
    return result
