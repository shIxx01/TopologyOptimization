# SPDX-License-Identifier: LGPL-3.0-or-later
"""The assistant dialog of a topology optimization."""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from ..core import domains as dom
from ..core import elsets as elset_reader
from ..core import fem
from ..features.topology_object import find_analysis

SCHRITTE = ("Domains", "Parameter", "Lauf", "Ergebnisse")
_aktive_panels = {}          # Panel-Instanzen am Leben halten (sonst raeumt der GC sie ab)


def panel_for(name):
    return _aktive_panels.get(name)


def open_assistant(obj):
    """Open the assistant for an optimization object (called by the view provider)."""
    if obj is None:
        return
    if panel_for(obj.Name) is not None:
        App.Console.PrintMessage("TopoOpt: der Assistent ist fuer '%s' bereits offen.\n" % obj.Label)
        return
    # an object from a file written by an older version may miss properties
    from ..features.topology_object import ensure_properties
    ensure_properties(obj)
    panel = AssistantPanel(obj)
    _aktive_panels[obj.Name] = panel
    try:
        Gui.Control.showDialog(panel)
    except Exception as exc:
        _aktive_panels.pop(obj.Name, None)
        App.Console.PrintWarning("TopoOpt: Assistent konnte nicht geoeffnet werden (%s)\n" % exc)


