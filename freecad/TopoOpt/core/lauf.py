# SPDX-License-Identifier: LGPL-3.0-or-later
"""Read the progress of a beso run from its log files.

beso writes two files next to the input file:

* ``<mesh>.log`` - beso's own protocol.  It contains the **table of iterations**,
  which is the source for the charts::

       i              mass    ener_dens_mean
       0 19999.99999999998                0.0
       1 19369.413573798036                0.0

  With a failure index (``domain_FI``) the table has four more columns
  (``FI_violated``, ``FI_mean``, ``FI_mean_without_state0``, ``FI_max``).
* ``<mesh>_topoopt.log`` - what the run prints (CalculiX output); this addon writes it
  and shows the last lines in the "Details" field.

Nothing here blocks: the files are simply read while the run goes on.
"""

import os
import re

START = re.compile(r"initial optimization domains mass\s+([0-9.eE+-]+)")
ITERATION = re.compile(r"new iteration number\s+(\d+)")
MASSE = re.compile(r"^mass\s*=\s*([0-9.eE+-]+)", re.MULTILINE)

# die Iterationstabelle: i, mass, ener_dens_mean und - mit Failure Index - vier weitere
TABELLE = re.compile(
    r"^\s*(\d+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)"
    r"(?:\s+(\d+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+))?\s*$")


def tabelle_lesen(beso_log):
    """Die Iterationstabelle aus der beso-Logdatei.

    Returns [(iteration, {"mass":…, "ener":…, "fi_violated":…, "fi_mean":…, "fi_max":…}), …]
    in der Reihenfolge der Datei; leere Liste, wenn es die Datei nicht gibt.
    """
    ergebnis = []
    if not beso_log or not os.path.isfile(beso_log):
        return ergebnis
    try:
        with open(beso_log, encoding="utf8", errors="replace") as fh:
            for zeile in fh:
                treffer = TABELLE.match(zeile)
                if not treffer:
                    continue
                try:
                    werte = {"mass": float(treffer.group(2)), "ener": float(treffer.group(3))}
                    if treffer.group(4) is not None:
                        werte["fi_violated"] = int(treffer.group(4))
                        werte["fi_mean"] = float(treffer.group(5))
                        werte["fi_mean_ohne"] = float(treffer.group(6))
                        werte["fi_max"] = float(treffer.group(7))
                except (TypeError, ValueError):
                    continue
                ergebnis.append((int(treffer.group(1)), werte))
    except OSError:
        return []
    return ergebnis


def fortschritt(beso_log, ziel_anteil=None):
    """Was die Tabelle über den Lauf sagt.

    Returns a dict with ``start`` (mass of iteration 0), ``ziel`` (when
    ``ziel_anteil`` is given), ``iteration``, ``masse``, ``massen`` [(i, mass), …] and
    ``werte`` (the whole table for the charts).
    """
    tabelle = tabelle_lesen(beso_log)
    ergebnis = {"start": None, "ziel": None, "iteration": 0, "masse": None, "massen": [],
                "werte": tabelle}
    if not tabelle:
        return ergebnis
    ergebnis["start"] = tabelle[0][1].get("mass")
    ergebnis["iteration"] = tabelle[-1][0]
    ergebnis["masse"] = tabelle[-1][1].get("mass")
    ergebnis["massen"] = [(i, werte.get("mass")) for i, werte in tabelle]
    if ergebnis["start"] and ziel_anteil:
        ergebnis["ziel"] = ergebnis["start"] * float(ziel_anteil)
    return ergebnis


def anteil(start, masse, ziel_anteil):
    """Wie weit der Lauf ist, in Prozent (0 = Startmasse, 100 = Zielmasse)."""
    if not start or not masse:
        return 0.0
    ziel = min(max(float(ziel_anteil or 0.0), 0.01), 0.99)
    return max(0.0, min(100.0, (start - masse) / (start * (1.0 - ziel)) * 100.0))


def verlauf_lesen(log_pfad, ziel_anteil=None):
    """Unser eigenes Protokoll (<mesh>_topoopt.log) für das Detail-Feld.

    Returns a dict with ``text`` (whole file), ``iteration``, ``massen`` and ``fertig``.
    """
    ergebnis = {"text": "", "iteration": 0, "massen": [], "fertig": False,
                "start": None, "ziel": None}
    if not log_pfad or not os.path.isfile(log_pfad):
        return ergebnis
    try:
        with open(log_pfad, encoding="utf8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return ergebnis
    ergebnis["text"] = text
    start = START.search(text)
    if start:
        try:
            ergebnis["start"] = float(start.group(1))
            if ziel_anteil:
                ergebnis["ziel"] = ergebnis["start"] * float(ziel_anteil)
        except ValueError:
            pass
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
                ergebnis["massen"].append((laufende, float(masse.group(1))))
            except ValueError:
                continue
    if "Job finished" in text:
        ergebnis["fertig"] = True
    return ergebnis
