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
    """Leave the process with a status code.

    os._exit() and not sys.exit(): FreeCAD catches SystemExit from a script and
    runs the script a second time (measured - the output appeared twice), which
    makes a test unrepeatable.  The output buffers are flushed first because
    os._exit() does not do that.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


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

# Persistenz: speichern und die gespeicherte Datei pruefen.
# App.openDocument() wird hier bewusst NICHT benutzt: FreeCAD fuehrt ein
# Startskript danach erneut aus (gleicher Prozess, gemessen) - das macht einen
# Test unberechenbar.  Siehe Documentation/development.md.
pfad = os.path.join(tempfile.gettempdir(), "topoopt_headless_test.FCStd")
if os.path.exists(pfad):
    os.remove(pfad)
obj.Domains = ["TestSet|design"]
doc.saveAs(pfad)
App.closeDocument(doc.Name)

import zipfile  # noqa: E402

with zipfile.ZipFile(pfad) as archiv:
    xml = archiv.read("Document.xml").decode("utf8", "ignore")
pruefe('name="TopologieOptimierung"' in xml, "Objekt steht in der gespeicherten Datei")
pruefe("AnalysisName" in xml and 'Analysis"' in xml, "Analyse-Name ist gespeichert")
pruefe("Domains" in xml and "TestSet|design" in xml, "Rollen sind gespeichert")
pruefe("TopologyObject" in xml, "Proxy-Klasse (TopologyObject) ist gespeichert")
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

# --- Eingabedatei finden (Suchreihenfolge) ---------------------------------
import shutil as _shutil  # noqa: E402
import tempfile as _tempfile  # noqa: E402
import uuid as _uuid  # noqa: E402
from freecad.TopoOpt.core import fem as fem_core  # noqa: E402

doc3 = App.newDocument("TopoOptSuchTest")
# a name per run: FreeCAD may run the script twice (see the note about
# App.openDocument() in Documentation/development.md), so nothing may collide
dummy_mesh = doc3.addObject("App::FeaturePython",
                            "SuchMesh_%s" % _uuid.uuid4().hex[:8])
dummy_solver = doc3.addObject("App::FeaturePython", "SuchSolver")
dummy_solver.addProperty("App::PropertyString", "WorkingDirectory", "Test", "test")
dummy_solver.addProperty("App::PropertyString", "WorkingDir", "Test", "test")
dateiname = "%s.inp" % dummy_mesh.Name
ordner = _tempfile.mkdtemp(prefix="fcfem_topoopt_test_")
ordner2 = _tempfile.mkdtemp(prefix="fcfem_topoopt_other_")

pruefe(fem_core.find_inp(dummy_solver, dummy_mesh, "TopoOptTest", gemerkt=ordner)[0] is None,
       "ohne Datei wird nichts gefunden")

# 1. der (gemerkte) FEM-Arbeitsordner wird verwendet
pruefe(fem_core.arbeitsordner(dummy_solver, "TopoOptTest", dummy_mesh, gemerkt=ordner) == ordner,
       "gemerkter FEM-Arbeitsordner wird verwendet")

with open(os.path.join(ordner, dateiname), "w") as fh:
    fh.write("*ELSET, ELSET=SuchSet\n1, 2, 3\n")
pfad, quelle = fem_core.find_inp(dummy_solver, dummy_mesh, "TopoOptTest", gemerkt=ordner)
pruefe(quelle == "fem", "Datei im FEM-Arbeitsordner wird gefunden")
pruefe(os.path.dirname(pfad) == ordner, "der FEM-Arbeitsordner wird verwendet")

# 2. Datei nur in einem anderen FEM-Arbeitsordner
os.remove(os.path.join(ordner, dateiname))
with open(os.path.join(ordner2, dateiname), "w") as fh:
    fh.write("*ELSET, ELSET=SuchSet\n1, 2, 3\n")
pfad, quelle = fem_core.find_inp(dummy_solver, dummy_mesh, "TopoOptTest", gemerkt=ordner)
pruefe(quelle == "other", "anderer FEM-Arbeitsordner wird gefunden")
kopie = fem_core.uebernehme_inp(pfad, dummy_solver, "TopoOptTest", dummy_mesh, gemerkt=ordner)
pruefe(os.path.dirname(kopie) == ordner and os.path.isfile(kopie),
       "gefundene Datei wird in den FEM-Arbeitsordner kopiert")
pruefe(fem_core.datei_info(kopie).startswith("0.0 kB"), "Dateiinfo nennt Groesse (%s)"
       % fem_core.datei_info(kopie))

# 3. nur der eigene (alte) Arbeitsordner
os.remove(os.path.join(ordner, dateiname))
os.remove(os.path.join(ordner2, dateiname))
eigener = fem_core.run_dir("TopoOptTest", dummy_mesh.Name)
with open(os.path.join(eigener, dateiname), "w") as fh:
    fh.write("*ELSET, ELSET=SuchSet\n1, 2, 3\n")
pfad, quelle = fem_core.find_inp(dummy_solver, dummy_mesh, "TopoOptTest", gemerkt=ordner)
pruefe(quelle == "own", "eigener Arbeitsordner wird als letztes gefunden")
_shutil.rmtree(ordner, ignore_errors=True)
_shutil.rmtree(ordner2, ignore_errors=True)
_shutil.rmtree(eigener, ignore_errors=True)
App.closeDocument(doc3.Name)

# --- Uebersetzung (englische Quelle, deutsche Uebersetzung) -----------------
from freecad.TopoOpt.core import i18n  # noqa: E402

unbekannt = "a text that is not in the dictionary"
pruefe(i18n.uebersetze(unbekannt) == unbekannt, "unbekannte Texte bleiben unveraendert")
pruefe(i18n.uebersetze("Initialize") in ("Initialize", "Initialisieren"),
       "bekannter Text wird uebersetzt oder bleibt englisch: %r" % i18n.uebersetze("Initialize"))
pruefe(i18n.sprache() in ("", "de", "en", "fr", "es", "it"), "Sprache erkannt: %r" % i18n.sprache())

print()
if fehler:
    print("%d Pruefung(en) fehlgeschlagen" % len(fehler))
    beenden(1)
print("Alle Pruefungen bestanden", flush=True)
beenden(0)
