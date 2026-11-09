#!/usr/bin/env python
# SPDX-License-Identifier: LGPL-3.0-or-later
"""Headless test of the addon - run it with the FreeCAD console interpreter:

    "<FreeCAD>/bin/freecadcmd.exe" tests/headless_test.py

Exit code 0 = all checks passed.  The addon has to be installed in FreeCAD's Mod
directory (see Documentation/development.md).

A script that stops with an exception also leaves FreeCADCmd with exit code 0 (measured), so the
closing line matters as much as the exit code - the CI checks both."""

import os
import sys
import tempfile

import FreeCAD as App

# The messages are German.  Without a UTF-8 locale (LANG=C) sys.stdout would be ASCII
# and a print() with an umlaut would abort the run - the remaining checks would then
# never run.  That is why the output is pinned to UTF-8, with "replace" as the fallback.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf8", errors="replace")
        except (AttributeError, ValueError):
            pass

errors = []


def check(condition, text):
    # flush=True: FreeCAD quits the process at sys.exit() without flushing the
    # buffers, so print() output would be lost when stdout is redirected
    print("%-5s %s" % ("OK" if condition else "FEHLT", text), flush=True)
    if not condition:
        errors.append(text)


def finish(code):
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
    import freecad.TopoOpt as module
except ImportError as exc:
    print("FEHLT Modul freecad.TopoOpt ist nicht importierbar (%s)" % exc)
    print("      Liegt das Addon im Mod-Ordner von FreeCAD? "
          "Siehe Documentation/development.md")
    finish(1)

from freecad.TopoOpt.features import create_topology_object, find_analysis  # noqa: E402

print("FreeCAD %s, Addon %s" % (".".join(App.Version()[:3]), module.__version__))
print()

doc = App.newDocument("TopoOptTest")
analysis = doc.addObject("Fem::FemAnalysis", "Analysis")
obj = create_topology_object(doc, analysis)
doc.recompute()

check(obj.TypeId == "App::FeaturePython", "Objekt ist ein FeaturePython-Objekt")
check(obj.Name in [o.Name for o in analysis.Group], "Objekt liegt als Kind in der Analyse")
check(obj.AnalysisName == analysis.Name, "AnalysisName ist gespeichert")
check(find_analysis(obj) is analysis, "find_analysis findet die Analyse ueber die Gruppe")

analysis.removeObject(obj)
check(find_analysis(obj) is analysis, "find_analysis findet sie auch auszerhalb ueber den Namen")
analysis.addObject(obj)

# Persistence: save the document and check the saved file.
# App.openDocument() is deliberately NOT used here: FreeCAD then runs a start
# script a second time (same process, measured) - that makes a test
# unpredictable.  See Documentation/development.md.
path = os.path.join(tempfile.gettempdir(), "topoopt_headless_test.FCStd")
if os.path.exists(path):
    os.remove(path)
obj.Domains = ["TestSet|design"]
doc.saveAs(path)
App.closeDocument(doc.Name)

import zipfile  # noqa: E402

with zipfile.ZipFile(path) as archive:
    xml = archive.read("Document.xml").decode("utf8", "ignore")
check('name="TopologieOptimierung"' in xml, "Objekt steht in der gespeicherten Datei")
check("AnalysisName" in xml and 'Analysis"' in xml, "Analyse-Name ist gespeichert")
check("Domains" in xml and "TestSet|design" in xml, "Rollen sind gespeichert")
check("TopologyObject" in xml, "Proxy-Klasse (TopologyObject) ist gespeichert")
os.remove(path)

# --- element sets and roles (pure logic, no document) -----------------------
from freecad.TopoOpt.core import domains as dom        # noqa: E402
from freecad.TopoOpt.core import elsets as elset_reader  # noqa: E402

example = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "beispiel.inp")
read_sets = elset_reader.read_elsets(example)
check(read_sets.get("MaterialSolidSolid") == 4, "Elemente aus *ELEMENT-ELSET gelesen (4)")
check(read_sets.get("NichtDesignSolid") == 2, "zweites Set gelesen (2)")
check(read_sets.get("Eall") == 6, "Sammelset Eall gelesen (6)")
check(read_sets.get("Reihe") == 6, "GENERATE-Set gelesen (10..20 Schritt 2 = 6)")
check(read_sets.get("VerweisSet") == 4, "Set-Verweis wird aufgeloest (VerweisSet -> 4)")
check(elset_reader.element_types(example) == ["C3D4"], "Elementtyp erkannt (C3D4)")
check(elset_reader.total_elements(example) == 6, "Gesamtzahl der Elemente (6)")

visible = dom.visible_elsets(read_sets)
check("Eall" not in visible, "Sammelset wird nicht angeboten")
check(len(visible) == 4, "vier Sets werden angeboten")

proposal = dom.suggestion(read_sets)
check(proposal.get("Eall") is None, "Sammelset bekommt keine Rolle")
check(set(proposal.values()) == {dom.DESIGN},
       "ohne Vorbelegung ist jedes Set Design-Raum (nicht 'ignorieren')")

proposal_single = dom.suggestion({"MaterialSolidSolid": 4, "Eall": 4})
check(proposal_single.get("MaterialSolidSolid") == dom.DESIGN,
       "auch ein einzelnes Set ist Design-Raum")

stored = dom.format_domains({"B": dom.NON_DESIGN, "A": dom.DESIGN})
check(stored == ["A|design", "B|non_design"], "Rollen werden stabil formatiert")
parsed = dom.parse_domains(stored)
check(parsed == {"A": dom.DESIGN, "B": dom.NON_DESIGN}, "Rollen werden wieder eingelesen")

roles = dom.roles_for({"A": 10, "B": 10, "Neu": 10}, parsed)
check(roles == {"A": dom.DESIGN, "B": dom.NON_DESIGN, "Neu": dom.DESIGN},
       "Gespeichertes gilt weiter, ein neues Set ist Design-Raum (%s)" % roles)
