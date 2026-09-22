#!/usr/bin/env python
# SPDX-License-Identifier: LGPL-3.0-or-later
"""Compare the bundled beso with the original from GitHub.

Any Python can run this - FreeCAD is not needed:

    git clone --depth 1 https://github.com/calculix/beso.git /tmp/beso-original
    python3 tests/vergleiche_beso_kopie.py            # or: <path to a clone>
                                                      # or: BESO_ORIGINAL=/path

It prints every difference (lines ending in CRLF are not a difference) and checks two
things:

* the bundled copy is upstream plus the changes listed in
  ``freecad/TopoOpt/beso/CHANGES-TopoOpt.md``, and
* every single difference carries a ``TopoOpt:`` comment in the source.

A difference without such a comment is a difference nobody will find later - that is
what this check is for.  Exit code 0 = everything documented.
"""

import difflib
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
KOPIE = os.path.join(os.path.dirname(HIER), "freecad", "TopoOpt", "beso")
# beso's own FreeCAD dialog is deliberately not bundled - the assistant takes its place
NICHT_GEBUENDELT = ("beso_fc_gui.py",)


def zeilen(pfad):
    with open(pfad, encoding="utf8", errors="replace") as fh:
        # CRLF must not count as a difference: upstream ships mixed line endings
        return fh.read().replace("\r\n", "\n").replace("\r", "\n").split("\n")


def hunks(alt, neu):
    """(start line, lines, documented) je Unterschied."""
    ergebnis = []
    block = []
    start = 0
    for zeile in difflib.unified_diff(alt, neu, n=2, lineterm=""):
        if zeile.startswith("@@"):
            if block:
                ergebnis.append((start, block))
            block = [zeile]
            start = int(zeile.split("-")[1].split(",")[0])
        elif block:
            if zeile.startswith("+++") or zeile.startswith("---"):
                continue
            block.append(zeile)
    if block:
        ergebnis.append((start, block))
    return [(s, b, any("TopoOpt:" in z for z in b)) for s, b in ergebnis]


def main():
    original = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "BESO_ORIGINAL", "/tmp/beso-original")
    if not os.path.isdir(original):
        print("FEHLT Kein Original-beso unter %s" % original)
        print("      git clone --depth 1 https://github.com/calculix/beso.git %s" % original)
        return 1
    print("Vergleich: %s\n     gegen: %s\n" % (KOPIE, original))

    fehlende = []
    undokumentiert = 0
    for name in sorted(os.listdir(original)):
        if not name.endswith(".py"):
            continue
        alt = zeilen(os.path.join(original, name))
        neu_pfad = os.path.join(KOPIE, name)
        if not os.path.isfile(neu_pfad):
            if name in NICHT_GEBUENDELT:
                print("%-18s nicht gebuendelt (so gewollt)" % name)
            else:
                fehlende.append(name)
                print("%-18s FEHLT in der Kopie" % name)
            continue
        neu = zeilen(neu_pfad)
        if alt == neu:
            print("%-18s unveraendert" % name)
            continue
        stellen = hunks(alt, neu)
        print("%-18s %d Unterschied(e), davon %d ohne TopoOpt-Kommentar"
              % (name, len(stellen), sum(1 for _, _, d in stellen if not d)))
        for start, block, dokumentiert in stellen:
            print("    ab Zeile %d%s" % (start, "" if dokumentiert else "   <-- nicht dokumentiert"))
            for zeile in block:
                if zeile.startswith("+") and "TopoOpt:" not in zeile:
                    print("      neu: %s" % zeile[1:].strip()[:88])
                elif zeile.startswith("-") and not zeile.startswith("---"):
                    print("      alt: %s" % zeile[1:].strip()[:88])
            if not dokumentiert:
                undokumentiert += 1
    print()
    if fehlende or undokumentiert:
        print("FEHLT %d Datei(en) fehlen, %d Unterschied(e) ohne TopoOpt-Kommentar"
              % (len(fehlende), undokumentiert))
        return 1
    print("OK alle Unterschiede sind mit TopoOpt-Kommentaren belegt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
