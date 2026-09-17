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

# --- Parameter (Schritt 2) --------------------------------------------------
from freecad.TopoOpt.core import params as prm  # noqa: E402

pruefe(prm.mass_ratios("gentle") == (0.01, 0.02), "Massenraten 'sanft' wie in der beso-GUI")
pruefe(prm.mass_ratios("fast") == (0.03, 0.06), "Massenraten 'schnell' wie in der beso-GUI")
pruefe(prm.mass_ratios("unbekannt") == (0.015, 0.03), "unbekannte Stufe faellt auf 'normal'")
pruefe(prm.parse_filters(prm.format_filters([["casting", 2.0, "(0, 0, 1)"]]))
       == [["casting", 2.0, "(0, 0, 1)"]], "Filter werden geschrieben und gelesen")
pruefe(prm.parse_filters(prm.format_filters([["erode sensitivity", "auto"],
                                             ["simple", 3.0]]))
       == [["erode sensitivity", "auto"], ["simple", 3.0]],
       "Morphologie-Filter werden geschrieben und gelesen")
pruefe(len(prm.FILTER_TYPES) == 9 and "combined" not in prm.FILTER_TYPES,
       "beso kennt 9 Filtertypen (%s)" % (prm.FILTER_TYPES,))
pruefe("open-close sensitivity" in prm.FILTER_TYPES and "casting" in prm.FILTER_TYPES,
       "die beso-Typen sind vollstaendig")
pruefe(prm.parse_filters("kein Python") == [["simple", "robust"]],
       "unbrauchbarer Filtertext faellt auf beso-Standard zurueck")
pruefe(prm.parse_filters(prm.format_filters([["quatsch", 1]])) == [["simple", "robust"]],
       "unbekannter Filtertyp wird verworfen")

doc4 = App.newDocument("TopoOptParameterTest")
analyse4 = doc4.addObject("Fem::FemAnalysis", "Analyse")
obj4 = create_topology_object(doc4, analyse4, "TopoOpt4")
pruefe(abs(obj4.MassGoalRatio - 0.6) < 1e-9, "Zielmasse startet bei 0,6 (60 % vom Nutzer)")
pruefe(obj4.OptimizationBase == "stiffness", "Optimierungsziel startet mit 'stiffness'")
pruefe(obj4.IterationsLimit == "auto", "Iterationen starten mit 'auto'")
pruefe(abs(obj4.Tolerance - 1e-3) < 1e-12, "Toleranz startet mit 1e-3 (beso-Standard)")
pruefe(obj4.CpuCores == 0, "Kerne starten bei 0 (alle)")
pruefe(obj4.MassChange == "normal", "Massenänderung startet mit 'normal'")
pruefe(obj4.SaveIterations == 10, "jede 10. Iteration wird gespeichert (spart Platz)")
pruefe(obj4.ResultFormat == "inp vtk", "Ergebnisformat startet mit 'inp vtk'")

obj4.MassGoalRatio = 0.3
obj4.OptimizationBase = "buckling"
obj4.IterationsLimit = "25"
obj4.CpuCores = 4
obj4.Filters = prm.format_filters([["simple", 7.5], ["casting", 2.0, "(0, 0, 1)"]])
pfad4 = os.path.join(tempfile.gettempdir(), "topoopt_params_test.FCStd")
doc4.saveAs(pfad4)
App.closeDocument(doc4.Name)
import zipfile as _zipfile  # noqa: E402
with _zipfile.ZipFile(pfad4) as _z:
    _xml = _z.read("Document.xml").decode("utf8", "ignore")
pruefe('name="MassGoalRatio"' in _xml and "0.3" in _xml, "Zielmasse ist gespeichert")
pruefe("buckling" in _xml, "Optimierungsziel ist gespeichert")
pruefe("casting" in _xml, "Filter sind gespeichert")
pruefe('name="CpuCores"' in _xml, "Kerne sind gespeichert")
os.remove(pfad4)

# --- mitgeliefertes beso + Filterradius -------------------------------------
from freecad.TopoOpt.core import beso as beso_modul  # noqa: E402
from freecad.TopoOpt.core import radius as radius_modul  # noqa: E402

ordner, fehlend = beso_modul.pruefe()
pruefe(not fehlend, "beso liegt vollstaendig im Addon (%s)" % ordner)
if fehlend:
    print("beso: fehlende Dateien %s" % (fehlend,), flush=True)

lib, filters = beso_modul.module()
pruefe(hasattr(lib, "import_inp") and hasattr(filters, "prepare2s"),
       "beso_lib und beso_filters sind geladen")
pruefe("beso_lib" in sys.modules and sys.modules["beso_lib"] is lib,
       "beso_lib steht unter seinem eigenen Namen (so importiert beso sich selbst)")

beispiel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "beispiel.inp")
daten = radius_modul.gelesen(beispiel, ["MaterialSolidSolid", "NichtDesignSolid"],
                             ["MaterialSolidSolid"])
print("Elementdaten: mittel=%.4f maximum=%.4f anzahl=%s"
      % (daten.get("mittel", -1), daten.get("maximum", -1), daten.get("anzahl", -1)), flush=True)
pruefe(daten.get("anzahl", 0) > 0, "beso liest Elementgroessen aus der .inp (%s Elemente)"
       % daten.get("anzahl"))
pruefe(0 < daten.get("mittel", 0) <= daten.get("maximum", 0),
       "mittlere Groesse liegt unter der groessten (%.4f <= %.4f)"
       % (daten.get("mittel", 0), daten.get("maximum", 0)))