roles_empty = dom.roles_for({"A": 10, "B": 10})
check(set(roles_empty.values()) == {dom.DESIGN},
       "ohne Vorbelegung ist alles Design-Raum")

# --- find the input file (search order) -------------------------------------
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
file_name = "%s.inp" % dummy_mesh.Name
folder = _tempfile.mkdtemp(prefix="fcfem_topoopt_test_")
folder2 = _tempfile.mkdtemp(prefix="fcfem_topoopt_other_")

check(fem_core.find_inp(dummy_solver, dummy_mesh, "TopoOptTest", remembered=folder)[0] is None,
       "ohne Datei wird nichts gefunden")

# 1. the (remembered) FEM working directory is used
check(fem_core.working_dir(dummy_solver, "TopoOptTest", dummy_mesh, remembered=folder) == folder,
       "gemerkter FEM-Arbeitsordner wird verwendet")

with open(os.path.join(folder, file_name), "w") as fh:
    fh.write("*ELSET, ELSET=SuchSet\n1, 2, 3\n")
path, source = fem_core.find_inp(dummy_solver, dummy_mesh, "TopoOptTest", remembered=folder)
check(source == "fem", "Datei im FEM-Arbeitsordner wird gefunden")
check(os.path.dirname(path) == folder, "der FEM-Arbeitsordner wird verwendet")

# 2. file only in another FEM working directory
os.remove(os.path.join(folder, file_name))
with open(os.path.join(folder2, file_name), "w") as fh:
    fh.write("*ELSET, ELSET=SuchSet\n1, 2, 3\n")
path, source = fem_core.find_inp(dummy_solver, dummy_mesh, "TopoOptTest", remembered=folder)
check(source == "other", "anderer FEM-Arbeitsordner wird gefunden")
copy = fem_core.adopt_inp(path, dummy_solver, "TopoOptTest", dummy_mesh, remembered=folder)
check(os.path.dirname(copy) == folder and os.path.isfile(copy),
       "gefundene Datei wird in den FEM-Arbeitsordner kopiert")
check(fem_core.file_info(copy).startswith("0.0 kB"), "Dateiinfo nennt Groesse (%s)"
       % fem_core.file_info(copy))

# 3. only our own (old) working directory
os.remove(os.path.join(folder, file_name))
os.remove(os.path.join(folder2, file_name))
own_folder = fem_core.run_dir("TopoOptTest", dummy_mesh.Name)
with open(os.path.join(own_folder, file_name), "w") as fh:
    fh.write("*ELSET, ELSET=SuchSet\n1, 2, 3\n")
path, source = fem_core.find_inp(dummy_solver, dummy_mesh, "TopoOptTest", remembered=folder)
check(source == "own", "eigener Arbeitsordner wird als letztes gefunden")
_shutil.rmtree(folder, ignore_errors=True)
_shutil.rmtree(folder2, ignore_errors=True)
_shutil.rmtree(own_folder, ignore_errors=True)
App.closeDocument(doc3.Name)

# --- translation (English source, German translation) -----------------------
from freecad.TopoOpt.core import i18n  # noqa: E402

unknown = "a text that is not in the dictionary"
check(i18n.translate(unknown) == unknown, "unbekannte Texte bleiben unveraendert")
check(i18n.translate("Initialize") in ("Initialize", "Initialisieren"),
       "bekannter Text wird uebersetzt oder bleibt englisch: %r" % i18n.translate("Initialize"))
# The language comes from FreeCAD's settings or from the system - which language that
# is depends on the machine (in a CI without a locale it is "C").  The check therefore
# covers only what the function promises: an empty result or a code made of letters.
detected = i18n.language()
check(detected == "" or detected.isalpha(),
       "die Sprache wird als Kuerzel erkannt (%r)" % detected)

# --- parameters (step 2) ----------------------------------------------------
from freecad.TopoOpt.core import params as prm  # noqa: E402

check(prm.mass_ratios("gentle") == (0.01, 0.02), "Massenraten 'sanft' wie in der beso-GUI")
check(prm.mass_ratios("fast") == (0.03, 0.06), "Massenraten 'schnell' wie in der beso-GUI")
check(prm.mass_ratios("unbekannt") == (0.015, 0.03), "unbekannte Stufe faellt auf 'normal'")
check(prm.parse_filters(prm.format_filters([["casting", 2.0, "(0, 0, 1)"]]))
       == [["casting", 2.0, "(0, 0, 1)"]], "Filter werden geschrieben und gelesen")
check(prm.parse_filters(prm.format_filters([["erode sensitivity", "auto"],
                                             ["simple", 3.0]]))
       == [["erode sensitivity", "auto"], ["simple", 3.0]],
       "Morphologie-Filter werden geschrieben und gelesen")
check(len(prm.FILTER_TYPES) == 9 and "combined" not in prm.FILTER_TYPES,
       "beso kennt 9 Filtertypen (%s)" % (prm.FILTER_TYPES,))
check("open-close sensitivity" in prm.FILTER_TYPES and "casting" in prm.FILTER_TYPES,
       "die beso-Typen sind vollstaendig")
check(prm.parse_filters("kein Python") == [["simple", "robust"]],
       "unbrauchbarer Filtertext faellt auf beso-Standard zurueck")
check(prm.parse_filters(prm.format_filters([["quatsch", 1]])) == [["simple", "robust"]],
       "unbekannter Filtertyp wird verworfen")

