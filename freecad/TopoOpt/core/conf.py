# SPDX-License-Identifier: LGPL-3.0-or-later
"""Write the beso configuration and start the optimization.

beso reads its configuration from the folder of ``beso_main.py``
(``exec(open(os.path.join(beso_dir, "beso_conf.py")).read())``) - that is why the
beso files are copied into a small sub folder of the working directory for a run:

    <working directory>/
        FEMMeshGmsh.inp              the input file (stays where it is)
        topoopt_beso/
            beso_main.py ...         copies of the files that ship with the addon
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
from . import domains as dom
from . import elsets as elset_reader

SUBFOLDER = "topoopt_beso"
TEMPLATE = "beso_conf_vorlage.py"


def _limit(value):
    """beso expects "auto" or a number."""
    text = str(value).strip()
    if text.lower() in ("auto", ""):
        return "auto"
    try:
        return int(float(text))
    except ValueError:
        return "auto"


def _robust_value(obj):
    """The computed robust radius; without a check beso's own "auto"."""
    radius = float(getattr(obj, "RobusterRadius", 0.0))
    return radius if radius > 0 else "auto"


def _filter_list(obj):
    """The filters from the object, "robust" replaced by the computed radius."""
    from . import params as params_modul
    entries = []
    for entry in params_modul.parse_filters(getattr(obj, "Filters", "")):
        if entry[1] == "robust":
            entry = [entry[0], _robust_value(obj)] + list(entry[2:])
        entries.append(entry)
    return entries


def conf_text(obj, inp_path, domains, working_dir):
    """The content of beso_conf.py for this run."""
    from . import params as params_modul
    # "ignore" does not appear here at all - such sets play no role for the
    # optimization (neither design nor non-design space)
    domains = dom.active(domains)
    design = [name for name, role in domains.items() if role == dom.DESIGN]
    mass_add, mass_remove = params_modul.mass_ratios(getattr(obj, "MassChange", "normal"))
    stress = {name: value for name, value in
              dom.parse_stress(getattr(obj, "StressLimits", [])).items() if name in domains}
    # shell thicknesses are in the .inp (*SHELL SECTION per element set) - without
    # them beso computes with its example value 1.0 mm and the mass would be wrong
    # by the factor of the thickness (measured: 10 mm shell -> mass 2000 instead of 20000).
    thicknesses = {name: d for name, d in
                   elset_reader.read_shell_thicknesses(inp_path).items() if name in domains}
    return "\n".join([
        "# written by TopoOpt: beso's own template first, then the values of the assistant",
        "import os as _os",
        "exec(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), %r),"
        " encoding='utf8').read())" % TEMPLATE,
        "",
        "# --- working directory and input file ---",
        "path = %r" % working_dir,
        "file_name = %r" % os.path.basename(inp_path),
        "path_calculix = %r" % calculix_path(),
        "cpu_cores = %d" % int(getattr(obj, "CpuCores", 0)),
        "",
        "# --- what the assistant sets (step 2) ---",
        "mass_goal_ratio = %r" % float(getattr(obj, "MassGoalRatio", 0.6)),
        "filter_list = %r" % (_filter_list(obj),),
        "optimization_base = %r" % str(getattr(obj, "OptimizationBase", "stiffness")),
        "mass_addition_ratio = %r" % mass_add,
        "mass_removal_ratio = %r" % mass_remove,
        "ratio_type = 'relative'",
        "iterations_limit = %r" % _limit(getattr(obj, "IterationsLimit", "auto")),
        "tolerance = %r" % float(getattr(obj, "Tolerance", 1e-3)),
        "FI_violated_tolerance = %d" % int(getattr(obj, "FIViolatedTolerance", 1)),
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
        "# Schalendicken aus der Eingabedatei (*SHELL SECTION) - je Element-Set eigener Wert",
        "thickness = %r" % (dict(thicknesses),),
        "for _name, _d in thickness.items():",
        "    domain_thickness[_name] = [_d, _d]",
        "",
        "# Eine angegebene zulaessige Spannung (MPa) je Domain schaltet den Failure",
        "# Index ein - unabhaengig vom Optimierungsziel. Format wie in besos Beispiel:",
        "# innere Tupel = getrennte FIs, zweite Liste = zweiter Elementzustand.",
        "stress_limits = %r" % (dict(stress),),
        "for _name, _sigma in stress_limits.items():",
        "    domain_FI[_name] = [[('stress_von_Mises', _sigma * 1e6)],",
        "                        [('stress_von_Mises', _sigma)]]",
        "",
        "# beso_main calls plt.show() at the end - without a window the run ends by itself",
        "import matplotlib as _mpl",
        "_mpl.use('Agg')",
        "",
    ])


