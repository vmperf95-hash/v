"""
3DS Hunter - Logiciel Windows de détection 3D Secure pour la prospection B2B.
GUI moderne avec CustomTkinter.
"""
import os
import sys
import threading
import queue
from datetime import datetime

import customtkinter as ctk
from tkinter import messagebox, filedialog
import tkinter as tk

# Permet de lancer depuis /app/windows_app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.detector import analyze_site
from core.contact_extractor import extract_contacts
from core.scraper import discover_ecommerce_sites
from core.exporter import export_csv, export_excel


APP_NAME = "3DS Hunter - Prospection B2B"
VERSION = "1.0.0"

# Couleurs du thème custom
COLOR_BG = "#0d1117"
COLOR_PANEL = "#161b22"
COLOR_ACCENT = "#00d4aa"  # Vert turquoise
COLOR_ACCENT_HOVER = "#00b894"
COLOR_DANGER = "#ff6b6b"
COLOR_WARNING = "#ffa726"
COLOR_SUCCESS = "#4caf50"
COLOR_TEXT = "#e6edf3"
COLOR_TEXT_DIM = "#8b949e"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        self.configure(fg_color=COLOR_BG)

        # Stockage des résultats
        self.results = []
        self.event_queue = queue.Queue()
        self.scan_thread = None
        self.scan_stop_flag = threading.Event()

        self._build_layout()
        self._poll_queue()

    # ----------------- LAYOUT ---------------------
    def _build_layout(self):
        # Sidebar
        self.sidebar = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0, width=240)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo / titre
        logo = ctk.CTkLabel(
            self.sidebar, text="🛡️  3DS HUNTER",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_ACCENT,
        )
        logo.pack(pady=(28, 4), padx=20)
        sub = ctk.CTkLabel(
            self.sidebar, text="Prospection B2B",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_DIM,
        )
        sub.pack(pady=(0, 28))

        # Boutons nav
        self.nav_buttons = {}
        nav_items = [
            ("scan", "🔎  Découverte / Scan", self.show_scan),
            ("results", "📊  Résultats", self.show_results),
            ("export", "💾  Export", self.show_export),
            ("about", "ℹ️  À propos", self.show_about),
        ]
        for key, label, cmd in nav_items:
            btn = ctk.CTkButton(
                self.sidebar, text=label, command=cmd,
                anchor="w", fg_color="transparent",
                text_color=COLOR_TEXT, hover_color="#21262d",
                font=ctk.CTkFont(family="Segoe UI", size=14),
                height=42, corner_radius=8,
            )
            btn.pack(fill="x", padx=14, pady=4)
            self.nav_buttons[key] = btn

        # Status en bas de sidebar
        self.stats_frame = ctk.CTkFrame(self.sidebar, fg_color="#0d1117", corner_radius=8)
        self.stats_frame.pack(side="bottom", fill="x", padx=14, pady=14)
        self.stats_label = ctk.CTkLabel(
            self.stats_frame, text="0 sites analysés",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_DIM,
            justify="left",
        )
        self.stats_label.pack(padx=10, pady=10)

        # Zone principale
        self.main = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.main.pack(side="left", fill="both", expand=True)

        # Création des pages
        self.pages = {}
        self.pages["scan"] = ScanPage(self.main, self)
        self.pages["results"] = ResultsPage(self.main, self)
        self.pages["export"] = ExportPage(self.main, self)
        self.pages["about"] = AboutPage(self.main, self)

        self.show_scan()

    def _highlight_nav(self, key):
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=COLOR_ACCENT, text_color="#0d1117")
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT)

    def _show_page(self, key):
        for k, page in self.pages.items():
            page.pack_forget()
        self.pages[key].pack(fill="both", expand=True, padx=24, pady=24)
        self._highlight_nav(key)

    def show_scan(self): self._show_page("scan")
    def show_results(self):
        self.pages["results"].refresh()
        self._show_page("results")
    def show_export(self): self._show_page("export")
    def show_about(self): self._show_page("about")

    # ----------------- SCAN LOGIC ------------------
    def start_scan(self, urls, extract_contacts_flag=True):
        if self.scan_thread and self.scan_thread.is_alive():
            messagebox.showwarning("Scan en cours", "Un scan est déjà en cours.")
            return
        self.scan_stop_flag.clear()
        self.results = []
        self.scan_thread = threading.Thread(
            target=self._scan_worker,
            args=(urls, extract_contacts_flag),
            daemon=True,
        )
        self.scan_thread.start()

    def stop_scan(self):
        self.scan_stop_flag.set()

    def _scan_worker(self, urls, extract_contacts_flag):
        total = len(urls)
        self.event_queue.put(("scan_start", total))
        for i, url in enumerate(urls):
            if self.scan_stop_flag.is_set():
                self.event_queue.put(("scan_stop", None))
                return
            try:
                self.event_queue.put(("scan_progress", (i + 1, total, url)))
                r = analyze_site(url, deep=True)
                if extract_contacts_flag and r.get("is_ecommerce"):
                    try:
                        r["contacts"] = extract_contacts(r["final_url"])
                    except Exception as e:
                        r["contacts"] = {"emails": [], "phones": [], "error": str(e)}
                else:
                    r["contacts"] = {"emails": [], "phones": [], "has_contact_form": False,
                                     "contact_pages": [], "socials": {}, "company_name": ""}
                self.results.append(r)
                self.event_queue.put(("scan_result", r))
            except Exception as e:
                self.event_queue.put(("scan_error", (url, str(e))))
        self.event_queue.put(("scan_done", None))

    def start_discovery(self, keywords, max_per_query, then_scan, extract_contacts_flag):
        if self.scan_thread and self.scan_thread.is_alive():
            messagebox.showwarning("Scan en cours", "Un scan est déjà en cours.")
            return
        self.scan_stop_flag.clear()
        self.scan_thread = threading.Thread(
            target=self._discovery_worker,
            args=(keywords, max_per_query, then_scan, extract_contacts_flag),
            daemon=True,
        )
        self.scan_thread.start()

    def _discovery_worker(self, keywords, max_per_query, then_scan, extract_contacts_flag):
        self.event_queue.put(("discover_start", None))

        def progress_cb(i, total, q):
            self.event_queue.put(("discover_progress", (i, total, q)))

        urls = discover_ecommerce_sites(
            keywords, max_per_query=max_per_query, progress_cb=progress_cb
        )
        self.event_queue.put(("discover_done", urls))

        if then_scan and urls:
            self.results = []
            total = len(urls)
            self.event_queue.put(("scan_start", total))
            for i, url in enumerate(urls):
                if self.scan_stop_flag.is_set():
                    self.event_queue.put(("scan_stop", None))
                    return
                try:
                    self.event_queue.put(("scan_progress", (i + 1, total, url)))
                    r = analyze_site(url, deep=True)
                    if extract_contacts_flag and r.get("is_ecommerce"):
                        try:
                            r["contacts"] = extract_contacts(r["final_url"])
                        except Exception:
                            r["contacts"] = {"emails": [], "phones": []}
                    else:
                        r["contacts"] = {"emails": [], "phones": [], "has_contact_form": False,
                                         "contact_pages": [], "socials": {}, "company_name": ""}
                    self.results.append(r)
                    self.event_queue.put(("scan_result", r))
                except Exception as e:
                    self.event_queue.put(("scan_error", (url, str(e))))
            self.event_queue.put(("scan_done", None))

    def _poll_queue(self):
        try:
            while True:
                event, data = self.event_queue.get_nowait()
                self._handle_event(event, data)
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

    def _handle_event(self, event, data):
        page = self.pages["scan"]
        if event == "scan_start":
            page.on_scan_start(data)
        elif event == "scan_progress":
            i, total, url = data
            page.on_scan_progress(i, total, url)
        elif event == "scan_result":
            page.on_scan_result(data)
            self._update_stats()
        elif event == "scan_done":
            page.on_scan_done()
            self._update_stats()
        elif event == "scan_stop":
            page.on_scan_stop()
        elif event == "scan_error":
            url, err = data
            page.log(f"❌ Erreur sur {url}: {err}", color=COLOR_DANGER)
        elif event == "discover_start":
            page.log("🔎 Lancement de la découverte automatique...", color=COLOR_ACCENT)
        elif event == "discover_progress":
            i, total, q = data
            page.on_discover_progress(i, total, q)
        elif event == "discover_done":
            urls = data
            page.log(f"✅ Découverte terminée : {len(urls)} site(s) trouvé(s).", color=COLOR_SUCCESS)

    def _update_stats(self):
        total = len(self.results)
        no_3ds = sum(1 for r in self.results if r.get("verdict") == "Sans 3DS Probable")
        prospects = sum(1 for r in self.results
                        if r.get("verdict") in ("Sans 3DS Probable", "Incertain"))
        with_3ds = sum(1 for r in self.results if r.get("verdict") == "3DS Probable")
        text = (
            f"📊 {total} sites analysés\n"
            f"🎯 {prospects} prospects\n"
            f"❌ {no_3ds} sans 3DS\n"
            f"✅ {with_3ds} avec 3DS"
        )
        self.stats_label.configure(text=text)


