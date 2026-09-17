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
    DESIGN: "Design-Raum (wird optimiert)",
    NON_DESIGN: "Nicht-Design-Raum (bleibt)",
    IGNORE: "ignorieren",
}
LABEL_ROLES = {label: role for role, label in ROLE_LABELS.items()}

# element sets that only collect everything - of no use in the table
# (FreeCAD writes Eall/Evolumes, Efaces, Eedges, Enodes for the whole model)
SAMMELSETS = ("eall", "all_available", "evolumes", "efaces", "eedges", "enodes")


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
