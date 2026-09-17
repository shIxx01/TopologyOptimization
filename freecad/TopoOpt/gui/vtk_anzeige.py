# SPDX-License-Identifier: LGPL-3.0-or-later
"""Show the iterations of a run in FreeCAD (the viewer of the first prototype).

Deliberately without any automation: the file is loaded on a click, exactly the
iteration in the field is shown, and the display is **one** mesh object that is
updated (not one object per iteration - that would flood the tree).
"""

import Mesh

from ..core import vtk as vtk_modul


class Spieler(object):
    """Holds the loaded data and updates a mesh object."""

    def __init__(self, daten, doc, objekt_name="TopoOpt_Iteration",
                 label="TopoOpt iteration"):
        self.punkte = daten["punkte"]
        self.zellen = daten["zellen"]
        self.zustaende = daten["zustaende"]
        self.namen = daten["namen"]
        self.doc = doc
        self.objekt_name = objekt_name
        self.label = label
        self._objekt = None

    @classmethod
    def laden(cls, pfad, doc, objekt_name="TopoOpt_Iteration", label="TopoOpt iteration"):
        daten = vtk_modul.laden(pfad)
        return cls(daten, doc, objekt_name, label)

    @property
    def anzahl(self):
        return len(self.zustaende)

    def _anzeigeobjekt(self):
        if self._objekt is not None:
            return self._objekt
        obj = self.doc.getObject(self.objekt_name)
        if obj is None or not hasattr(obj, "Mesh"):
            if obj is not None:                     # falscher Typ belegt den Namen
                self.doc.removeObject(self.objekt_name)
            obj = self.doc.addObject("Mesh::Feature", self.objekt_name)
            obj.Label = self.label
        self._objekt = obj
        return obj

    def zeigen(self, nummer, farbe=(0.80, 0.80, 0.84)):
        """Iteration ``nummer`` (1-basiert) als Materialoberflaeche anzeigen."""
        nummer = max(1, min(self.anzahl, int(nummer)))
        zustand = self.zustaende[nummer - 1]
        flaechen = vtk_modul.randflaechen(self.zellen, zustand, self.punkte)
        netz = Mesh.Mesh()
        netz.addFacets([(self.punkte[p], self.punkte[q], self.punkte[r])
                        for p, q, r in flaechen])
        obj = self._anzeigeobjekt()
        obj.Mesh = netz
        self.doc.recompute()
        try:
            seher = obj.ViewObject
            if seher is not None:
                seher.ShapeColor = farbe
                seher.Visibility = True
        except Exception:
            pass
        ergebnis = vtk_modul.zusammenfassung({"zellen": self.zellen,
                                              "zustaende": self.zustaende,
                                              "namen": self.namen}, nummer)
        ergebnis["flaechen"] = len(flaechen)
        ergebnis["objekt"] = obj.Name
        return ergebnis
