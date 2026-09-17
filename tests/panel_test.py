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
import shutil
import sys
import tempfile
import traceback

HIER = os.path.dirname(os.path.abspath(__file__))
AUSGABE = os.path.join(HIER, "panel_test_ausgabe.txt")
zeilen = []
fehler = []


def log(text):
    zeilen.append(str(text))


def pruefe(bedingung, text):
    log("%-5s %s" % ("OK" if bedingung else "FEHLT", text))
    if not bedingung:
        fehler.append(text)


try:
    # FreeCAD does not pass script arguments through sys.argv, so the document is
    # given in an environment variable (see Documentation/development.md)
    quelle = os.environ.get("TOPOOPT_TEST_DOKUMENT", "") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if quelle.lower().endswith(".py"):
        quelle = ""          # never treat a script as a document
    if not quelle or not os.path.isfile(quelle):
        raise SystemExit("Aufruf: TOPOOPT_TEST_DOKUMENT=<dokument.FCStd> freecad.exe "
                         "tests/panel_test.py")

    import FreeCAD as App

    from freecad.TopoOpt.features import create_topology_object
    from freecad.TopoOpt.gui import assistant as assist
    from freecad.TopoOpt.gui.assistant import AssistantPanel

    kopie = os.path.join(tempfile.gettempdir(), "TopoOpt_PanelTest.FCStd")
    if os.path.exists(kopie):
        os.remove(kopie)
    shutil.copy(quelle, kopie)
    if os.path.getsize(kopie) < 1000:                 # a document is never that small
        raise SystemExit("Die Kopie von %s sieht nicht wie ein Dokument aus." % quelle)
    doc = App.openDocument(kopie)
    log("Dokument: %s (%d Objekte)" % (doc.Name, len(doc.Objects)))

    analysen = [o for o in doc.Objects if o.TypeId.startswith("Fem::FemAnalysis")]
    pruefe(bool(analysen), "das Testdokument enthaelt eine FEM-Analyse")
    if not analysen:
        raise SystemExit(1)
    analyse = analysen[0]
    log("Analyse: %s | Kinder: %s" % (analyse.Name, [o.Name for o in analyse.Group]))

    obj = create_topology_object(doc, analyse)
    panel = AssistantPanel(obj)
    panel.laden()          # sofort laden, nicht auf den Timer warten

    log("Status : %s" % panel.status.text())
    log("Kopf   : %s" % panel.kopf.text())
    log("Arbeit : %s" % obj.WorkingDir)

    # Beim Oeffnen darf nichts erzeugt werden
    if not obj.InpFile:
        pruefe(panel.tabelle.rowCount() == 0, "ohne Eingabedatei bleibt die Tabelle leer")
        pruefe(bool(panel.status.text()), "Hinweis auf fehlende Eingabedatei vorhanden")
        log("keine Eingabedatei vorhanden -> Button wird geklickt")
        panel._inp_erzeugen()

    pruefe(bool(obj.InpFile) and os.path.isfile(obj.InpFile),
           "CalculiX-Eingabedatei vorhanden (%s)" % obj.InpFile)
    log("Dateiinfo: %s" % panel.info.text())
    pruefe(panel.tabelle.rowCount() > 0, "Tabelle hat Zeilen (%d)" % panel.tabelle.rowCount())
    pruefe(bool(panel.status.text()), "Statusmeldung vorhanden: %s" % panel.status.text()[:110])
    pruefe("(.inp)" in panel.knopf_inp.text(), "Knopf nennt die Dateiendung: %s"
           % panel.knopf_inp.text())
    pruefe("Quelle" in panel.pfad_feld.toolTip() or "Source" in panel.pfad_feld.toolTip(),
           "Pfad-Tooltip nennt die Quelle: %s" % panel.pfad_feld.toolTip().replace("\n", " | "))
    pruefe("|" not in panel.info.text() and obj.WorkingDir not in panel.info.text(),
           "Dateizeile nennt nur Groesse und Stand: %s" % panel.info.text())
    pruefe(panel.knopf_ordner.isEnabled(), "Ordner-Knopf ist aktiv, wenn es die Datei gibt")
    pruefe(obj.WorkingDir in panel.knopf_ordner.toolTip(),
           "Ordner-Knopf nennt das Arbeitsverzeichnis im Tooltip")
    pruefe("color" in panel.status.styleSheet(), "Hinweistext ist eingefaerbt (%s)"
           % panel.status.styleSheet())

    rollen = {}
    for zeile in range(panel.tabelle.rowCount()):
        name = panel.tabelle.item(zeile, 0).text()
        feld = panel.tabelle.cellWidget(zeile, 1)
        anzahl = panel.tabelle.item(zeile, 2).text()
        rollen[name] = feld.currentText()
        log("  %-28s %-30s %s" % (name, feld.currentText(), anzahl))
        pruefe(name.lower() not in ("eall", "evolumes", "efaces", "eedges", "enodes"),
               "'%s' ist kein Sammelset" % name)
    pruefe(bool(obj.Domains), "Rollen im Objekt gespeichert: %s" % (obj.Domains,))
    pruefe(any("design" in e for e in obj.Domains),
           "ein Design-Raum ist vorbelegt")

    # Rolle umschalten, wie es der Nutzer in der Tabelle tut
    erster = sorted(rollen)[0]
    for zeile in range(panel.tabelle.rowCount()):
        if panel.tabelle.item(zeile, 0).text() == erster:
            feld = panel.tabelle.cellWidget(zeile, 1)
            feld.setCurrentIndex(1)                       # Nicht-Design-Raum
    pruefe(any(e.startswith(erster + "|") and "non_design" in e for e in obj.Domains),
           "Aenderung in der Tabelle landet sofort im Objekt")

    # Schritt 2: Parameter
    panel._zeige_schritt(2)
    pruefe(panel.seiten.currentIndex() == 1, "Schritt 2 zeigt die Parameter-Seite")
    breite = panel.form.minimumSizeHint().width()
    log("Mindestbreite des Panels: %d px" % breite)
    pruefe(breite <= 360, "Panel laesst sich schmal ziehen (%d px)" % breite)
    pruefe(panel.feld_kerne.value() == 0
           and panel.feld_kerne.specialValueText() in ("all", "alle"),
           "Kerne zeigen '%s' statt der 0" % panel.feld_kerne.specialValueText())
    pruefe(panel.feld_speichern.value() == 10,
           "Speicher-Intervall startet bei 10 (%d)" % panel.feld_speichern.value())
    pruefe(panel.kopf.parent() is not panel.form,
           "Kopfzeile steckt in Schritt 1, nicht ueber allen Schritten")
    pruefe(panel.schritt_knoepfe[0].parent().parent() is panel.form,
           "Schrittleiste sitzt oben im Panel")

    # Filter: Standard ist besos [["simple", "auto"]]
    pruefe(panel.filter_zeilen[0]["typ"].currentData() == "simple",
           "Filter 1 startet mit 'simple' (%s)" % panel.filter_zeilen[0]["typ"].currentData())
    pruefe(panel.filter_zeilen[0]["radius_modus"].currentData() == "auto",
           "Filter 1 startet mit automatischem Radius")
    pruefe(panel.filter_zeilen[1]["typ"].currentData() == "none",
           "Filter 2 ist zunaechst aus")
    panel.filter_zeilen[0]["radius_modus"].setCurrentIndex(
        panel.filter_zeilen[0]["radius_modus"].findData("manual"))
    panel.filter_zeilen[0]["radius_wert"].setValue(4.5)
    log("Filter im Objekt: %s" % obj.Filters)
    pruefe("4.5" in obj.Filters, "manueller Radius landet im Objekt: %s" % obj.Filters)
    panel.filter_zeilen[1]["typ"].setCurrentIndex(panel.filter_zeilen[1]["typ"].findData("casting"))
    pruefe("casting" in obj.Filters, "zweiter Filter (casting) landet im Objekt: %s" % obj.Filters)
    pruefe(panel.filter_zeilen[1]["richtung"].isHidden() is False,
           "Richtungsfeld ist bei casting eingeblendet")
    panel.filter_zeilen[1]["typ"].setCurrentIndex(panel.filter_zeilen[1]["typ"].findData("none"))
    pruefe("casting" not in obj.Filters, "ausgeschalteter Filter verschwindet: %s" % obj.Filters)
    pruefe(panel.filter_zeilen[0]["richtung"].isHidden(),
           "Richtungsfeld ist bei simple ausgeblendet")
    pruefe(panel.filter_zeilen[0]["radius_wert"].isHidden() is False,
           "mm-Feld ist bei manuellem Radius eingeblendet")
    panel.filter_zeilen[0]["radius_modus"].setCurrentIndex(
        panel.filter_zeilen[0]["radius_modus"].findData("auto"))
    pruefe(panel.filter_zeilen[0]["radius_wert"].isHidden(),
           "mm-Feld ist bei automatischem Radius ausgeblendet")
    breite2 = panel.form.minimumSizeHint().width()
    log("Mindestbreite nach Filteraenderung: %d px" % breite2)
    pruefe(panel.feld_masse.value() == 40, "Zielmasse zeigt 40 %% (%d)" % panel.feld_masse.value())
    pruefe(panel.combo_basis.currentData() == "stiffness",
           "Optimierungsziel steht auf stiffness (%s)" % panel.combo_basis.currentData())
    panel.slider_masse.setValue(30)
    pruefe(panel.feld_masse.value() == 30, "Zahlenfeld folgt dem Schieberegler")
    pruefe(abs(obj.MassGoalRatio - 0.30) < 1e-9,
           "Schieberegler schreibt die Zielmasse ins Objekt (%.3f)" % obj.MassGoalRatio)
    panel.feld_kerne.setValue(4)
    pruefe(obj.CpuCores == 4, "Kerne landen im Objekt (%d)" % obj.CpuCores)
    panel.feld_iterationen.setText("25")
    panel._parameter_geaendert()
    pruefe(obj.IterationsLimit == "25", "Iterationsgrenze landet im Objekt (%s)" % obj.IterationsLimit)
    panel.feld_iterationen.setText("")
    panel._parameter_geaendert()
    pruefe(obj.IterationsLimit == "auto", "leeres Feld wird wieder 'auto'")
    panel._zeige_schritt(1)
    pruefe(panel.seiten.currentIndex() == 0, "zurueck zu Schritt 1")

    panel.reject()
    pruefe(assist.panel_for(obj.Name) is None, "Assistent wurde geschlossen (reject)")

    # Kopfzeile: fehlende Teile muessen gemeldet werden
    from freecad.TopoOpt.core import fem as fem_modul
    solver_objekt = fem_modul.find_solver(analyse)
    analyse.removeObject(solver_objekt)
    panel2 = AssistantPanel(obj)
    panel2.laden()
    log("Kopf ohne Solver: %s" % panel2.kopf.text())
    pruefe("nicht vorhanden" in panel2.kopf.text() or "not available" in panel2.kopf.text(),
           "fehlender Solver wird im Kopf gemeldet")
    pruefe("inp" in panel2.status.text().lower(),
           "der Hinweis nennt die Datei, nicht die Objekte: %s" % panel2.status.text())
    pruefe(not panel2.knopf_inp.isEnabled(),
           "ohne Solver laesst sich keine Eingabedatei erzeugen")
    pruefe("Solver" in panel2.knopf_inp.toolTip(),
           "der Knopf erklaert im Tooltip, was fehlt: %s" % panel2.knopf_inp.toolTip())
    analyse.addObject(solver_objekt)
    panel2.laden()
    log("Kopf mit Solver : %s" % panel2.kopf.text())
    pruefe("nicht vorhanden" not in panel2.kopf.text()
           and "not available" not in panel2.kopf.text(),
           "mit vollstaendiger Analyse ist keine rote Meldung mehr da")
    panel2.reject()
    App.closeDocument(doc.Name)
    os.remove(kopie)
    log("ERGEBNIS: %s" % ("OK" if not fehler else "%d FEHLER" % len(fehler)))
except SystemExit as exc:
    if exc.code not in (0, None):
        log("ABBRUCH: %s" % exc)
        fehler.append("Abbruch")
except Exception:
    log("AUSNAHME:\n" + traceback.format_exc())
    fehler.append("Ausnahme")
finally:
    with open(AUSGABE, "w", encoding="utf8") as f:
        f.write("\n".join(zeilen) + "\n")
    sys.exit(1 if fehler else 0)
