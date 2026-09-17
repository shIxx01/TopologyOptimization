# SPDX-License-Identifier: LGPL-3.0-or-later
"""The TopoOpt workbench."""

import FreeCAD as App
import FreeCADGui as Gui

from .commands.create_optimization import CreateOptimizationCommand
from .core.i18n import uebersetze
from .resources import icon


class TopoOptWorkbench(Gui.Workbench):
    """Workbench with a single entry point: create a topology optimization."""

    MenuText = "TopoOpt"
    ToolTip = uebersetze("Topology optimization with CalculiX (beso)")
    Icon = icon("TopoOpt-wb.svg")

    def Initialize(self):
        self.commands = [CreateOptimizationCommand.Name]
        self.appendToolbar("TopoOpt", self.commands)
        self.appendMenu("TopoOpt", self.commands)

    def GetClassName(self):
        return "Gui::PythonWorkbench"

    @classmethod
    def Install(cls):
        """Register the workbench once (addWorkbench raises on a second call)."""
        try:
            if cls.MenuText in Gui.listWorkbenches():
                return
            Gui.addWorkbench(cls())
        except Exception as exc:  # never break the FreeCAD start
            App.Console.PrintError("TopoOpt: workbench not registered (%s)\n" % exc)