doc4 = App.newDocument("TopoOptParameterTest")
analysis4 = doc4.addObject("Fem::FemAnalysis", "Analyse")
obj4 = create_topology_object(doc4, analysis4, "TopoOpt4")
check(abs(obj4.MassGoalRatio - 0.6) < 1e-9, "Zielmasse startet bei 0,6 (60 %)")
check(obj4.OptimizationBase == "stiffness", "Optimierungsziel startet mit 'stiffness'")
check(obj4.IterationsLimit == "auto", "Iterationen starten mit 'auto'")
check(abs(obj4.Tolerance - 1e-3) < 1e-12, "Toleranz startet mit 1e-3 (beso-Standard)")
check(obj4.FIViolatedTolerance == 1, "FI-Toleranz startet bei 1 (beso-Standard)")
check(obj4.CpuCores == 0, "Kerne starten bei 0 (alle)")
check(obj4.MassChange == "normal", "Massenänderung startet mit 'normal'")
check(obj4.SaveIterations == 10, "jede 10. Iteration wird gespeichert (spart Platz)")
check(obj4.ResultFormat == "inp vtk", "Ergebnisformat startet mit 'inp vtk'")

obj4.MassGoalRatio = 0.3
obj4.OptimizationBase = "buckling"
obj4.IterationsLimit = "25"
obj4.CpuCores = 4
obj4.FIViolatedTolerance = 5
obj4.Filters = prm.format_filters([["simple", 7.5], ["casting", 2.0, "(0, 0, 1)"]])
path4 = os.path.join(tempfile.gettempdir(), "topoopt_params_test.FCStd")
doc4.saveAs(path4)
App.closeDocument(doc4.Name)
import zipfile as _zipfile  # noqa: E402
with _zipfile.ZipFile(path4) as _z:
    _xml = _z.read("Document.xml").decode("utf8", "ignore")
check('name="MassGoalRatio"' in _xml and "0.3" in _xml, "Zielmasse ist gespeichert")
check("buckling" in _xml, "Optimierungsziel ist gespeichert")
check("casting" in _xml, "Filter sind gespeichert")
check('name="CpuCores"' in _xml, "Kerne sind gespeichert")
check('name="FIViolatedTolerance"' in _xml, "FI-Toleranz ist gespeichert")
os.remove(path4)

# --- bundled beso + filter radius -------------------------------------------
from freecad.TopoOpt.core import beso as beso_module  # noqa: E402
from freecad.TopoOpt.core import radius as radius_module  # noqa: E402

folder, missing = beso_module.check()
check(not missing, "beso liegt vollstaendig im Addon (%s)" % folder)
if missing:
    print("beso: fehlende Dateien %s" % (missing,), flush=True)

lib, filters = beso_module.module()
check(hasattr(lib, "import_inp") and hasattr(filters, "prepare2s"),
       "beso_lib und beso_filters sind geladen")
check("beso_lib" in sys.modules and sys.modules["beso_lib"] is lib,
       "beso_lib steht unter seinem eigenen Namen (so importiert beso sich selbst)")

example = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "beispiel.inp")
data = radius_module.read_data(example, ["MaterialSolidSolid", "NichtDesignSolid"],
                               ["MaterialSolidSolid"])
print("Elementdaten: mittel=%.4f maximum=%.4f anzahl=%s"
      % (data.get("mean", -1), data.get("maximum", -1), data.get("count", -1)), flush=True)
check(data.get("count", 0) > 0, "beso liest Elementgroessen aus der .inp (%s Elemente)"
       % data.get("count"))
check(0 < data.get("mean", 0) <= data.get("maximum", 0),
       "mittlere Groesse liegt unter der groessten (%.4f <= %.4f)"
       % (data.get("mean", 0), data.get("maximum", 0)))

too_small = radius_module.without_neighbours(data, data["mean"] * 0.1)
large_enough = radius_module.without_neighbours(data, data["mean"] * 10.0)
print("ohne Nachbarn: bei 0,1x mittel %d, bei 10x mittel %d"
      % (len(too_small), len(large_enough)), flush=True)
check(len(too_small) > 0, "bei zu kleinem Radius fehlen Nachbarn (%d Elemente)" % len(too_small))
check(len(large_enough) == 0, "bei grossem Radius hat jedes Element Nachbarn")

# the fast grid check has to return the same as beso's prepare2s
equal = True
for factor in (0.5, 1.0, 1.5, 2.0, 3.0):
    radius = factor * data["mean"]
    if sorted(radius_module.without_neighbours(data, radius)) != \
            sorted(radius_module.without_neighbours_beso(data, radius)):
        equal = False
        print("Unterschied bei Faktor %.1f" % factor, flush=True)
check(equal, "schnelle Pruefung und besos prepare2s stimmen ueberein")

result = radius_module.robust(data)
print("robuster Radius: Faktor %.1f -> %.4f mm, ohne Nachbarn: %d"
      % (result.get("factor", -1), result.get("radius", -1),
         result.get("without_neighbours", -1)), flush=True)
check(result.get("without_neighbours") == 0,
       "robuster Radius laesst kein Element ohne Nachbarn")
check(result.get("radius", 0) >= radius_module.BESO_AUTO * data["mean"],
       "robuster Radius ist mindestens so gross wie besos 'auto'")
check(radius_module.robust({}) == {}, "ohne Elementdaten kommt ein leeres Ergebnis")
# beso writes a log file next to the .inp while reading it (write_to_log) - remove it
# again in the test, in the working directory it is wanted
protocol_file = os.path.splitext(example)[0] + ".log"
if os.path.isfile(protocol_file):
    os.remove(protocol_file)

# --- step 3: the configuration for beso -------------------------------------
from freecad.TopoOpt.core import conf as conf_module  # noqa: E402

check(conf_module.SUBFOLDER == "topoopt_beso",
       "beso laeuft in einem Unterordner des Arbeitsordners (%s)" % conf_module.SUBFOLDER)
check("ccx" in os.path.basename(conf_module.calculix_path()).lower(),
       "CalculiX wird gefunden (%s)" % conf_module.calculix_path())
check("python" in os.path.basename(conf_module.python_path() or "").lower(),
       "ein Python fuer den Lauf wird gefunden (%s)" % conf_module.python_path())
