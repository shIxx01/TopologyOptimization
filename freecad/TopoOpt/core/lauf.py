# SPDX-License-Identifier: LGPL-3.0-or-later
"""Read the progress of a beso run from its log file.

beso writes three things we can follow (see the log of a real run):

    initial optimization domains mass 19999.99999999998
    ----------- new iteration number 1 ----------
    mass = 19369.413573798036

So this module only reads the log file - the run itself is an external process and
FreeCAD must not wait for it.
"""

import os
import re

START = re.compile(r"initial optimization domains mass\s+([0-9.eE+-]+)")
ITERATION = re.compile(r"new iteration number\s+(\d+)")
MASSE = re.compile(r"^mass\s*=\s*([0-9.eE+-]+)", re.MULTILINE)


def verlauf_lesen(log_pfad, ziel_anteil=None):
    """Was bisher im Log steht.

    Returns a dict with:
        start        first mass (None while unknown)
        ziel         target mass, when ``ziel_anteil`` is given
        iteration    highest iteration number seen
        massen       [(iteration, mass), ...] in order
        masse        last mass of the run
        fertig       True when the run finished ("Job finished" or a final state)
        text         the whole log (for the detail box)
    """
    ergebnis = {"start": None, "ziel": None, "iteration": 0, "massen": [],
                "masse": None, "fertig": False, "text": ""}
    if not log_pfad or not os.path.isfile(log_pfad):
        return ergebnis
    try:
        with open(log_pfad, encoding="utf8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return ergebnis
    ergebnis["text"] = text

    treffer = START.search(text)
    if treffer:
        try:
            ergebnis["start"] = float(treffer.group(1))
        except ValueError:
            ergebnis["start"] = None
    if ergebnis["start"] and ziel_anteil:
        ergebnis["ziel"] = ergebnis["start"] * float(ziel_anteil)

    # die Iterationen stehen in Reihenfolge im Log: erst die Nummer, dann die Masse
    laufende = 0
    for zeile in text.splitlines():
        nummer = ITERATION.search(zeile)
        if nummer:
            laufende = int(nummer.group(1))
            ergebnis["iteration"] = max(ergebnis["iteration"], laufende)
            continue
        masse = MASSE.match(zeile.strip())
        if masse and laufende:
            try:
                wert = float(masse.group(1))
            except ValueError:
                continue
            ergebnis["massen"].append((laufende, wert))
            ergebnis["masse"] = wert
    if "Job finished" in text:
        ergebnis["fertig"] = True
    return ergebnis
