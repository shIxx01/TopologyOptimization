# SPDX-License-Identifier: LGPL-3.0-or-later
"""Finding the FEM parts of a document and preparing the CalculiX input file."""

import os
import re
import tempfile

import FreeCAD as App

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
    """Working directory for beso - without spaces, inside the temp directory.

    CalculiX cuts the job name at the first space, so a directory with spaces
    would silently produce a 0 byte .dat file.
    """
    root = os.path.join(tempfile.gettempdir(), "TopoOpt")
    sicher = re.sub(r"[^A-Za-z0-9_.-]", "_", "%s_%s" % (doc_name, base_name))
    pfad = os.path.join(root, sicher)
    os.makedirs(pfad, exist_ok=True)
    return pfad


def write_inp(analysis, solver, mesh, target_dir):
    """Create the .inp with FreeCAD's writer and return its path.

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


def prepare_inp(analysis, mesh, solver, doc_name, erneut=False):
    """Working directory and .inp for an analysis. Returns (verzeichnis, inp_pfad).

    An existing .inp is reused unless `erneut` is True - writing it takes a few
    seconds for a fine mesh.
    """
    verzeichnis = run_dir(doc_name, mesh.Name if mesh else "modell")
    inp = os.path.join(verzeichnis, "%s.inp" % (mesh.Name if mesh else "modell"))
    if os.path.isfile(inp) and not erneut:
        return verzeichnis, inp
    App.Console.PrintMessage("TopoOpt: erzeuge %s ...\n" % inp)
    pfad = write_inp(analysis, solver, mesh, verzeichnis)
    return verzeichnis, pfad