# The interpreter must never be FreeCAD itself: on FreeCADCmd "-u" is FreeCAD's own
# option (user parameter file), beso_main.py would be overwritten instead of running
# (measured in the Flatpak - there sys.executable is the FreeCADCmd in the app directory).
check(conf_module.python_path() is None
       or "freecad" not in os.path.basename(conf_module.python_path()).lower(),
       "der Interpreter ist nicht FreeCAD selbst (%s)" % conf_module.python_path())
check(conf_module.calculix_path() == "ccx" or os.path.isfile(conf_module.calculix_path()),
       "der gefundene Solver ist eine Datei (%s)" % conf_module.calculix_path())
check(conf_module.python_path() is None or os.path.isfile(conf_module.python_path()),
       "der gefundene Interpreter ist eine Datei (%s)" % conf_module.python_path())
# without Python there is no run: a clear message instead of starting a wrong process,
# and nothing is written into the working directory
_real_python_path = conf_module.python_path
conf_module.python_path = lambda: None
try:
    conf_module.start(None, None, {}, None)
    check(False, "ohne Python wird der Lauf abgelehnt")
except RuntimeError as message:
    check("python" in str(message).lower(),
           "ohne Python kommt eine klare Meldung (%s)" % message)
except Exception as message:  # noqa: BLE001
    check(False, "ohne Python kommt ein RuntimeError, nicht %r" % message)
finally:
    conf_module.python_path = _real_python_path

# --- which ccx is used, and what it can do (D45, D46) ------------------------
# The FEM preference is simulated - the real settings of this machine stay untouched.
import shutil  # noqa: E402

_real_fem_ccx = conf_module._fem_ccx
_ccx_dir = tempfile.mkdtemp(prefix="topoopt_ccx_")
_fake_ccx = os.path.join(_ccx_dir, "ccx_fake")
open(_fake_ccx, "w", encoding="utf8").close()
try:
    conf_module._fem_ccx = lambda: (_fake_ccx, _fake_ccx)
    path, origin, note = conf_module._resolve_calculix()
    check(path == os.path.abspath(_fake_ccx) and origin == "FreeCAD preference" and not note,
          "der Solver aus Preferences > FEM > CalculiX gewinnt (%s, %s)" % (path, origin))
    check(conf_module.calculix_path() == os.path.abspath(_fake_ccx),
          "calculix_path() liefert genau diesen Solver")
    conf_module._fem_ccx = lambda: ("", os.path.join(_ccx_dir, "gibt_es_nicht"))
    path, origin, note = conf_module._resolve_calculix()
    check(origin != "FreeCAD preference" and os.path.isfile(path),
          "eine unbrauchbare FEM-Einstellung faellt auf den mitgelieferten Solver zurueck (%s)"
          % path)
    check("gibt_es_nicht" in note,
          "der Rueckfall wird benannt statt verschwiegen (%r)" % note)
finally:
    conf_module._fem_ccx = _real_fem_ccx
    shutil.rmtree(_ccx_dir, ignore_errors=True)
path, origin, note = conf_module._resolve_calculix()
check(os.path.isfile(path) and not note,
       "nach dem Zuruecksetzen gilt wieder die echte Umgebung (%s, %s)" % (path, origin))


class _SolverStub:
    pass


_solver_stub = _SolverStub()
_solver_stub.PastixMixedPrecision = True
check(conf_module.solver_environment(_solver_stub) == {"PASTIX_MIXED_PRECISION": "1"},
       "PastixMixedPrecision wird als PASTIX_MIXED_PRECISION=1 durchgereicht")
_solver_stub.PastixMixedPrecision = False
check(conf_module.solver_environment(_solver_stub) == {"PASTIX_MIXED_PRECISION": "0"},
       "ohne die Option steht PASTIX_MIXED_PRECISION=0")
check(conf_module.solver_environment(_SolverStub()) == {"PASTIX_MIXED_PRECISION": "0"},
       "ein Solver ohne die Eigenschaft ergibt trotzdem einen Wert")

# the solver type of the FEM solver lands in the .inp as *STATIC, SOLVER=...
_inp_dir = tempfile.mkdtemp(prefix="topoopt_solver_")
_probe = os.path.join(_inp_dir, "probe.inp")
with open(_probe, "w", encoding="utf8") as fh:
    fh.write("*NODE\n1, 0., 0., 0.\n*STATIC, SOLVER=PASTIX\n")
check(elset_reader.solver_keyword(_probe) == "PASTIX",
       "der Solverwunsch der Eingabedatei wird gelesen (PASTIX)")
with open(_probe, "w", encoding="utf8") as fh:
    fh.write("*NODE\n1, 0., 0., 0.\n*STATIC\n")
check(elset_reader.solver_keyword(_probe) == "",
       "ohne SOLVER-Attribut wird kein Solver gemeldet")
check(elset_reader.solver_keyword(os.path.join(_inp_dir, "fehlt.inp")) == "",
       "ohne Eingabedatei wird kein Solver gemeldet")
shutil.rmtree(_inp_dir, ignore_errors=True)

doc5 = App.newDocument("TopoOptConfTest")
analysis5 = doc5.addObject("Fem::FemAnalysis", "Analyse")
obj5 = create_topology_object(doc5, analysis5, "TopoOpt5")
obj5.MassGoalRatio = 0.6
obj5.IterationsLimit = "auto"
obj5.Filters = "[['simple', 'robust']]"
obj5.RobusterRadius = 4.85
domains4 = {"SetA": "design", "SetB": "non_design"}
text = conf_module.conf_text(obj5, os.path.join("C:", os.sep, "tmp", "Mesh.inp"), domains4,
                            os.path.join("C:", os.sep, "tmp"))
check("path = " in text and "tmp" in text, "der Arbeitsordner steht in der Konfiguration")
check("file_name = 'Mesh.inp'" in text, "die Eingabedatei steht in der Konfiguration")
check("mass_goal_ratio = 0.6" in text, "die Zielmasse steht in der Konfiguration")
check("FI_violated_tolerance = 1" in text, "die FI-Toleranz steht in der Konfiguration")
obj5.FIViolatedTolerance = 5
text_fi = conf_module.conf_text(obj5, os.path.join("C:", os.sep, "tmp", "Mesh.inp"), domains4,
                               os.path.join("C:", os.sep, "tmp"))