# =================== PAGES ====================

class ScanPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=COLOR_BG)
        self.app = app
        self._build()

    def _build(self):
        title = ctk.CTkLabel(
            self, text="Découverte & Analyse de Sites",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=COLOR_TEXT, anchor="w",
        )
        title.pack(fill="x", pady=(0, 4))
        sub = ctk.CTkLabel(
            self,
            text="Identifie automatiquement les sites e-commerce dépourvus de 3D Secure",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLOR_TEXT_DIM, anchor="w",
        )
        sub.pack(fill="x", pady=(0, 18))

        # Onglets : Manuel / Auto
        tabs = ctk.CTkTabview(
            self, fg_color=COLOR_PANEL,
            segmented_button_fg_color=COLOR_PANEL,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_selected_hover_color=COLOR_ACCENT_HOVER,
            segmented_button_unselected_color="#21262d",
            text_color=COLOR_TEXT,
            corner_radius=10, height=200,
        )
        tabs.pack(fill="x", pady=(0, 14))
        tabs.add("✍️ Saisie manuelle")
        tabs.add("🤖 Découverte auto")

        self._build_manual_tab(tabs.tab("✍️ Saisie manuelle"))
        self._build_auto_tab(tabs.tab("🤖 Découverte auto"))

        # Console / log
        log_frame = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=10)
        log_frame.pack(fill="both", expand=True)

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=14, pady=(12, 4))
        ctk.CTkLabel(
            log_header, text="📡 Console de scan",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLOR_TEXT,
        ).pack(side="left")

        self.progress = ctk.CTkProgressBar(
            log_header, height=8, progress_color=COLOR_ACCENT,
            fg_color="#21262d", width=300,
        )
        self.progress.set(0)
        self.progress.pack(side="right", padx=(10, 0))

        self.progress_label = ctk.CTkLabel(
            log_header, text="", font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_DIM,
        )
        self.progress_label.pack(side="right", padx=(0, 10))

        self.log_text = ctk.CTkTextbox(
            log_frame, fg_color="#010409", text_color=COLOR_TEXT,
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=8, wrap="word",
        )
        self.log_text.pack(fill="both", expand=True, padx=14, pady=(8, 14))
        self.log_text.configure(state="disabled")

    def _build_manual_tab(self, parent):
        ctk.CTkLabel(
            parent, text="Colle une ou plusieurs URLs (une par ligne)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_DIM, anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 6))

        self.urls_text = ctk.CTkTextbox(
            parent, fg_color="#010409", text_color=COLOR_TEXT,
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=8, height=80,
        )
        self.urls_text.pack(fill="x", padx=14, pady=(0, 8))
        self.urls_text.insert("1.0", "https://exemple-boutique.fr\n")

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(0, 12))

        self.manual_extract = ctk.CTkSwitch(
            actions, text="Extraire les contacts",
            progress_color=COLOR_ACCENT, text_color=COLOR_TEXT,
        )
        self.manual_extract.select()
        self.manual_extract.pack(side="left")

        ctk.CTkButton(
            actions, text="📁 Importer .txt/.csv",
            command=self._import_file,
            fg_color="#21262d", hover_color="#30363d", text_color=COLOR_TEXT,
            corner_radius=8, height=36,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            actions, text="🚀 Lancer le scan",
            command=self._launch_manual_scan,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#0d1117", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            corner_radius=8, height=36,
        ).pack(side="right")

    def _build_auto_tab(self, parent):
        ctk.CTkLabel(
            parent, text="Mots-clés cibles (séparés par virgule). Ex: bijoux, vêtement bio, accessoires moto",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_DIM, anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 6))

        self.keywords_entry = ctk.CTkEntry(
            parent, fg_color="#010409", text_color=COLOR_TEXT,
            placeholder_text="ex: bijoux artisanaux, cosmétiques naturels",
            corner_radius=8, height=38,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.keywords_entry.pack(fill="x", padx=14, pady=(0, 8))

        opts = ctk.CTkFrame(parent, fg_color="transparent")
        opts.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(opts, text="Max sites / requête :",
                     text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12)).pack(side="left")
        self.max_results_var = tk.IntVar(value=15)
        self.max_results_slider = ctk.CTkSlider(
            opts, from_=5, to=30, number_of_steps=25,
            variable=self.max_results_var, width=160,
            progress_color=COLOR_ACCENT, button_color=COLOR_ACCENT,
        )
        self.max_results_slider.pack(side="left", padx=8)
        self.max_results_label = ctk.CTkLabel(opts, text="15",
                                              text_color=COLOR_TEXT, font=ctk.CTkFont(size=12, weight="bold"))
        self.max_results_label.pack(side="left")
        self.max_results_var.trace_add(
            "write", lambda *a: self.max_results_label.configure(text=str(self.max_results_var.get()))
        )

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(8, 12))

        self.auto_extract = ctk.CTkSwitch(
            actions, text="Extraire les contacts",
            progress_color=COLOR_ACCENT, text_color=COLOR_TEXT,
        )
        self.auto_extract.select()
        self.auto_extract.pack(side="left")

        self.auto_scan = ctk.CTkSwitch(
            actions, text="Analyser après découverte",
            progress_color=COLOR_ACCENT, text_color=COLOR_TEXT,
        )
        self.auto_scan.select()
        self.auto_scan.pack(side="left", padx=(20, 0))

        ctk.CTkButton(
            actions, text="🛑 Arrêter",
            command=self.app.stop_scan,
            fg_color=COLOR_DANGER, hover_color="#d44444", text_color="#fff",
            corner_radius=8, height=36, width=110,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            actions, text="🤖 Lancer la découverte",
            command=self._launch_discovery,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#0d1117", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            corner_radius=8, height=36,
        ).pack(side="right")

    # ---- Actions
    def _import_file(self):
        path = filedialog.askopenfilename(
            title="Importer une liste d'URLs",
            filetypes=[("Texte", "*.txt"), ("CSV", "*.csv"), ("Tous", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            # Sépare par retour ligne, virgule, point-virgule
            import re
            urls = re.split(r"[\r\n,;]+", content)
            urls = [u.strip() for u in urls if u.strip()]
            self.urls_text.delete("1.0", "end")
            self.urls_text.insert("1.0", "\n".join(urls))
            self.log(f"📁 {len(urls)} URLs importées depuis {os.path.basename(path)}", color=COLOR_ACCENT)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de lire le fichier : {e}")

    def _launch_manual_scan(self):
        raw = self.urls_text.get("1.0", "end").strip()
        urls = [u.strip() for u in raw.splitlines() if u.strip()]
        if not urls:
            messagebox.showwarning("Aucune URL", "Saisis au moins une URL à analyser.")
            return
        self._clear_log()
        self.log(f"🚀 Démarrage du scan de {len(urls)} site(s)", color=COLOR_ACCENT)
        self.app.start_scan(urls, extract_contacts_flag=bool(self.manual_extract.get()))

    def _launch_discovery(self):
        raw = self.keywords_entry.get().strip()
        if not raw:
            messagebox.showwarning("Mots-clés manquants",
                                   "Saisis au moins un mot-clé (ex: bijoux, cosmétiques)")
            return
        keywords = [k.strip() for k in raw.split(",") if k.strip()]
        self._clear_log()
        self.app.start_discovery(
            keywords,
            max_per_query=self.max_results_var.get(),
            then_scan=bool(self.auto_scan.get()),
            extract_contacts_flag=bool(self.auto_extract.get()),
        )

    # ---- Logging
    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.progress.set(0)
        self.progress_label.configure(text="")

    def log(self, message, color=None):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ---- Event handlers
    def on_scan_start(self, total):
        self.progress.set(0)
        self.progress_label.configure(text=f"0 / {total}")

    def on_scan_progress(self, i, total, url):
        self.progress.set(i / total if total else 0)
        self.progress_label.configure(text=f"{i} / {total}")
        self.log(f"🔍 [{i}/{total}] Analyse de {url}")

    def on_scan_result(self, r):
        verdict = r.get("verdict", "?")
        score = r.get("score_3ds", 0)
        if verdict == "3DS Probable":
            emoji = "✅"
        elif verdict == "Sans 3DS Probable":
            emoji = "🎯"
        elif verdict == "Incertain":
            emoji = "⚠️"
        else:
            emoji = "❌"
        gws = ", ".join(g["name"] for g in r.get("gateways", [])) or "aucune"
        self.log(f"{emoji} {r['url']} → {verdict} ({score}/100) | Passerelles: {gws}")

    def on_scan_done(self):
        self.progress.set(1)
        self.log("🏁 Scan terminé.", color=COLOR_SUCCESS)
        self.log("👉 Va dans l'onglet 'Résultats' pour voir le détail, ou 'Export' pour télécharger.",
                 color=COLOR_ACCENT)

    def on_scan_stop(self):
        self.log("🛑 Scan interrompu par l'utilisateur.", color=COLOR_WARNING)

    def on_discover_progress(self, i, total, q):
        self.progress.set(i / total if total else 0)
        self.progress_label.configure(text=f"{i} / {total}")
        self.log(f"🔎 Requête {i}/{total} : « {q} »")


class ResultsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=COLOR_BG)
        self.app = app
        self.filter_var = tk.StringVar(value="Tous")
        self._build()

    def _build(self):
        title = ctk.CTkLabel(
            self, text="Résultats d'analyse",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=COLOR_TEXT, anchor="w",
        )
        title.pack(fill="x", pady=(0, 16))

        # Filtres
        filter_frame = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=10)
        filter_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            filter_frame, text="Filtrer :",
            text_color=COLOR_TEXT, font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=(14, 10), pady=12)

        for label in ["Tous", "🎯 Prospects (sans 3DS + Incertain)", "❌ Sans 3DS",
                      "⚠️ Incertain", "✅ Avec 3DS"]:
            ctk.CTkRadioButton(
                filter_frame, text=label, variable=self.filter_var, value=label,
                command=self.refresh, text_color=COLOR_TEXT,
                fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            ).pack(side="left", padx=8, pady=12)

        # Scrollable area for cards
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=COLOR_BG,
            scrollbar_button_color="#30363d",
            scrollbar_button_hover_color=COLOR_ACCENT,
        )
        self.scroll.pack(fill="both", expand=True)

    def refresh(self):
        for child in self.scroll.winfo_children():
            child.destroy()

        results = self.app.results
        f = self.filter_var.get()
        if "Prospects" in f:
            results = [r for r in results if r.get("verdict") in ("Sans 3DS Probable", "Incertain")]
        elif "Sans 3DS" in f:
            results = [r for r in results if r.get("verdict") == "Sans 3DS Probable"]
        elif "Incertain" in f:
            results = [r for r in results if r.get("verdict") == "Incertain"]
        elif "Avec 3DS" in f:
            results = [r for r in results if r.get("verdict") == "3DS Probable"]

        if not results:
            ctk.CTkLabel(
                self.scroll, text="Aucun résultat à afficher.\nLance d'abord un scan dans l'onglet Découverte.",
                text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=14),
                justify="center",
            ).pack(pady=80)
            return

        # Tri : prospects d'abord (score bas)
        results = sorted(results, key=lambda r: r.get("score_3ds", 999))

        for r in results:
            self._build_card(r)

    def _build_card(self, r):
        verdict = r.get("verdict", "?")
        score = r.get("score_3ds", 0)
        if verdict == "3DS Probable":
            badge_color, badge_text = COLOR_SUCCESS, "✅ AVEC 3DS"
        elif verdict == "Sans 3DS Probable":
            badge_color, badge_text = COLOR_DANGER, "🎯 PROSPECT"
        elif verdict == "Incertain":
            badge_color, badge_text = COLOR_WARNING, "⚠️ INCERTAIN"
        elif verdict == "Pas e-commerce":
            badge_color, badge_text = "#6b7280", "🚫 PAS E-COMMERCE"
        else:
            badge_color, badge_text = "#6b7280", "❌ " + verdict.upper()

        card = ctk.CTkFrame(self.scroll, fg_color=COLOR_PANEL, corner_radius=12)
        card.pack(fill="x", padx=4, pady=6)

        # Header
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(14, 6))

        # Badge gauche
        badge = ctk.CTkLabel(
            header, text=badge_text, fg_color=badge_color, text_color="#0d1117",
            font=ctk.CTkFont(size=11, weight="bold"),
            corner_radius=6, padx=10, pady=4,
        )
        badge.pack(side="left")

        # URL
        url_lbl = ctk.CTkLabel(
            header, text=f"  {r.get('url', '')}",
            text_color=COLOR_TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
        )
        url_lbl.pack(side="left")

        # Score à droite
        score_lbl = ctk.CTkLabel(
            header, text=f"Score 3DS : {score}/100",
            text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=12),
        )
        score_lbl.pack(side="right")

        # Détails
        details = ctk.CTkFrame(card, fg_color="transparent")
        details.pack(fill="x", padx=18, pady=(0, 14))

        company = (r.get("contacts") or {}).get("company_name", "")
        if company:
            ctk.CTkLabel(
                details, text=f"🏢 {company}",
                text_color=COLOR_TEXT, font=ctk.CTkFont(size=12),
                anchor="w", justify="left",
            ).pack(fill="x", pady=(4, 0))

        gws = r.get("gateways", [])
        if gws:
            gw_text = "💳 Passerelles : " + ", ".join(g["name"] for g in gws)
        else:
            gw_text = "💳 Passerelles : aucune détectée"
        ctk.CTkLabel(
            details, text=gw_text, text_color=COLOR_TEXT_DIM,
            font=ctk.CTkFont(size=12), anchor="w", justify="left", wraplength=900,
        ).pack(fill="x", pady=2)

        contacts = r.get("contacts") or {}
        emails = contacts.get("emails", [])
        phones = contacts.get("phones", [])
        if emails or phones:
            cinfo = ""
            if emails:
                cinfo += f"📧 {', '.join(emails[:3])}"
                if len(emails) > 3:
                    cinfo += f" (+{len(emails) - 3})"
            if phones:
                if cinfo:
                    cinfo += "    "
                cinfo += f"📞 {', '.join(phones[:2])}"
            ctk.CTkLabel(
                details, text=cinfo,
                text_color=COLOR_ACCENT, font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w", justify="left", wraplength=900,
            ).pack(fill="x", pady=4)

        if contacts.get("has_contact_form"):
            ctk.CTkLabel(
                details, text="📝 Formulaire de contact disponible",
                text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=11),
                anchor="w",
            ).pack(fill="x", pady=2)

        reason = r.get("reason", "")
        if reason:
            ctk.CTkLabel(
                details, text=f"💡 {reason}",
                text_color=COLOR_TEXT_DIM, font=ctk.CTkFont(size=11),
                anchor="w", justify="left", wraplength=900,
            ).pack(fill="x", pady=(4, 0))


class ExportPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=COLOR_BG)
        self.app = app
        self._build()

    def _build(self):
        title = ctk.CTkLabel(
            self, text="Exporter les résultats",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=COLOR_TEXT, anchor="w",
        )
        title.pack(fill="x", pady=(0, 16))

        info = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=12)
        info.pack(fill="x", pady=(0, 18))
        ctk.CTkLabel(
            info,
            text="Exporte tes prospects (sites sans 3DS) avec leurs coordonnées de contact\n"
                 "pour les contacter et leur proposer ton service d'installation 3D Secure.",
            text_color=COLOR_TEXT, font=ctk.CTkFont(size=13),
            justify="left",
        ).pack(padx=18, pady=18, anchor="w")

        # Output dir
        dir_frame = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=12)
        dir_frame.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            dir_frame, text="📂 Dossier de destination",
            text_color=COLOR_TEXT, font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(14, 6))

        path_row = ctk.CTkFrame(dir_frame, fg_color="transparent")
        path_row.pack(fill="x", padx=18, pady=(0, 14))

        default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exports")
        self.output_var = tk.StringVar(value=default_dir)
        ctk.CTkEntry(
            path_row, textvariable=self.output_var,
            fg_color="#010409", text_color=COLOR_TEXT,
            corner_radius=8, height=36,
            font=ctk.CTkFont(family="Consolas", size=12),
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            path_row, text="📁 Choisir",
            command=self._pick_dir,
            fg_color="#21262d", hover_color="#30363d", text_color=COLOR_TEXT,
            corner_radius=8, height=36, width=110,
        ).pack(side="left")

        # Boutons export
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x")

        ctk.CTkButton(
            btns, text="📄  Exporter en CSV",
            command=self._export_csv,
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER,
            text_color="#0d1117", font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=10, height=52,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            btns, text="📊  Exporter en Excel (.xlsx)",
            command=self._export_excel,
            fg_color="#388e7a", hover_color="#2c6f60",
            text_color="#fff", font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=10, height=52,
        ).pack(side="left", fill="x", expand=True, padx=(8, 0))

        # Status
        self.status_label = ctk.CTkLabel(
            self, text="", text_color=COLOR_ACCENT,
            font=ctk.CTkFont(size=13),
            wraplength=900, justify="left",
        )
        self.status_label.pack(fill="x", pady=18)

    def _pick_dir(self):
        d = filedialog.askdirectory(title="Choisir un dossier")
        if d:
            self.output_var.set(d)

    def _check_results(self):
        if not self.app.results:
            messagebox.showwarning("Aucun résultat",
                                   "Lance d'abord un scan dans l'onglet Découverte.")
            return False
        return True

    def _export_csv(self):
        if not self._check_results():
            return
        try:
            path = export_csv(self.app.results, self.output_var.get())
            self.status_label.configure(
                text=f"✅ Export CSV réussi !\n{path}",
                text_color=COLOR_SUCCESS,
            )
            self._open_folder(os.path.dirname(path))
        except Exception as e:
            messagebox.showerror("Erreur", f"Export échoué : {e}")

    def _export_excel(self):
        if not self._check_results():
            return
        try:
            path = export_excel(self.app.results, self.output_var.get())
            self.status_label.configure(
                text=f"✅ Export Excel réussi !\n{path}\n\n"
                     f"3 onglets : Tous les sites • Prospects • Déjà 3DS",
                text_color=COLOR_SUCCESS,
            )
            self._open_folder(os.path.dirname(path))
        except Exception as e:
            messagebox.showerror("Erreur", f"Export échoué : {e}")

    def _open_folder(self, path):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass


class AboutPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=COLOR_BG)
        self.app = app
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="À propos de 3DS Hunter",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=COLOR_TEXT, anchor="w",
        ).pack(fill="x", pady=(0, 18))

        card = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=12)
        card.pack(fill="both", expand=True)

        text = (
            f"🛡️  3DS Hunter v{VERSION}\n\n"
            "Outil de prospection B2B pour identifier les sites e-commerce\n"
            "dépourvus de 3D Secure / authentification forte (SCA - PSD2).\n\n"
            "🔍 Méthodes de détection combinées :\n"
            "   • Identification de la passerelle de paiement (Stripe, PayPlug, Mollie, Adyen, PayPal,\n"
            "     Lyra/SystemPay, Atos SIPS, Monetico, Stancer, Checkout.com, Shopify Payments...)\n"
            "   • Recherche de mots-clés 3DS / SCA dans les CGV/mentions légales\n"
            "   • Score de probabilité de 0 à 100\n\n"
            "📧 Extraction automatique des coordonnées (emails, téléphones, formulaires)\n"
            "🤖 Découverte automatique via DuckDuckGo (sans clé API)\n"
            "📊 Export CSV + Excel multi-onglets\n\n"
            "⚠️  Important : ce logiciel produit une estimation basée sur des heuristiques.\n"
            "Une absence de 3DS n'est confirmée qu'en testant un paiement réel.\n"
            "Utilise ces données comme point de départ pour ta prospection.\n\n"
            "🤝 Conseil prospection : cible en priorité les sites avec verdict \"Sans 3DS Probable\".\n"
            "Pour les \"Incertain\", contacte-les pour proposer un audit gratuit."
        )
        ctk.CTkLabel(
            card, text=text, text_color=COLOR_TEXT,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            justify="left", anchor="w",
        ).pack(padx=24, pady=24, anchor="nw", fill="both")


# ================ ENTRY POINT ==================

def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
