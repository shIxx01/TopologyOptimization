# SPDX-License-Identifier: LGPL-3.0-or-later
"""Laesst die drei beso-Staende auf demselben echten Modell laufen und misst die Zeit.

Basis ist ein vorhandener Arbeitsordner eines echten Laufs (Modell + fertige
beso_conf.py).  Daraus werden drei Kopien gemacht; in jede kommt die beso-Kopie
einer Variante, die Konfiguration bleibt gleich (nur das Iterationslimit wird
gesetzt).  Gemessen wird die Zeit bis zur ersten Iteration (Filteraufbau) und
die Gesamtzeit, dazu der Massenverlauf aus dem beso-Log.

Aufruf:  python tests/vergleich_lauf.py [basis-ordner] [limit]
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HIER = os.path.dirname(os.path.abspath(__file__))
PYTHON = r"C:\Program Files\FreeCAD 26.3\bin\python.exe"
KLON = os.path.join(tempfile.gettempdir(), "beso-original")
PROTOTYP = r"C:\Users\Tom\topologie-optimierung\workbench\TopologieOptimierung\vendor\beso"
ADDON = r"C:\Users\Tom\AppData\Roaming\FreeCAD\v26-3\Mod\TopologyOptimization\freecad\TopoOpt\beso"
ARBEIT = os.path.join(tempfile.gettempdir(), "topoopt_varianten")
BERICHT = os.path.join(HIER, "vergleich_lauf.md")
DATEIEN = ("beso_main.py", "beso_lib.py", "beso_filters.py", "beso_plots.py")

VARIANTEN = (("original", KLON), ("prototyp", PROTOTYP), ("addon", ADDON))
BASIS = os.path.join(tempfile.gettempdir(), "topoopt",
                     "TopologieOptimierung_KI_Workbench_FEMMeshNetgen")


def lauf(name, quelle, basis, limit):
    ziel = os.path.join(ARBEIT, "lauf_%s" % name)
    if os.path.isdir(ziel):
        shutil.rmtree(ziel, ignore_errors=True)
    if os.path.isdir(ziel):                    # Windows gibt Dateien verzoegert frei
        ziel = "%s_%d" % (ziel, int(time.time()))
    shutil.copytree(basis, ziel)
    for datei in DATEIEN:                      # beso-Kopie dieser Variante einsetzen
        q = os.path.join(quelle, datei)
        if os.path.isfile(q):
            shutil.copyfile(q, os.path.join(ziel, datei))
    conf_pfad = os.path.join(ziel, "beso_conf.py")
    text = io.open(conf_pfad, encoding="utf8", errors="replace").read()
    text = re.sub(r"iterations_limit\s*=\s*.*", "iterations_limit = %d" % limit, text)
    # lambda: re.sub wuerde Backslashes im Ersatztext als Escape lesen
    text = re.sub(r"^path\s*=\s*.*$", lambda m: "path = %r" % ziel, text, flags=re.M)
    text = re.sub(r"^path_calculix\s*=\s*.*$",
                  lambda m: "path_calculix = %r"
                  % r"C:\Program Files\FreeCAD 26.3\bin\ccx.EXE", text, flags=re.M)
    io.open(conf_pfad, "w", encoding="utf8").write(text)
    # den Netznamen nur herauslesen - die conf braucht beim Ausfuehren Variablen
    # des Prototyp-Runners, die es hier nicht gibt
    treffer = re.search(r"^name\s*=\s*['\"]([^'\"]+)", text, re.M)
    netz = treffer.group(1) if treffer else "FEMMeshNetgen"
    log = os.path.join(ziel, "%s.log" % netz)
    if os.path.isfile(log):
        alt = os.path.join(ziel, "%s_vorher.log" % netz)
        if os.path.isfile(alt):                  # Rest eines frueheren Versuchs
            os.remove(alt)
        os.rename(log, alt)
    start = time.time()
    ausgabe_pfad = os.path.join(ziel, "variante_stdout.txt")
    with open(ausgabe_pfad, "wb") as ausgabe_datei:
        prozess = subprocess.Popen([PYTHON, os.path.join(ziel, "beso_main.py")], cwd=ziel,
                                   stdout=ausgabe_datei, stderr=subprocess.STDOUT)
        erste = None
        while prozess.poll() is None and time.time() - start < 3600:
            if erste is None and os.path.isfile(log):
                if "new iteration number 1" in io.open(log, encoding="utf8",
                                                       errors="replace").read():
                    erste = time.time() - start
            time.sleep(0.5)
    gesamt = time.time() - start
    ausgabe = io.open(ausgabe_pfad, encoding="utf8", errors="replace").read()
    massen = []
    if os.path.isfile(log):
        for z in io.open(log, encoding="utf8", errors="replace").read().splitlines():
            teile = z.split()
            if len(teile) > 2 and teile[0].isdigit():
                try:
                    massen.append(round(float(teile[1]), 2))
                except ValueError:
                    pass
    return {"name": name, "code": prozess.returncode, "erste": erste, "gesamt": gesamt,
            "massen": massen[:6], "fehler": [z for z in ausgabe.splitlines()
                                             if "Error" in z or "ERROR" in z][:2]}


def main():
    basis = sys.argv[1] if len(sys.argv) > 1 else BASIS
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    if not os.path.isdir(basis):
        print("Basisordner fehlt: %s" % basis)
        return
    if not os.path.isdir(ARBEIT):
        os.makedirs(ARBEIT)
    inp = [f for f in os.listdir(basis) if f.endswith(".inp")]
    zeilen = ["# Laufvergleich der drei beso-Staende auf demselben echten Modell", "",
              "Modell: `%s`, Iterationslimit %d" % (inp[0] if inp else "?", limit), "",
              "| Variante | Zeit bis Iteration 1 | Gesamtzeit | Code | Massen |",
              "|---|---|---|---|---|"]
    for name, quelle in VARIANTEN:
        if not os.path.isdir(quelle):
            zeilen.append("| %s | - | - | fehlt | - |" % name)
            continue
        e = lauf(name, quelle, basis, limit)
        print("  %-9s: Iter1 %s, gesamt %.1f s, code %s, Massen %s"
              % (name, ("%.1f s" % e["erste"]) if e["erste"] else "-", e["gesamt"],
                 e["code"], e["massen"]), flush=True)
        if e["fehler"]:
            print("      Meldung: %s" % e["fehler"], flush=True)
        zeilen.append("| %s | %s | %.1f s | %s | %s |"
                      % (name, ("%.1f s" % e["erste"]) if e["erste"] else "> %.1f s" % e["gesamt"],
                         e["gesamt"], e["code"], e["massen"]))
    with open(BERICHT, "w", encoding="utf8") as fh:
        fh.write("\n".join(zeilen) + "\n")
    print("Bericht: %s" % BERICHT)


main()