obj5.FIViolatedTolerance = 1
check("FI_violated_tolerance = 5" in text_fi and "FI_violated_tolerance = 1" not in text_fi,
       "ein geaenderter Wert der FI-Toleranz wird geschrieben (5)")
check("{'SetA': True, 'SetB': False}" in text,
       "Design- und Nicht-Design-Raum stehen in der Konfiguration")
check("['simple', 4.85]" in text,
       "der robuste Radius wird als Zahl geschrieben (kein 'robust' fuer beso)")
check("_mpl.use('Agg')" in text, "ohne Fenster am Ende (beso_main ruft plt.show)")

# "ignore" means: the set does not appear in the optimization - no design
# space, no non-design space, and it needs no permissible stress either
domains_ignore = {"SetA": "design", "SetB": "non_design", "SetC": "ignore"}
text_ignore = conf_module.conf_text(obj5, os.path.join("C:", os.sep, "tmp", "Mesh.inp"),
                                   domains_ignore, os.path.join("C:", os.sep, "tmp"))
optimized_line = [z for z in text_ignore.splitlines() if z.startswith("domain_optimized")][0]
check("SetC" not in optimized_line and "SetA" in optimized_line,
       "domain_optimized enthaelt kein ignoriertes Set (%s)" % optimized_line)
check("SetC" not in text_ignore,
       "ein ignoriertes Set kommt in der Konfiguration nicht vor")
check("beso_conf_vorlage.py" in text, "die Vorlage von beso wird als Grundlage gelesen")

folder4 = _tempfile.mkdtemp(prefix="topoopt_conf_")
target4, conf4 = conf_module.write_files(obj5, os.path.join(folder4, "Mesh.inp"),
                                      domains4, folder4)
check(os.path.isfile(conf4), "beso_conf.py wird geschrieben")
check(os.path.isfile(os.path.join(target4, "beso_main.py")), "beso_main.py liegt im Unterordner")
check(os.path.isfile(os.path.join(target4, "beso_conf_vorlage.py")),
       "die beso-Vorlage liegt unveraendert daneben")

# --- the run is started unbuffered ------------------------------------------
# Without -u/PYTHONUNBUFFERED the child buffers in blocks: the log file stays empty
# until the run ends, and the details field in the panel shows nothing while the run
# is going on (measured: 0 bytes until the process ends).
_real_popen = conf_module.subprocess.Popen
_calls = []


class _FakeProcess(object):
    returncode = None


def _fake_popen(args, **kwargs):
    _calls.append((args, kwargs))
    return _FakeProcess()


_conf_test_folder = _tempfile.mkdtemp(prefix="topoopt_start_")
_inp5 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "beispiel.inp")
conf_module.subprocess.Popen = _fake_popen
try:
    process5, log5, conf5 = conf_module.start(obj5, _inp5, domains4, _conf_test_folder)
finally:
    conf_module.subprocess.Popen = _real_popen
if _calls:
    _args, _kwargs = _calls[0]
    check("-u" in _args, "der Lauf startet ungepuffert (-u): %s" % _args)
    check(_kwargs.get("env", {}).get("PYTHONUNBUFFERED") == "1",
           "PYTHONUNBUFFERED steht in der Umgebung des Laufs")
    check(_kwargs.get("env", {}).get("PYTHONUTF8") == "1",
           "PYTHONUTF8 steht in der Umgebung des Laufs")
else:
    check(False, "der Lauf wird gestartet (Popen wurde aufgerufen)")

# --- permissible stress -> failure index ------------------------------------
limits = dom.parse_stress(["SetA|235.0", "SetB|", "SetC|kaputt", "SetD|0"])
check(limits == {"SetA": 235.0},
       "nur gueltige, positive Spannungen werden gelesen (%s)" % limits)
check(dom.format_stress({"SetA": 235.0}) == ["SetA|235.0"],
       "die Spannungen werden als Liste gespeichert (%s)" % dom.format_stress({"SetA": 235.0}))

check("stress_limits = {}" in text,
       "ohne Spannung schreibt die Konfiguration keine Failure-Index-Werte")

obj5.StressLimits = ["SetA|235.0"]
text2 = conf_module.conf_text(obj5, os.path.join("C:", os.sep, "tmp", "Mesh.inp"), domains4,
                             os.path.join("C:", os.sep, "tmp"))
check("stress_limits = {'SetA': 235.0}" in text2,
       "die zulaessige Spannung steht in der Konfiguration")
check("domain_FI[_name] = [[('stress_von_Mises', _sigma * 1e6)]" in text2,
       "daraus wird besos domain_FI (Stress in Pa plus zulaessiger Wert)")

# the hard proof: the written configuration executes and sets domain_FI
obj5.StressLimits = ["SetA|235.0", "SetB|100.0"]
target5, conf5 = conf_module.write_files(obj5, os.path.join(folder4, "Mesh.inp"),
                                      domains4, folder4)
namespace = {"__file__": conf5}          # the configuration reads the template via __file__
# beso_main defines these names before it reads the configuration (line 25 ff.);
# the configuration builds on them - without them it does not run
for _name in ("domain_optimized", "domain_density", "domain_material", "domain_thickness",
              "domain_offset", "domain_orientation", "domain_FI", "domain_same_state"):
    namespace[_name] = {}
exec(open(conf5, encoding="utf8").read(), namespace)
fi = namespace.get("domain_FI", {})
check(fi.get("SetA") == [[("stress_von_Mises", 235.0e6)], [("stress_von_Mises", 235.0)]],
       "die Konfiguration setzt domain_FI fuer SetA (%s)" % (fi.get("SetA"),))
check(fi.get("SetB") == [[("stress_von_Mises", 100.0e6)], [("stress_von_Mises", 100.0)]],
       "die Konfiguration setzt domain_FI fuer SetB (%s)" % (fi.get("SetB"),))
