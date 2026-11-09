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

SHORT_FORM = re.compile(r"^\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*$")
ATTRIBUTE = re.compile(r"([A-Za-z_]+)\s*=\s*\"?([^,\"]+)\"?")


def _attribute(line):
    """All KEY=VALUE attributes of a card line, keys in upper case."""
    result = {}
    for key, value in ATTRIBUTE.findall(line):
        result[key.strip().upper()] = value.strip()
    return result


def _is_number(text):
    return text.lstrip("-").isdigit()


def _raw_data(inp_path):
    """{set name: (number of own elements, [referenced set names])}."""
    raw = {}
    if not inp_path or not os.path.isfile(inp_path):
        return raw

    current = None
    mode = None          # "elemente" (from *ELEMENT) or "elset" (from *ELSET)
    generate = False
    try:
        with open(inp_path, "r", encoding="utf8", errors="ignore") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("*"):
                    kind = stripped.upper()
                    attrs = _attribute(stripped)
                    if kind.startswith("*ELEMENT"):
                        current, mode, generate = attrs.get("ELSET"), "elemente", False
                    elif kind.startswith("*ELSET"):
                        current, mode = attrs.get("ELSET"), "elset"
                        generate = "GENERATE" in kind
                    else:
                        current, mode, generate = None, None, False
                    if current:
                        raw.setdefault(current, [0, []])
                    continue
                if not current or not stripped:
                    continue
                if mode == "elemente":
                    if _is_number(stripped.split(",")[0].strip()):
                        raw[current][0] += 1
                    continue
                if generate:
                    match = SHORT_FORM.match(stripped)
                    if match:
                        start, end, step = (int(g) for g in match.groups())
                        if step:
                            raw[current][0] += max(0, (end - start) // step + 1)
                    continue
                # normal notation: element numbers (up to 16 per line) or
                # a reference to another set name
                for part in (t.strip() for t in stripped.split(",")):
                    if not part:
                        continue
                    if _is_number(part):
                        raw[current][0] += 1
                    elif part not in raw[current][1]:
                        raw[current][1].append(part)
    except OSError:
        return {}
    return {name: (count, refs) for name, (count, refs) in raw.items()}


def read_elsets(inp_path):
    """Element sets of an .inp as {name: number of elements} (references resolved)."""
    raw = _raw_data(inp_path)
    result = {}

    def resolve(name, seen):
        if name in result:
            return result[name]
        if name not in raw or name in seen:      # cycle or unknown
            return 0
        seen = seen | {name}
        count, refs = raw[name]
        for target in refs:
            count += resolve(target, seen)
        result[name] = count
        return count

    for name in raw:
        resolve(name, set())
    return result


def read_shell_thicknesses(inp_path):
    """Shell thicknesses from the ``*SHELL SECTION`` cards: ``{elset: thickness_mm}``.

    FreeCAD writes a separate card for every surface elset::

        *SHELL SECTION, ELSET=MaterialSolidElementGeometry2D, MATERIAL=MaterialSolid, OFFSET=0
        10

    This makes the assignment element set -> thickness **unambiguous**, even when a
    model has several thicknesses (then there are several cards) - nothing has to be
    guessed.  A volume model has no such card; the result is empty then.
    """
    thicknesses = {}
    if not inp_path or not os.path.isfile(inp_path):
        return thicknesses
    current = None
    pending = False
    try:
        with open(inp_path, "r", encoding="utf8", errors="ignore") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("*"):
                    attrs = _attribute(stripped)
                    if stripped.upper().startswith("*SHELL SECTION") and attrs.get("ELSET"):
                        current = attrs["ELSET"]
                        pending = True
                        continue
                    current, pending = None, False
                    continue
                if not stripped or not pending or current is None:
                    continue
                # the first number on the card is the thickness
                try:
                    thicknesses[current] = float(stripped.split(",")[0].strip())
                except ValueError:
                    pass
                pending = False
    except OSError:
        return {}
    return thicknesses


def read_section_materials(inp_path):
    """Material per element set from the section cards: ``{elset: material name}``.

    FreeCAD writes the finished assignment into the input file::

        *SOLID SECTION, ELSET=MaterialSolidSolid, MATERIAL=MaterialSolid

    This makes it unambiguous which material CalculiX uses for this set - even
    when a model contains several materials.  It is therefore the truth and not
    the name of the set (which only *looks* like the material).
    """
    assignment = {}
    if not inp_path or not os.path.isfile(inp_path):
        return assignment
    try:
        with open(inp_path, "r", encoding="utf8", errors="ignore") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped.startswith("*"):
                    continue
                upper_line = stripped.upper()
                if not (upper_line.startswith("*SOLID SECTION") or upper_line.startswith("*SHELL SECTION")):
                    continue
                attrs = _attribute(stripped)
                if attrs.get("ELSET") and attrs.get("MATERIAL"):
                    assignment[attrs["ELSET"]] = attrs["MATERIAL"]
    except OSError:
        return {}
    return assignment


def check_inp(inp_path, sets=None):
    """Is the input file complete - and does every element set have a material?

    A file that was interrupted in the middle of writing does not always stand
    out: FreeCAD writes nodes, elements and materials and only then the
    section cards, the ``*STEP`` and the boundary conditions.  CalculiX then
    computes nothing, the result file stays empty, and beso only reports
    "CalculiX results not found" - without saying what the cause is.

    In addition every element set the optimization knows about needs a
    section card (``*SOLID SECTION``/``*SHELL SECTION``).  If it is missing, the
    set belongs to no body-material assignment (typical: a material was placed
    on surfaces) and CalculiX leaves the elements out.

    Returns ``{"present": bool, "missing_cards": [card, ...],
    "without_material": [set, ...]}``
    """
    result = {"present": False, "missing_cards": [], "without_material": []}
    if not inp_path or not os.path.isfile(inp_path):
        return result
    result["present"] = True
    cards = {"*STEP": False, "*MATERIAL": False}
    section_sets = set()
    try:
        with open(inp_path, "r", encoding="utf8", errors="ignore") as fh:
            for line in fh:
                if not line.startswith("*"):
                    continue
                upper_line = line.strip().upper()
                for name in cards:
                    if upper_line.startswith(name):
                        cards[name] = True
                if upper_line.startswith("*SOLID SECTION") or upper_line.startswith("*SHELL SECTION"):
                    elset = _attribute(line).get("ELSET")
                    if elset:
                        section_sets.add(elset)
    except OSError:
        return result
    # *MATERIAL and *STEP stand in the second half: if one is missing, the file was
    # interrupted while writing (boundary conditions are deliberately NOT checked -
    # a model can also be written without them)
    result["missing_cards"] = [name for name in ("*MATERIAL", "*STEP")
                               if not cards[name]]
    if sets:
        result["without_material"] = sorted(name for name in sets if name not in section_sets)
    return result


def total_elements(inp_path):
    """Number of elements in the mesh (from the *ELEMENT cards)."""
    raw = _raw_data(inp_path)
    return max([count for count, _ in raw.values()] or [0])


def element_types(inp_path):
    """Set of element types from the *ELEMENT cards, e. g. ["C3D10"]."""
    types = []
    if not inp_path or not os.path.isfile(inp_path):
        return types
    try:
        with open(inp_path, "r", encoding="utf8", errors="ignore") as fh:
            for line in fh:
                if not line.lstrip().upper().startswith("*ELEMENT"):
                    continue
                element_type = _attribute(line).get("TYPE", "").upper()
                if element_type and element_type not in types:
                    types.append(element_type)
    except OSError:
        pass
    return types


def solver_keyword(inp_path):
    """The matrix solver the input file asks for ("" when it asks for none).

    FreeCAD writes the *Solver type* of its CalculiX solver as an attribute of the
    analysis card (``*STATIC, SOLVER=PASTIX``).  A ccx that was built without that
    library then stops with "*ERROR ... the PASTIX library is not linked", which
    looks like a broken model.  Knowing the request lets the assistant say it
    before the run.
    """
    if not inp_path or not os.path.isfile(inp_path):
        return ""
    try:
        with open(inp_path, "r", encoding="utf8", errors="ignore") as fh:
            for line in fh:
                if not line.startswith("*"):
                    continue
                solver = _attribute(line).get("SOLVER", "")
                if solver:
                    return solver.upper()
    except OSError:
        pass
    return ""