zu_klein = radius_modul.ohne_nachbarn(daten, daten["mittel"] * 0.1)
gross_genug = radius_modul.ohne_nachbarn(daten, daten["mittel"] * 10.0)
print("ohne Nachbarn: bei 0,1x mittel %d, bei 10x mittel %d"
      % (len(zu_klein), len(gross_genug)), flush=True)
pruefe(len(zu_klein) > 0, "bei zu kleinem Radius fehlen Nachbarn (%d Elemente)" % len(zu_klein))
pruefe(len(gross_genug) == 0, "bei grossem Radius hat jedes Element Nachbarn")

# die schnelle Gitterpruefung muss dasselbe liefern wie besos prepare2s
gleich = True
for faktor in (0.5, 1.0, 1.5, 2.0, 3.0):
    radius = faktor * daten["mittel"]
    if sorted(radius_modul.ohne_nachbarn(daten, radius)) != \
            sorted(radius_modul.ohne_nachbarn_beso(daten, radius)):
        gleich = False
        print("Unterschied bei Faktor %.1f" % faktor, flush=True)
pruefe(gleich, "schnelle Pruefung und besos prepare2s stimmen ueberein")

ergebnis = radius_modul.robust(daten)
print("robuster Radius: Faktor %.1f -> %.4f mm, ohne Nachbarn: %d"
      % (ergebnis.get("faktor", -1), ergebnis.get("radius", -1),
         ergebnis.get("ohne_nachbarn", -1)), flush=True)
pruefe(ergebnis.get("ohne_nachbarn") == 0,
       "robuster Radius laesst kein Element ohne Nachbarn")
pruefe(ergebnis.get("radius", 0) >= radius_modul.BESO_AUTO * daten["mittel"],
       "robuster Radius ist mindestens so gross wie besos 'auto'")
pruefe(radius_modul.robust({}) == {}, "ohne Elementdaten kommt ein leeres Ergebnis")
# beso schreibt beim Einlesen eine Logdatei neben die .inp (write_to_log) - im Test
# wieder weg damit, im Arbeitsordner ist sie gewollt
protokoll = os.path.splitext(beispiel)[0] + ".log"
if os.path.isfile(protokoll):
    os.remove(protokoll)

# --- Schritt 3: die Konfiguration fuer beso ---------------------------------
from freecad.TopoOpt.core import conf as conf_modul  # noqa: E402

pruefe(conf_modul.UNTERORDNER == "topoopt_beso",
       "beso laeuft in einem Unterordner des Arbeitsordners (%s)" % conf_modul.UNTERORDNER)
pruefe("ccx" in os.path.basename(conf_modul.calculix_pfad()).lower(),
       "CalculiX wird gefunden (%s)" % conf_modul.calculix_pfad())
pruefe("python" in os.path.basename(conf_modul.python_pfad()).lower(),
       "ein Python fuer den Lauf wird gefunden (%s)" % conf_modul.python_pfad())

doc5 = App.newDocument("TopoOptConfTest")
analyse5 = doc5.addObject("Fem::FemAnalysis", "Analyse")
obj5 = create_topology_object(doc5, analyse5, "TopoOpt5")
obj5.MassGoalRatio = 0.6
obj5.IterationsLimit = "auto"
obj5.Filters = "[['simple', 'robust']]"
obj5.RobusterRadius = 4.85
domains4 = {"SetA": "design", "SetB": "non_design"}
text = conf_modul.conf_text(obj5, os.path.join("C:", os.sep, "tmp", "Mesh.inp"), domains4,
                            os.path.join("C:", os.sep, "tmp"))
pruefe("path = " in text and "tmp" in text, "der Arbeitsordner steht in der Konfiguration")
pruefe("file_name = 'Mesh.inp'" in text, "die Eingabedatei steht in der Konfiguration")
pruefe("mass_goal_ratio = 0.6" in text, "die Zielmasse steht in der Konfiguration")
pruefe("{'SetA': True, 'SetB': False}" in text,
       "Design- und Nicht-Design-Raum stehen in der Konfiguration")
pruefe("['simple', 4.85]" in text,
       "der robuste Radius wird als Zahl geschrieben (kein 'robust' fuer beso)")
pruefe("_mpl.use('Agg')" in text, "ohne Fenster am Ende (beso_main ruft plt.show)")
pruefe("beso_conf_vorlage.py" in text, "die Vorlage von beso wird als Grundlage gelesen")

ordner4 = _tempfile.mkdtemp(prefix="topoopt_conf_")
ziel4, conf4 = conf_modul.schreibe_dateien(obj5, os.path.join(ordner4, "Mesh.inp"),
                                           domains4, ordner4)
pruefe(os.path.isfile(conf4), "beso_conf.py wird geschrieben")
pruefe(os.path.isfile(os.path.join(ziel4, "beso_main.py")), "beso_main.py liegt im Unterordner")
pruefe(os.path.isfile(os.path.join(ziel4, "beso_conf_vorlage.py")),
       "die beso-Vorlage liegt unveraendert daneben")
pruefe(os.path.isfile(os.path.join(ziel4, "beso_lib.py")), "beso_lib.py liegt im Unterordner")
pruefe(conf_modul.log_pfad(os.path.join(ordner4, "Mesh.inp")).endswith("Mesh_topoopt.log"),
       "die Logdatei liegt neben der Eingabedatei")
_shutil.rmtree(ordner4, ignore_errors=True)

print()
if fehler:
    print("%d Pruefung(en) fehlgeschlagen" % len(fehler))
    beenden(1)
print("Alle Pruefungen bestanden", flush=True)
beenden(0)
