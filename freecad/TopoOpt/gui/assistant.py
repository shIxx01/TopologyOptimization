# SPDX-License-Identifier: LGPL-3.0-or-later
"""The assistant dialog of a topology optimization."""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from ..core import domains as dom
from ..core import elsets as elset_reader
from ..core import fem
from ..core.i18n import uebersetze
from ..features.topology_object import find_analysis, ensure_properties

SCHRITTE = ("Initialize", "Parameters", "Run", "Results")

# where a found input file came from (keys used by fem.find_inp)
QUELLTEXTE = {
    "fem": "FEM working directory of the solver",
    "other": "another FEM working directory",
    "own": "own working directory (old version)",
    "written": "written",
}

# tooltip of the button that writes the input file
TIP_INP = ("Write the .inp from the FEM model (mesh, material, boundary conditions).\n"
           "Takes a few seconds for fine meshes, FreeCAD is blocked while it runs.")

# colours of the status line
FARBE_FEHLER = "#b04040"      # something is wrong
FARBE_AUFTRAG = "#b07000"     # the user has to do something
FARBE_OK = "#2e7d32"          # everything is ready
FARBE_GRAU = "#808080"        # side note (size and date of the file)
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
        self._geschlossen = False

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(uebersetze("Topology Optimization"))
        aussen = QtWidgets.QVBoxLayout(self.form)
        aussen.setContentsMargins(8, 8, 8, 8)
        aussen.setSpacing(6)

        self.kopf = QtWidgets.QLabel("")
        self.kopf.setTextFormat(QtCore.Qt.RichText)
        aussen.addWidget(self.kopf)

        aussen.addWidget(self._schrittleiste())

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

        # row 0: the path and the button that opens the folder in the file manager
        self.pfad_feld = QtWidgets.QLineEdit()
        self.pfad_feld.setReadOnly(True)
        self.pfad_feld.setToolTip(uebersetze("The optimizer writes its iteration files "
                                              "next to this file."))
        layout.addWidget(self.pfad_feld, 0, 0)
        self.knopf_ordner = QtWidgets.QPushButton(uebersetze("Open working directory"))
        self.knopf_ordner.clicked.connect(self._ordner_oeffnen)
        self.knopf_ordner.setEnabled(False)   # enabled as soon as the directory is known
        layout.addWidget(self.knopf_ordner, 0, 1)

        # row 1: size and date of the file (nothing else - what happened is in the hint)
        self.info = QtWidgets.QLabel("")
        self.info.setStyleSheet("color: %s;" % FARBE_GRAU)
        layout.addWidget(self.info, 1, 0, 1, 2)

        # row 2: button on the left, hint on the right
        self.knopf_inp = QtWidgets.QPushButton(uebersetze("Write input file (.inp)"))
        self.knopf_inp.setToolTip(uebersetze(TIP_INP))
        self.knopf_inp.clicked.connect(self._inp_erzeugen)
        layout.addWidget(self.knopf_inp, 2, 0)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status, 2, 1)
        layout.setColumnStretch(1, 1)
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
    def _setze_kopf(self):
        """Header line: every part of the analysis case - present in green, missing in red."""
        teile = []
        for titel, wert in (("Analysis", self.analyse), ("Mesh", self.netz), ("Solver", self.solver)):
            if wert is None:
                teile.append('<span style="color:%s">%s: %s</span>'
                             % (FARBE_FEHLER, uebersetze(titel), uebersetze("not available")))
            else:
                teile.append('<span style="color:%s">%s: %s</span>'
                             % (FARBE_OK, uebersetze(titel), wert.Label))
        self.kopf.setText(" &nbsp;|&nbsp; ".join(teile))

    def laden(self):
        """Look at analysis, mesh and an existing input file. Writes nothing."""
        QtWidgets.QApplication.processEvents()
        self._setze_status(uebersetze("Looking for the analysis, the mesh and an existing "
                                      "CalculiX input file ..."))
        self.analyse = find_analysis(self.obj)
        self.netz = fem.find_mesh(self.analyse) if self.analyse is not None else None
        self.solver = fem.find_solver(self.analyse) if self.analyse is not None else None
        self._setze_kopf()
        if self.analyse is None or self.netz is None or self.solver is None:
            # what is missing is in the header line; this hint is about the file
            self._uebernehme_inp("", "")
            self._setze_status(uebersetze("No .inp file yet."), "auftrag")
            return
        self.obj.WorkingDir = fem.arbeitsordner(self.solver, self.obj.Document.Name, self.netz,
                                                gemerkt=self.obj.WorkingDir)

        pfad, quelle = fem.find_inp(self.solver, self.netz, self.obj.Document.Name,
                                    gemerkt=self.obj.WorkingDir)
        if not pfad:
            self._uebernehme_inp("", "")
            self._setze_status(uebersetze("No .inp file yet."), "auftrag")
            return

        kopie = fem.uebernehme_inp(pfad, self.solver, self.obj.Document.Name, self.netz,
                                   gemerkt=self.obj.WorkingDir)
        self._uebernehme_inp(kopie, quelle)
        typen = ", ".join(elset_reader.element_types(kopie)) or "?"
        self._setze_status(uebersetze("Input file used (source: %s). %d element set(s), element "
                                       "type %s.")
                           % (uebersetze(QUELLTEXTE.get(quelle, quelle)),
                              len(self.elsets), typen), "ok")

    def _uebernehme_inp(self, pfad, quelle):
        """Set the input file in the object and fill the table from it."""
        self.obj.InpFile = pfad
        self.pfad_feld.setText(pfad or "")
        self.pfad_feld.setCursorPosition(0)
        # size and date only - where the file came from is part of the hint
        self.info.setText(fem.datei_info(pfad) if pfad else uebersetze("no file yet"))
        self.knopf_inp.setText(uebersetze("Write input file (.inp)" if not pfad
                                          else "Rewrite input file (.inp)"))
        ordner = os.path.dirname(pfad) if pfad else self.obj.WorkingDir
        da = bool(ordner) and os.path.isdir(ordner)
        self.knopf_ordner.setEnabled(da)
        self.knopf_ordner.setToolTip(uebersetze("Show this directory in the file manager: %s")
                                     % ordner if da
                                     else uebersetze("There is no working directory yet."))
        # writing an input file needs the whole analysis case
        bereit = self.analyse is not None and self.netz is not None and self.solver is not None
        self.knopf_inp.setEnabled(bereit)
        if bereit:
            self.knopf_inp.setToolTip(TIP_INP)
        else:
            self.knopf_inp.setToolTip(uebersetze("Possible as soon as the analysis has a mesh "
                                                 "and a solver."))

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
                                           "be written."), "fehler")
            return
        self.knopf_inp.setEnabled(False)
        self._setze_status(uebersetze("Writing the CalculiX input file from the FEM model ... "
                                      "FreeCAD is blocked while it runs."), "info")
        try:
            pfad, dauer = fem.erzeuge_inp(self.analyse, self.solver, self.netz,
                                          self.obj.Document.Name, gemerkt=self.obj.WorkingDir)
        except Exception as exc:
            self._setze_status(uebersetze("The input file could not be written: %s") % exc,
                               "fehler")
            self.knopf_inp.setEnabled(True)
            return
        self._uebernehme_inp(pfad, "written")
        typen = ", ".join(elset_reader.element_types(pfad)) or "?"
        self._setze_status(uebersetze("Input file written in %.1f s. %d element set(s), "
                                       "element type %s.") % (dauer, len(self.elsets), typen), "ok")
        self.knopf_inp.setEnabled(True)

    def _ordner_oeffnen(self):
        """Show the working directory in the file manager of the system."""
        ordner = os.path.dirname(self.obj.InpFile) if self.obj.InpFile else self.obj.WorkingDir
        if not ordner or not os.path.isdir(ordner):
            self._setze_status(uebersetze("There is no working directory yet."), "fehler")
            return
        try:
            os.startfile(ordner)                      # Windows
        except Exception:
            try:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(ordner))
            except Exception as exc:
                self._setze_status(uebersetze("The directory could not be opened (%s): %s")
                                   % (exc, ordner), "fehler")

    def _setze_status(self, text, art="info"):
        """Status line: red for problems, orange while the user has to act, green when ready."""
        self.status.setText(text)
        farbe = {"fehler": FARBE_FEHLER, "auftrag": FARBE_AUFTRAG, "ok": FARBE_OK}.get(art, "")
        self.status.setStyleSheet("color: %s;" % farbe if farbe else "")
        QtWidgets.QApplication.processEvents()

    # ------------------------------------------------------ Task-Panel-API
    def getStandardButtons(self):
        # .value because an int is expected (PySide6: the enum cannot be cast with int())
        return QtWidgets.QDialogButtonBox.Ok.value | QtWidgets.QDialogButtonBox.Close.value

    def _schliessen(self):
        """Close the task dialog (FreeCAD calls accept()/reject() but does not close)."""
        if self._geschlossen:
            return
        self._geschlossen = True
        _aktive_panels.pop(self.obj.Name, None)
        try:
            Gui.Control.closeDialog()
        except Exception as exc:
            App.Console.PrintWarning("TopoOpt: dialog could not be closed (%s)\n" % exc)

    def accept(self):
        self._schliessen()

    def reject(self):
        self._schliessen()
