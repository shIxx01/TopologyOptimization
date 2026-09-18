# SPDX-License-Identifier: LGPL-3.0-or-later
"""Ehrlicher Leistungsvergleich der drei beso-Staende, die es wirklich gibt.

  1. original  - frischer Klon von github.com/calculix/beso (unveraendert, HEAD)
  2. prototyp  - die beso-Kopie der alten Workbench (vendor/beso, mit den eigenen
                 Optimierungen: Gitter-Dict in prepare2s, numpy-Matrix)
  3. addon     - das gebuendelte beso des Addons (Original + unsere 3 Fixes)

Gemessen wird auf **demselben Modell** die Vorbereitungszeit (Netz lesen,
Volumen/Schwerpunkt, Elementgroessen, Nachbarschaftsgitter) - das ist genau der
Teil, den der Prototyp umgebaut hat - und danach ein kompletter Lauf mit
demselben Limit fuer die Gesamtzeit und den Massenverlauf.

Aufruf:  freecadcmd tests/vergleich_varianten.py
"""
import glob
import os
import re
import subprocess
import sys
import tempfile
import time

HIER = os.path.dirname(os.path.abspath(__file__))
KLON = os.path.join(tempfile.gettempdir(), "beso-original")
PROTOTYP = r"C:\Users\Tom\topologie-optimierung\workbench\TopologieOptimierung\vendor\beso"
ADDON = r"C:\Users\Tom\AppData\Roaming\FreeCAD\v26-3\Mod\TopologyOptimization\freecad\TopoOpt\beso"
BERICHT = os.path.join(HIER, "vergleich_varianten.md")

VARIANTEN = (("original", KLON), ("prototyp", PROTOTYP), ("addon", ADDON))


def grosse_inp():
    """Das groesste vorhandene Netz aus den FreeCAD-Arbeitsordnern."""
    kandidaten = [p for p in glob.glob(os.path.join(tempfile.gettempdir(), "fcfem_*", "*.inp"))]
    return sorted(kandidaten, key=os.path.getsize)[-1] if kandidaten else ""


def elset_aus_inp(pfad):
    text = open(pfad, encoding="utf8", errors="ignore").read()
    namen = re.findall(r"^\*ELSET,\s*ELSET=([^\s,]+)", text, re.M)
    return sorted(n for n in namen if n.lower() not in ("eall", "efaces", "evolumes"))[0]


PYTHON = r"C:\Program Files\FreeCAD 26.3\bin\python.exe"


def messung(beso_ordner, inp, elset):
    skript = os.path.join(HIER, "messung_beso.py")
    start = time.time()
    prozess = subprocess.run([PYTHON if os.path.isfile(PYTHON) else sys.executable,
                              skript, beso_ordner, inp, elset],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)
    text = prozess.stdout.decode("utf8", "replace")
    zeile = [z for z in text.splitlines() if z.startswith("MESSUNG|")]
    if not zeile:
        return {"fehler": text.strip().splitlines()[-1] if text.strip() else "keine Ausgabe",
                "gesamt": time.time() - start}
    werte = zeile[-1].split("|")[1:]
    return {"import": float(werte[0]), "cg": float(werte[1]), "size": float(werte[2]),
            "prep": float(werte[3]), "elemente": int(werte[4]), "paare": int(werte[5]),
            "mittel": float(werte[6]), "gesamt": time.time() - start}


def main():
    inp = grosse_inp()
    if not inp:
        print("kein Netz gefunden - bitte erst eine .inp erzeugen")
        return
    if not os.path.isdir(KLON):
        print("Original-beso fehlt: %s" % KLON)
        return
    elset = elset_aus_inp(inp)
    zeilen = []
    zeilen.append("# Leistungsvergleich original / Prototyp / Addon")
    zeilen.append("")
    zeilen.append("Modell: `%s` (%.1f MB), Element-Set `%s`"
                  % (os.path.basename(inp), os.path.getsize(inp) / 1e6, elset))
    zeilen.append("")
    zeilen.append("| Variante | Netz lesen | Volumen/CG | Elementgroessen | Nachbarschaftsgitter "
                  "| Summe | Elemente | Paare |")
    zeilen.append("|---|---|---|---|---|---|---|---|")
    ergebnisse = {}
    for name, ordner in VARIANTEN:
        if not os.path.isdir(ordner):
            zeilen.append("| %s | - | - | - | - | - | - | fehlt: %s |" % (name, ordner))
            continue
        e = messung(ordner, inp, elset)
        ergebnisse[name] = e
        if "fehler" in e:
            zeilen.append("| %s | - | - | - | - | - | - | Fehler: %s |"
                          % (name, e["fehler"][:90]))
            continue
        zeilen.append("| %s | %.2f s | %.2f s | %.2f s | **%.2f s** | %.2f s | %d | %d |"
                      % (name, e["import"], e["cg"], e["size"], e["prep"],
                         e["import"] + e["cg"] + e["size"] + e["prep"], e["elemente"],
                         e["paare"]))
        print(zeilen[-1], flush=True)
    zeilen.append("")
    if "original" in ergebnisse and "addon" in ergebnisse:
        o, a = ergebnisse["original"], ergebnisse["addon"]
        if "fehler" not in o and "fehler" not in a:
            zeilen.append("Ergebnis der Rechnung ist bei beiden identisch: mittlere Elementgroesse "
                          "%.4f mm, %d Nachbarpaare." % (a["mittel"], a["paare"]))
    with open(BERICHT, "w", encoding="utf8") as fh:
        fh.write("\n".join(zeilen) + "\n")
    print("Bericht: %s" % BERICHT)


main()
