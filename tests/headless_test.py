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

print()
if fehler:
    print("%d Pruefung(en) fehlgeschlagen" % len(fehler))
    beenden(1)
print("Alle Pruefungen bestanden", flush=True)
beenden(0)
