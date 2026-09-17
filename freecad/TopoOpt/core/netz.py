# SPDX-License-Identifier: LGPL-3.0-or-later
"""Das Ergebnisnetz eines Laufs laden - das echte FEM-Netz, kein Schaubild.

beso sichert jede gespeicherte Iteration als Zustandspaar ``<name>_state0.inp`` /
``<name>_state1.inp`` (Zustand 1 = Element steht, Zustand 0 = Element entfernt).
``state1`` ist damit das Material, das am Ende uebrig ist - ein richtiges
CalculiX-Eingabefile mit Netzknoten, Elementen und Materialdaten.

Geladen wird es mit FreeCADs eigenem FEM-Import (``feminout.importInpMesh``), wie es
der erste Prototyp gemacht hat.  Daraus wird ein Mesh-Objekt, mit dem man in FreeCAD
weiterarbeiten kann (zum Beispiel eine FEM-Rechnung darauf).

Das ist etwas anderes als der VTK-Player in ``core/vtk.py``: der zeigt aus
``resulting_states.vtk`` die **Oberflaeche** des stehengebliebenen Materials und
dient nur dem Ansehen (und dem Iterationsfilm).
"""

import os

# Zustandsdatei einer Iteration ("file001_state1.inp")
ENDUNG = "_state1.inp"


def neueste_state1(ordner):
    """Die zuletzt geschriebene Zustandsdatei im Arbeitsordner.

    Nach Aenderungszeit sortiert, nicht alphabetisch: alphabetisch waere die
    hoechste Iterationsnummer **eines frueheren** Laufs die "letzte".
    Returns den Pfad oder "".
    """
    if not ordner or not os.path.isdir(ordner):
        return ""
    kandidaten = [name for name in os.listdir(ordner) if name.endswith(ENDUNG)]
    if not kandidaten:
        return ""
    kandidaten.sort(key=lambda name: os.path.getmtime(os.path.join(ordner, name)))
    return os.path.join(ordner, kandidaten[-1])


def laden(pfad, dokument=None):
    """Das Netz aus einer Zustandsdatei als Mesh-Objekt ins Dokument legen.

    Ein fehlender Importeur wird als klare Meldung weitergegeben - ohne FEM-Modul
    kann FreeCAD die Datei nicht lesen.
    """
    if not pfad or not os.path.isfile(pfad):
        raise ValueError("Datei nicht gefunden: %s" % (pfad or "-"))
    try:
        import femimport                      # noqa: F401  (laedt den Importeur)
    except Exception:
        pass
    from feminout import importInpMesh
    if dokument is not None:
        import FreeCADGui
        FreeCADGui.ActiveDocument = FreeCADGui.getDocument(dokument.Name)
    importInpMesh.import_inp(pfad)
    return pfad