check("SetC" not in fi, "ohne Spannung bleibt die Domain ohne Failure Index")
check(os.path.isfile(os.path.join(target4, "beso_lib.py")), "beso_lib.py liegt im Unterordner")
check(conf_module.log_path(os.path.join(folder4, "Mesh.inp")).endswith("Mesh_topoopt.log"),
       "die Logdatei liegt neben der Eingabedatei")
_shutil.rmtree(folder4, ignore_errors=True)

# --- step 3: read the protocol of a run -------------------------------------
from freecad.TopoOpt.core import lauf as run_module  # noqa: E402

# A ccx without PaStiX/PARDISO answers an .inp that asks for it with this line; the
# assistant then names the library instead of leaving the user with a dead run (D46).
check(run_module.missing_library(
        " *ERROR in linstatic: the PASTIX library is not linked\n") == "PASTIX",
      "eine fehlende PASTIX-Bibliothek wird im Log erkannt")
check(run_module.missing_library(
        "*ERROR in linstatic: the PARDISO library is not linked\n") == "PARDISO",
      "eine fehlende PARDISO-Bibliothek wird im Log erkannt")
check(run_module.missing_library("Job finished\n\n") == "",
      "ein normales Log meldet keine fehlende Bibliothek")
check(run_module.missing_library(None) == "",
      "ohne Logtext wird nichts gemeldet")

# --- step 3: read beso's iteration table ------------------------------------
beso_example = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                             "beso_beispiel.log")
# The recording of a run is a test input and lives in the repository.  If it is missing
# that is reported - but the run does not stop: a missing file must not swallow the
# checks after it (the VTK and state readers).
check(os.path.isfile(beso_example), "die Testdatei tests/data/beso_beispiel.log ist da")
table = run_module.read_table(beso_example)
check(len(table) == 6, "die Iterationstabelle wird gelesen (6 Zeilen, 2 Laeufe)")
if len(table) == 6:
    check(table[0][0] == 0 and abs(table[0][1]["mass"] - 20000.0) < 1e-6,
           "die Startmasse wird gelesen: %s" % table[0][1]["mass"])
    check(abs(table[2][1]["mass"] - 19110.748316642857) < 1e-6,
           "die Masse der dritten Iteration wird gelesen")
    check(table[3][1].get("fi_violated") == 0 and abs(table[5][1]["fi_max"] - 1.1) < 1e-6,
           "die FI-Spalten werden gelesen (ueberlastet=%s, FI_max=%s)"
           % (table[3][1].get("fi_violated"), table[5][1].get("fi_max")))
    check("fi_mean" not in table[0][1],
           "ohne Failure Index gibt es keine FI-Werte (nur Masse und Energiedichte)")

f = run_module.progress(beso_example, 0.6)
# without a table, iteration/mass/target are None - the checks have to report that,
# not abort with a TypeError (otherwise the errors after them are never seen)
check(f["iteration"] == 2 and f["mass"] is not None
       and abs(f["mass"] - 19110.748316642857) < 1e-6,
       "der Fortschritt kennt Iteration und Masse (%s, %s)" % (f["iteration"], f["mass"]))
check(f["target"] is not None and abs(f["target"] - 20000.0 * 0.6) < 1e-6,
       "die Zielmasse ist der Anteil der Startmasse: %s" % f["target"])
check(abs(run_module.ratio(f["start"], f["mass"], 0.6) - 11.12) < 0.1,
       "der Fortschritt in Prozent: %.1f %%" % run_module.ratio(f["start"], f["mass"], 0.6))
check(run_module.ratio(20000.0, 8000.0, 0.6) == 100.0,
       "bei der Zielmasse steht der Balken auf 100 %")

example_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                            "lauf_beispiel.log")
run_data = run_module.read_history(example_log, 0.6)
print("Lauf-Protokoll: start=%s ziel=%s iteration=%s massen=%s fertig=%s"
      % (run_data["start"], run_data["target"], run_data["iteration"],
         run_data["masses"], run_data["done"]), flush=True)
check(run_data["start"] is not None and abs(run_data["start"] - 20000.0) < 1e-6,
       "die Startmasse wird gelesen (%s)" % run_data["start"])
check(abs((run_data["target"] or 0) - 12000.0) < 1e-6,
       "die Zielmasse ist Anteil x Startmasse (%s)" % run_data["target"])
check(run_data["iteration"] == 2, "die Iterationen werden gezaehlt (%d)"
       % run_data["iteration"])
check(len(run_data["masses"]) == 2 and abs(run_data["masses"][1][1] - 19110.748) < 1e-3,
       "die Massen je Iteration werden gelesen (%s)" % (run_data["masses"],))
check(run_data["done"] is True, "das Ende des Laufs wird erkannt")
check(run_module.read_history("gibt-es-nicht.log")["iteration"] == 0,
       "ohne Logdatei kommt ein leeres Ergebnis")

# --- shell thicknesses from the .inp (*SHELL SECTION) -----------------------
shell_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                      "schale_beispiel.inp")
thicknesses = elset_reader.read_shell_thicknesses(shell_file)
check(thicknesses == {"MaterialSolidElementGeometry2D": 10.0,
                  "MaterialSolidElementGeometry2D001": 2.5},
       "die Schalendicken werden je Element-Set gelesen (%s)" % (thicknesses,))
# a solid model has no SHELL SECTION card
check(elset_reader.read_shell_thicknesses(os.path.join(
           os.path.dirname(os.path.abspath(__file__)), "data", "beispiel.inp")) == {},
       "ohne SHELL SECTION bleibt die Dicke leer")

# the configuration takes over exactly the thicknesses of the existing domains
text_shell = conf_module.conf_text(obj5, shell_file,
                                   {"MaterialSolidElementGeometry2D": "design",
                                    "MaterialSolidElementGeometry2D001": "non_design"},
                                   os.path.join("C:", os.sep, "tmp"))
