#!/usr/bin/env python
# SPDX-License-Identifier: LGPL-3.0-or-later
"""GUI test of the addon.

GUI FreeCAD writes nothing to stdout, so this script writes its result into
tests/gui_test_ausgabe.txt and quits FreeCAD afterwards:

    rm -f tests/gui_test_ausgabe.txt
    ("<FreeCAD>/bin/freecad.exe" "C:/.../tests/gui_test.py" >/dev/null 2>&1 &)
    # wait for the file, then read it

Checks: workbench registered and activatable, toolbar and menu present, icons
exist, the command works with and without an active analysis.
"""

import os
import sys
import traceback

HIER = os.path.dirname(os.path.abspath(__file__))
AUSGABE = os.path.join(HIER, "gui_test_ausgabe.txt")
zeilen = []
fehler = []


def log(text):
    zeilen.append(str(text))


def pruefe(bedingung, text):
    log("%-5s %s" % ("OK" if bedingung else "FEHLT", text))
    if not bedingung:
        fehler.append(text)


try:
    import FreeCAD as App
    import FreeCADGui as Gui
    from PySide import QtWidgets

    log("FreeCAD %s" % ".".join(App.Version()[:3]))

    from freecad.TopoOpt.commands.create_optimization import (
        CreateOptimizationCommand,
        active_analysis,
    )

    # 1. Workbench
    workbenches = list(Gui.listWorkbenches().keys())
    pruefe("TopoOptWorkbench" in workbenches, "Workbench TopoOptWorkbench ist registriert")
    if "TopoOptWorkbench" in workbenches:
        Gui.activateWorkbench("TopoOptWorkbench")
        Gui.updateGui()
        fenster = Gui.getMainWindow()
        toolbars = [tb.objectName() for tb in fenster.findChildren(QtWidgets.QToolBar)]
        menus = [m.title() for m in fenster.menuBar().findChildren(QtWidgets.QMenu)]
        pruefe("TopoOpt" in toolbars, "Toolbar 'TopoOpt' vorhanden")
        pruefe("TopoOpt" in menus, "Menue 'TopoOpt' vorhanden")
        wb = Gui.listWorkbenches()["TopoOptWorkbench"]
        pruefe(os.path.isfile(wb.Icon), "Workbench-Icon existiert (%s)" % wb.Icon)

    # 2. Command and icon
    command = CreateOptimizationCommand()
    res = command.GetResources()
    pruefe(command.Name == "TopoOpt_CreateOptimization", "Befehlsname ist TopoOpt_CreateOptimization")
    pruefe(os.path.isfile(res["Pixmap"]), "Befehlssymbol existiert (%s)" % res["Pixmap"])
    log("     MenuText: %s" % res["MenuText"])

    # 3. no analysis
    doc = App.newDocument("TopoOptGuiTest")
    pruefe(active_analysis() is None, "ohne Analyse ist keine aktiv")

    # 4. analysis present and active
    analysis = doc.addObject("Fem::FemAnalysis", "Analysis")
    doc.recompute()
    import FemGui
    FemGui.setActiveAnalysis(analysis)
    pruefe(active_analysis() is analysis, "aktive Analyse wird gefunden")

    command.Activated()
    doc.recompute()
    obj = doc.getObject("TopologieOptimierung")
    pruefe(obj is not None, "Befehl hat das Objekt angelegt")
    if obj is not None:
        pruefe(obj.Name in [o.Name for o in analysis.Group], "Objekt liegt in der Analyse")
        pruefe(os.path.isfile(obj.ViewObject.Proxy.getIcon()), "Objektsymbol existiert")

    App.closeDocument(doc.Name)
    log("ERGEBNIS: %s" % ("OK" if not fehler else "%d FEHLER" % len(fehler)))
except Exception:
    log("AUSNAHME:\n" + traceback.format_exc())
    fehler.append("Ausnahme")
finally:
    with open(AUSGABE, "w", encoding="utf8") as f:
        f.write("\n".join(zeilen) + "\n")
    sys.exit(1 if fehler else 0)