class AssistantPanel:
    """Step-by-step dialog: domains, parameters, run, results.

    Only the first step exists so far; the further steps are shown in the step
    bar but are not selectable yet.
    """

    def __init__(self, obj):
        self.obj = obj
        self.domains = {}          # elset -> rolle (Spiegel des Objekts)
        self.elsets = {}           # elset -> Anzahl Elemente

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Topologie-Optimierung")
        aussen = QtWidgets.QVBoxLayout(self.form)
        aussen.setContentsMargins(8, 8, 8, 8)
        aussen.setSpacing(6)

        self.kopf = QtWidgets.QLabel("Analyse: -   |   Netz: -")
        aussen.addWidget(self.kopf)

        aussen.addWidget(self._schrittleiste())

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        aussen.addWidget(self.status)

        aussen.addWidget(self._domain_tabelle(), 1)

        fuss = QtWidgets.QHBoxLayout()
        self.knopf_inp = QtWidgets.QPushButton("CalculiX-Eingabedatei neu erzeugen")
        self.knopf_inp.setToolTip("Liest das Netz neu ein und schreibt die .inp erneut.\n"
                                  "Noetig, wenn du Netz, Material oder Randbedingungen geaendert hast.")
        self.knopf_inp.clicked.connect(self._inp_neu)
        fuss.addWidget(self.knopf_inp)
        fuss.addStretch(1)
        self.pfad_feld = QtWidgets.QLineEdit()
        self.pfad_feld.setReadOnly(True)
        self.pfad_feld.setToolTip("Arbeitsordner der Optimierung (ohne Leerzeichen, "
                                  "auszerhalb deiner Dokumente)")
        fuss.addWidget(self.pfad_feld, 1)
        aussen.addLayout(fuss)

        # Panel zuerst anzeigen, dann die (langsame) Arbeit erledigen
        QtCore.QTimer.singleShot(50, self.laden)

    # ------------------------------------------------------------------ UI
    def _schrittleiste(self):
        leiste = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(leiste)
        layout.setContentsMargins(0, 0, 0, 0)
        self.schritt_knoepfe = []
        for nummer, name in enumerate(SCHRITTE, start=1):
            knopf = QtWidgets.QToolButton()
            knopf.setText("%d %s" % (nummer, name))
            knopf.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
            knopf.setEnabled(nummer == 1)
            knopf.setToolTip("Dieser Schritt ist noch nicht eingebaut."
                             if nummer > 1 else "Element-Sets auswaehlen")
            layout.addWidget(knopf)
            self.schritt_knoepfe.append(knopf)
        layout.addStretch(1)
        return leiste

    def _domain_tabelle(self):
        rahmen = QtWidgets.QGroupBox("Element-Sets der Analyse")
        layout = QtWidgets.QVBoxLayout(rahmen)
        self.tabelle = QtWidgets.QTableWidget(0, 3)
        self.tabelle.setHorizontalHeaderLabels(["Element-Set", "Rolle", "Elemente"])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        kopf.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        kopf.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.tabelle)
        return rahmen

    # --------------------------------------------------------------- Daten
    def laden(self, erneut=False):
        """Read analysis, mesh and element sets; fill the table."""
        QtWidgets.QApplication.processEvents()
        self._setze_status("Suche Analyse und Netz ...")
        analyse = find_analysis(self.obj)
        if analyse is None:
            self._setze_status("Keine FEM-Analyse gefunden. Bitte das Objekt in eine Analyse "
                               "legen (aktive Analyse) oder die Analyse wiederherstellen.", fehler=True)
            return
        netz = fem.find_mesh(analyse)
        solver = fem.find_solver(analyse)
        self.kopf.setText("Analyse: %s   |   Netz: %s"
                          % (analyse.Label, netz.Label if netz else "-"))
        if netz is None or solver is None:
            self._setze_status("Die Analyse braucht ein Netz und einen Solver "
                               "(FEM-Arbeitsbereich: Netz und Solver anlegen).", fehler=True)
            return

        try:
            self._setze_status("Bereite Arbeitsordner und CalculiX-Eingabedatei vor ...")
            QtWidgets.QApplication.processEvents()
            verzeichnis, inp = fem.prepare_inp(analyse, netz, solver,
                                               self.obj.Document.Name, erneut=erneut)
        except Exception as exc:
            self._setze_status("Die CalculiX-Eingabedatei konnte nicht erzeugt werden: %s" % exc,
                               fehler=True)
            return

        self.obj.WorkingDir = verzeichnis
        self.obj.InpFile = inp
        self.pfad_feld.setText(verzeichnis)
        self.pfad_feld.setCursorPosition(0)

        alle = elset_reader.read_elsets(inp)
        self.elsets = dom.zeige_elsets(alle)
        typen = elset_reader.element_types(inp)
        if not self.elsets:
            self._setze_status("In %s wurden keine Element-Sets gefunden." % inp, fehler=True)
            return

        gespeichert = dom.parse_domains(self.obj.Domains)
        if gespeichert:
            self.domains = {name: gespeichert.get(name, dom.IGNORE) for name in self.elsets}
        else:
            self.domains = dom.vorschlag(self.elsets)
            self._speichere_domains()
        self._fuelle_tabelle()
        self._setze_status("%d Element-Set(s) aus %s gelesen (Elementtyp: %s). "
                           "Der Design-Raum wird optimiert, der Nicht-Design-Raum bleibt stehen."
                           % (len(self.elsets), os.path.basename(inp), ", ".join(typen) or "?"))
        self.obj.Document.recompute()

    def _fuelle_tabelle(self):
        self.tabelle.setRowCount(0)
        for name in sorted(self.elsets):
            zeile = self.tabelle.rowCount()
            self.tabelle.insertRow(zeile)
            self.tabelle.setItem(zeile, 0, QtWidgets.QTableWidgetItem(name))
            auswahl = QtWidgets.QComboBox()
            for rolle in (dom.DESIGN, dom.NON_DESIGN, dom.IGNORE):
                auswahl.addItem(dom.ROLE_LABELS[rolle], rolle)
            auswahl.setCurrentIndex(list((dom.DESIGN, dom.NON_DESIGN, dom.IGNORE))
                                    .index(self.domains.get(name, dom.IGNORE)))
            auswahl.currentIndexChanged.connect(
                lambda _index, feld=auswahl, setname=name: self._rolle_geaendert(setname, feld))
            self.tabelle.setCellWidget(zeile, 1, auswahl)
            anzahl = QtWidgets.QTableWidgetItem("{:,}".format(self.elsets[name]).replace(",", "."))
            anzahl.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.tabelle.setItem(zeile, 2, anzahl)

    def _rolle_geaendert(self, elset, feld):
        rolle = feld.itemData(feld.currentIndex())
        self.domains[elset] = rolle
        self._speichere_domains()
        App.Console.PrintMessage("TopoOpt: '%s' ist jetzt %s.\n"
                                 % (elset, dom.ROLE_LABELS.get(rolle, rolle)))

    def _speichere_domains(self):
        self.obj.Domains = dom.format_domains(self.domains)

    def _inp_neu(self):
        self.laden(erneut=True)

    def _setze_status(self, text, fehler=False):
        self.status.setText(text)
        self.status.setStyleSheet("color: #b04040;" if fehler else "")
        QtWidgets.QApplication.processEvents()

    # ------------------------------------------------------ Task-Panel-API
    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.Close

    def accept(self):
        _aktive_panels.pop(self.obj.Name, None)

    def reject(self):
        _aktive_panels.pop(self.obj.Name, None)
