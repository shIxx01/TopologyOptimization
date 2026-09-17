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
    panel.laden()

    log("Status : %s" % panel.status.text())
    log("Kopf   : %s" % panel.kopf.text())
    log("Arbeit : %s" % obj.WorkingDir)

    # Beim Oeffnen darf nichts erzeugt werden
    if not obj.InpFile:
        pruefe(panel.tabelle.rowCount() == 0, "ohne Eingabedatei bleibt die Tabelle leer")
        pruefe("erzeugen" in panel.status.text().lower(),
               "Hinweis auf fehlende Eingabedatei")
        log("keine Eingabedatei vorhanden -> Button wird geklickt")
        panel._inp_erzeugen()

    pruefe(bool(obj.InpFile) and os.path.isfile(obj.InpFile),
           "CalculiX-Eingabedatei vorhanden (%s)" % obj.InpFile)
    log("Dateiinfo: %s" % panel.info.text())
    pruefe(panel.tabelle.rowCount() > 0, "Tabelle hat Zeilen (%d)" % panel.tabelle.rowCount())
    pruefe("s" in panel.status.text() or "Eingabedatei" in panel.status.text(),
           "Status nennt Dauer bzw. Quelle: %s" % panel.status.text()[:120])

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

    panel.reject()
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
