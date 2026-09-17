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
    """Working directory of the optimization - without spaces, inside temp.

    CalculiX cuts the job name at the first space, so a directory with spaces
    would silently produce a 0 byte .dat file.
    """
    root = os.path.join(tempfile.gettempdir(), "TopoOpt")
    sicher = re.sub(r"[^A-Za-z0-9_.-]", "_", "%s_%s" % (doc_name, base_name))
    pfad = os.path.join(root, sicher)
    os.makedirs(pfad, exist_ok=True)
    return pfad


def find_inp(solver, mesh, doc_name):
    """Look for an input file that already exists. Returns (path, source) or (None, "").

    If the user ran the analysis before (solver panel: "Write .inp file"), the
    file is already there and does not have to be written again:

    1. working directory of the solver (where FreeCAD writes it),
    2. FreeCAD's own FEM working directories (%TEMP%/fcfem_*), newest first,
    3. a working directory this addon used in an earlier session.
    """
    if mesh is None:
        return None, ""
    dateiname = "%s.inp" % mesh.Name

    arbeitsordner = getattr(solver, "WorkingDirectory", "") or ""
    if arbeitsordner and os.path.isdir(arbeitsordner):
        pfad = os.path.join(arbeitsordner, dateiname)
        if os.path.isfile(pfad):
            return pfad, "solver"

    kandidaten = []
    for ordner in glob.glob(os.path.join(tempfile.gettempdir(), "fcfem_*")):
        pfad = os.path.join(ordner, dateiname)
        if os.path.isfile(pfad):
            kandidaten.append(pfad)
    if kandidaten:
        return max(kandidaten, key=os.path.getmtime), "freecad"

    pfad = os.path.join(run_dir(doc_name, mesh.Name), dateiname)
    if os.path.isfile(pfad):
        return pfad, "own"
    return None, ""


def uebernehme_inp(quelle, doc_name, mesh):
    """Copy an existing input file into the working directory of the optimization.

    The optimizer writes its iteration files next to the input file, so they
    belong together in one directory - and FreeCAD's own directory stays
    untouched.  Returns the path of the copy.
    """
    ziel = os.path.join(run_dir(doc_name, mesh.Name), "%s.inp" % mesh.Name)
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


def erzeuge_inp(analysis, solver, mesh, doc_name):
    """Write a new input file into the working directory. Returns (path, seconds)."""
    ziel = run_dir(doc_name, mesh.Name)
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
