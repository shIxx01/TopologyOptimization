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
from ..core.params import BASES, FORMATS, MASS_CHANGE
from ..features.topology_object import find_analysis, ensure_properties

SCHRITTE = ("Initialize", "Parameters", "Run", "Results")

# steps that are built (the others show a placeholder)
GEBAUTE_SCHRITTE = (1, 2)
SCHRITT_TIPPS = {
    1: "Prepare the analysis case: CalculiX input file and element sets",
    2: "Set target mass, filters and iteration limits",
    3: "Run the optimization with CalculiX",
    4: "Look at the result and compare it with the FEM result",
}

# range of the target-mass slider in percent (0 and 100 % make no sense)
MASSE_MIN = 5
MASSE_MAX = 95


def _combo_schmal(combo, zeichen=6):
    """A combo box may be narrow - the popup shows the full text anyway."""
    combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(zeichen)
    return combo


def _label_wrap(text):
    """A label that wraps instead of forcing the panel wide."""
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    return label

# labels of the choices - the stored values are the strings beso knows
BASIS_LABELS = {
    "stiffness": "Stiffness - the part becomes as stiff as possible (usual)",
    "buckling": "Buckling - the part becomes resistant against buckling",
    "heat": "Heat conduction - the heat flows as well as possible",
    "failure_index": "Failure index - stresses stay below a limit",
}
MASS_CHANGE_LABELS = {
    "gentle": "gentle (1 % / 2 % per iteration)",
    "normal": "normal (1.5 % / 3 % per iteration)",
    "fast": "fast (3 % / 6 % per iteration)",
}
TIP_MASSE = ("How much of the material stays: 40 % means the optimized part keeps about "
             "40 % of its mass.")

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
        self._schritt = 1

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(uebersetze("Topology Optimization"))
        aussen = QtWidgets.QVBoxLayout(self.form)
        aussen.setContentsMargins(8, 8, 8, 8)
        aussen.setSpacing(6)

        self.kopf = QtWidgets.QLabel("")
        self.kopf.setTextFormat(QtCore.Qt.RichText)
        self.kopf.setWordWrap(True)
        aussen.addWidget(self.kopf)

        aussen.addWidget(self._schrittleiste())

        # one page per step; only the steps that are built can be chosen
        self.seiten = QtWidgets.QStackedWidget()
        self.seiten.addWidget(self._seite_initialisieren())
        self.seiten.addWidget(self._seite_parameter())
        for _ in range(len(SCHRITTE) - 2):
            self.seiten.addWidget(self._seite_platzhalter())
        aussen.addWidget(self.seiten, 1)
        self._zeige_schritt(1)

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
            knopf.setCheckable(True)
            gebaut = nummer in GEBAUTE_SCHRITTE
            knopf.setEnabled(gebaut)
            knopf.setToolTip(uebersetze(SCHRITT_TIPPS.get(nummer, "")) if gebaut
                             else uebersetze("This step is not built yet."))
            if gebaut:
                knopf.clicked.connect(lambda _checked=False, n=nummer: self._zeige_schritt(n))
            layout.addWidget(knopf)
            self.schritt_knoepfe.append(knopf)
        layout.addStretch(1)
        return leiste

    def _zeige_schritt(self, nummer):
        """Switch to a step (page of the stack) and mark its button."""
        self._schritt = nummer
        self.seiten.setCurrentIndex(nummer - 1)
        for index, knopf in enumerate(self.schritt_knoepfe, start=1):
            knopf.setChecked(index == nummer)

    def _seite_platzhalter(self):
        seite = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(seite)
        label = _label_wrap(uebersetze("This step is not built yet."))
        layout.addWidget(label)
        layout.addStretch(1)
        return seite

    def _seite_initialisieren(self):
        seite = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(seite)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._inp_bereich())
        layout.addWidget(self._domain_tabelle(), 1)
        return seite

    def _seite_parameter(self):
        """Step 2: the parameters of the optimization (defaults from beso_conf.py)."""
        seite = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(seite)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- target mass -------------------------------------------------
        rahmen = QtWidgets.QGroupBox(uebersetze("Target mass"))
        form = QtWidgets.QGridLayout(rahmen)
        self.slider_masse = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider_masse.setRange(MASSE_MIN, MASSE_MAX)
        self.slider_masse.setMinimumWidth(80)
        self.slider_masse.setToolTip(uebersetze(TIP_MASSE))
        self.feld_masse = QtWidgets.QSpinBox()
        self.feld_masse.setRange(MASSE_MIN, MASSE_MAX)
        self.feld_masse.setSuffix(" %")
        self.feld_masse.setToolTip(uebersetze(TIP_MASSE))
        self.slider_masse.valueChanged.connect(self._masse_geaendert)
        self.feld_masse.valueChanged.connect(self._masse_geaendert)
        form.addWidget(self.slider_masse, 0, 0)
        form.addWidget(self.feld_masse, 0, 1)
        layout.addWidget(rahmen)

        # --- the optimization itself -------------------------------------
        rahmen = QtWidgets.QGroupBox(uebersetze("Optimization"))
        form = QtWidgets.QGridLayout(rahmen)
        zeile = 0
        form.addWidget(_label_wrap(uebersetze("What is optimized")), zeile, 0)
        self.combo_basis = _combo_schmal(QtWidgets.QComboBox())
        for wert in BASES:
            self.combo_basis.addItem(uebersetze(BASIS_LABELS.get(wert, wert)), wert)
        self.combo_basis.currentIndexChanged.connect(self._parameter_geaendert)
        form.addWidget(self.combo_basis, zeile, 1)

        zeile += 1
        form.addWidget(_label_wrap(uebersetze("Maximum iterations")), zeile, 0)
        self.feld_iterationen = QtWidgets.QLineEdit()
        self.feld_iterationen.setToolTip(uebersetze("'auto' lets beso estimate the number of "
                                                    "iterations, a number stops after it."))
        self.feld_iterationen.editingFinished.connect(self._parameter_geaendert)
        form.addWidget(self.feld_iterationen, zeile, 1)

        zeile += 1
        form.addWidget(_label_wrap(uebersetze("Stop tolerance")), zeile, 0)
        self.feld_toleranz = QtWidgets.QDoubleSpinBox()
        self.feld_toleranz.setDecimals(5)
        self.feld_toleranz.setRange(0.00001, 1.0)
        self.feld_toleranz.setSingleStep(0.0005)
        self.feld_toleranz.setToolTip(uebersetze("The optimization stops when the mean stress "
                                                 "changes less than this value in the last "
                                                 "5 iterations (beso: 0.001)."))
        self.feld_toleranz.valueChanged.connect(self._parameter_geaendert)
        form.addWidget(self.feld_toleranz, zeile, 1)

        zeile += 1
        form.addWidget(_label_wrap(uebersetze("Material change per iteration")), zeile, 0)
        self.combo_masse_aenderung = _combo_schmal(QtWidgets.QComboBox())
        for schluessel in MASS_CHANGE:
            self.combo_masse_aenderung.addItem(
                uebersetze(MASS_CHANGE_LABELS.get(schluessel, schluessel)), schluessel)
        self.combo_masse_aenderung.setToolTip(uebersetze("How much material beso adds or "
                                                         "removes per iteration."))
        self.combo_masse_aenderung.currentIndexChanged.connect(self._parameter_geaendert)
        form.addWidget(self.combo_masse_aenderung, zeile, 1)

        zeile += 1
        form.addWidget(_label_wrap(uebersetze("Processor cores")), zeile, 0)
        self.feld_kerne = QtWidgets.QSpinBox()
        self.feld_kerne.setRange(0, 128)
        # 0 shows as "all" - setSpecialValueText() works because the minimum is 0
        self.feld_kerne.setSpecialValueText(uebersetze("all"))
        self.feld_kerne.setToolTip(uebersetze("Cores for the solver; 'all' uses every core "
                                              "of the computer."))
        self.feld_kerne.valueChanged.connect(self._parameter_geaendert)
        form.addWidget(self.feld_kerne, zeile, 1)
        layout.addWidget(rahmen)

        # --- result files ------------------------------------------------
        rahmen = QtWidgets.QGroupBox(uebersetze("Result files"))
        form = QtWidgets.QGridLayout(rahmen)
        form.addWidget(_label_wrap(uebersetze("Save every n-th iteration")), 0, 0)
        self.feld_speichern = QtWidgets.QSpinBox()
        self.feld_speichern.setRange(0, 100)
        self.feld_speichern.setToolTip(uebersetze("0 saves only the final result. Every saved "
                                                  "iteration needs disk space (a fine mesh "
                                                  "can need 100 MB and more)."))
        self.feld_speichern.valueChanged.connect(self._parameter_geaendert)
        form.addWidget(self.feld_speichern, 0, 1)
        form.addWidget(_label_wrap(uebersetze("Format of the result meshes")), 1, 0)
        self.combo_format = _combo_schmal(QtWidgets.QComboBox())
        for wert in FORMATS:
            self.combo_format.addItem(wert, wert)
        self.combo_format.currentIndexChanged.connect(self._parameter_geaendert)
        form.addWidget(self.combo_format, 1, 1)
        layout.addWidget(rahmen)
        layout.addStretch(1)
        return seite

    def _inp_bereich(self):
        rahmen = QtWidgets.QGroupBox(uebersetze("CalculiX input file (.inp)"))
        layout = QtWidgets.QGridLayout(rahmen)

        # row 0: the path and the button that opens the folder in the file manager
        self.pfad_feld = QtWidgets.QLineEdit()
        self.pfad_feld.setReadOnly(True)
        self.pfad_feld.setMinimumWidth(100)
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
        rahmen = QtWidgets.QGroupBox(uebersetze("Domains - roles of the elements"))
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
        self._fuelle_parameter()
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
        self._setze_status(uebersetze("%d element set(s), element type %s.")
                           % (len(self.elsets), typen), "ok")

    def _uebernehme_inp(self, pfad, quelle):
        """Set the input file in the object and fill the table from it."""
        self.obj.InpFile = pfad
        self.pfad_feld.setText(pfad or "")
        self.pfad_feld.setCursorPosition(0)
        # where the file came from is a side note - the hint stays short
        tip = uebersetze("The optimizer writes its iteration files next to this file.")
        if pfad and quelle:
            tip = ("%s\n%s" % (uebersetze("Source: %s") % uebersetze(
                QUELLTEXTE.get(quelle, quelle)), tip))
        self.pfad_feld.setToolTip(tip)
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
            auswahl = _combo_schmal(QtWidgets.QComboBox())
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
        self._setze_status(uebersetze("%d element set(s), element type %s.")
                           % (len(self.elsets), typen), "ok")
        App.Console.PrintMessage("TopoOpt: %s\n" % uebersetze("input file written in %.1f s")
                                 % dauer)
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

    # ------------------------------------------------- Schritt 2: Parameter
    def _masse_geaendert(self, wert):
        """Slider and spin box show the same value, the object stores the fraction."""
        for widget in (self.slider_masse, self.feld_masse):
            if widget.value() != wert:
                widget.blockSignals(True)
                widget.setValue(wert)
                widget.blockSignals(False)
        self._parameter_geaendert()

    def _parameter_geaendert(self):
        """Every change goes straight into the object (like the domain roles)."""
        self.obj.MassGoalRatio = round(self.feld_masse.value() / 100.0, 4)
        self.obj.OptimizationBase = self.combo_basis.currentData()
        text = self.feld_iterationen.text().strip()
        self.obj.IterationsLimit = text if text else "auto"
        self.obj.Tolerance = self.feld_toleranz.value()
        self.obj.MassChange = self.combo_masse_aenderung.currentData()
        self.obj.CpuCores = self.feld_kerne.value()
        self.obj.SaveIterations = self.feld_speichern.value()
        self.obj.ResultFormat = self.combo_format.currentData()

    def _fuelle_parameter(self):
        """Show the parameters of the object in the widgets (without writing back)."""
        felder = (self.slider_masse, self.feld_masse, self.combo_basis, self.feld_iterationen,
                  self.feld_toleranz, self.combo_masse_aenderung, self.feld_kerne,
                  self.feld_speichern, self.combo_format)
        for feld in felder:
            feld.blockSignals(True)
        try:
            prozent = int(round(float(getattr(self.obj, "MassGoalRatio", 0.4)) * 100))
            prozent = min(max(prozent, MASSE_MIN), MASSE_MAX)
            self.slider_masse.setValue(prozent)
            self.feld_masse.setValue(prozent)
            self.combo_basis.setCurrentIndex(max(
                0, self.combo_basis.findData(getattr(self.obj, "OptimizationBase", "stiffness"))))
            self.feld_iterationen.setText(str(getattr(self.obj, "IterationsLimit", "auto")))
            self.feld_toleranz.setValue(min(max(float(getattr(self.obj, "Tolerance", 1e-3)),
                                                0.00001), 1.0))
            self.combo_masse_aenderung.setCurrentIndex(max(
                0, self.combo_masse_aenderung.findData(getattr(self.obj, "MassChange", "normal"))))
            self.feld_kerne.setValue(int(getattr(self.obj, "CpuCores", 0)))
            self.feld_speichern.setValue(int(getattr(self.obj, "SaveIterations", 1)))
            self.combo_format.setCurrentIndex(max(
                0, self.combo_format.findData(getattr(self.obj, "ResultFormat", "inp vtk"))))
        finally:
            for feld in felder:
                feld.blockSignals(False)

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
