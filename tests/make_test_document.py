#!/usr/bin/env python
# SPDX-License-Identifier: LGPL-3.0-or-later
"""Create the test document for the addon - a small FEM model, fully self made.

    ("<FreeCAD>/bin/freecad.exe" "C:/.../tests/make_test_document.py" >/dev/null 2>&1 &)

The document is written to %TEMP%/TopoOpt_Test/modell.FCStd (path can be given in
the environment variable TOPOOPT_TEST_DOKUMENT) and contains: a box, a material, a
FEM analysis with a coarse gmsh mesh and a CalculiX solver.  It is deliberately
small (a few hundred elements), so the tests run in seconds, and it is created
from scratch instead of using a document of the developer's own project.
"""

import os
import sys
import traceback

HIER = os.path.dirname(os.path.abspath(__file__))
AUSGABE = os.path.join(HIER, "make_test_document_ausgabe.txt")

zeilen = []


def log(text):
    zeilen.append(str(text))


try:
    import FreeCAD as App
    import ObjectsFem
    from PySide import QtWidgets

    FreeCADGui = None
    try:
        import FreeCADGui
    except ImportError:
        pass

    ziel = os.environ.get("TOPOOPT_TEST_DOKUMENT") or os.path.join(
        os.environ.get("TEMP", "/tmp"), "TopoOpt_Test", "modell.FCStd")
    os.makedirs(os.path.dirname(ziel), exist_ok=True)

    doc = App.newDocument("TopoOpt_Testmodell")

    # 1. die Geometrie: ein Balken 100 x 20 x 10 mm
    kasten = doc.addObject("Part::Box", "Balken")
    kasten.Length = 100.0
    kasten.Width = 20.0
    kasten.Height = 10.0
    doc.recompute()

    # 2. Material - mit Zuordnung zum Koerper, sonst schreibt FreeCAD kein
    #    Material-ELSET in die Eingabedatei (und die Domains-Tabelle bleibt leer)
    material = ObjectsFem.makeMaterialSolid(doc, "MaterialSolid")
    material.Material = {
        "Name": "Steel",
        "YoungsModulus": "210000 MPa",
        "PoissonRatio": "0.30",
        "Density": "7900 kg/m^3",
    }
    material.References = [(kasten, "Solid1")]

    # 3. Vernetzung (grob, damit die Tests schnell sind)
    netz = ObjectsFem.makeMeshGmsh(doc, "FEMMeshGmsh")
    netz.Shape = kasten
    netz.CharacteristicLengthMax = 8.0
    netz.CharacteristicLengthMin = 8.0
    doc.recompute()

    # 4. Analyse mit Netz, Material und Solver
    analyse = ObjectsFem.makeAnalysis(doc, "Analysis")
    solver = ObjectsFem.makeSolverCalculiXCcxTools(doc, "SolverCalculiX")
    analyse.addObject(material)
    analyse.addObject(netz)
    analyse.addObject(solver)
    doc.recompute()

    # 5. Netz wirklich erzeugen (gmsh laeuft als externes Programm)
    import femmesh.gmshtools as gmshtools
    ergebnis = gmshtools.GmshTools(netz).create_mesh()
    log("Netz erzeugt: %s" % ergebnis)
    log("Knoten: %d, Volumenelemente: %d"
        % (netz.FemMesh.NodeCount, netz.FemMesh.VolumeCount))

    doc.recompute()
    doc.saveAs(ziel)
    log("Dokument gespeichert: %s (%d Bytes)" % (ziel, os.path.getsize(ziel)))
    log("Objekte: %s" % ", ".join(sorted(o.Name for o in doc.Objects)))

    if FreeCADGui is not None:
        App.closeDocument(doc.Name)
    log("ERGEBNIS: OK")
except Exception:
    log("AUSNAHME:\n" + traceback.format_exc())

with open(AUSGABE, "w", encoding="utf8") as f:
    f.write("\n".join(zeilen) + "\n")

if FreeCADGui is not None:
    sys.exit(0)
print("\n".join(zeilen))
