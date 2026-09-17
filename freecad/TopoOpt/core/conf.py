# SPDX-License-Identifier: LGPL-3.0-or-later
"""Write the beso configuration and start the optimization.

beso reads its configuration from the folder of ``beso_main.py``
(``exec(open(os.path.join(beso_dir, "beso_conf.py")).read())``) - that is why the
beso files are copied into a small sub folder of the working directory for a run:

    <working directory>/
        FEMMeshGmsh.inp              the input file (stays where it is)
        topoopt_beso/
            beso_main.py ...         kopies of the files that ship with the addon
            beso_conf_vorlage.py     beso's own template, untouched
            beso_conf.py             written by this addon

The configuration reads beso's template first and sets the values of the assistant
afterwards, so every option we do not touch keeps beso's own default.  Nothing in
the addon folder is written to, and several runs can exist next to each other.

beso runs as its own process: FreeCAD stays responsive, the output lands in a log
file next to the input file and the dialog can read it while the run goes on.
"""

import os
import shutil
import subprocess
import sys
import time

from . import beso as beso_modul

UNTERORDNER = "topoopt_beso"
VORLAGE = "beso_conf_vorlage.py"


def _limit(wert):
    """beso erwartet "auto" oder eine Zahl."""
    text = str(wert).strip()
    if text.lower() in ("auto", ""):
        return "auto"
    try:
        return int(float(text))
    except ValueError:
        return "auto"


def _robuster_wert(obj):
    """Der berechnete robuste Radius; ohne Prüfung beso's eigenes "auto"."""
    radius = float(getattr(obj, "RobusterRadius", 0.0))
    return radius if radius > 0 else "auto"


def _filter_liste(obj):
    """Die Filter aus dem Objekt, "robust" durch den berechneten Radius ersetzt."""
    from . import params as params_modul
    liste = []
    for eintrag in params_modul.parse_filters(getattr(obj, "Filters", "")):
        if eintrag[1] == "robust":
            eintrag = [eintrag[0], _robuster_wert(obj)] + list(eintrag[2:])
        liste.append(eintrag)
    return liste


def conf_text(obj, inp_pfad, domains, arbeit_ordner):
    """Der Inhalt von beso_conf.py für diesen Lauf."""
    from . import params as params_modul
    design = [name for name, rolle in domains.items() if rolle == "design"]
    mass_add, mass_remove = params_modul.mass_ratios(getattr(obj, "MassChange", "normal"))
    return "\n".join([
        "# written by TopoOpt: beso's own template first, then the values of the assistant",
        "import os as _os",
        "exec(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), %r),"
        " encoding='utf8').read())" % VORLAGE,
        "",
        "# --- working directory and input file ---",
        "path = %r" % arbeit_ordner,
        "file_name = %r" % os.path.basename(inp_pfad),
        "path_calculix = %r" % calculix_pfad(),
        "cpu_cores = %d" % int(getattr(obj, "CpuCores", 0)),
        "",
        "# --- what the assistant sets (step 2) ---",
        "mass_goal_ratio = %r" % float(getattr(obj, "MassGoalRatio", 0.6)),
        "filter_list = %r" % (_filter_liste(obj),),
        "optimization_base = %r" % str(getattr(obj, "OptimizationBase", "stiffness")),
        "mass_addition_ratio = %r" % mass_add,
        "mass_removal_ratio = %r" % mass_remove,
        "ratio_type = 'relative'",
        "iterations_limit = %r" % _limit(getattr(obj, "IterationsLimit", "auto")),
        "tolerance = %r" % float(getattr(obj, "Tolerance", 1e-3)),
        "save_iteration_results = %d" % int(getattr(obj, "SaveIterations", 10)),
        "save_resulting_format = %r" % str(getattr(obj, "ResultFormat", "inp vtk")),
        "",
        "# --- the domains of the model ---",
        "elset_name = %r" % (design[0] if design else sorted(domains)[0]),
        "domain_optimized = %r" % ({name: (name in design) for name in domains},),
        "# beso's template brings example values for a domain called 'all_available':",
        "# density, material and thickness are taken over for our domains (beso expects",
        "# them per domain), the example data for failure indices and the like is dropped",
        "for _name in list(domain_optimized):",
        "    for _d in (domain_density, domain_material, domain_thickness):",
        "        if _name not in _d and 'all_available' in _d:",
        "            _d[_name] = _d['all_available']",
        "for _d in (domain_offset, domain_orientation, domain_FI, domain_same_state):",
        "    _d.clear()",
        "",
        "# beso_main calls plt.show() at the end - without a window the run ends by itself",
        "import matplotlib as _mpl",
        "_mpl.use('Agg')",
        "",
    ])


