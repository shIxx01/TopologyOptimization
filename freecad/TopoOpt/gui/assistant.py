# SPDX-License-Identifier: LGPL-3.0-or-later
"""The assistant dialog of a topology optimization."""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from ..core import domains as dom
from ..core import elsets as elset_reader
from ..core import fem
from ..core.i18n import uebersetze
from ..features.topology_object import find_analysis, ensure_properties

SCHRITTE = ("Initialize", "Parameters", "Run", "Results")

# where a found input file came from (keys used by fem.find_inp)
QUELLTEXTE = {
    "solver": "Working directory of the solver",
    "freecad": "FEM working directory of FreeCAD",
    "own": "Working directory of TopoOpt",
    "written": "written",
}
_aktive_panels = {}          # Panel-Instanzen am Leben halten (sonst raeumt der GC sie ab)


def panel_for(name):
    return _aktive_panels.get(name)


def open_assistant(obj):
    """Open the assistant for an optimization object (called by the view provider)."""
    if obj is None:
        return
    if panel_for(obj.Name) is not None:
        App.Console.PrintMessage("TopoOpt: the assistant for '%s' is already open.\n" % obj.Label)
        return
    ensure_properties(obj)                 # an object from an older file may miss properties
    panel = AssistantPanel(obj)
    _aktive_panels[obj.Name] = panel
    try:
        Gui.Control.showDialog(panel)
    except Exception as exc:
        _aktive_panels.pop(obj.Name, None)
        App.Console.PrintWarning("TopoOpt: the assistant could not be opened (%s)\n" % exc)


