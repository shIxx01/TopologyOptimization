# SPDX-License-Identifier: LGPL-3.0-or-later
"""The bundled beso optimizer (see beso/CHANGES-TopoOpt.md).

beso ships with this addon, so a user installs the workbench and can start - there is
no second download and no path to configure.  The folder is looked up relative to this
file, so it works wherever FreeCAD put the addon.

The beso modules keep their own names ("beso_lib", ...) because they import each other
that way ("import beso_lib" inside beso_filters).  They are put into ``sys.modules``
directly - nothing is added to ``sys.path``, and loading happens once.
"""

import importlib.util
import os
import sys

#: folder of the bundled beso (…/TopoOpt/beso)
ORDNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "beso")

#: files beso needs for an optimization and for reading the input file
DATEIEN = ("beso_main.py", "beso_lib.py", "beso_filters.py", "beso_plots.py",
           "beso_separate.py", "beso_conf.py")


def pruefe():
    """(folder, list of missing files) - so the dialog can say what is wrong."""
    fehlend = [name for name in DATEIEN if not os.path.isfile(os.path.join(ORDNER, name))]
    return ORDNER, fehlend


def _lade(name):
    """Load one beso module from the addon folder (once)."""
    if name in sys.modules:                      # already loaded by us or by beso
        return sys.modules[name]
    pfad = os.path.join(ORDNER, "%s.py" % name)
    spec = importlib.util.spec_from_file_location(name, pfad)
    if spec is None or spec.loader is None:
        raise ImportError("beso: %s nicht gefunden (%s)" % (name, ORDNER))
    modul = importlib.util.module_from_spec(spec)
    # registered under its own name BEFORE it is executed: beso_filters does
    # "import beso_lib" and must find it
    sys.modules[name] = modul
    spec.loader.exec_module(modul)
    return modul


def module():
    """beso_lib and beso_filters from the bundled beso."""
    return _lade("beso_lib"), _lade("beso_filters")
