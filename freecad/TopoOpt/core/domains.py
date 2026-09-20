# SPDX-License-Identifier: LGPL-3.0-or-later
"""Domain table: which element set is design space, which one is not.

The roles are stored in the document object as a string list, one entry per set
(`"<elset>|<role>"`), so the document is the single source of truth - the table
only shows it and writes changes straight back.
"""

# roles used in the document object
DESIGN = "design"
NON_DESIGN = "non_design"
IGNORE = "ignore"

ROLE_LABELS = {
    DESIGN: "Design space (optimized)",
    NON_DESIGN: "Non-design space (kept)",
    IGNORE: "ignore",
}
LABEL_ROLES = {label: role for role, label in ROLE_LABELS.items()}

# element sets that only collect everything - of no use in the table
# (FreeCAD writes Eall/Evolumes, Efaces, Eedges, Enodes for the whole model)
SAMMELSETS = ("eall", "all_available", "evolumes", "efaces", "eedges", "enodes")


def aktive(domains):
    """Die Domains, die in der Optimierung vorkommen.

    "ignore" heisst: diese Elemente spielen fuer die Optimierung keine Rolle.
    Solche Sets kommen nicht in die beso-Konfiguration - sie brauchen dann auch
    keine zulaessige Spannung und werden nicht ausgewertet.
    """
    return {name: rolle for name, rolle in (domains or {}).items() if rolle != IGNORE}


def parse_domains(werte):
    """["set|design", ...] -> {"set": "design"}."""
    ergebnis = {}
    for eintrag in werte or []:
        if "|" not in eintrag:
            continue
        name, rolle = eintrag.split("|", 1)
        name = name.strip()
        if name:
            ergebnis[name] = rolle.strip()
    return ergebnis


def format_domains(domains):
    """{"set": "design"} -> ["set|design", ...] (stabile Reihenfolge)."""
    return ["%s|%s" % (name, domains[name]) for name in sorted(domains)]


def parse_stress(werte):
    """["set|235.0", ...] -> {"set": 235.0} (allowable stress in MPa)."""
    ergebnis = {}
    for eintrag in werte or []:
        if "|" not in eintrag:
            continue
        name, wert = eintrag.split("|", 1)
        name = name.strip()
        try:
            zahl = float(wert.strip().replace(",", "."))
        except ValueError:
            continue
        if name and zahl > 0:
            ergebnis[name] = zahl
    return ergebnis


def format_stress(limits, aus=None):
    """{"set": 235.0} -> ["set|235.0", ...] (stabile Reihenfolge).

    ``aus`` sind Sets mit **bewusst** leerem Feld: sie werden als "<set>|0"
    gespeichert, damit der Vorschlag aus dem Material nicht wieder auftaucht.
    """
    ergebnis = ["%s|%r" % (name, limits[name]) for name in sorted(limits)]
    ergebnis += ["%s|0" % name for name in sorted(set(aus or ()) - set(limits))]
    return ergebnis


def aus_stress(werte):
    """Die als "<set>|0" gespeicherten Sets (bewusst ohne Spannung)."""
    ergebnis = set()
    for eintrag in werte or []:
        if "|" not in eintrag:
            continue
        name, wert = eintrag.split("|", 1)
        try:
            zahl = float(wert.strip().replace(",", "."))
        except ValueError:
            continue
        if name.strip() and zahl <= 0:
            ergebnis.add(name.strip())
    return ergebnis


def vorschlag(elsets):
    """A first suggestion for the incoming sets.

    Every set starts as "ignore".  If there is exactly one ordinary set, it is
    suggested as design space - that is the usual single body model.  Sets that
    only collect everything (Eall) are not offered at all.
    """
    vorschlaege = {}
    for name in elsets:
        if name.lower() in SAMMELSETS:
            continue
        vorschlaege[name] = IGNORE
    offen = [n for n in vorschlaege if vorschlaege[n] == IGNORE]
    if len(offen) == 1:
        vorschlaege[offen[0]] = DESIGN
    return vorschlaege


def zeige_elsets(elsets):
    """Sets for the table: collector sets are hidden."""
    return {name: anzahl for name, anzahl in elsets.items() if name.lower() not in SAMMELSETS}
