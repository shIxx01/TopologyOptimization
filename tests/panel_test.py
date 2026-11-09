#!/usr/bin/env python
# SPDX-License-Identifier: LGPL-3.0-or-later
"""Integration test of the assistant with a real FEM document.

The dialog cannot be checked without a document that contains a FEM analysis
with a mesh (a mesh is expensive to build in the test itself), so this test takes
the path of a document as argument - it works on a **copy** in the temp directory
and never writes to the original:

    ("<FreeCAD>/bin/freecad.exe" "C:/.../tests/panel_test.py" "C:/.../mein.FCStd" &)
    # wait for tests/panel_test_ausgabe.txt, then read it

Checks: the .inp is written into the working directory, the table lists the
element sets with their sizes, collector sets (Eall, Evolumes) are hidden, the
first free set is suggested as design space, and a change in the table is stored
in the document object.
"""

import os
import time
import shutil
import sys
import tempfile
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(HERE, "panel_test_ausgabe.txt")
lines = []
errors = []


def log(text):
    lines.append(str(text))


def check(condition, text):
    log("%-5s %s" % ("OK" if condition else "FEHLT", text))
    if not condition:
        errors.append(text)


try:
    # FreeCAD does not pass script arguments through sys.argv, so the document is
    # given in an environment variable (see Documentation/development.md)
    source = os.environ.get("TOPOOPT_TEST_DOKUMENT", "") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if source.lower().endswith(".py"):
        source = ""          # never treat a script as a document
    if not source or not os.path.isfile(source):
        raise SystemExit("Aufruf: TOPOOPT_TEST_DOKUMENT=<dokument.FCStd> freecad.exe "
                         "tests/panel_test.py")

    import FreeCAD as App

    from freecad.TopoOpt.features import create_topology_object
    from freecad.TopoOpt.gui import assistant as assist
    from freecad.TopoOpt.gui.assistant import AssistantPanel
    from freecad.TopoOpt.core import domains as dom

    copy = os.path.join(tempfile.gettempdir(), "TopoOpt_PanelTest.FCStd")
    if os.path.exists(copy):
        os.remove(copy)
    shutil.copy(source, copy)
    if os.path.getsize(copy) < 1000:                 # a document is never that small
        raise SystemExit("Die Kopie von %s sieht nicht wie ein Dokument aus." % source)
    doc = App.openDocument(copy)
    log("Dokument: %s (%d Objekte)" % (doc.Name, len(doc.Objects)))

    analyses = [o for o in doc.Objects if o.TypeId.startswith("Fem::FemAnalysis")]
    check(bool(analyses), "das Testdokument enthaelt eine FEM-Analyse")
    if not analyses:
        raise SystemExit(1)
    analysis = analyses[0]
    log("Analyse: %s | Kinder: %s" % (analysis.Name, [o.Name for o in analysis.Group]))

    obj = create_topology_object(doc, analysis)
    panel = AssistantPanel(obj)
    panel.load()          # load right away, do not wait for the timer

    log("Status : %s" % panel.status.text())
    log("Kopf   : %s" % panel.header.text())
    log("Arbeit : %s" % obj.WorkingDir)

    # Nothing may be created when the panel is opened
    if not obj.InpFile:
        check(panel.table.rowCount() == 0, "ohne Eingabedatei bleibt die Tabelle leer")
        check(bool(panel.status.text()), "Hinweis auf fehlende Eingabedatei vorhanden")
        log("keine Eingabedatei vorhanden -> Button wird geklickt")
        panel._write_inp()

    check(bool(obj.InpFile) and os.path.isfile(obj.InpFile),
           "CalculiX-Eingabedatei vorhanden (%s)" % obj.InpFile)
    log("Dateiinfo: %s" % panel.info.text())
    check(panel.table.rowCount() > 0, "Tabelle hat Zeilen (%d)" % panel.table.rowCount())
    check(bool(panel.status.text()), "Statusmeldung vorhanden: %s" % panel.status.text()[:110])
    check("(.inp)" in panel.inp_button.text(), "Knopf nennt die Dateiendung: %s"
           % panel.inp_button.text())
    check("Quelle" in panel.path_field.toolTip() or "Source" in panel.path_field.toolTip(),
           "Pfad-Tooltip nennt die Quelle: %s" % panel.path_field.toolTip().replace("\n", " | "))
    check("|" not in panel.info.text() and obj.WorkingDir not in panel.info.text(),
           "Dateizeile nennt nur Groesse und Stand: %s" % panel.info.text())
    check(panel.open_folder_button.isEnabled(), "Ordner-Knopf ist aktiv, wenn es die Datei gibt")
    check(obj.WorkingDir in panel.open_folder_button.toolTip(),
           "Ordner-Knopf nennt das Arbeitsverzeichnis im Tooltip")
    check("color" in panel.status.styleSheet(), "Hinweistext ist eingefaerbt (%s)"
           % panel.status.styleSheet())

    roles = {}
    for row in range(panel.table.rowCount()):
        name = panel.table.item(row, 0).text()
        field = panel.table.cellWidget(row, 1)
        count = panel.table.item(row, 2).text()
        roles[name] = field.currentText()
        log("  %-28s %-30s %s" % (name, field.currentText(), count))
        check(name.lower() not in ("eall", "evolumes", "efaces", "eedges", "enodes"),
               "'%s' ist kein Sammelset" % name)
    check(bool(obj.Domains), "Rollen im Objekt gespeichert: %s" % (obj.Domains,))
    check(any("design" in e for e in obj.Domains),
           "ein Design-Raum ist vorbelegt")

    # flip the role the way the table allows
    first = sorted(roles)[0]
    for row in range(panel.table.rowCount()):
        if panel.table.item(row, 0).text() == first:
            field = panel.table.cellWidget(row, 1)
            field.setCurrentIndex(1)                       # non-design space
    check(any(e.startswith(first + "|") and "non_design" in e for e in obj.Domains),
           "Aenderung in der Tabelle landet sofort im Objekt")

    # step 2: parameters
    panel._show_step(2)
    check(panel.pages.currentIndex() == 1, "Schritt 2 zeigt die Parameter-Seite")
    width = panel.form.minimumSizeHint().width()
    log("Mindestbreite des Panels: %d px" % width)
    check(width <= 360, "Panel laesst sich schmal ziehen (%d px)" % width)
    check(panel.cores_field.value() == 0
           and panel.cores_field.specialValueText() in ("all", "alle"),
           "Kerne zeigen '%s' statt der 0" % panel.cores_field.specialValueText())
    check(panel.save_field.value() == 10,
           "Speicher-Intervall startet bei 10 (%d)" % panel.save_field.value())
    check(panel.header.parent() is not panel.form,
           "Kopfzeile steckt in Schritt 1, nicht ueber allen Schritten")
    # the domain table is as high as its content, not higher
    header_height = panel.table.horizontalHeader().height()
    expected = header_height + panel.table.rowCount() * panel.table.rowHeight(0) + 8
    check(abs(panel.table.height() - expected) <= 12,
           "die Domain-Tabelle ist so hoch wie ihr Inhalt (%d px, erwartet ~%d)"
           % (panel.table.height(), expected))
    check(panel.table.height() < 200,
           "die Tabelle fuellt nicht den ganzen Schritt (%d px)" % panel.table.height())
    check(panel.step_label.parent() is panel.form,
           "Schrittleiste sitzt oben im Panel (ausserhalb des Rollbereichs)")
    check(len(panel.scroll_areas) == 3 and all(r.widget() is not None for r in panel.scroll_areas),
           "jede Seite hat ihre eigene Rollflaeche (%d)" % len(panel.scroll_areas))
    check(panel.scroll_areas[0].verticalScrollBar().maximum() == 0,
           "im ersten Schritt ist kein Rollbalken noetig (max %d)"
           % panel.scroll_areas[0].verticalScrollBar().maximum())

    # permissible stress: empty = no FI, value = FI (one column per domain)
    check(len(panel.stress_fields) == len(panel.elsets),
           "jede Domain hat ein Feld fuer die zulaessige Spannung (%d Felder)"
           % len(panel.stress_fields))
    first = sorted(panel.elsets)[0]
    check(panel.stress_fields[first].text() == "",
           "das Feld ist am Anfang leer (kein Failure Index)")
    panel.stress_fields[first].setText("235")
    check(panel.obj.StressLimits == ["%s|235.0" % first],
           "der Wert landet im Objekt (%s)" % (panel.obj.StressLimits,))
    check(first in panel.stress, "der Wert steht auch im Assistenten")
    panel.stress_fields[first].setText("")
    check(panel.obj.StressLimits == ["%s|0" % first],
           "leeres Feld nimmt die Spannung heraus und merkt sich das (%s)"
           % (panel.obj.StressLimits,))

    # material with a yield strength: the field stays empty anyway (the choice is up to
    # the user), the hint under the list names the possible value
    material_old = doc.getObject("MaterialSolid")
    values_old = dict(material_old.Material)
    values_new = dict(values_old)
    values_new["YieldStrength"] = "315 MPa"
    material_old.Material = values_new
    doc.recompute()
    panel.obj.StressLimits = []
    panel.stress = {}
    panel.stress_cleared = set()
    panel._fill_table()
    panel._material_suggestion()
    check(panel.stress_fields[first].text() == "",
           "das Feld bleibt leer, auch wenn das Material eine Streckgrenze hat (%s)"
           % panel.stress_fields[first].text())
    check(panel.obj.StressLimits == [],
           "ohne Eintrag wird nichts im Objekt gespeichert (%s)" % (panel.obj.StressLimits,))
    check(panel.stress_possible.get(first) == 315.0,
           "der moegliche Wert aus dem Material ist bekannt (%s)" % (panel.stress_possible,))
    check(not panel.stress_note.isHidden() and "315" in panel.stress_note.text(),
           "der Hinweis nennt den Materialwert (%s)" % panel.stress_note.text()[:70])
    panel.stress_fields[first].setText("200")
    check(panel.stress_note.isHidden(),
           "mit eingetragenem Wert verschwindet der Hinweis")
    panel.stress_fields[first].setText("")
    check(not panel.stress_note.isHidden()
           and "failure-index" in panel.stress_note.text().lower(),
           "ohne Wert weist der Hinweis auf den fehlenden Failure-Index hin (%s)"
           % panel.stress_note.text()[:70])
    # material without a yield strength: the hint names no value
    material_old.Material = values_old
    doc.recompute()
    panel.obj.StressLimits = []
    panel.stress = {}
    panel.stress_cleared = set()
    panel._fill_table()
    panel._material_suggestion()
    check(not panel.stress_note.isHidden() and "315" not in panel.stress_note.text(),
           "ohne Streckgrenze im Material nennt der Hinweis keinen Wert (%s)"
           % panel.stress_note.text()[:70])
    check(not panel.stress_note.isHidden()
           and "streckgrenze" in panel.stress_note.text().lower(),
           "stattdessen steht dort, dass keine Streckgrenze hinterlegt ist (%s)"
           % panel.stress_note.text()[:70])
    panel.obj.StressLimits = []
    panel.stress = {}
    panel._fill_table()
    doc.recompute()

    # sigma on only some of the domains -> red warning (beso aborts otherwise)
    panel.elsets["ZweitesSet"] = 100
    panel.domains["ZweitesSet"] = dom.DESIGN      # belongs to the optimization
    panel.stress = {first: 235.0}
    panel._show_stress_note()
    check(not panel.stress_note.isHidden()
           and "ZweitesSet" in panel.stress_note.text()
           and "#b04040" in panel.stress_note.styleSheet(),
           "sigma nur teilweise gesetzt wird rot gemeldet (%s)"
           % panel.stress_note.text()[:80])
    del panel.elsets["ZweitesSet"]
    del panel.domains["ZweitesSet"]
    panel.stress = {}
    panel.stress_cleared = set()
    panel._fill_table()

    # an ignored set needs no permissible stress
    panel.elsets["IgnoriertSet"] = 50
    panel.domains["IgnoriertSet"] = dom.IGNORE
    panel.stress = {}
    panel._show_stress_note()
    check("IgnoriertSet" not in panel.stress_note.text(),
           "ein ignoriertes Set verlangt kein sigma (%s)" % panel.stress_note.text()[:60])
    del panel.elsets["IgnoriertSet"]
    del panel.domains["IgnoriertSet"]
    panel._fill_table()

    # input file without a section card for a set -> red hint in step 1
    source = panel.obj.InpFile
    broken = os.path.join(tempfile.gettempdir(), "TopoOpt_PanelKaputt.inp")
    with open(source, encoding="utf8", errors="ignore") as in_file, \
            open(broken, "w", encoding="utf8") as out_file:
        for line in in_file:
            if line.upper().startswith("*SOLID SECTION"):
                continue                     # section card left out
            out_file.write(line)
    panel._adopt_inp(broken, "")
    check(not panel.inp_note.isHidden() and first in panel.inp_note.text(),
           "ohne Section-Karte warnt das Panel (%s)" % panel.inp_note.text()[:80])
    check("section" in panel.inp_note.text().lower(),
           "der Hinweis nennt die fehlende Karte")
    panel._adopt_inp(source, "")
    check(panel.inp_note.isHidden(),
           "mit vollstaendiger Datei verschwindet der Hinweis")

    # material without a Young's modulus -> hint with the material name (FreeCAD
    # would abort)
    material_probe = doc.getObject("MaterialSolid")
    values_probe = dict(material_probe.Material)
    without_e = dict(values_probe)
    without_e.pop("YoungsModulus", None)
    material_probe.Material = without_e
    doc.recompute()
    panel._fill_table()
    check(not panel.inp_note.isHidden() and "MaterialSolid" in panel.inp_note.text()
           and "YoungsModulus" in panel.inp_note.text(),
           "ein Material ohne E-Modul wird mit Namen gemeldet (%s)"
           % panel.inp_note.text()[:90])
    material_probe.Material = values_probe
    doc.recompute()
    panel._fill_table()
    check(panel.inp_note.isHidden(),
           "nach dem Ergaenzen der Werte verschwindet der Hinweis")

    # filters: the default is beso's [["simple", "auto"]]
    check(len(panel.filter_rows) == 1,
           "Standard: eine Filterzeile (%d)" % len(panel.filter_rows))
    check(panel.filter_rows[0]["type"].currentData() == "simple",
           "Filter 1 startet mit 'simple' (%s)" % panel.filter_rows[0]["type"].currentData())
    check(panel.filter_rows[0]["radius_mode"].currentData() == "robust",
           "Filter 1 startet mit 'robust' (%s)" % panel.filter_rows[0]["radius_mode"].currentData())
    check(panel.tolerance_field.text() in ("0,001", "0.001"),
           "Toleranz ohne Fuellnullen: %s" % panel.tolerance_field.text())

    # the robust radius is only computed on a button press (slow with fine meshes)
    # first put the role back to design space: without design space there is no radius
    for row in range(panel.table.rowCount()):
        if panel.table.item(row, 0).text() == first:
            panel.table.cellWidget(row, 1).setCurrentIndex(0)
    log("Radius-Info vor der Pruefung: %s" % panel.filter_rows[0]["radius_info"].text())
    check(panel.filter_rows[0]["radius_info"].text() in ("calculate", "berechnen"),
           "ohne Wert steht 'berechnen' im Feld (%s)" % panel.filter_rows[0]["radius_info"].text())
    check("color" in panel.filter_rows[0]["radius_info"].styleSheet(),
           "das 'berechnen' ist eingefaerbt (%s)" % panel.filter_rows[0]["radius_info"].styleSheet())
    check("robust" in obj.Filters, "robust steht im Objekt: %s" % obj.Filters)
    check(panel.filter_rows[0]["check"].isHidden() is False,
           "der Pruef-Knopf ist bei 'robust' sichtbar")
    check(panel.filter_rows[0]["check"].text() == "\u21bb",
           "der Pruef-Knopf ist das Pfeilsymbol (%r)" % panel.filter_rows[0]["check"].text())
    check(panel.filter_rows[0]["check"].toolTip() != "",
           "der Pruef-Knopf hat einen Tooltip")
    panel.filter_rows[0]["check"].click()
    log("Radius-Info nach der Pruefung: %s" % panel.filter_rows[0]["radius_info"].text())
    check(obj.RobusterRadius > 0, "robuster Radius ist berechnet (%.4f mm)"
           % obj.RobusterRadius)
    check("mm" in panel.filter_rows[0]["radius_info"].text()
           or "mm" in panel.filter_rows[0]["radius_info"].toolTip(),
           "die Filterzeile zeigt den berechneten Radius (%s)"
           % panel.filter_rows[0]["radius_info"].text())

    check(panel.add_filter_button.text() == "+",
           "der Hinzufuegen-Knopf heisst '+': %r" % panel.add_filter_button.text())
    panel.add_filter_button.click()
    check(len(panel.filter_rows) == 2, "Knopf '+ Filter' fuegt eine Zeile hinzu")
    check(panel.filter_rows[1]["type"].currentData() == "none",
           "die neue Zeile startet mit 'kein Filter'")
    panel.filter_rows[1]["type"].setCurrentIndex(panel.filter_rows[1]["type"].findData("casting"))
    check("casting" in obj.Filters, "zweiter Filter (casting) landet im Objekt: %s" % obj.Filters)
    check(panel.filter_rows[1]["direction"].isHidden() is False,
           "Richtungsfeld ist bei casting eingeblendet")

    panel.filter_rows[0]["type"].setCurrentIndex(
        panel.filter_rows[0]["type"].findData("erode sensitivity"))
    check("erode sensitivity" in obj.Filters,
           "Morphologie-Filter landet im Objekt: %s" % obj.Filters)
    panel.filter_rows[0]["radius_mode"].setCurrentIndex(
        panel.filter_rows[0]["radius_mode"].findData("manual"))
    panel.filter_rows[0]["radius_value"].setValue(4.5)
    log("Filter im Objekt: %s" % obj.Filters)
    check("4.5" in obj.Filters, "manueller Radius landet im Objekt: %s" % obj.Filters)
    check(panel.filter_rows[0]["radius_value"].isHidden() is False,
           "mm-Feld ist bei manuellem Radius eingeblendet")
    check(panel.filter_rows[0]["check"].isHidden(),
           "der Pruef-Knopf ist bei 'manuell' ausgeblendet")

    panel.filter_rows[1]["remove"].click()
    check(len(panel.filter_rows) == 1, "Knopf '-' entfernt die Zeile (%d)" % len(panel.filter_rows))
    check("casting" not in obj.Filters, "entfernter Filter verschwindet: %s" % obj.Filters)
    check(panel.filter_rows[0]["direction"].isHidden(),
           "Richtungsfeld ist bei erode ausgeblendet")
    panel.filter_rows[0]["radius_mode"].setCurrentIndex(
        panel.filter_rows[0]["radius_mode"].findData("auto"))
    check(panel.filter_rows[0]["radius_value"].isHidden(),
           "mm-Feld ist bei automatischem Radius ausgeblendet")
    width2 = panel.form.minimumSizeHint().width()
    log("Mindestbreite nach Filteraenderung: %d px" % width2)
    check(panel.mass_field.value() == 60, "Zielmasse zeigt 60 %% (%d)" % panel.mass_field.value())
    check(panel.base_combo.currentData() == "stiffness",
           "Optimierungsziel steht auf stiffness (%s)" % panel.base_combo.currentData())
    panel.mass_slider.setValue(30)
    check(panel.mass_field.value() == 30, "Zahlenfeld folgt dem Schieberegler")
    check(abs(obj.MassGoalRatio - 0.30) < 1e-9,
           "Schieberegler schreibt die Zielmasse ins Objekt (%.3f)" % obj.MassGoalRatio)
    panel.cores_field.setValue(4)
    check(obj.CpuCores == 4, "Kerne landen im Objekt (%d)" % obj.CpuCores)
    panel.iterations_field.setText("25")
    panel._params_changed()
    check(obj.IterationsLimit == "25", "Iterationsgrenze landet im Objekt (%s)" % obj.IterationsLimit)
    panel.iterations_field.setText("")
    panel._params_changed()
    check(obj.IterationsLimit == "auto", "leeres Feld wird wieder 'auto'")
    panel._show_step(1)
    check(panel.pages.currentIndex() == 0, "zurueck zu Schritt 1")

    panel.reject()
    check(assist.panel_for(obj.Name) is None, "Assistent wurde geschlossen (reject)")

    # header line: missing parts have to be reported
    from freecad.TopoOpt.core import fem as fem_module
    solver_obj = fem_module.find_solver(analysis)
    analysis.removeObject(solver_obj)
    panel2 = AssistantPanel(obj)
    panel2.load()
    log("Kopf ohne Solver: %s" % panel2.header.text())
    check("nicht vorhanden" in panel2.header.text() or "not available" in panel2.header.text(),
           "fehlender Solver wird im Kopf gemeldet")
    check("inp" in panel2.status.text().lower(),
           "der Hinweis nennt die Datei, nicht die Objekte: %s" % panel2.status.text())
    check(not panel2.inp_button.isEnabled(),
           "ohne Solver laesst sich keine Eingabedatei erzeugen")
    check("Solver" in panel2.inp_button.toolTip(),
           "der Knopf erklaert im Tooltip, was fehlt: %s" % panel2.inp_button.toolTip())
    analysis.addObject(solver_obj)
    panel2.load()
    log("Kopf mit Solver : %s" % panel2.header.text())
    check("nicht vorhanden" not in panel2.header.text()
           and "not available" not in panel2.header.text(),
           "mit vollstaendiger Analyse ist keine rote Meldung mehr da")
    # step 3: the run page with a real (very short) run
    panel2._show_step(3)
    check(panel2.pages.currentIndex() == 2, "Schritt 3 zeigt die Lauf-Seite")
    check(panel2.start_button.text() in ("Start optimization", "Optimierung starten"),
           "der Knopf heisst 'Optimierung starten' (%s)" % panel2.start_button.text())
    check(panel2.detail.isHidden(), "das Detail-Feld ist zugeklappt")
    panel2.detail_button.setChecked(True)
    panel2._toggle_detail()
    check(panel2.detail.isHidden() is False, "das Detail-Feld klappt auf")

    obj.IterationsLimit = "1"                     # compute only one iteration
    panel2.start_button.click()
    check(panel2._run_process is not None, "der Lauf wurde gestartet")
    check(panel2.start_button.text() in ("Cancel", "Abbrechen"),
           "waehrend des Laufs heisst der Knopf 'Abbrechen' (%s)" % panel2.start_button.text())
    log("Lauf gestartet, warte auf das Ende ...")
    start_time = time.time()
    while panel2._run_process.poll() is None and time.time() - start_time < 180:
        panel2._update_run()
        time.sleep(1)
    panel2._update_run()
    masses = [values.get("mass") for _, values in panel2.history.values]
    log("Lauf beendet: code=%s, Verlauf=%s, Status=%s, Balken=%d %%"
        % (panel2._run_process.returncode, masses[:3],
           panel2.run_status.text(), panel2.bar.value()))
    check(panel2._run_process.returncode == 0,
           "der Lauf endet mit 0 (%s)" % panel2._run_process.returncode)
    check(bool(masses), "der Verlauf hat Werte aus beso's Tabelle (%s)" % (masses[:3],))
    check(panel2.history.target_mass is not None and panel2.history.target_mass > 0,
           "die Zielmasse im Verlauf ist gesetzt (%.1f)" % (panel2.history.target_mass or -1))
    check(panel2.bar.value() > 0,
           "der Fortschrittsbalken ist gewandert (%d %%)" % panel2.bar.value())

    # error case in the run update: run over, details collapsed.  Expanding them must
    # not call itself - that was a RecursionError (995 <-> 1116).
    panel2.run_timer.stop()
    panel2._run_process = None
    panel2.detail_button.setChecked(False)
    panel2.detail.setVisible(False)
    try:
        panel2._update_run()
        returned = True
    except RecursionError:
        returned = False
    check(returned, "der Fehlerfall im Lauf-Update kreist nicht in einer Rekursion")
    check(not panel2.detail.isHidden(),
           "dabei klappt das Detailfeld auf und zeigt den Log-Auszug")
    check(panel2.bar.value() < 100,
           "der Balken springt am Ende nicht auf 100 %% - die Zielmasse war nicht erreicht "
           "(%d %%)" % panel2.bar.value())
    check(panel2.history._window is not None,
           "das Verlaufsfenster wurde beim Start geoeffnet")
    check(len(panel2.history._axes) == 4,
           "das Verlaufsfenster hat vier Diagramme (%d)" % len(panel2.history._axes))

    # Issue #5: "Show diagrams" has to bring an open chart tab to the front.
    # The tab lives in the QMdiArea; setActiveSubWindow only works when the window
    # itself or its parentWidget() is the subwindow.
    from FreeCAD.Plot import Plot as _Plot
    from PySide import QtWidgets as _Qt
    import FreeCADGui as _Gui
    _mdi = _Gui.getMainWindow().findChild(_Qt.QMdiArea)
    _ours = panel2.history.show()
    if _mdi is not None and _ours is not None:
        _sub = _ours.parentWidget() if not hasattr(_ours, "mdiArea") else _ours
        _foreign = _Plot.figure("Fremder Tab")
        _mdi.setActiveSubWindow(_foreign.parentWidget() if not hasattr(_foreign, "mdiArea")
                               else _foreign)
        _active_before = _mdi.activeSubWindow()
        _mode_before = _mdi.viewMode()
        panel2.history.show()
        _active_after = _mdi.activeSubWindow()
        check(_active_after is _sub,
               "'Show diagrams' holt den Diagramm-Tab nach vorn (vorher %r, nachher %r)"
               % (_active_before.windowTitle() if _active_before else None,
                  _active_after.windowTitle() if _active_after else None))
        check(_mdi.viewMode() == _mode_before,
               "die Fenster bleiben im Tab-Modus (Modus %s -> %s, 0 = Tabs)"
               % (_mode_before, _mdi.viewMode()))
        if _foreign is not None and _foreign.parentWidget() is not None:
            _foreign.parentWidget().close()
    else:
        check(False, "QMdiArea und Verlaufsfenster stehen fuer den Tab-Test bereit")
    check(panel2.show_charts_button.text() in ("Show diagrams", "Diagramme anzeigen"),
           "die Diagramme gehoeren zu den Ergebnissen (%s)" % panel2.show_charts_button.text())
    check(panel2.iterations_button.text() in ("Show iterations", "Iterationen anzeigen"),
           "der VTK-Knopf heisst 'Iterationen anzeigen' (%s)" % panel2.iterations_button.text())
    check(panel2.load_mesh_button.text() in ("Load result network", "Ergebnisnetz laden"),
           "der Knopf fuer das echte Netz heisst 'Ergebnisnetz laden' (%s)"
           % panel2.load_mesh_button.text())
    check("Iteration" in panel2.run_status.text(),
           "die Statuszeile nennt die Iteration (%s)" % panel2.run_status.text())
    check(panel2.start_button.text() in ("Start optimization", "Optimierung starten"),
           "nach dem Lauf heisst der Knopf wieder 'Optimierung starten' (%s)"
           % panel2.start_button.text())
    check(panel2.player is not None,
           "das Ergebnis wurde nach dem Lauf automatisch geladen")
    check(panel2.detail_button.isChecked(), "das Detail-Feld bleibt offen")
    check(panel2.run_status.parent() is panel2.detail_button.parent(),
           "der Lauf-Status teilt sich die Zeile mit 'Details' (keine leere Zeile)")
    check(panel2.run_status.text() != "",
           "der Status ist gefuellt (%s)" % panel2.run_status.text())

    # The status shares the line with "Details" but gets the rest of the width.
    # Before, a stretch item sat in front of it: the wrapping label only got its
    # preferred width and the text wrapped onto two lines.
    from PySide import QtWidgets as _Qt  # noqa: E402
    panel2.form.resize(560, 760)
    panel2.form.show()
    _Qt.QApplication.processEvents()
    panel2.run_status.setText("Iteration 2 | Masse 57836, Ziel 36319")
    _Qt.QApplication.processEvents()
    _metrics = panel2.run_status.fontMetrics()
    _text = _metrics.horizontalAdvance(panel2.run_status.text())
    _width = panel2.run_status.width()
    _height = panel2.run_status.height()
    check(_width >= _text,
           "der Status hat Platz fuer eine Zeile (Label %d px, Text %d px)" % (_width, _text))
    check(_height <= _metrics.height() * 1.7,
           "der Status steht in einer Zeile (%d px hoch, Zeilenhoehe %d px)"
           % (_height, _metrics.height()))
    panel2.form.hide()

    # While the run is going on "Show iterations" shows the last intermediate state:
    # beso writes one fileNNN.vtk per saved iteration - same format, but only part of
    # the states.  resulting_states.vtk only exists at the end of the run.
    _old_folder = panel2.obj.WorkingDir
    _folder = tempfile.mkdtemp(prefix="topoopt_zwischen_")
    panel2.obj.WorkingDir = _folder
    _mid_state = os.path.join(_folder, "file030.vtk")
    with open(_mid_state, "w", encoding="utf8") as fh:
        fh.write("# vtk DataFile Version 3.0\n")
    check(panel2._result_path() == _mid_state,
           "waehrend des Laufs gilt der Zwischenstand (%s)" % panel2._result_path())
    check(not panel2._is_final_state(_mid_state), "eine fileNNN.vtk ist kein Endstand")
    check(panel2._result_iteration(_mid_state) == 30,
           "die Iteration kommt aus dem Dateinamen (%d)" % panel2._result_iteration(_mid_state))
    panel2.player = None
    panel2.result_info.setText("")
    panel2._update_results()
    check(panel2.iterations_button.isEnabled(),
           "'Iterationen anzeigen' ist schon mit einem Zwischenstand aktiv")
    check("30" in panel2.result_info.text(),
           "der Hinweis nennt die Iteration (%s)" % panel2.result_info.text())
    _end = os.path.join(_folder, "resulting_states.vtk")
    with open(_end, "w", encoding="utf8") as fh:
        fh.write("# vtk DataFile Version 3.0\n")
    check(panel2._result_path() == _end, "der Endstand hat Vorrang")
    check(panel2._is_final_state(_end), "resulting_states.vtk gilt als Endstand")
    panel2.obj.WorkingDir = _old_folder
    shutil.rmtree(_folder, ignore_errors=True)
    check("min" in panel2.run_time.text(), "die Laufzeit laeuft mit (%s)"
           % panel2.run_time.text())

    # FI tolerance (D42): the field in the assistant belongs to the object
    panel2.fi_tolerance_field.setValue(7)
    check(int(panel2.obj.FIViolatedTolerance) == 7,
           "die FI-Toleranz aus dem Panel landet im Objekt (%s)"
           % panel2.obj.FIViolatedTolerance)
    panel2.obj.FIViolatedTolerance = 3
    panel2._fill_parameters()
    check(int(panel2.fi_tolerance_field.value()) == 3,
           "die FI-Toleranz aus dem Objekt steht im Panel (%s)"
           % panel2.fi_tolerance_field.value())
    check(panel2.run_time.parent() is panel2.start_button.parent(),
           "die Laufzeit steht in derselben Zeile wie der Start-Knopf")
    # playback speed of the VTK player
    check(panel2.pace_combo.count() == 4,
           "vier Abspielgeschwindigkeiten stehen zur Wahl (%d)" % panel2.pace_combo.count())
    panel2.pace_combo.setCurrentIndex(2)
    check(panel2.result_timer.interval() == 2000,
           "der Takt wirkt auf den Timer (%d ms)" % panel2.result_timer.interval())

    # results in the same step ("Berechnung"): show VTK iterations
    check(panel2.step_label.text().count(" › ") == 2,
           "die Schrittleiste nennt drei Schritte (%s)" % panel2.step_label.text())
    check("Berechnung" in panel2.step_label.text()
           or "Calculation" in panel2.step_label.text(),
           "der dritte Schritt heisst 'Berechnung' (%s)" % panel2.step_label.text())
    check(not panel2.back_button.isHidden(),
           "am dritten Schritt steht 'Zurueck' unten bereit")
    check(panel2.next_button.isHidden(),
           "am letzten Schritt gibt es kein 'Weiter' mehr")
    log("Schieberegler-Breite: %d px (Panel %d px)"
        % (panel2.result_slider.width(), panel2.form.width()))
    check(panel2.result_slider.width() > 100,
           "der Schieberegler bekommt mehr Platz (%d px)" % panel2.result_slider.width())
    check(panel2.back_button.parent() is panel2.form,
           "die Navigation sitzt unten im Panel (nicht im Rollbereich)")
    check(panel2.iterations_button.isEnabled(),
           "der Knopf 'Iterationen anzeigen' ist nach dem Lauf frei")
    check(os.path.isfile(panel2._result_path()),
           "resulting_states.vtk liegt im Arbeitsordner (%s)"
           % os.path.basename(panel2._result_path()))
    player = panel2._show_result()
    check(player is not None, "die Ergebnisdatei wird eingelesen")
    if player is not None:
        log("VTK: %d Iterationen, Schieberegler %d..%d, Info: %s"
            % (player.count, panel2.result_slider.minimum(),
               panel2.result_slider.maximum(), panel2.result_info.text()))
        check(player.count >= 1, "der Player kennt die Iterationen (%d)" % player.count)
        check(panel2.result_slider.maximum() == player.count,
               "der Schieberegler reicht bis zur letzten Iteration (%d)"
               % panel2.result_slider.maximum())
        check("Iteration" in panel2.result_info.text(),
               "die Info nennt die Iteration (%s)" % panel2.result_info.text())
        check(panel2.obj.Document.getObject("TopoOpt_Iteration") is not None,
               "das Anzeigeobjekt liegt im Dokument (TopoOpt_Iteration)")
        if panel2.result_slider.maximum() > 1:
            previous = panel2.result_slider.value()
            panel2._result_step(-1)
            check(panel2.result_slider.value() == previous - 1,
                   "der Knopf 'zurueck' geht eine Iteration zurueck (%d -> %d)"
                   % (previous, panel2.result_slider.value()))
        check(bool(panel2._logfile_path()), "die Logdatei des Laufs wird gefunden (%s)"
               % os.path.basename(panel2._logfile_path()))
        check("von" in panel2.result_info.text() or "of" in panel2.result_info.text(),
               "die Info nennt auch die Gesamtzahl")
    from freecad.TopoOpt.core import netz as mesh_module
    state1 = mesh_module.latest_state1(panel2.obj.WorkingDir)
    check(bool(state1), "die Zustandsdatei der letzten Iteration wird gefunden (%s)"
           % os.path.basename(state1 or "-"))
    objects_before = len(panel2.obj.Document.Objects)
    loaded_mesh = panel2._load_result_mesh()
    objects_after = len(panel2.obj.Document.Objects)
    log("Ergebnisnetz: %s | Info: %s" % (os.path.basename(loaded_mesh or "-"),
                                         panel2.result_info.text()))
    check(bool(loaded_mesh), "das Ergebnisnetz wird geladen (%s)" % (loaded_mesh or "-"))
    check(objects_after > objects_before,
           "das geladene Netz liegt als neues Objekt im Dokument (%d -> %d)"
           % (objects_before, objects_after))
    panel2._show_step(1)

    # error cases: no mesh/solver means no input file, no .inp/design means no run
    def _subject():
        new_obj = create_topology_object(doc, analysis, "Szenario%d" % int(time.time() * 1000 % 100000))
        subject = AssistantPanel(new_obj)
        subject._show_step(3)
        subject.load()
        return new_obj, subject

    mesh_obj = fem_module.find_mesh(analysis)
    mesh_was_in_document = [o for o in doc.Objects if o is mesh_obj] != []
    if not mesh_was_in_document:
        analysis.addObject(mesh_obj)
        doc.recompute()
    # without a mesh: no input file, header line red
    analysis.removeObject(mesh_obj)
    doc.recompute()
    new_obj, subject = _subject()
    check(not subject.inp_button.isEnabled() and "nicht vorhanden" in subject.header.text(),
           "ohne Netz laesst sich keine Eingabedatei erzeugen (%s)" % subject.header.text()[:60])
    analysis.addObject(mesh_obj)
    doc.recompute()

    # without a solver: the same
    analysis.removeObject(solver_obj)
    doc.recompute()
    new_obj, subject = _subject()
    check(not subject.inp_button.isEnabled() and "nicht vorhanden" in subject.header.text(),
           "ohne Solver laesst sich keine Eingabedatei erzeugen (%s)" % subject.header.text()[:60])
    analysis.addObject(solver_obj)
    doc.recompute()

    # without an input file: the run does not start
    # find_inp deliberately also searches the FEM working directory and foreign
    # %TEMP%/fcfem_* directories; on a machine that has seen runs it finds a file there -
    # the test would then never have "no input file" (measured: 233 temp directories, the
    # panel found an .inp).  That is why the search is switched off for this test; what is
    # checked is the panel logic.
    from freecad.TopoOpt.core import fem as _fem
    _real_find_inp = _fem.find_inp
    _fem.find_inp = lambda *a, **k: (None, "")
    try:
        new_obj, subject = _subject()
        new_obj.InpFile = ""
        subject._start_run()
        check(subject._run_process is None
               and ("input file" in subject.status.text().lower()
                    or "Eingabedatei" in subject.status.text()),
               "ohne Eingabedatei startet kein Lauf (%s)" % subject.status.text())
    finally:
        _fem.find_inp = _real_find_inp

    # without design space: the run does not start
    new_obj, subject = _subject()
    for name in list(subject.domains):
        subject.domains[name] = "ignore"
    subject._save_domains()
    subject._start_run()
    check(subject._run_process is None and "esign" in subject.status.text(),
           "ohne Design-Raum startet kein Lauf (%s)" % subject.status.text())

    # the solver spreads the model over several files: there is no complete .inp, so
    # writing it and starting the run are refused with a clear reason (D46)
    new_obj, subject = _subject()
    subject.solver.SplitInputWriter = True
    try:
        subject._write_inp()
        check("Split input write" in subject.status.text(),
               "mit 'Split input write' wird keine Eingabedatei geschrieben (%s)"
               % subject.status.text())
        subject._start_run()
        check(subject._run_process is None and "Split input write" in subject.status.text(),
               "mit 'Split input write' startet kein Lauf (%s)" % subject.status.text())
    finally:
        subject.solver.SplitInputWriter = False

    # the .inp asks for PaStiX: step 1 names the risk instead of leaving a dead run
    new_obj, subject = _subject()
    probe = os.path.join(os.path.dirname(new_obj.InpFile), "solverprobe.inp")
    with open(probe, "w", encoding="utf8") as fh:
        fh.write("*NODE\n1, 0., 0., 0.\n*STATIC, SOLVER=PASTIX\n")
    new_obj.InpFile = probe
    subject._check_inp()
    check("PASTIX" in subject.inp_note.text(),
           "der Solverwunsch der .inp wird in Schritt 1 gemeldet (%s)"
           % subject.inp_note.text()[-120:])
    os.remove(probe)

    panel2.reject()
    App.closeDocument(doc.Name)
    os.remove(copy)
    log("ERGEBNIS: %s" % ("OK" if not errors else "%d FEHLER" % len(errors)))
except SystemExit as exc:
    if exc.code not in (0, None):
        log("ABBRUCH: %s" % exc)
        errors.append("Abbruch")
except Exception:
    log("AUSNAHME:\n" + traceback.format_exc())
    errors.append("Ausnahme")
finally:
    with open(OUTPUT, "w", encoding="utf8") as f:
        f.write("\n".join(lines) + "\n")
    sys.exit(1 if errors else 0)