class AssistantPanel:
    """Step-by-step dialog: initialize, parameters, run, results.

    The first step prepares the analysis case: it looks for the CalculiX input
    file that FreeCAD may have written before (solver panel), shows it and reads
    the element sets.  Nothing heavy happens when the dialog opens - writing a new
    input file is a click of the user's own, because it can take a few seconds and
    FreeCAD is blocked while it runs.
    """

    def __init__(self, obj):
        self.obj = obj
        self.domains = {}          # elset -> role (mirror of the document object)
        self.elsets = {}           # elset -> number of elements
        self.analyse = None
        self.netz = None
        self.solver = None

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(uebersetze("Topology Optimization"))
        aussen = QtWidgets.QVBoxLayout(self.form)
        aussen.setContentsMargins(8, 8, 8, 8)
        aussen.setSpacing(6)

        self.kopf = QtWidgets.QLabel(uebersetze("Analysis: %s   |   Mesh: %s") % ("-", "-"))
        aussen.addWidget(self.kopf)

        aussen.addWidget(self._schrittleiste())

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        aussen.addWidget(self.status)

        aussen.addWidget(self._inp_bereich())
        aussen.addWidget(self._domain_tabelle(), 1)

        QtCore.QTimer.singleShot(50, self.laden)

    # ------------------------------------------------------------------ UI
    def _schrittleiste(self):
        leiste = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(leiste)
        layout.setContentsMargins(0, 0, 0, 0)
        self.schritt_knoepfe = []
        for nummer, name in enumerate(SCHRITTE, start=1):
            knopf = QtWidgets.QToolButton()
            knopf.setText("%d %s" % (nummer, uebersetze(name)))
            knopf.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
            knopf.setEnabled(nummer == 1)
            knopf.setToolTip(uebersetze("Prepare the analysis case: CalculiX input file and "
                                        "element sets") if nummer == 1
                             else uebersetze("This step is not built yet."))
            layout.addWidget(knopf)
            self.schritt_knoepfe.append(knopf)
        layout.addStretch(1)
        return leiste

    def _inp_bereich(self):
        rahmen = QtWidgets.QGroupBox(uebersetze("CalculiX input file (basis of the optimization)"))
        layout = QtWidgets.QGridLayout(rahmen)

        self.pfad_feld = QtWidgets.QLineEdit()
        self.pfad_feld.setReadOnly(True)
        self.pfad_feld.setToolTip(uebersetze("The optimizer writes its iteration files "
                                              "next to this file."))
        layout.addWidget(self.pfad_feld, 0, 0, 1, 2)

        self.info = QtWidgets.QLabel("")
        layout.addWidget(self.info, 1, 0)

        self.knopf_inp = QtWidgets.QPushButton(uebersetze("Write input file"))
        self.knopf_inp.setToolTip(uebersetze("Write the .inp from the FEM model (mesh, material, "
                                             "boundary conditions).\nTakes a few seconds for fine "
                                             "meshes, FreeCAD is blocked while it runs."))
        self.knopf_inp.clicked.connect(self._inp_erzeugen)
        layout.addWidget(self.knopf_inp, 1, 1)
        return rahmen

    def _domain_tabelle(self):
        rahmen = QtWidgets.QGroupBox(uebersetze("Domains - which elements are optimized?"))
        layout = QtWidgets.QVBoxLayout(rahmen)
        self.tabelle = QtWidgets.QTableWidget(0, 3)
        self.tabelle.setHorizontalHeaderLabels([uebersetze("Element set"), uebersetze("Role"),
                                                uebersetze("Elements")])
        self.tabelle.verticalHeader().setVisible(False)
        self.tabelle.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        kopf = self.tabelle.horizontalHeader()
        kopf.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        kopf.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        kopf.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.tabelle)
        return rahmen

    # --------------------------------------------------------------- Daten
    def laden(self):
        """Look at analysis, mesh and an existing input file. Writes nothing."""
        QtWidgets.QApplication.processEvents()
        self._setze_status(uebersetze("Looking for the analysis, the mesh and an existing "
                                      "CalculiX input file ..."))
        self.analyse = find_analysis(self.obj)
        if self.analyse is None:
            self._setze_status(uebersetze("No FEM analysis found. Please put the object into an "
                                           "analysis (active analysis) or restore the analysis."),
                               fehler=True)
            return
        self.netz = fem.find_mesh(self.analyse)
        self.solver = fem.find_solver(self.analyse)
        self.kopf.setText(uebersetze("Analysis: %s   |   Mesh: %s")
                          % (self.analyse.Label, self.netz.Label if self.netz else "-"))
        self.obj.WorkingDir = fem.run_dir(self.obj.Document.Name,
                                          self.netz.Name if self.netz else "model")
        if self.netz is None or self.solver is None:
            self._setze_status(uebersetze("The analysis needs a mesh and a solver (FEM workbench: "
                                           "create mesh and solver)."), fehler=True)
            return

        pfad, quelle = fem.find_inp(self.solver, self.netz, self.obj.Document.Name)
        if not pfad:
            self._uebernehme_inp("", "")
            self._setze_status(uebersetze("There is no CalculiX input file for the analysis '%s' "
                                           "yet. Click 'Write input file' so that the element sets "
                                           "can be read.") % self.analyse.Label)
            return

        kopie = fem.uebernehme_inp(pfad, self.obj.Document.Name, self.netz)
        self._uebernehme_inp(kopie, quelle)
        typen = ", ".join(elset_reader.element_types(kopie)) or "?"
        self._setze_status(uebersetze("Input file used (source: %s). %d element set(s), element "
                                       "type %s. The design space is optimized, the non-design "
                                       "space is kept.")
                           % (uebersetze(QUELLTEXTE.get(quelle, quelle)),
                              len(self.elsets), typen))

    def _uebernehme_inp(self, pfad, quelle):
        """Set the input file in the object and fill the table from it."""
        self.obj.InpFile = pfad
        self.pfad_feld.setText(pfad or "")
        self.pfad_feld.setCursorPosition(0)
        info = fem.datei_info(pfad)
        if pfad and quelle:
            self.info.setText("%s - %s" % (uebersetze(QUELLTEXTE.get(quelle, quelle)), info))
        else:
            self.info.setText(uebersetze("no file yet") if not pfad else info)
        self.knopf_inp.setText(uebersetze("Write input file" if not pfad
                                           else "Rewrite input file"))

        if not pfad or not os.path.isfile(pfad):
            self.elsets = {}
            self.tabelle.setRowCount(0)
            return
        self.elsets = dom.zeige_elsets(elset_reader.read_elsets(pfad))
        gespeichert = dom.parse_domains(self.obj.Domains)
        if gespeichert:
            self.domains = {name: gespeichert.get(name, dom.IGNORE) for name in self.elsets}
        else:
            self.domains = dom.vorschlag(self.elsets)
            self._speichere_domains()
        self._fuelle_tabelle()
        self.obj.Document.recompute()

    def _fuelle_tabelle(self):
        self.tabelle.setRowCount(0)
        for name in sorted(self.elsets):
            zeile = self.tabelle.rowCount()
            self.tabelle.insertRow(zeile)
            self.tabelle.setItem(zeile, 0, QtWidgets.QTableWidgetItem(name))
            auswahl = QtWidgets.QComboBox()
            reihenfolge = (dom.DESIGN, dom.NON_DESIGN, dom.IGNORE)
            for rolle in reihenfolge:
                auswahl.addItem(uebersetze(dom.ROLE_LABELS[rolle]), rolle)
            auswahl.setCurrentIndex(reihenfolge.index(self.domains.get(name, dom.IGNORE)))
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
        App.Console.PrintMessage(uebersetze("TopoOpt: '%s' is now %s.\n")
                                 % (elset, uebersetze(dom.ROLE_LABELS.get(rolle, rolle))))

    def _speichere_domains(self):
        self.obj.Domains = dom.format_domains(self.domains)

    # -------------------------------------------------------------- Aktionen
    def _inp_erzeugen(self):
        """Write a new input file - only on an explicit click (can take seconds)."""
        if self.analyse is None or self.netz is None or self.solver is None:
            self._setze_status(uebersetze("Without analysis, mesh and solver no input file can "
                                           "be written."), fehler=True)
            return
        self.knopf_inp.setEnabled(False)
        self._setze_status(uebersetze("Writing the CalculiX input file from the FEM model ... "
                                      "FreeCAD is blocked while it runs."))
        try:
            pfad, dauer = fem.erzeuge_inp(self.analyse, self.solver, self.netz,
                                          self.obj.Document.Name)
        except Exception as exc:
            self._setze_status(uebersetze("The input file could not be written: %s") % exc,
                               fehler=True)
            self.knopf_inp.setEnabled(True)
            return
        self._uebernehme_inp(pfad, "written")
        typen = ", ".join(elset_reader.element_types(pfad)) or "?"
        self._setze_status(uebersetze("Input file written in %.1f s. %d element set(s), "
                                       "element type %s.") % (dauer, len(self.elsets), typen))
        self.knopf_inp.setEnabled(True)

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
