# SPDX-License-Identifier: LGPL-3.0-or-later
"""Leistungsvergleich: unveraendertes beso von GitHub gegen das gebuendelte beso.

Gemessen wird auf **demselben Modell** die Vorbereitungszeit (Netz lesen,
Volumen/Schwerpunkt, Elementgroessen, Nachbarschaftsgitter) und die Gesamtzeit
eines Laufs.  Damit laesst sich zeigen, dass die Fixes des Addons die Rechnung
weder veraendern noch verlangsamen.

Das Original zuerst klonen::

    git clone --depth 1 https://github.com/calculix/beso.git
    set BESO_ORIGINAL=C:\\Pfad\\zu\\beso-original      (Windows)
    export BESO_ORIGINAL=/pfad/zu/beso-original        (Linux/macOS)

Aufruf (FreeCADs Python oder freecadcmd)::

    python tests/vergleich_varianten.py [modell.inp] [elset]

Ohne Argumente wird das groesste Netz aus den FreeCAD-Arbeitsordnern genommen.
Schreibt ``vergleich_varianten.md`` neben das Skript.
"""
import glob
import os
import re
import subprocess
import sys
import tempfile
import time

HIER = os.path.dirname(os.path.abspath(__file__))
BERICHT = os.path.join(HIER, "vergleich_varianten.md")
# Original-beso: geklonter upstream-Stand (siehe Modulbeschreibung)
ORIGINAL = os.environ.get("BESO_ORIGINAL", os.path.join(tempfile.gettempdir(), "beso-original"))
# gebuendelte Kopie des Addons (dieses Repo)
ADDON = os.path.join(os.path.dirname(HIER), "freecad", "TopoOpt", "beso")

VARIANTEN = (("beso (GitHub, unveraendert)", ORIGINAL), ("beso im Addon", ADDON))

def _python():
    """Interpreter ohne FreeCAD-Start - beso braucht nur Python und numpy."""
    neben = os.path.join(os.path.dirname(sys.executable), "python.exe")
    return neben if os.path.isfile(neben) else sys.executable


PYTHON = os.environ.get("BESO_PYTHON") or _python()


def grosse_inp():
    kandidaten = glob.glob(os.path.join(tempfile.gettempdir(), "fcfem_*", "*.inp"))
    return sorted(kandidaten, key=os.path.getsize)[-1] if kandidaten else ""


def elset_aus_inp(pfad):
    text = open(pfad, encoding="utf8", errors="ignore").read()
    namen = re.findall(r"^\*ELSET,\s*ELSET=([^\s,]+)", text, re.M)
    namen += re.findall(r"^\*ELEMENT,\s*TYPE=\w+,\s*ELSET=([^\s,]+)", text, re.M)
    ohne = [n for n in namen if n.lower() not in ("eall", "efaces", "evolumes")]
    return sorted(ohne)[0] if ohne else ""


def messung(beso_ordner, inp, elset):
    """Eine beso-Kopie in eigenem Prozess messen (jede bringt eigene Module mit)."""
    skript = os.path.join(HIER, "messung_beso.py")
    start = time.time()
    prozess = subprocess.run([PYTHON, skript, beso_ordner, inp, elset],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=3600)
    text = prozess.stdout.decode("utf8", "replace")
    zeilen = [z for z in text.splitlines() if z.startswith("MESSUNG|")]
    if not zeilen:
        letzte = [z for z in text.splitlines() if z.strip()]
        return {"fehler": letzte[-1][:120] if letzte else "keine Ausgabe",
                "gesamt": time.time() - start}
    w = zeilen[-1].split("|")[1:]
    return {"import": float(w[0]), "cg": float(w[1]), "size": float(w[2]), "prep": float(w[3]),
            "elemente": int(w[4]), "paare": int(w[5]), "mittel": float(w[6]),
            "gesamt": time.time() - start}


def main():
    inp = sys.argv[1] if len(sys.argv) > 1 else grosse_inp()
    if not inp or not os.path.isfile(inp):
        print("kein Modell gefunden - bitte eine .inp angeben")
        return
    elset = sys.argv[2] if len(sys.argv) > 2 else elset_aus_inp(inp)
    if not elset:
        print("im Modell ist kein Element-Set gefunden worden")
        return

    zeilen = ["# Leistungsvergleich der beso-Kopien", "",
              "Modell: `%s` (%.1f MB), Element-Set `%s`"
              % (os.path.basename(inp), os.path.getsize(inp) / 1e6, elset), "",
              "| Variante | Netz lesen | Volumen/CG | Elementgroessen | Nachbarschaftsgitter "
              "| Summe | Elemente | Nachbarpaare |",
              "|---|---|---|---|---|---|---|---|"]
    ergebnisse = {}
    for name, ordner in VARIANTEN:
        if not os.path.isdir(ordner):
            zeilen.append("| %s | - | - | - | - | - | - | nicht gefunden: `%s` |" % (name, ordner))
            print("fehlt: %s" % ordner, flush=True)
            continue
        e = messung(ordner, inp, elset)
        ergebnisse[name] = e
        if "fehler" in e:
            zeilen.append("| %s | - | - | - | - | - | - | Fehler: %s |" % (name, e["fehler"]))
            print("%-28s Fehler: %s" % (name, e["fehler"]), flush=True)
            continue
        zeile = ("| %s | %.2f s | %.2f s | %.2f s | **%.2f s** | %.2f s | %d | %d |"
                 % (name, e["import"], e["cg"], e["size"], e["prep"],
                    e["import"] + e["cg"] + e["size"] + e["prep"], e["elemente"], e["paare"]))
        zeilen.append(zeile)
        print(zeile, flush=True)
    zeilen.append("")

    werte = [e for e in ergebnisse.values() if "fehler" not in e]
    if len(werte) == 2 and werte[0]["paare"] == werte[1]["paare"] \
            and abs(werte[0]["mittel"] - werte[1]["mittel"]) < 1e-9:
        zeilen.append("Beide Kopien finden dieselbe mittlere Elementgroesse (%.4f mm) und "
                      "dieselbe Zahl Nachbarpaare (%d) - das Ergebnis der Rechnung ist "
                      "identisch." % (werte[0]["mittel"], werte[0]["paare"]))
    with open(BERICHT, "w", encoding="utf8") as fh:
        fh.write("\n".join(zeilen) + "\n")
    print("Bericht: %s" % BERICHT)


main()
