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
    from freecad.TopoOpt.core import domains as dom

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

    # zulaessige Spannung: leer = kein FI, Wert = FI (wie im Prototyp eine Spalte je Domain)
    pruefe(len(panel.felder_stress) == len(panel.elsets),
           "jede Domain hat ein Feld fuer die zulaessige Spannung (%d Felder)"
           % len(panel.felder_stress))
    erster = sorted(panel.elsets)[0]
    pruefe(panel.felder_stress[erster].text() == "",
           "das Feld ist am Anfang leer (kein Failure Index)")
    panel.felder_stress[erster].setText("235")
    pruefe(panel.obj.StressLimits == ["%s|235.0" % erster],
           "der Wert landet im Objekt (%s)" % (panel.obj.StressLimits,))
    pruefe(erster in panel.stress, "der Wert steht auch im Assistenten")
    panel.felder_stress[erster].setText("")
    pruefe(panel.obj.StressLimits == ["%s|0" % erster],
           "leeres Feld nimmt die Spannung heraus und merkt sich das (%s)"
           % (panel.obj.StressLimits,))

    # Material mit Streckgrenze -> Vorschlag (wie gewuenscht: nur wenn dort ein Wert steht)
    material_alt = doc.getObject("MaterialSolid")
    werte_alt = dict(material_alt.Material)
    werte_neu = dict(werte_alt)
    werte_neu["YieldStrength"] = "315 MPa"
    material_alt.Material = werte_neu
    doc.recompute()
    panel.obj.StressLimits = []
    panel.stress = {}
    panel.stress_aus = set()
    panel._fuelle_tabelle()
    panel._vorschlag_aus_material()
    pruefe(panel.stress.get(erster) == 315.0,
           "die Streckgrenze aus dem Material wird vorgeschlagen (%s)" % panel.stress)
    pruefe(panel.felder_stress[erster].text() in ("315", "315,0", "315.0"),
           "der Vorschlag steht im Feld (%s)" % panel.felder_stress[erster].text())
    pruefe(panel.obj.StressLimits == ["%s|315.0" % erster],
           "der Vorschlag ist auch im Objekt gespeichert (%s)" % (panel.obj.StressLimits,))
    # wer das Feld bewusst leer laesst, bekommt keinen Vorschlag mehr
    panel.obj.StressLimits = ["%s|0" % erster]
    panel.stress = {}
    panel.stress_aus = dom.aus_stress(panel.obj.StressLimits)
    panel._fuelle_tabelle()
    panel._vorschlag_aus_material()
    pruefe(erster not in panel.stress,
           "wer das Feld geleert hat, bekommt den Vorschlag nicht wieder (%s)" % panel.stress)
    # das Material wieder wie vorher lassen (der Lauf in Schritt 3 soll ohne FI rechnen)
    material_alt.Material = werte_alt
    panel.obj.StressLimits = []
    panel.stress = {}
    panel.stress_aus = set()
    panel._fuelle_tabelle()
    doc.recompute()

    # Filter: Standard ist besos [["simple", "auto"]]
    pruefe(len(panel.filter_zeilen) == 1,
           "Standard: eine Filterzeile (%d)" % len(panel.filter_zeilen))
    pruefe(panel.filter_zeilen[0]["typ"].currentData() == "simple",
           "Filter 1 startet mit 'simple' (%s)" % panel.filter_zeilen[0]["typ"].currentData())
    pruefe(panel.filter_zeilen[0]["radius_modus"].currentData() == "robust",
           "Filter 1 startet mit 'robust' (%s)" % panel.filter_zeilen[0]["radius_modus"].currentData())
    pruefe(panel.feld_toleranz.text() in ("0,001", "0.001"),
           "Toleranz ohne Fuellnullen: %s" % panel.feld_toleranz.text())

    # der robuste Radius wird nur auf Knopfdruck gerechnet (dauert bei feinen Netzen)
    # vorher die Rolle zurueck auf Design-Raum: ohne Design-Raum gibt es keinen Radius
    for zeile in range(panel.tabelle.rowCount()):
        if panel.tabelle.item(zeile, 0).text() == erster:
            panel.tabelle.cellWidget(zeile, 1).setCurrentIndex(0)
    log("Radius-Info vor der Pruefung: %s" % panel.filter_zeilen[0]["radius_info"].text())
    pruefe(panel.filter_zeilen[0]["radius_info"].text() in ("calculate", "berechnen"),
           "ohne Wert steht 'berechnen' im Feld (%s)" % panel.filter_zeilen[0]["radius_info"].text())
    pruefe("color" in panel.filter_zeilen[0]["radius_info"].styleSheet(),
           "das 'berechnen' ist eingefaerbt (%s)" % panel.filter_zeilen[0]["radius_info"].styleSheet())
    pruefe("robust" in obj.Filters, "robust steht im Objekt: %s" % obj.Filters)
    pruefe(panel.filter_zeilen[0]["pruefen"].isHidden() is False,
           "der Pruef-Knopf ist bei 'robust' sichtbar")
    pruefe(panel.filter_zeilen[0]["pruefen"].text() == "\u21bb",
           "der Pruef-Knopf ist das Pfeilsymbol (%r)" % panel.filter_zeilen[0]["pruefen"].text())
    pruefe(panel.filter_zeilen[0]["pruefen"].toolTip() != "",
           "der Pruef-Knopf hat einen Tooltip")
    panel.filter_zeilen[0]["pruefen"].click()
    log("Radius-Info nach der Pruefung: %s" % panel.filter_zeilen[0]["radius_info"].text())
    pruefe(obj.RobusterRadius > 0, "robuster Radius ist berechnet (%.4f mm)"
           % obj.RobusterRadius)
    pruefe("mm" in panel.filter_zeilen[0]["radius_info"].text()
           or "mm" in panel.filter_zeilen[0]["radius_info"].toolTip(),
           "die Filterzeile zeigt den berechneten Radius (%s)"
           % panel.filter_zeilen[0]["radius_info"].text())

    pruefe(panel.knopf_filter_plus.text() == "+",
           "der Hinzufuegen-Knopf heisst '+': %r" % panel.knopf_filter_plus.text())
    panel.knopf_filter_plus.click()
    pruefe(len(panel.filter_zeilen) == 2, "Knopf '+ Filter' fuegt eine Zeile hinzu")
    pruefe(panel.filter_zeilen[1]["typ"].currentData() == "none",
           "die neue Zeile startet mit 'kein Filter'")
    panel.filter_zeilen[1]["typ"].setCurrentIndex(panel.filter_zeilen[1]["typ"].findData("casting"))
    pruefe("casting" in obj.Filters, "zweiter Filter (casting) landet im Objekt: %s" % obj.Filters)
    pruefe(panel.filter_zeilen[1]["richtung"].isHidden() is False,
           "Richtungsfeld ist bei casting eingeblendet")

    panel.filter_zeilen[0]["typ"].setCurrentIndex(
        panel.filter_zeilen[0]["typ"].findData("erode sensitivity"))
    pruefe("erode sensitivity" in obj.Filters,
           "Morphologie-Filter landet im Objekt: %s" % obj.Filters)
    panel.filter_zeilen[0]["radius_modus"].setCurrentIndex(
        panel.filter_zeilen[0]["radius_modus"].findData("manual"))
    panel.filter_zeilen[0]["radius_wert"].setValue(4.5)
    log("Filter im Objekt: %s" % obj.Filters)
    pruefe("4.5" in obj.Filters, "manueller Radius landet im Objekt: %s" % obj.Filters)
    pruefe(panel.filter_zeilen[0]["radius_wert"].isHidden() is False,
           "mm-Feld ist bei manuellem Radius eingeblendet")
    pruefe(panel.filter_zeilen[0]["pruefen"].isHidden(),
           "der Pruef-Knopf ist bei 'manuell' ausgeblendet")

    panel.filter_zeilen[1]["minus"].click()
    pruefe(len(panel.filter_zeilen) == 1, "Knopf '-' entfernt die Zeile (%d)" % len(panel.filter_zeilen))
    pruefe("casting" not in obj.Filters, "entfernter Filter verschwindet: %s" % obj.Filters)
    pruefe(panel.filter_zeilen[0]["richtung"].isHidden(),
           "Richtungsfeld ist bei erode ausgeblendet")
    panel.filter_zeilen[0]["radius_modus"].setCurrentIndex(
        panel.filter_zeilen[0]["radius_modus"].findData("auto"))
    pruefe(panel.filter_zeilen[0]["radius_wert"].isHidden(),
           "mm-Feld ist bei automatischem Radius ausgeblendet")
    breite2 = panel.form.minimumSizeHint().width()
    log("Mindestbreite nach Filteraenderung: %d px" % breite2)
    pruefe(panel.feld_masse.value() == 60, "Zielmasse zeigt 60 %% (%d)" % panel.feld_masse.value())
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
    # Schritt 3: die Lauf-Seite mit einem echten (sehr kurzen) Lauf
    panel2._zeige_schritt(3)
    pruefe(panel2.seiten.currentIndex() == 2, "Schritt 3 zeigt die Lauf-Seite")
    pruefe(panel2.knopf_lauf.text() in ("Start optimization", "Optimierung starten"),
           "der Knopf heisst 'Optimierung starten' (%s)" % panel2.knopf_lauf.text())
    pruefe(panel2.detail.isHidden(), "das Detail-Feld ist zugeklappt")
    panel2.knopf_detail.setChecked(True)
    panel2._detail_umschalten()
    pruefe(panel2.detail.isHidden() is False, "das Detail-Feld klappt auf")

    obj.IterationsLimit = "1"                     # nur eine Iteration rechnen
    panel2.knopf_lauf.click()
    pruefe(panel2._lauf_prozess is not None, "der Lauf wurde gestartet")
    pruefe(panel2.knopf_lauf.text() in ("Cancel", "Abbrechen"),
           "waehrend des Laufs heisst der Knopf 'Abbrechen' (%s)" % panel2.knopf_lauf.text())
    log("Lauf gestartet, warte auf das Ende ...")
    beginn = time.time()
    while panel2._lauf_prozess.poll() is None and time.time() - beginn < 180:
        panel2._lauf_aktualisieren()
        time.sleep(1)
    panel2._lauf_aktualisieren()
    massen = [werte.get("mass") for _, werte in panel2.verlauf.werte]
    log("Lauf beendet: code=%s, Verlauf=%s, Status=%s, Balken=%d %%"
        % (panel2._lauf_prozess.returncode, massen[:3],
           panel2.lauf_status.text(), panel2.balken.value()))
    pruefe(panel2._lauf_prozess.returncode == 0,
           "der Lauf endet mit 0 (%s)" % panel2._lauf_prozess.returncode)
    pruefe(bool(massen), "der Verlauf hat Werte aus beso's Tabelle (%s)" % (massen[:3],))
    pruefe(panel2.verlauf.zielmasse is not None and panel2.verlauf.zielmasse > 0,
           "die Zielmasse im Verlauf ist gesetzt (%.1f)" % (panel2.verlauf.zielmasse or -1))
    pruefe(panel2.balken.value() > 0,
           "der Fortschrittsbalken ist gewandert (%d %%)" % panel2.balken.value())
    pruefe(panel2.balken.value() < 100,
           "der Balken springt am Ende nicht auf 100 %% - die Zielmasse war nicht erreicht "
           "(%d %%)" % panel2.balken.value())
    pruefe(panel2.verlauf._fenster is not None,
           "das Verlaufsfenster wurde beim Start geoeffnet")
    pruefe(len(panel2.verlauf._achsen) == 4,
           "das Verlaufsfenster hat vier Diagramme (%d)" % len(panel2.verlauf._achsen))
    pruefe(panel2.chk_verlauf.isChecked(), "Verlauf oeffnet standardmaessig beim Start")
    pruefe("Iteration" in panel2.lauf_status.text(),
           "die Statuszeile nennt die Iteration (%s)" % panel2.lauf_status.text())
    pruefe(panel2.knopf_lauf.text() in ("Start optimization", "Optimierung starten"),
           "nach dem Lauf heisst der Knopf wieder 'Optimierung starten' (%s)"
           % panel2.knopf_lauf.text())
    pruefe(panel2.knopf_detail.isChecked(), "das Detail-Feld bleibt offen")

    # Ergebnisse im selben Schritt ("Berechnung"): VTK-Iterationen anzeigen
    pruefe(len(panel2.schritt_knoepfe) == 3,
           "die Schrittleiste hat drei Schritte (%d)" % len(panel2.schritt_knoepfe))
    pruefe(panel2.schritt_knoepfe[-1].text().endswith(("Calculation", "Berechnung")),
           "der dritte Schritt heisst 'Berechnung' (%s)" % panel2.schritt_knoepfe[-1].text())
    pruefe(panel2.knopf_ergebnis.isEnabled(),
           "der Knopf 'Iterationen anzeigen' ist nach dem Lauf frei")
    pruefe(os.path.isfile(panel2._ergebnis_pfad()),
           "resulting_states.vtk liegt im Arbeitsordner (%s)"
           % os.path.basename(panel2._ergebnis_pfad()))
    spieler = panel2._ergebnis_anzeigen()
    pruefe(spieler is not None, "die Ergebnisdatei wird eingelesen")
    if spieler is not None:
        log("VTK: %d Iterationen, Schieberegler %d..%d, Info: %s"
            % (spieler.anzahl, panel2.ergebnis_slider.minimum(),
               panel2.ergebnis_slider.maximum(), panel2.ergebnis_info.text()))
        pruefe(spieler.anzahl >= 1, "der Player kennt die Iterationen (%d)" % spieler.anzahl)
        pruefe(panel2.ergebnis_slider.maximum() == spieler.anzahl,
               "der Schieberegler reicht bis zur letzten Iteration (%d)"
               % panel2.ergebnis_slider.maximum())
        pruefe("Iteration" in panel2.ergebnis_info.text(),
               "die Info nennt die Iteration (%s)" % panel2.ergebnis_info.text())
        pruefe(panel2.obj.Document.getObject("TopoOpt_Iteration") is not None,
               "das Anzeigeobjekt liegt im Dokument (TopoOpt_Iteration)")
        if panel2.ergebnis_slider.maximum() > 1:
            vorher = panel2.ergebnis_slider.value()
            panel2._ergebnis_schritt(-1)
            pruefe(panel2.ergebnis_slider.value() == vorher - 1,
                   "der Knopf 'zurueck' geht eine Iteration zurueck (%d -> %d)"
                   % (vorher, panel2.ergebnis_slider.value()))
        pruefe(bool(panel2._log_pfad()), "die Logdatei des Laufs wird gefunden (%s)"
               % os.path.basename(panel2._log_pfad()))
        pruefe("von" in panel2.ergebnis_info.text() or "of" in panel2.ergebnis_info.text(),
               "die Info nennt auch die Gesamtzahl")
    panel2._zeige_schritt(1)

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