check("thickness = {'MaterialSolidElementGeometry2D': 10.0, "
       "'MaterialSolidElementGeometry2D001': 2.5}" in text_shell,
       "beide Dicken stehen in der Konfiguration")
check("domain_thickness[_name] = [_d, _d]" in text_shell,
       "daraus wird besos domain_thickness je Domain")
text_only_one = conf_module.conf_text(obj5, shell_file,
                                     {"MaterialSolidElementGeometry2D": "design"},
                                     os.path.join("C:", os.sep, "tmp"))
check("thickness = {'MaterialSolidElementGeometry2D': 10.0}" in text_only_one,
       "nur die Dicke der vorhandenen Domain wird uebernommen")
check("thickness = {}" in text,
       "ein Volumenmodell bekommt keine Schalendicke in die Konfiguration")

# --- permissible stress from the material -----------------------------------
from freecad.TopoOpt.core import material as material_module  # noqa: E402

check(material_module.MPa("315 MPa") == 315.0,
       "eine Materialangabe in MPa wird gelesen (%s)" % material_module.MPa("315 MPa"))
check(abs(material_module.MPa("2.1e+08 kg/(mm*s^2)") - 210000.0) < 1e-6,
       "FreeCADs Einheit kg/(mm*s^2) wird umgerechnet (%s)" % material_module.MPa("2.1e+08 kg/(mm*s^2)"))
check(material_module.MPa("45 GPa") == 45000.0 and material_module.MPa("1000 psi") > 6.8,
       "GPa und psi werden umgerechnet")
check(material_module.MPa("") is None and material_module.MPa("zach MPa") is None
       and material_module.MPa("5 fuss") is None,
       "unbrauchbare Angaben liefern keinen Vorschlag")

# Values as in FreeCAD's material cards: Aluminum-6061-T6 has 'YieldStrength: 276 MPa',
# CalculiX-Steel has no yield strength (only YoungsModulus)
yield_values = material_module.yield_strength(
    [("MaterialSolidSolid", {"Name": "Alu", "YieldStrength": "276 MPa",
                             "UltimateTensileStrength": "310 MPa"})],
    ["MaterialSolidSolid"])
check(yield_values == {"MaterialSolidSolid": 276.0},
       "die Streckgrenze der Karte wird zum Vorschlag (%s)" % (yield_values,))
without = material_module.yield_strength(
    [("MaterialSolidSolid", {"Name": "CalculiX-Steel", "YoungsModulus": "2.1e+08 kg/(mm*s^2)"})],
    ["MaterialSolidSolid"])
check(without == {}, "ohne Streckgrenze in der Karte kommt kein Vorschlag (%s)" % (without,))
several = material_module.yield_strength(
    [("MaterialSolid", {"YieldStrength": "276 MPa"}),
     ("AnderesMaterial", {"YieldStrength": "100 MPa"})],
    ["MaterialSolidSolid", "AnderesMaterialSolid"])
check(several == {"MaterialSolidSolid": 276.0, "AnderesMaterialSolid": 100.0},
       "bei mehreren Materialien wird ueber den Namen zugeordnet (%s)" % (several,))
only_one = material_module.yield_strength([("Irgendwas", {"YieldStrength": "235 MPa"})],
                                         ["VoelligAnderes"])
check(only_one == {"VoelligAnderes": 235.0},
       "bei genau einem Material gilt es fuer alle Sets (%s)" % (only_one,))

# The assignment from the input file takes precedence: it says which material
# CalculiX really uses.  The name of the set only looks like a material.
section_inp = os.path.join(tempfile.gettempdir(), "topoopt_section_test.inp")
with open(section_inp, "w", encoding="utf8") as fh:
    fh.write("*NODE\n1, 0, 0, 0\n2, 1, 0, 0\n3, 0, 1, 0\n4, 0, 0, 1\n5, 1, 1, 0\n"
             "*ELEMENT, TYPE=C3D10, ELSET=MaterialSolidSolid\n1, 1,2,3,4,5\n"
             "*SOLID SECTION, ELSET=MaterialSolidSolid, MATERIAL=MaterialSolid\n"
             "*SHELL SECTION, ELSET=FlaechenSet, MATERIAL=MaterialSolid001, OFFSET=0\n5\n")
assignment = elset_reader.read_section_materials(section_inp)
check(assignment == {"MaterialSolidSolid": "MaterialSolid", "FlaechenSet": "MaterialSolid001"},
       "die Materialzuordnung kommt aus den Section-Karten (%s)" % (assignment,))
from_inp = material_module.yield_strength(
    [("MaterialSolid", {"YieldStrength": "235 MPa"}),
     ("MaterialSolid001", {"YieldStrength": "276 MPa"})],
    ["MaterialSolidSolid"], {"MaterialSolidSolid": "MaterialSolid001"})
check(from_inp == {"MaterialSolidSolid": 276.0},
       "die Zuordnung aus der .inp schlaegt den Namensanfang (%s)" % (from_inp,))
without_inp = material_module.yield_strength(
    [("MaterialSolid", {"YieldStrength": "235 MPa"}),
     ("MaterialSolid001", {"YieldStrength": "276 MPa"})],
    ["MaterialSolidSolid"])
check(without_inp == {"MaterialSolidSolid": 235.0},
       "ohne Zuordnung in der .inp greift der Namensanfang (%s)" % (without_inp,))

# A truncated input file and a set without a material assignment have to stand out
broken = os.path.join(tempfile.gettempdir(), "topoopt_kaputt.inp")
with open(broken, "w", encoding="utf8") as fh:
    fh.write("*NODE\n1, 0, 0, 0\n2, 1, 0, 0\n"
             "*ELEMENT, TYPE=C3D10, ELSET=Set1\n1, 1,2\n"
             "*MATERIAL, NAME=M1\n*ELASTIC\n210000, 0.3\n")
