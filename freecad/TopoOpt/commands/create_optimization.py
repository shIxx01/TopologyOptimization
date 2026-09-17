# SPDX-License-Identifier: LGPL-3.0-or-later
"""The command that creates a topology optimization.

The optimization belongs to a FEM analysis, so the command follows the same rule
as the FEM commands themselves: an analysis has to be *active* (shown in bold in
the tree, FemGui.setActiveAnalysis).  Without an active analysis the user gets a
hint instead of a silently created object somewhere in the document.
"""

import FreeCAD as App
import FreeCADGui as Gui

from ..features import create_topology_object
from ..resources import icon

translate = App.Qt.translate


def active_analysis():
    """The analysis that is currently active, or None."""
    try:
        import FemGui
    except ImportError:  # FEM workbench not available
        return None
    try:
        return FemGui.getActiveAnalysis()
    except Exception:
        return None


class CreateOptimizationCommand:
    """Add a topology optimization to the active FEM analysis."""

    Name = "TopoOpt_CreateOptimization"

    def GetResources(self):
        return {
            "Pixmap": icon("TopoOpt.svg"),
            "MenuText": translate("TopoOpt", "Topologie-Optimierung"),
            "ToolTip": translate("TopoOpt",
                                 "Neue Topologie-Optimierung in der aktiven FEM-Analyse anlegen"),
        }

    def IsActive(self):
        return Gui.ActiveDocument is not None

    def Activated(self):
        doc = App.ActiveDocument
        if doc is None:
            return
        analysis = active_analysis()
        if analysis is None:
            self._hint_no_analysis()
            return
        obj = create_topology_object(doc, analysis)
        doc.recompute()
        App.Console.PrintMessage(
            "TopoOpt: '%s' wurde der Analyse '%s' hinzugefuegt.\n" % (obj.Label, analysis.Label))

    def _hint_no_analysis(self):
        from PySide import QtWidgets
        QtWidgets.QMessageBox.information(
            Gui.getMainWindow(),
            translate("TopoOpt", "Keine aktive Analyse"),
            translate("TopoOpt",
                      "Bitte zuerst eine FEM-Analyse im Modellbaum aktivieren "
                      "(Doppelklick oder Rechtsklick > Analyse aktivieren).\n\n"
                      "Die Topologie-Optimierung wird dieser Analyse hinzugefuegt."))

    @classmethod
    def Install(cls):
        try:
            Gui.addCommand(cls.Name, cls())
        except Exception as exc:  # never break the FreeCAD start
            App.Console.PrintError("TopoOpt: command not registered (%s)\n" % exc)
