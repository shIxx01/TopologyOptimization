# SPDX-License-Identifier: LGPL-3.0-or-later
"""Parameters of the optimization.

The values and the names are taken from beso itself (beso_conf.py of the
upstream project) - nothing here is invented:

* ``mass_goal_ratio = 0.4``            target mass as a fraction
* ``optimization_base = "stiffness"``  "stiffness", "buckling", "heat",
                                       "failure_index"
* ``filter_list = [["simple", "auto"]]``
                                       [[type, range, domain, ...], ...] with the
                                       types "simple" and "casting" (casting needs
                                       a direction vector: ("casting", 2., (0, 0, 1)))
* ``mass_addition_ratio``/``mass_removal_ratio`` differ per speed setting
* ``iterations_limit = "auto"``        or a number
* ``tolerance = 1e-3``
* ``cpu_cores = 0``                    0 = all cores
* ``save_iteration_results = 1``       0 = only the final result
* ``save_resulting_format = "inp vtk"`` or "frd"
"""

import ast

# what can be optimized (beso_lib/beso_main decide on these strings)
BASES = ("stiffness", "buckling", "heat", "failure_index")

# how fast the mass is changed, taken from the speed slider of the beso GUI
MASS_CHANGE = {
    "gentle": (0.01, 0.02),
    "normal": (0.015, 0.03),
    "fast": (0.03, 0.06),
}

# the filter types beso knows (beso_conf.py, section "filter types"): the morphology
# filters work on the sensitivities ("... sensitivity") or on the element states
# ("... state").  "over points" is documented in beso itself as "does not work
# correctly, need a fix", "over nodes" is not offered (it needs a lot of memory for
# 2nd order elements and is the slowest of all).
FILTER_TYPES = (
    "simple",               # averages the sensitivity over all elements in the radius
    "erode sensitivity",    # minimum sensitivity number in the radius
    "dilate sensitivity",   # maximum sensitivity number in the radius
    "open sensitivity",     # erode then dilate - removes elements smaller than the radius
    "close sensitivity",    # dilate then erode - closes holes smaller than the radius
    "open-close sensitivity",
    "close-open sensitivity",
    "combine sensitivity",  # average of erode and dilate
    "casting",              # demouldable in one direction
)
# the types that are not manufacturing filters (casting has a direction instead of a
# plain radius)
MORPHOLOGY_TYPES = FILTER_TYPES[1:8]

FORMATS = ("inp vtk", "frd")

DEFAULT_FILTERS = [["simple", "auto"]]


def mass_ratios(speed):
    """(addition, removal) for a speed setting, beso default for unknown values."""
    return MASS_CHANGE.get(speed, MASS_CHANGE["normal"])


def format_filters(filters):
    """Sensitivity filters as the text stored in the object."""
    return repr([list(f) for f in filters])


def parse_filters(text):
    """Read the filters back. Unknown text gives the default filter."""
    if not text:
        return [list(f) for f in DEFAULT_FILTERS]
    try:
        # ast.literal_eval and not eval: the text comes from a document file and
        # only ever contains a list of lists of numbers and strings
        roh = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return [list(f) for f in DEFAULT_FILTERS]
    ergebnis = []
    for eintrag in roh:
        if not isinstance(eintrag, (list, tuple)) or len(eintrag) < 2:
            continue
        typ = str(eintrag[0])
        if typ not in FILTER_TYPES:
            continue
        reichweite = eintrag[1]
        if not isinstance(reichweite, (int, float)):
            reichweite = "auto"
        rest = [str(w) for w in eintrag[2:]]
        ergebnis.append([typ, reichweite] + rest)
    return ergebnis or [list(f) for f in DEFAULT_FILTERS]