def calculix_path():
    """The CalculiX solver (ccx): the one set in FreeCAD's FEM preferences,
    else the one FreeCAD ships, else the first on the system search path."""
    candidates = []
    try:
        # FEM's own lookup (Preferences > FEM > CalculiX > binary path); it
        # returns the plain name "ccx" when no path is set
        from femsolver import settings as fem_settings
        fem_ccx = fem_settings.get_binary("Calculix", silent=True)
        if fem_ccx and os.path.isabs(fem_ccx):
            candidates.append(fem_ccx)
    except ImportError:
        pass    # FEM workbench not available
    if sys.executable:
        # ccx sits next to the FreeCAD program - in the Flatpak that is /app/bin
        for name in ("ccx", "ccx.exe"):
            candidates.append(os.path.join(os.path.dirname(sys.executable), name))
    try:
        import FreeCAD
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(FreeCAD.__file__)),
                                       "..", "bin", "ccx"))
    except Exception:
        # FreeCAD is compiled in (Flatpak) and then has no __file__
        pass
    for name in ("ccx", "ccx.exe"):
        candidates.append(os.path.join(sys.prefix, "bin", name))
    for path in candidates:
        path = os.path.abspath(path)
        if os.path.isfile(path):
            return path
    return shutil.which("ccx") or "ccx"     # the system search path last


def python_path():
    """A Python with numpy and matplotlib - the one of FreeCAD.

    Returns None when none is found.  The run is then refused instead of starting
    the wrong process: in FreeCAD's Flatpak ``sys.executable`` is FreeCADCmd,
    and the ``-u`` passed to beso_main.py would be FreeCAD's own option there
    (user parameter file) - the file would be overwritten and the run fail.
    """
    candidates = []
    if sys.executable:
        candidates.append(sys.executable)
        for name in ("python3", "python", "python.exe"):
            candidates.append(os.path.join(os.path.dirname(sys.executable), name))
    for name in ("python3", "python", "python.exe"):
        candidates.append(os.path.join(sys.prefix, "bin", name))
    for path in candidates:
        if path and os.path.isfile(path) and "python" in os.path.basename(path).lower():
            return path
    return shutil.which("python3") or shutil.which("python")


def write_files(obj, inp_path, domains, working_dir):
    """Put beso into the working directory and write the configuration.

    Returns (folder of the beso copy, path of beso_conf.py).
    """
    target = os.path.join(working_dir, SUBFOLDER)
    os.makedirs(target, exist_ok=True)
    for name in beso_modul.FILES:
        if name == "beso_conf.py":
            # beso's template stays untouched under its own name
            shutil.copyfile(os.path.join(beso_modul.FOLDER, name), os.path.join(target, TEMPLATE))
        else:
            shutil.copyfile(os.path.join(beso_modul.FOLDER, name), os.path.join(target, name))
    conf = os.path.join(target, "beso_conf.py")
    with open(conf, "w", encoding="utf8") as fh:
        fh.write(conf_text(obj, inp_path, domains, working_dir))
    return target, conf


def log_path(inp_path):
    """Our protocol (CalculiX output) sits next to the input file."""
    return "%s_topoopt.log" % os.path.splitext(inp_path)[0]


def beso_log_path(inp_path):
    """beso writes its own file next to the input file (file_name + .log).

    It holds the iteration table from which the history charts are read.
    """
    return "%s.log" % os.path.splitext(inp_path)[0]


def _log_aside(inp_path):
    """Copy the previous beso log file aside - otherwise beso appends to it."""
    log = beso_log_path(inp_path)
    if not os.path.isfile(log):
        return
    old = "%s_vorher.log" % os.path.splitext(inp_path)[0]
    try:
        os.replace(log, old)
    except OSError:
        pass


def start(obj, inp_path, domains, working_dir):
    """Write the configuration and start beso as its own process.

    Returns (process, path of our log file, path of beso_conf.py).
    """
    # check first: without Python there is no run, and nothing should be written
    # either.  The message reaches the dialog through the caller.
    interpreter = python_path()
    if not interpreter:
        raise RuntimeError("No Python interpreter with numpy and matplotlib was found - "
                           "TopoOpt needs the Python that ships with FreeCAD.")
    target, conf = write_files(obj, inp_path, domains, working_dir)
    _log_aside(inp_path)
    log = log_path(inp_path)
    with open(log, "w", encoding="utf8") as fh:
        fh.write("TopoOpt run started: %s\n" % time.strftime("%d.%m.%Y %H:%M:%S"))
        fh.write("Input file : %s\n" % inp_path)
        fh.write("Config     : %s\n" % conf)
        fh.write("beso log   : %s\n\n" % beso_log_path(inp_path))
    # CREATE_NO_WINDOW: otherwise a console window flashes up on Windows
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    # -u / PYTHONUNBUFFERED: without it the child buffers its output in blocks and
    # the log file stays empty until the buffer is full or the run ends - the
    # details field would then only have something to read after the job (measured:
    # 0 bytes during the run, everything only at the end)
    environment = dict(os.environ)
    environment["PYTHONUNBUFFERED"] = "1"
    environment.setdefault("PYTHONUTF8", "1")
    process = subprocess.Popen([interpreter, "-u", os.path.join(target, "beso_main.py")],
                               cwd=working_dir, creationflags=flags, env=environment,
                               stdout=open(log, "a", encoding="utf8"),
                               stderr=subprocess.STDOUT)
    return process, log, conf
