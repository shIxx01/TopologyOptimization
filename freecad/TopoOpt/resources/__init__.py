# SPDX-License-Identifier: LGPL-3.0-or-later
"""Paths to the resources of the addon."""

import os

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:  # pragma: no cover - only if executed without a file
    import FreeCAD as App

    _HERE = os.path.join(App.getUserAppDataDir(), "Mod", "TopologyOptimization", "freecad", "TopoOpt", "resources")

ICON_DIR = os.path.join(os.path.dirname(_HERE), "resources", "icons")


def icon(name):
    """Absolute path of an icon file inside resources/icons."""
    return os.path.join(ICON_DIR, name)
