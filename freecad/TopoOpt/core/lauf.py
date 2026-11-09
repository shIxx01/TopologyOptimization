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
MASS = re.compile(r"^mass\s*=\s*([0-9.eE+-]+)", re.MULTILINE)

# The iteration table has a different number of columns depending on the model: the
# header starts with "i  mass  ener_dens_mean" (or heat_flux_mean) and gets more with
# a failure index: FI_violated per domain (plus "all" when there is more than one
# domain), FI_mean, FI_mean_without_state0 and FI_max per domain (also with "all").
# Measured: 3 columns, 4 with a failure index and one domain, 8 with two domains -
# which is why the columns are assigned through the header.
HEADER_MARKERS = {"mass": "mass", "ener_dens_mean": "ener", "heat_flux_mean": "ener",
                  "FI_mean": "fi_mean", "_without_state0": "fi_mean_without_state0"}


def _header_positions(line):
    """Positions of the known columns, taken from the header row of the iteration table."""
    tokens = line.split()
    positions = {}
    for number, token in enumerate(tokens):
        for marker, name in HEADER_MARKERS.items():
            if token == marker or (marker.startswith("FI_") and token.startswith(marker)):
                positions[name] = number
    if "fi_mean" in positions:
        # the combined "all" column sits directly before FI_mean, otherwise it is the only domain
        positions["fi_violated"] = positions["fi_mean"] - 1
    if positions.get("fi_mean"):
        # FI_max: the last column of the table is "all" (or the only domain)
        positions["fi_max"] = len(tokens) - 1
    return positions


def read_table(beso_log):
    """The iteration table from beso's log file.

    Returns [(iteration, {"mass":…, "ener":…, "fi_violated":…, "fi_mean":…, "fi_max":…}), …]
    in the order of the file; an empty list when the file does not exist.
    """
    result = []
    if not beso_log or not os.path.isfile(beso_log):
        return result
    positions = {}
    try:
        with open(beso_log, encoding="utf8", errors="replace") as fh:
            for line in fh:
                if "mass" in line and ("ener_dens_mean" in line or "heat_flux_mean" in line):
                    positions = _header_positions(line)
                    continue
                if not positions:
                    continue
                fields = line.split()
                if len(fields) <= max(positions.values()):
                    continue
                if not fields[0].isdigit():
                    continue
                try:
                    values = {"mass": float(fields[positions["mass"]]),
                              "ener": float(fields[positions["ener"]])}
                    for name in ("fi_violated", "fi_mean", "fi_mean_without_state0", "fi_max"):
                        if name in positions:
                            values[name] = float(fields[positions[name]])
                    if "fi_violated" in values:
                        values["fi_violated"] = int(values["fi_violated"])
                except (TypeError, ValueError, IndexError):
                    continue
                result.append((int(fields[0]), values))
    except OSError:
        return []
    return result


def progress(beso_log, target_ratio=None):
    """What the table says about the run.

    Returns a dict with ``start`` (mass of iteration 0), ``target`` (when
    ``target_ratio`` is given), ``iteration``, ``mass``, ``masses`` [(i, mass), …] and
    ``values`` (the whole table for the charts).
    """
    table = read_table(beso_log)
    result = {"start": None, "target": None, "iteration": 0, "mass": None, "masses": [],
              "values": table}
    if not table:
        return result
    result["start"] = table[0][1].get("mass")
    result["iteration"] = table[-1][0]
    result["mass"] = table[-1][1].get("mass")
    result["masses"] = [(i, values.get("mass")) for i, values in table]
    if result["start"] and target_ratio:
        result["target"] = result["start"] * float(target_ratio)
    return result


def ratio(start, mass, target_ratio):
    """How far the run has come, in percent (0 = start mass, 100 = target mass)."""
    if not start or not mass:
        return 0.0
    target = min(max(float(target_ratio or 0.0), 0.01), 0.99)
    return max(0.0, min(100.0, (start - mass) / (start * (1.0 - target)) * 100.0))


def read_history(log_path, target_ratio=None):
    """Our own protocol (<mesh>_topoopt.log) for the details field.

    Returns a dict with ``text`` (whole file), ``iteration``, ``masses`` and ``done``.
    """
    result = {"text": "", "iteration": 0, "masses": [], "done": False,
              "start": None, "target": None}
    if not log_path or not os.path.isfile(log_path):
        return result
    try:
        with open(log_path, encoding="utf8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return result
    result["text"] = text
    start = START.search(text)
    if start:
        try:
            result["start"] = float(start.group(1))
            if target_ratio:
                result["target"] = result["start"] * float(target_ratio)
        except ValueError:
            pass
    running = 0
    for line in text.splitlines():
        number = ITERATION.search(line)
        if number:
            running = int(number.group(1))
            result["iteration"] = max(result["iteration"], running)
            continue
        mass = MASS.match(line.strip())
        if mass and running:
            try:
                result["masses"].append((running, float(mass.group(1))))
            except ValueError:
                continue
    if "Job finished" in text:
        result["done"] = True
    return result


def missing_library(text):
    """Which CalculiX library the log says is missing ("" when it says none).

    A ccx built without PaStiX/PARDISO answers an input file that asks for them with
    ``*ERROR in linstatic: the PASTIX library is not linked`` and exits.  That reads
    like a broken model; naming the library turns it into an instruction.
    """
    upper = (text or "").upper()
    for name in ("PASTIX", "PARDISO"):
        if "%s LIBRARY IS NOT LINKED" % name in upper:
            return name
    return ""
