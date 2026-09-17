#!/usr/bin/env python
# SPDX-License-Identifier: LGPL-3.0-or-later
"""Headless test of the addon - run it with the FreeCAD console interpreter:

    "<FreeCAD>/bin/freecadcmd.exe" tests/headless_test.py

Exit code 0 = all checks passed.  The addon has to be installed in FreeCAD's Mod
directory (see Documentation/development.md).
"""

import os
import sys
import tempfile

import FreeCAD as App

fehler = []


def pruefe(bedingung, text):
    # flush=True: FreeCAD quits the process at sys.exit() without flushing the
    # buffers, so print() output would be lost when stdout is redirected
    print("%-5s %s" % ("OK" if bedingung else "FEHLT", text), flush=True)
    if not bedingung:
        fehler.append(text)


def beenden(code):
    sys.stdout.flush()
    sys.stderr.flush()
    sys.exit(code)


try:
    import freecad.TopoOpt as modul
except ImportError as exc:
    print("FEHLT Modul freecad.TopoOpt ist nicht importierbar (%s)" % exc)
    print("      Liegt das Addon im Mod-Ordner von FreeCAD? "
          "Siehe Documentation/development.md")
    beenden(1)

from freecad.TopoOpt.features import create_topology_object, find_analysis  # noqa: E402

print("FreeCAD %s, Addon %s" % (".".join(App.Version()[:3]), modul.__version__))
print()

doc = App.newDocument("TopoOptTest")
analysis = doc.addObject("Fem::FemAnalysis", "Analysis")
obj = create_topology_object(doc, analysis)
doc.recompute()

pruefe(obj.TypeId == "App::FeaturePython", "Objekt ist ein FeaturePython-Objekt")
pruefe(obj.Name in [o.Name for o in analysis.Group], "Objekt liegt als Kind in der Analyse")
pruefe(obj.AnalysisName == analysis.Name, "AnalysisName ist gespeichert")
pruefe(find_analysis(obj) is analysis, "find_analysis findet die Analyse ueber die Gruppe")

analysis.removeObject(obj)
pruefe(find_analysis(obj) is analysis, "find_analysis findet sie auch auszerhalb ueber den Namen")
analysis.addObject(obj)

# Persistenz: speichern, neu laden, Proxy und Eigenschaften pruefen
pfad = os.path.join(tempfile.gettempdir(), "topoopt_headless_test.FCStd")
if os.path.exists(pfad):
    os.remove(pfad)
doc.saveAs(pfad)
App.closeDocument(doc.Name)

doc2 = App.openDocument(pfad)
geladen = doc2.getObject("TopologieOptimierung")
pruefe(geladen is not None, "Objekt ist nach dem Laden wieder da")
if geladen is not None:
    pruefe(type(geladen.Proxy).__name__ == "TopologyObject", "Proxy ist nach dem Laden gesetzt")
    pruefe(geladen.AnalysisName == "Analysis", "AnalysisName ueberlebt das Speichern")
    analyse_geladen = find_analysis(geladen)
    pruefe(analyse_geladen is not None and analyse_geladen.Name == "Analysis",
           "find_analysis findet die Analyse nach dem Laden")
    pruefe(geladen.Name in [o.Name for o in analyse_geladen.Group],
           "Objekt haengt nach dem Laden wieder in der Analyse")
App.closeDocument(doc2.Name)
os.remove(pfad)

# --- Element-Sets und Rollen (reine Logik, ohne Dokument) -------------------
from freecad.TopoOpt.core import domains as dom        # noqa: E402
from freecad.TopoOpt.core import elsets as elset_reader  # noqa: E402

beispiel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "beispiel.inp")
gelesen = elset_reader.read_elsets(beispiel)
pruefe(gelesen.get("MaterialSolidSolid") == 4, "Elemente aus *ELEMENT-ELSET gelesen (4)")
pruefe(gelesen.get("NichtDesignSolid") == 2, "zweites Set gelesen (2)")
pruefe(gelesen.get("Eall") == 6, "Sammelset Eall gelesen (6)")
pruefe(gelesen.get("Reihe") == 6, "GENERATE-Set gelesen (10..20 Schritt 2 = 6)")
pruefe(gelesen.get("VerweisSet") == 4, "Set-Verweis wird aufgeloest (VerweisSet -> 4)")
pruefe(elset_reader.element_types(beispiel) == ["C3D4"], "Elementtyp erkannt (C3D4)")
pruefe(elset_reader.gesamt_elemente(beispiel) == 6, "Gesamtzahl der Elemente (6)")

sichtbar = dom.zeige_elsets(gelesen)
pruefe("Eall" not in sichtbar, "Sammelset wird nicht angeboten")
pruefe(len(sichtbar) == 4, "vier Sets werden angeboten")

vorschlag = dom.vorschlag(gelesen)
pruefe(vorschlag.get("Eall") is None, "Sammelset bekommt keine Rolle")
pruefe(set(vorschlag.values()) == {dom.IGNORE}, "bei mehreren Sets ist nichts vorbelegt")

vorschlag_eins = dom.vorschlag({"MaterialSolidSolid": 4, "Eall": 4})
pruefe(vorschlag_eins.get("MaterialSolidSolid") == dom.DESIGN,
       "bei genau einem Set wird der Design-Raum vorbelegt")

gespeichert = dom.format_domains({"B": dom.NON_DESIGN, "A": dom.DESIGN})
pruefe(gespeichert == ["A|design", "B|non_design"], "Rollen werden stabil formatiert")
zurueck = dom.parse_domains(gespeichert)
pruefe(zurueck == {"A": dom.DESIGN, "B": dom.NON_DESIGN}, "Rollen werden wieder eingelesen")

print()
if fehler:
    print("%d Pruefung(en) fehlgeschlagen" % len(fehler))
    beenden(1)
print("Alle Pruefungen bestanden", flush=True)
beenden(0)
