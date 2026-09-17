# SPDX-License-Identifier: LGPL-3.0-or-later
"""Kleine CalculiX-Modelle fuer die Szenario-Matrix erzeugen.

beso liest ausschliesslich die ``.inp`` - FreeCAD muss dafuer nicht laufen.  Die
Modelle hier sind winzig (8 Hexaeder bzw. 8 Dreiecke) und haben echte Lasten und
Lager, damit ``stiffness`` nicht an fehlenden CalculiX-Ergebnissen scheitert.

Erzeugt in ``tests/szenarien``:
  modell_3d_hex.inp    2x2x2 Hexaeder (C3D8), 20 mm Wuerfel, Zug von oben
  modell_2d_schale.inp 2x4 S3-Dreiecke, 20 x 10 mm, 5 mm Dicke, Zug an der Kante
  modell_2d_ohne_dicke.inp  dasselbe ohne *SHELL SECTION (Fehlerfall)

Aufruf:  python tests/make_szenario_inp.py   (normales Python, kein FreeCAD)
"""
import os

HIER = os.path.dirname(os.path.abspath(__file__))
ZIEL = os.path.join(HIER, "szenarien")


def hexaeder_modell(kanten=20.0, teile=2):
    """Wuerfel aus Hexaedern, unten fest, Zug nach unten oben."""
    schritt = kanten / teile
    knoten = {}
    zeilen = ["*NODE"]
    nummer = 0
    for k in range(teile + 1):
        for j in range(teile + 1):
            for i in range(teile + 1):
                nummer += 1
                knoten[(i, j, k)] = nummer
                zeilen.append("%d, %.6f, %.6f, %.6f"
                              % (nummer, i * schritt, j * schritt, k * schritt))
    elemente = ["*ELEMENT, TYPE=C3D8, ELSET=MaterialSolidSolid"]
    nummer = 0
    for k in range(teile):
        for j in range(teile):
            for i in range(teile):
                nummer += 1
                e = [knoten[(i, j, k)], knoten[(i + 1, j, k)],
                     knoten[(i + 1, j + 1, k)], knoten[(i, j + 1, k)],
                     knoten[(i, j, k + 1)], knoten[(i + 1, j, k + 1)],
                     knoten[(i + 1, j + 1, k + 1)], knoten[(i, j + 1, k + 1)]]
                elemente.append("%d, %s" % (nummer, ", ".join(str(x) for x in e)))
    unten = [knoten[(i, j, 0)] for i in range(teile + 1) for j in range(teile + 1)]
    oben = [knoten[(i, j, teile)] for i in range(teile + 1) for j in range(teile + 1)]
    return "\n".join(zeilen + elemente + [
        "*ELSET, ELSET=Eall",
        "MaterialSolidSolid",
        "*MATERIAL, NAME=MaterialSolid",
        "*ELASTIC",
        "210000, 0.3",
        "*DENSITY",
        "7.9e-09",
        "*BOUNDARY",
        "\n".join("%d, 1, 3, 0.0" % n for n in unten),
        "*STEP",
        "*STATIC",
        "*CLOAD",
        "\n".join("%d, 3, -%.1f" % (n, 1000.0 / len(oben)) for n in oben),
        "*NODE FILE",
        "U",
        "*EL FILE",
        "S, E, ENER",
        "*END STEP",
        "",
    ])


def schalen_modell(dicke=5.0, mit_dicke=True):
    """Flaeche 20 x 10 mm aus zwei S3-Streifen, links fest, Zug rechts unten."""
    punkte = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0),
              (0.0, 10.0), (10.0, 10.0), (20.0, 10.0)]
    zeilen = ["*NODE"]
    for i, (x, y) in enumerate(punkte, start=1):
        zeilen.append("%d, %.6f, %.6f, 0.0" % (i, x, y))
    zeilen.append("*ELEMENT, TYPE=S3, ELSET=MaterialSolidElementGeometry2D")
    zeilen.append("1, 1, 2, 5")
    zeilen.append("2, 1, 5, 4")
    zeilen.append("3, 2, 3, 6")
    zeilen.append("4, 2, 6, 5")
    zeilen += ["*ELSET, ELSET=Eall", "MaterialSolidElementGeometry2D"]
    if mit_dicke:
        zeilen += ["*SHELL SECTION, ELSET=MaterialSolidElementGeometry2D, "
                   "MATERIAL=MaterialSolid, OFFSET=0", "%g" % dicke]
    zeilen += [
        "*MATERIAL, NAME=MaterialSolid",
        "*ELASTIC",
        "210000, 0.3",
        "*DENSITY",
        "7.9e-09",
        "*BOUNDARY",
        "1, 1, 3, 0.0",
        "4, 1, 3, 0.0",
        "*STEP",
        "*STATIC",
        "*CLOAD",
        "3, 2, -500.0",
        "6, 2, -500.0",
        "*NODE FILE",
        "U",
        "*EL FILE",
        "S, E, ENER",
        "*END STEP",
        "",
    ]
    return "\n".join(zeilen)


def main():
    if not os.path.isdir(ZIEL):
        os.makedirs(ZIEL)
    dateien = {
        "modell_3d_hex.inp": hexaeder_modell(),
        "modell_2d_schale.inp": schalen_modell(),
        "modell_2d_ohne_dicke.inp": schalen_modell(mit_dicke=False),
    }
    for name, inhalt in dateien.items():
        pfad = os.path.join(ZIEL, name)
        with open(pfad, "w", encoding="utf8", newline="\n") as fh:
            fh.write(inhalt)
        print("%-28s %6d Zeilen" % (name, inhalt.count("\n")), flush=True)
    print("Ordner:", ZIEL, flush=True)


main()
