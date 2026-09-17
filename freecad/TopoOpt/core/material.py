# SPDX-License-Identifier: LGPL-3.0-or-later
"""Read the allowable stress from the material of the model (if it has one).

FreeCAD material cards may carry a yield strength (``YieldStrength``); the metals in
the standard library do (Aluminium-6061-T6, Copper-…), the plain steel cards
("Steel", "CalculiX-Steel") do not.  When a value is there, the assistant suggests it
as the allowable stress - the user can still change or delete it.

The values in a material card come as text with a unit ("315 MPa",
"2.1e+08 kg/(mm*s^2)"), so they are parsed into MPa.
"""

import re

# Faktor auf MPa
EINHEITEN = {
    "gpa": 1000.0,
    "mpa": 1.0,
    "n/mm^2": 1.0,
    "n/mm2": 1.0,
    "ksi": 6.894757293168361,
    "psi": 0.006894757293168361,
    "kpa": 0.001,
    "kg/(mm*s^2)": 0.001,      # 1 kg/(mm*s^2) = 1 kPa
    "kg/(mm*s²)": 0.001,
    "pa": 1e-6,
}

ZAHL = re.compile(r"^\s*([-+0-9.eE,]+)\s*([A-Za-z0-9/().^*² ]*)\s*$")

# Schluessel, die eine Streckgrenze enthalten koennen (Reihenfolge = Vorrang)
SCHLUESSEL = ("YieldStrength", "UltimateTensileStrength", "CompressiveStrength")


def MPa(wert):
    """Eine Materialangabe in MPa umrechnen - oder None, wenn sie unbrauchbar ist."""
    if isinstance(wert, (int, float)):
        return float(wert) or None
    if not isinstance(wert, str):
        return None
    treffer = ZAHL.match(wert.replace(",", "."))
    if not treffer:
        return None
    try:
        zahl = float(treffer.group(1))
    except ValueError:
        return None
    einheit = treffer.group(2).strip().lower().replace(" ", "")
    faktor = EINHEITEN.get(einheit)
    if faktor is None:
        if not einheit:
            faktor = 1.0                 # ohne Einheit: als MPa lesen
        else:
            return None                  # unbekannte Einheit - lieber nichts vorschlagen
    ergebnis = zahl * faktor
    return ergebnis if ergebnis > 0 else None


def streckgrenze(materialien, elsets):
    """Was das Material der Element-Sets hergibt.

    ``materialien`` ist eine Liste von ``(Name, Werte-Dict)`` (siehe
    ``materialien_finden``), ``elsets`` die Menge der Element-Sets.  Zugeordnet wird
    ueber den Namen: das Material 'MaterialSolid' gehoert zu 'MaterialSolidSolid'.
    Gibt es nur ein Material, gilt es fuer alle Sets ohne eigenes Material.

    Returns {"<elset>": MPa}
    """
    ergebnis = {}
    eintraege = [(name, werte) for name, werte in materialien if isinstance(werte, dict)]
    for elset in elsets:
        passend = None
        for name, werte in eintraege:
            if name and elset.lower().startswith(name.lower()):
                passend = werte
                break
        if passend is None and len(eintraege) == 1:
            passend = eintraege[0][1]
        if passend is None:
            continue
        for schluessel in SCHLUESSEL:
            if schluessel in passend:
                wert = MPa(passend[schluessel])
                if wert:
                    ergebnis[elset] = wert
                    break
    return ergebnis


def materialien_finden(analyse):
    """Die Materialobjekte des Modells als [(Name, Werte-Dict), ...].

    Sucht in der Analyse und - falls noetig - im ganzen Dokument (FreeCAD legt
    Materialobjekte neben die Analyse).  Ohne Analyse wird das aktive Dokument
    genommen, damit der Vorschlag auch ohne gewaehlte Analyse funktioniert.
    """
    ergebnis = []
    kandidaten = []
    if analyse is not None:
        for kind in getattr(analyse, "Group", []) or []:
            kandidaten.append(kind)
    try:
        import FreeCAD as App
        doc = getattr(analyse, "Document", None) or getattr(App, "ActiveDocument", None)
        if doc is not None:
            for obj in doc.Objects:
                if obj not in kandidaten:
                    kandidaten.append(obj)
    except Exception:
        pass
    for obj in kandidaten:
        if not str(getattr(obj, "TypeId", "")).startswith("App::MaterialObject"):
            continue
        werte = getattr(obj, "Material", None)
        if isinstance(werte, dict):
            ergebnis.append((obj.Name, werte))
    return ergebnis
