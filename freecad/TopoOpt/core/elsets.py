# SPDX-License-Identifier: LGPL-3.0-or-later
"""Read element sets (ELSET) out of a CalculiX .inp file.

The names of the element sets are written by FreeCAD's writer and must not be
guessed (a 3D analysis uses `<material>Solid`, a 2D analysis uses
`<material><thickness>`, and numeric suffixes appear when a document holds more
than one body).  Reading them from the .inp is fast - measured 0.5 s for 41,666
TETRA10 elements - while the FemMesh Python API is unusable for mass queries
(96 ms per `getElementNodes()` call).

FreeCAD writes material sets as an attribute of the element cards
(`*Element, TYPE=C3D10, ELSET=Evolumes`) and the collector sets as separate cards
(`*ELSET, ELSET=Eall` with the single line `Evolumes`).  A card can therefore
contain element numbers *or* the name of another set, and the references have to
be resolved - otherwise `MaterialSolidSolid` looks like a one-element set.
"""

import os
import re

KURZFORM = re.compile(r"^\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*$")
ATTRIBUT = re.compile(r"([A-Za-z_]+)\s*=\s*\"?([^,\"]+)\"?")


def _attribute(zeile):
    """Alle KEY=VALUE-Attribute einer Kartenzeile, Schluessel in Grossbuchstaben."""
    ergebnis = {}
    for schluessel, wert in ATTRIBUT.findall(zeile):
        ergebnis[schluessel.strip().upper()] = wert.strip()
    return ergebnis


def _ist_zahl(text):
    return text.lstrip("-").isdigit()


def _rohdaten(inp_path):
    """{setname: (anzahl_eigener_elemente, [verwiesene_setnamen])}."""
    roh = {}
    if not inp_path or not os.path.isfile(inp_path):
        return roh

    aktuell = None
    modus = None          # "elemente" (aus *ELEMENT) oder "elset" (aus *ELSET)
    generate = False
    try:
        with open(inp_path, "r", encoding="utf8", errors="ignore") as fh:
            for zeile in fh:
                zu = zeile.strip()
                if zu.startswith("*"):
                    art = zu.upper()
                    attrs = _attribute(zu)
                    if art.startswith("*ELEMENT"):
                        aktuell, modus, generate = attrs.get("ELSET"), "elemente", False
                    elif art.startswith("*ELSET"):
                        aktuell, modus = attrs.get("ELSET"), "elset"
                        generate = "GENERATE" in art
                    else:
                        aktuell, modus, generate = None, None, False
                    if aktuell:
                        roh.setdefault(aktuell, [0, []])
                    continue
                if not aktuell or not zu:
                    continue
                if modus == "elemente":
                    if _ist_zahl(zu.split(",")[0].strip()):
                        roh[aktuell][0] += 1
                    continue
                if generate:
                    treffer = KURZFORM.match(zu)
                    if treffer:
                        start, ende, schritt = (int(g) for g in treffer.groups())
                        if schritt:
                            roh[aktuell][0] += max(0, (ende - start) // schritt + 1)
                    continue
                # normale Schreibweise: Elementnummern (bis 16 je Zeile) oder
                # ein Verweis auf einen anderen Set-Namen
                for teil in (t.strip() for t in zu.split(",")):
                    if not teil:
                        continue
                    if _ist_zahl(teil):
                        roh[aktuell][0] += 1
                    elif teil not in roh[aktuell][1]:
                        roh[aktuell][1].append(teil)
    except OSError:
        return {}
    return {name: (anzahl, verweise) for name, (anzahl, verweise) in roh.items()}


def read_elsets(inp_path):
    """Element sets einer .inp als {name: anzahl_elemente} (Verweise aufgeloest)."""
    roh = _rohdaten(inp_path)
    ergebnis = {}

    def aufloesen(name, gesehen):
        if name in ergebnis:
            return ergebnis[name]
        if name not in roh or name in gesehen:      # Zyklus oder unbekannt
            return 0
        gesehen = gesehen | {name}
        anzahl, verweise = roh[name]
        for ziel in verweise:
            anzahl += aufloesen(ziel, gesehen)
        ergebnis[name] = anzahl
        return anzahl

    for name in roh:
        aufloesen(name, set())
    return ergebnis


def gesamt_elemente(inp_path):
    """Number of elements in the mesh (from the *ELEMENT cards)."""
    roh = _rohdaten(inp_path)
    return max([anzahl for anzahl, _ in roh.values()] or [0])


def element_types(inp_path):
    """Menge der Elementtypen aus den *ELEMENT-Karten, z. B. ["C3D10"]."""
    typen = []
    if not inp_path or not os.path.isfile(inp_path):
        return typen
    try:
        with open(inp_path, "r", encoding="utf8", errors="ignore") as fh:
            for zeile in fh:
                if not zeile.lstrip().upper().startswith("*ELEMENT"):
                    continue
                typ = _attribute(zeile).get("TYPE", "").upper()
                if typ and typ not in typen:
                    typen.append(typ)
    except OSError:
        pass
    return typen
