# SPDX-License-Identifier: LGPL-3.0-or-later
"""Read ``resulting_states.vtk`` - the material states of every iteration.

beso writes this file once at the end of a run.  It contains **all** iterations as
separate cell fields:

    POINTS 72051            node coordinates (3 numbers per node)
    CELLS 41666 458326      per cell "10 <10 node numbers>" (TETRA10)
    CELL_TYPE 41666         all 24 (quadratic tetrahedron)
    CELL_DATA 41666         44 x "SCALARS element_statesNNN float" (0/1 per element)

Shown is the **surface of the material that is left**: from every tetrahedron with
state 1 the four triangles are collected and only the ones that occur once are
drawn - those are exactly the boundary faces.

This is the reader of the first prototype, kept because it works; the three traps it
had to solve are noted at the places where they are handled:

* node numbers are **0-based** (see :func:`laden`),
* the ``LOOKUP_TABLE`` line must not end a section (see :func:`_abschnitte`),
* the triangles must be turned outwards (see :func:`randflaechen`).
"""

import os

import FreeCAD


def _abschnitte(pfad):
    """Split the file into sections: keyword line -> following lines.

    More reliable than guessing line by line, because VTK wraps the numbers
    anywhere (the POINTS lines carry two nodes, the state lines 30 values).
    """
    abschnitte = []
    aktuell = None
    with open(pfad, "r", encoding="utf8", errors="replace") as fh:
        for zeile in fh:
            zu = zeile.strip()
            if not zu:
                continue
            if zu[0].isalpha():
                # "LOOKUP_TABLE default" belongs to the SCALARS section before it and
                # must not end it - otherwise every state value lands in that line and
                # the iterations stay empty.
                if zu.split()[0].upper() == "LOOKUP_TABLE":
                    continue
                aktuell = [zu, []]
                abschnitte.append(aktuell)
            elif aktuell is not None:
                aktuell[1].extend(zu.split())
    return abschnitte


def laden(pfad):
    """Read nodes, cells and the state arrays.

    Returns dict with ``punkte`` (list of Vector), ``zellen`` (list of 10 node
    indices), ``zustaende`` (list of bytearray, one per iteration) and ``namen``
    (iteration names from the file).

    Important: the node numbers in the file are **0-based** and are used directly as
    index into ``punkte``.  Subtracting 1 (as with CalculiX .inp) moves every cell;
    because Netgen does not number the nodes spatially, this creates far apart
    "corner nodes" and a torn mesh.  Measured on 300 cells: largest edge among the
    four corners median 1.42 mm, max 2.18 mm (right) against median 2.83 mm,
    max 81.76 mm (with -1).
    """
    abschnitte = _abschnitte(pfad)
    punkte, zellen, zustaende, namen = [], [], [], []
    for kopf, werte in abschnitte:
        teile = kopf.split()
        schluessel = teile[0].upper()
        if schluessel == "POINTS":
            anzahl = int(teile[1])
            zahlen = [float(w) for w in werte[:3 * anzahl]]
            punkte = [FreeCAD.Vector(zahlen[i], zahlen[i + 1], zahlen[i + 2])
                      for i in range(0, len(zahlen) - 2, 3)]
        elif schluessel == "CELLS" and len(teile) >= 2:
            anzahl = int(teile[1])
            rest = [int(w) for w in werte]
            i, gelesen = 0, 0
            while gelesen < anzahl and i < len(rest):
                knoten_je_zelle = rest[i]
                i += 1
                # Knotennummern sind 0-basiert - NICHT 1 abziehen (siehe Docstring)
                zellen.append(list(rest[i:i + knoten_je_zelle]))
                i += knoten_je_zelle
                gelesen += 1
        elif schluessel == "SCALARS" and len(teile) >= 2:
            anzahl = len(zellen)
            daten = bytearray(anzahl)
            for i, w in enumerate(werte[:anzahl]):
                daten[i] = 1 if float(w) > 0.5 else 0
            namen.append(teile[1])
            zustaende.append(daten)
    if not punkte or not zellen or not zustaende:
        raise ValueError("file contains no points/cells/states (%s)"
                         % os.path.basename(pfad))
    return {"punkte": punkte, "zellen": zellen, "zustaende": zustaende, "namen": namen}