report = elset_reader.check_inp(broken, ["Set1"])
check(report["missing_cards"] == ["*STEP"],
       "eine abgebrochene .inp wird erkannt (es fehlt %s)" % report["missing_cards"])
check(report["without_material"] == ["Set1"],
       "dazu faellt das Set ohne Section-Karte auf (%s)" % report["without_material"])

complete_file = os.path.join(tempfile.gettempdir(), "topoopt_ganz.inp")
with open(complete_file, "w", encoding="utf8") as fh:
    fh.write("*NODE\n1, 0, 0, 0\n2, 1, 0, 0\n3, 0, 1, 0\n4, 0, 0, 1\n5, 1, 1, 0\n"
             "*ELEMENT, TYPE=C3D10, ELSET=Set1\n1, 1,2,3,4,5\n"
             "*ELSET, ELSET=Set2\n1\n"
             "*MATERIAL, NAME=M1\n*ELASTIC\n210000, 0.3\n"
             "*SOLID SECTION, ELSET=Set1, MATERIAL=M1\n"
             "*STEP\n*STATIC\n*BOUNDARY\n1, 1, 3, 0.0\n*END STEP\n")
report2 = elset_reader.check_inp(complete_file, ["Set1", "Set2"])
check(report2["missing_cards"] == [], "eine vollstaendige .inp meldet keine fehlende Karte")
check(report2["without_material"] == ["Set2"],
       "nur das Set ohne Section-Karte wird genannt (%s)" % report2["without_material"])

# A material without a Young's modulus makes FreeCAD abort while writing the .inp
missing = material_module.missing_values(
    [("Vollstaendig", {"YoungsModulus": "210000 MPa", "PoissonRatio": "0.3"}),
     ("Leer", {"Density": "7.9e-06 kg/mm^3"}),
     ("OhneNu", {"YoungsModulus": "210000 MPa"})])
check(missing == {"Leer": ["YoungsModulus", "PoissonRatio"], "OhneNu": ["PoissonRatio"]},
       "fehlende Werkstoffwerte werden je Material gemeldet (%s)" % missing)
check(material_module.missing_values([("A", {"YoungsModulus": "x", "PoissonRatio": "y"})]) == {},
       "ein vollstaendiges Material wird nicht gemeldet")

# --- read VTK iterations (resulting_states.vtk) -------------------------------
from freecad.TopoOpt.core import vtk as vtk_module  # noqa: E402

vtk_example = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                            "states_beispiel.vtk")
vtk_data = vtk_module.load(vtk_example)
check(len(vtk_data["points"]) == 170, "die Knoten werden gelesen (%d)"
       % len(vtk_data["points"]))
check(len(vtk_data["cells"]) == 401, "die Zellen werden gelesen (%d)"
       % len(vtk_data["cells"]))
check(vtk_data["cells"][0][0] < len(vtk_data["points"]),
       "die Knotennummern sind 0-basiert (erste Nummer %d)" % vtk_data["cells"][0][0])
check(len(vtk_data["states"]) == 2 and vtk_data["names"][0] == "element_states001",
       "beide Iterationen werden gelesen (%s)" % (vtk_data["names"],))

# The node numbers are 0-based: cells shifted by -1 give corners that lie far
# apart.  The test checks that the cells really hang together (small edge
# lengths) instead of relying on the order.
def _largest_edge(points, cells, state):
    largest = 0.0
    for i, cell in enumerate(cells[:300]):
        if not state[i]:
            continue
        corners = [points[cell[j]] for j in range(4)]
        for a in range(4):
            for b in range(a + 1, 4):
                largest = max(largest, (corners[a] - corners[b]).Length)
    return largest

correct = _largest_edge(vtk_data["points"], vtk_data["cells"], vtk_data["states"][0])
shifted = _largest_edge(vtk_data["points"],
                             [[k - 1 for k in cell] for cell in vtk_data["cells"]],
                             vtk_data["states"][0])
# The example mesh is coarse (beam 100 x 20 x 10 mm, 401 elements): the largest
# element edge is around 13 mm, with shifted numbers above 100 mm.
check(correct < 20, "mit 0-basierten Nummern bleibt die groesste Kante zur Elementgroesse "
       "passend (%.2f mm)" % correct)
check(shifted > 5 * correct,
       "mit -1 verschobenen Nummern wird das Netz zerfetzt (%.2f mm gegen %.2f mm, Faktor %.1f)"
       % (shifted, correct, shifted / correct))

summary = vtk_module.summary(vtk_data, 1)
check(summary["number"] == 1 and summary["count"] == 2 and summary["total"] == 401,
       "die Zusammenfassung kennt Iteration, Anzahl und Zellen (%s)" % (summary,))
check(0 <= summary["percent"] <= 100, "der Materialanteil liegt zwischen 0 und 100 %% (%.1f)"
       % summary["percent"])

faces = vtk_module.boundary_faces(vtk_data["cells"], vtk_data["states"][-1],
                                    vtk_data["points"])
check(len(faces) > 100, "die Oberflaeche hat Flaechen (%d)" % len(faces))
volume = vtk_module.volume(vtk_data["points"], faces)
check(volume > 0, "die Flaechen zeigen nach aussen (Volumen %.1f positiv)" % volume)
flipped = vtk_module.volume(vtk_data["points"], [f[::-1] for f in faces])
check(flipped < 0, "umgedrehte Flaechen ergeben negatives Volumen (%.1f)" % flipped)
edges = vtk_module.edge_check(faces)
check(edges.get(2, 0) > 0.9 * sum(edges.values()),
       "die Kantenprobe zeigt eine geschlossene Oberflaeche (%s)" % (edges,))
check(vtk_module.cell_volume(vtk_data["points"], vtk_data["cells"],
                             vtk_data["states"][-1]) > 0,
       "das Zellvolumen des Materials ist positiv")

print()
if errors:
    print("%d Pruefung(en) fehlgeschlagen" % len(errors))
    finish(1)
print("Alle Pruefungen bestanden", flush=True)
finish(0)