def calculix_pfad():
    """Der CalculiX-Solver, der mit FreeCAD kommt."""
    kandidaten = []
    try:
        import FreeCAD
        kandidaten.append(os.path.join(os.path.dirname(os.path.abspath(FreeCAD.__file__)),
                                       "..", "bin", "ccx"))
    except Exception:
        pass
    for name in ("ccx.exe", "ccx"):
        kandidaten.append(os.path.join(sys.prefix, "bin", name))
    for pfad in kandidaten:
        pfad = os.path.abspath(pfad)
        if os.path.isfile(pfad):
            return pfad
    return "ccx"          # dann muss er im Suchpfad des Systems liegen


def python_pfad():
    """Ein Python mit numpy und matplotlib - das von FreeCAD."""
    kandidaten = []
    if sys.executable:
        kandidaten.append(sys.executable)
        for name in ("python.exe", "python"):
            kandidaten.append(os.path.join(os.path.dirname(sys.executable), name))
    for pfad in kandidaten:
        if pfad and os.path.isfile(pfad) and "python" in os.path.basename(pfad).lower():
            return pfad
    return sys.executable


def schreibe_dateien(obj, inp_pfad, domains, arbeit_ordner):
    """beso in den Arbeitsordner legen und die Konfiguration schreiben.

    Returns (folder of the beso copy, path of beso_conf.py).
    """
    ziel = os.path.join(arbeit_ordner, UNTERORDNER)
    os.makedirs(ziel, exist_ok=True)
    for name in beso_modul.DATEIEN:
        if name == "beso_conf.py":
            # beso's template stays untouched under its own name
            shutil.copyfile(os.path.join(beso_modul.ORDNER, name), os.path.join(ziel, VORLAGE))
        else:
            shutil.copyfile(os.path.join(beso_modul.ORDNER, name), os.path.join(ziel, name))
    conf = os.path.join(ziel, "beso_conf.py")
    with open(conf, "w", encoding="utf8") as fh:
        fh.write(conf_text(obj, inp_pfad, domains, arbeit_ordner))
    return ziel, conf


def log_pfad(inp_pfad):
    """Die Logdatei des Laufs liegt neben der Eingabedatei."""
    return "%s_topoopt.log" % os.path.splitext(inp_pfad)[0]


def starte(obj, inp_pfad, domains, arbeit_ordner):
    """Konfiguration schreiben und beso als eigenen Prozess starten.

    Returns (process, path of the log file, path of beso_conf.py).
    """
    ziel, conf = schreibe_dateien(obj, inp_pfad, domains, arbeit_ordner)
    log = log_pfad(inp_pfad)
    with open(log, "w", encoding="utf8") as fh:
        fh.write("TopoOpt run started: %s\n" % time.strftime("%d.%m.%Y %H:%M:%S"))
        fh.write("Input file : %s\n" % inp_pfad)
        fh.write("Config     : %s\n\n" % conf)
    prozess = subprocess.Popen([python_pfad(), os.path.join(ziel, "beso_main.py")],
                               cwd=arbeit_ordner,
                               stdout=open(log, "a", encoding="utf8"),
                               stderr=subprocess.STDOUT)
    return prozess, log, conf