def randflaechen(zellen, zustand, punkte):
    """Outward facing triangles of the material surface.

    From every tetrahedron with state 1 the four triangles are collected; a triangle
    two material cells share is inside and falls away.  Counting uses a dict (a list
    would be quadratic).

    The triangles are turned **outwards**: the normal has to point away from the
    fourth node of the tetrahedron.  Without that turn about half of the faces point
    inwards and are lit wrongly - that looks like a hole in the tree (seen in tests).

    Returns list of (i, j, k) node indices, oriented outwards.
    """
    offen = {}
    for i, zelle in enumerate(zellen):
        if not zustand[i]:
            continue
        ecken = (zelle[0], zelle[1], zelle[2], zelle[3])
        for k in range(4):
            gegenueber = ecken[k]
            dreieck = tuple(ecken[j] for j in range(4) if j != k)
            schluessel = tuple(sorted(dreieck))
            if schluessel in offen:
                offen[schluessel] = None            # innen: von zwei Zellen geteilt
            else:
                offen[schluessel] = (dreieck, gegenueber)

    ergebnis = []
    for schluessel, wert in offen.items():
        if wert is None:
            continue
        dreieck, gegenueber = wert
        p0, p1, p2 = (punkte[dreieck[0]], punkte[dreieck[1]], punkte[dreieck[2]])
        normale = (p1 - p0).cross(p2 - p0)
        if normale.dot(p0 - punkte[gegenueber]) < 0:
            dreieck = (dreieck[0], dreieck[2], dreieck[1])
        ergebnis.append(dreieck)
    return ergebnis


def kantenprobe(dreiecke):
    """How often does every edge occur?  Closed surface -> always 2."""
    zaehler = {}
    for a, b, c in dreiecke:
        for p, q in ((a, b), (b, c), (c, a)):
            schluessel = (p, q) if p < q else (q, p)
            zaehler[schluessel] = zaehler.get(schluessel, 0) + 1
    verteilung = {}
    for anzahl in zaehler.values():
        verteilung[anzahl] = verteilung.get(anzahl, 0) + 1
    return verteilung


def volumen(punkte, dreiecke):
    """Signed volume of the faces (correctly oriented -> positive)."""
    summe = 0.0
    for a, b, c in dreiecke:
        p0, p1, p2 = punkte[a], punkte[b], punkte[c]
        summe += p0.dot(p1.cross(p2))
    return summe / 6.0


def zellvolumen(punkte, zellen, zustand):
    """Sum of the volumes of all material cells (corner nodes only)."""
    summe = 0.0
    for i, zelle in enumerate(zellen):
        if not zustand[i]:
            continue
        a, b, c, d = (punkte[zelle[0]], punkte[zelle[1]],
                      punkte[zelle[2]], punkte[zelle[3]])
        summe += abs((b - a).dot((c - a).cross(d - a))) / 6.0
    return summe


def zusammenfassung(daten, nummer):
    """Wie viel Material steht in Iteration ``nummer`` (1-basiert)?"""
    anzahl = len(daten["zustaende"])
    nummer = max(1, min(anzahl, int(nummer)))
    zustand = daten["zustaende"][nummer - 1]
    material = int(sum(zustand))
    gesamt = len(daten["zellen"])
    return {"nummer": nummer, "anzahl": anzahl,
            "name": daten["namen"][nummer - 1] if nummer <= len(daten["namen"]) else "",
            "zellen": material, "gesamt": gesamt,
            "prozent": 100.0 * material / max(1, gesamt)}
