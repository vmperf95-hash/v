"""
Export des résultats vers CSV / Excel.
"""
import os
from datetime import datetime
import pandas as pd


def _rows_from_results(results):
    rows = []
    for r in results:
        gw_names = ", ".join(g["name"] for g in r.get("gateways", []))
        rows.append({
            "URL": r.get("url", ""),
            "URL finale": r.get("final_url", ""),
            "Nom Entreprise": (r.get("contacts") or {}).get("company_name", ""),
            "E-commerce": "Oui" if r.get("is_ecommerce") else "Non",
            "Verdict 3DS": r.get("verdict", ""),
            "Score 3DS": r.get("score_3ds", 0),
            "Passerelles détectées": gw_names,
            "Mots-clés 3DS": ", ".join(r.get("keywords_found", [])),
            "Emails": ", ".join((r.get("contacts") or {}).get("emails", [])),
            "Téléphones": ", ".join((r.get("contacts") or {}).get("phones", [])),
            "Formulaire contact": "Oui" if (r.get("contacts") or {}).get("has_contact_form") else "Non",
            "Pages contact": ", ".join((r.get("contacts") or {}).get("contact_pages", [])),
            "Facebook": (r.get("contacts") or {}).get("socials", {}).get("facebook", ""),
            "Instagram": (r.get("contacts") or {}).get("socials", {}).get("instagram", ""),
            "LinkedIn": (r.get("contacts") or {}).get("socials", {}).get("linkedin", ""),
            "Raison": r.get("reason", ""),
            "Status HTTP": r.get("status", ""),
        })
    return rows


def export_csv(results, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    rows = _rows_from_results(results)
    df = pd.DataFrame(rows)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"prospects_3ds_{ts}.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig", sep=";")
    return path


def export_excel(results, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    rows = _rows_from_results(results)
    df = pd.DataFrame(rows)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"prospects_3ds_{ts}.xlsx")

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Tous les sites")
        # Onglet prospects (sans 3DS ou incertain)
        prospects = df[df["Verdict 3DS"].isin(["Sans 3DS Probable", "Incertain"])]
        if not prospects.empty:
            prospects.to_excel(writer, index=False, sheet_name="Prospects")
        # Onglet avec 3DS
        ok = df[df["Verdict 3DS"] == "3DS Probable"]
        if not ok.empty:
            ok.to_excel(writer, index=False, sheet_name="Déjà 3DS")

        # Auto-fit colonnes
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    try:
                        val = str(cell.value) if cell.value else ""
                        if len(val) > max_len:
                            max_len = len(val)
                    except Exception:
                        pass
                ws.column_dimensions[col_letter].width = min(max_len + 2, 60)

    return path
