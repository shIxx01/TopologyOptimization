# SPDX-License-Identifier: LGPL-3.0-or-later
"""Finding the FEM parts of a document and preparing the CalculiX input file."""

import glob
import os
import re
import shutil
import tempfile
import time

KEIN_LEERZEICHEN = re.compile(r"\s")


def find_solver(analysis):
    """The solver object inside an analysis (or None)."""
    for member in analysis.Group:
        if "Solver" in member.TypeId:
            return member
    return None


def find_mesh(analysis):
    """The FEM mesh object inside an analysis (or None)."""
    for member in analysis.Group:
        if "FemMesh" in member.TypeId:
            return member
    return None


def find_materials(doc):
    """All material objects of the document, with their thickness objects."""
    materials, thicknesses = [], []
    for obj in doc.Objects:
        if obj.TypeId == "App::MaterialObjectPython" or "Material" in obj.TypeId:
            materials.append(obj)
        elif obj.TypeId == "Fem::ElementGeometry2D":
            thicknesses.append(obj)
    return materials, thicknesses


def run_dir(doc_name, base_name):
    """Fallback working directory - without spaces, inside temp.

    CalculiX cuts the job name at the first space, so a directory with spaces
    would silently produce a 0 byte .dat file.  Normally the FEM working
    directory of the solver is used (see arbeitsordner()).
    """
    root = os.path.join(tempfile.gettempdir(), "TopoOpt")
    sicher = re.sub(r"[^A-Za-z0-9_.-]", "_", "%s_%s" % (doc_name, base_name))
    pfad = os.path.join(root, sicher)
    os.makedirs(pfad, exist_ok=True)
    return pfad


def arbeitsordner(solver, doc_name="TopoOpt", mesh=None, gemerkt=""):
    """The working directory the FEM workbench uses for this solver.

    The optimization object is a child of the FEM analysis, so its files belong
    next to the FEM files: FreeCAD's own function is used, which honours the user
    setting (temporary / beside the document / custom).

    `gemerkt` is the directory stored in the document object from an earlier run.
    It is used when it still exists, because FreeCAD's get_temp_dir() builds a new
    directory on every call (measured: it does not cache) - without this the files
    would end up in a different directory each time the dialog is opened.
    """
    if gemerkt and os.path.isdir(gemerkt):
        return gemerkt

    from femtools import femutils

    pfad = ""
    try:
        pfad = femutils.get_pref_working_dir(solver)
    except Exception:
        # e.g. MustSaveError when the user wants the directory beside an
        # unsaved document
        pfad = ""
    if not pfad:
        try:
            pfad = femutils.get_temp_dir(solver)
        except Exception:
            pfad = ""
    if not pfad:
        pfad = run_dir(doc_name, mesh.Name if mesh else "modell")
    os.makedirs(pfad, exist_ok=True)
    return pfad


def find_inp(solver, mesh, doc_name, gemerkt=""):
    """Look for an input file that already exists. Returns (path, source) or (None, "").

    If the user ran the analysis before (solver panel: "Write .inp file"), the
    file is already there and does not have to be written again:

    1. the FEM working directory of the solver (where FreeCAD writes it),
    2. FreeCAD's other FEM working directories (%TEMP%/fcfem_*), newest first,
    3. a working directory this addon used in an earlier version.
    """
    if mesh is None:
        return None, ""
    dateiname = "%s.inp" % mesh.Name

    ordner = arbeitsordner(solver, doc_name, mesh, gemerkt)
    pfad = os.path.join(ordner, dateiname)
    if os.path.isfile(pfad):
        return pfad, "fem"

    kandidaten = []
    for weiterer in glob.glob(os.path.join(tempfile.gettempdir(), "fcfem_*")):
        pfad = os.path.join(weiterer, dateiname)
        if os.path.isfile(pfad) and os.path.abspath(pfad) != os.path.abspath(
                os.path.join(ordner, dateiname)):
            kandidaten.append(pfad)
    if kandidaten:
        return max(kandidaten, key=os.path.getmtime), "other"

    pfad = os.path.join(run_dir(doc_name, mesh.Name), dateiname)
    if os.path.isfile(pfad):
        return pfad, "own"
    return None, ""


def uebernehme_inp(quelle, solver, doc_name, mesh, gemerkt=""):
    """Copy an existing input file into the FEM working directory of the solver.

    The optimizer writes its iteration files next to the input file, so they
    belong next to the FEM files - and the directory the file came from stays
    untouched.  Returns the path of the copy.
    """
    ziel = os.path.join(arbeitsordner(solver, doc_name, mesh, gemerkt), "%s.inp" % mesh.Name)
    if os.path.abspath(quelle) != os.path.abspath(ziel):
        shutil.copyfile(quelle, ziel)
    return ziel


def write_inp(analysis, solver, mesh, target_dir):
    """Create the input file with FreeCAD's writer and return its path.

    The order matters: setup_working_dir() first, then update_objects() (without
    it `f.mesh` is missing), and write_inp_file() last - set_inp_file_name()
    alone has no effect, the writer builds the name from working_dir + base_name.
    """
    from femtools import ccxtools

    if mesh is None:
        raise ValueError("Die Analyse enthaelt kein Netz.")
    if solver is None:
        raise ValueError("Die Analyse enthaelt keinen Solver.")
    if KEIN_LEERZEICHEN.search(os.path.abspath(target_dir)):
        raise ValueError("Der Arbeitsordner darf keine Leerzeichen enthalten: %s" % target_dir)

    fem = ccxtools.FemToolsCcx(analysis=analysis, solver=solver)
    fem.set_base_name(mesh.Name)
    os.makedirs(target_dir, exist_ok=True)
    fem.setup_working_dir(param_working_dir=target_dir, create=True)
    fem.setup_ccx()
    fem.update_objects()
    fem.write_inp_file()
    return fem.inp_file_name


def erzeuge_inp(analysis, solver, mesh, doc_name, gemerkt=""):
    """Write a new input file into the FEM working directory. Returns (path, seconds).

    FreeCAD creates the directory if it does not exist yet (it is the same
    directory the solver would use), so the files of the optimization sit next to
    the FEM files.
    """
    ziel = arbeitsordner(solver, doc_name, mesh, gemerkt)
    if KEIN_LEERZEICHEN.search(os.path.abspath(ziel)):
        raise ValueError("Der Arbeitsordner darf keine Leerzeichen enthalten: %s" % ziel)
    start = time.time()
    pfad = write_inp(analysis, solver, mesh, ziel)
    return pfad, time.time() - start


def datei_info(pfad):
    """Short description of a file for the user: size and timestamp."""
    if not pfad or not os.path.isfile(pfad):
        return ""
    groesse = os.path.getsize(pfad)
    einheit = "kB"
    wert = groesse / 1024.0
    if wert > 1024:
        wert, einheit = wert / 1024.0, "MB"
    geaendert = time.strftime("%d.%m.%Y %H:%M", time.localtime(os.path.getmtime(pfad)))
    return "%.1f %s, Stand %s" % (wert, einheit, geaendert)
