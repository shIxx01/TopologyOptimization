# SPDX-License-Identifier: LGPL-3.0-or-later
"""GUI entry point - FreeCAD imports this file when a GUI is available.

FreeCAD loads the addon in this order:
    1. freecad.TopoOpt.__init__        (always, also in console mode)
    2. freecad.TopoOpt.init_gui        (only with GUI)
Keep it fast: it runs on every start of FreeCAD.
"""

import FreeCAD as App

try:
    from .commands.create_optimization import CreateOptimizationCommand
    from .workbench import TopoOptWorkbench

    CreateOptimizationCommand.Install()
    TopoOptWorkbench.Install()
except Exception as exc:  # never break the start of FreeCAD
    App.Console.PrintError("TopoOpt: GUI could not be loaded (%s)\n" % exc)
