# SPDX-License-Identifier: LGPL-3.0-or-later
"""The assistant dialog of a topology optimization."""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from ..core import domains as dom
from ..core import elsets as elset_reader
from ..core import fem
from ..core import radius as radius_modul
from ..core.i18n import uebersetze
from ..core.params import (BASES, FILTER_TYPES, FORMATS, MASS_CHANGE, format_filters,
                           parse_filters)
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


def _combo_schmal(combo, zeichen=5):
    """A combo box may be narrow - the popup shows the full text anyway."""
    combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(zeichen)
    return combo


def _label_wrap(text):
    """A label that wraps instead of forcing the panel wide."""
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    return label


class _ZahlFeld(QtWidgets.QDoubleSpinBox):
    """A number field without trailing zeros: 0.001 and not 0.00100."""

    def textFromValue(self, wert):
        text = super(_ZahlFeld, self).textFromValue(wert)
        trenner = "," if "," in text else "."
        if trenner in text:
            text = text.rstrip("0").rstrip(trenner)
        return text

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
TIP_MASSE = ("How much of the material stays: 60 % means the optimized part keeps about "
             "60 % of its mass.")

# the filter rows of step 2 (beso knows a list of filters; "no filter" means the row
# is left out)
FILTER_LABELS = {
    "simple": "simple - smooths, keeps the part round",
    "erode sensitivity": "erode - takes the smallest value in the radius",
    "dilate sensitivity": "dilate - takes the largest value in the radius",
    "open sensitivity": "open - removes small elements (erode, then dilate)",
    "close sensitivity": "close - closes small holes (dilate, then erode)",
    "open-close sensitivity": "open-close - open, then close",
    "close-open sensitivity": "close-open - close, then open",
    "combine sensitivity": "combine - mean of erode and dilate",
    "casting": "casting - demouldable in one direction",
}
FILTER_OPTIONEN = tuple([("none", "no filter")]
                        + [(typ, FILTER_LABELS.get(typ, typ)) for typ in FILTER_TYPES])
RADIUS_MODI = (("robust", "robust (recommended)"), ("auto", "automatic (as in beso)"),
               ("manual", "manual"))
TIP_RADIUS = ("'robust' asks beso for the smallest radius at which every element still has a "
              "neighbour (checked once, then the value is used). 'automatic (as in beso)' "
              "leaves beso's own value of 2 x mean element size, 'manual' uses your "
              "millimetres.")
TIP_FILTER = ("The filter smooths the result. 'simple' averages over all elements in the "
              "radius, 'casting' also keeps the part demouldable in one direction.")

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
        self._robust_daten = None      # Elementdaten aus der .inp (einmal holen)
        self._robust_ergebnis = None   # Ergebnis der robusten Radius-Suche (einmal)
        self._fuelle_laeuft = False    # beim Befuellen nicht neu rechnen

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(uebersetze("Topology Optimization"))
        aussen = QtWidgets.QVBoxLayout(self.form)
        aussen.setContentsMargins(8, 8, 8, 8)
        aussen.setSpacing(6)

        # the step bar is always there, so it sits above everything else
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
        # the header line (analysis, mesh, solver) belongs to this step only
        self.kopf = QtWidgets.QLabel("")
        self.kopf.setTextFormat(QtCore.Qt.RichText)
        self.kopf.setWordWrap(True)
        layout.addWidget(self.kopf)
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
        self.feld_toleranz = _ZahlFeld()
        self.feld_toleranz.setDecimals(6)
        self.feld_toleranz.setRange(0.000001, 1.0)
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
        layout.addWidget(rahmen)          # Optimierung

        layout.addWidget(self._filter_bereich())

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

    def _filter_bereich(self):
        """Step 2: the sensitivity filters - as many rows as the user needs.

        beso takes a list of filters and applies them one after the other
        (e.g. first "casting", then "simple"), so the number of rows is free.
        """
        rahmen = QtWidgets.QGroupBox(uebersetze("Filter"))
        aussen = QtWidgets.QVBoxLayout(rahmen)

        self.filter_layout = QtWidgets.QVBoxLayout()
        self.filter_layout.setSpacing(2)
        aussen.addLayout(self.filter_layout)
        self.filter_zeilen = []

        knopf_zeile = QtWidgets.QHBoxLayout()
        knopf_zeile.addStretch(1)               # the button sits on the right
        self.knopf_filter_plus = QtWidgets.QToolButton()
        self.knopf_filter_plus.setText("+")
        self.knopf_filter_plus.setToolTip(uebersetze("Add filter") + " - "
                                          + uebersetze("beso applies the filters one after the "
                                                       "other, for example first 'casting', then "
                                                       "'simple'."))
        self.knopf_filter_plus.clicked.connect(lambda: self._filter_hinzufuegen())
        knopf_zeile.addWidget(self.knopf_filter_plus)
        aussen.addLayout(knopf_zeile)

        hinweis = _label_wrap(uebersetze("The filter averages the sensitivities over the "
                                         "elements inside the radius and keeps the result "
                                         "smooth. 'automatic' uses beso's own value "
                                         "(2 x mean element size)."))
        hinweis.setStyleSheet("color: %s;" % FARBE_GRAU)
        aussen.addWidget(hinweis)
        return rahmen

    def _filter_hinzufuegen(self, typ="none", reichweite="auto", richtung="(0, 0, 1)"):
        """Add a filter row (also used when the dialog shows the stored filters)."""
        zeile = self._filter_zeile()
        zeile["typ"].setCurrentIndex(max(0, zeile["typ"].findData(typ)))
        if reichweite in ("auto", "robust"):
            zeile["radius_modus"].setCurrentIndex(
                max(0, zeile["radius_modus"].findData(reichweite)))
        elif isinstance(reichweite, (int, float)):
            zeile["radius_modus"].setCurrentIndex(
                max(0, zeile["radius_modus"].findData("manual")))
            zeile["radius_wert"].setValue(float(reichweite))
        zeile["richtung"].setText(str(richtung))
        self.filter_layout.addWidget(zeile["widget"])
        self.filter_zeilen.append(zeile)
        self._nummeriere_filter()
        self._filter_geaendert()
        return zeile

    def _filter_entfernen(self, zeile):
        """Remove one filter row (the "minus" button)."""
        if zeile not in self.filter_zeilen:
            return
        self.filter_zeilen.remove(zeile)
        self.filter_layout.removeWidget(zeile["widget"])
        zeile["widget"].setParent(None)
        zeile["widget"].deleteLater()
        self._nummeriere_filter()
        self._filter_geaendert()

    def _nummeriere_filter(self):
        for nummer, zeile in enumerate(self.filter_zeilen, start=1):
            zeile["label"].setText(uebersetze("Filter %d") % nummer)

    def _filter_zeile(self):
        """The widgets of one filter row (not yet added to the layout)."""
        zeile = {}
        zeile["widget"] = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(zeile["widget"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        zeile["label"] = _label_wrap("")
        layout.addWidget(zeile["label"])

        zeile["typ"] = _combo_schmal(QtWidgets.QComboBox(), 4)
        for wert, text in FILTER_OPTIONEN:
            zeile["typ"].addItem(uebersetze(text), wert)
        zeile["typ"].setToolTip(uebersetze(TIP_FILTER))
        zeile["typ"].currentIndexChanged.connect(self._filter_geaendert)
        layout.addWidget(zeile["typ"], 1)

        zeile["radius_modus"] = _combo_schmal(QtWidgets.QComboBox(), 4)
        for wert, text in RADIUS_MODI:
            zeile["radius_modus"].addItem(uebersetze(text), wert)
        zeile["radius_modus"].setToolTip(uebersetze(TIP_RADIUS))
        zeile["radius_modus"].currentIndexChanged.connect(self._filter_geaendert)
        layout.addWidget(zeile["radius_modus"])

        zeile["radius_wert"] = QtWidgets.QDoubleSpinBox()
        zeile["radius_wert"].setRange(0.001, 1000.0)
        zeile["radius_wert"].setDecimals(3)
        zeile["radius_wert"].setSuffix(" mm")
        zeile["radius_wert"].setValue(2.0)
        zeile["radius_wert"].setToolTip(uebersetze("Radius in millimetres - a larger radius "
                                                   "gives thicker struts and fewer fine "
                                                   "details. The filter needs a radius in "
                                                   "which every element has a neighbour."))
        zeile["radius_wert"].valueChanged.connect(self._filter_geaendert)
        layout.addWidget(zeile["radius_wert"])

        # shows what came out of the robust check (grau, klein)
        zeile["radius_info"] = _label_wrap("")
        zeile["radius_info"].setStyleSheet("color: %s;" % FARBE_GRAU)
        layout.addWidget(zeile["radius_info"], 1)

        # the check takes a few seconds on fine meshes - so the user starts it
        zeile["pruefen"] = QtWidgets.QToolButton()
        zeile["pruefen"].setText("\u21bb")       # circular arrow
        zeile["pruefen"].setToolTip(uebersetze("Check the robust filter radius now"))
        zeile["pruefen"].clicked.connect(lambda _checked=False, z=zeile: self._pruefe_radius(z))
        layout.addWidget(zeile["pruefen"])

        zeile["richtung"] = QtWidgets.QLineEdit("(0, 0, 1)")
        zeile["richtung"].setMinimumWidth(50)
        zeile["richtung"].setVisible(False)     # only the casting filter needs it
        zeile["richtung"].setToolTip(uebersetze("Only for the casting filter: the direction in "
                                                "which the part has to be demouldable."))
        zeile["richtung"].editingFinished.connect(self._filter_geaendert)
        layout.addWidget(zeile["richtung"])

        zeile["minus"] = QtWidgets.QToolButton()
        zeile["minus"].setText("\u2212")        # minus sign
        zeile["minus"].setToolTip(uebersetze("Remove this filter"))
        zeile["minus"].clicked.connect(lambda _checked=False, z=zeile: self._filter_entfernen(z))
        layout.addWidget(zeile["minus"])
        return zeile

    def _filter_geaendert(self):
        """Enable what belongs to the chosen filter type and store the filters."""
        for zeile in self.filter_zeilen:
            typ = zeile["typ"].currentData()
            aktiv = typ != "none"
            casting = typ == "casting"
            modus = zeile["radius_modus"].currentData()
            zeile["radius_modus"].setEnabled(aktiv)
            # only show what is needed: a hidden widget does not make the panel wider
            zeile["radius_wert"].setVisible(aktiv and modus == "manual")
            zeile["richtung"].setVisible(casting)
            zeile["richtung"].setEnabled(casting)
            if aktiv and modus == "robust":
                if self._robust_ergebnis is not None:
                    self._radius_anzeige(zeile)
                elif self.obj.RobusterRadius > 0:
                    # beim Oeffnen des Dialogs nicht rechnen - den gemerkten Wert zeigen
                    zeile["radius_info"].setText("%.3f mm" % self.obj.RobusterRadius)
                    zeile["radius_info"].setToolTip(
                        uebersetze("%.3f mm (saved value from the last check)")
                        % self.obj.RobusterRadius)
                else:
                    # kurz halten - ein langer Text macht das Panel breit
                    zeile["radius_info"].setText("\u2013")
                    zeile["radius_info"].setToolTip(
                        uebersetze("not checked yet - use the arrow button"))
            else:
                zeile["radius_info"].setText("")
                zeile["radius_info"].setToolTip("")
        self.obj.Filters = format_filters(self._sammle_filter())

    def _robusten_radius(self):
        """Der robuste Radius, gerechnet von beso (siehe core/radius.py).

        Die Elementdaten werden nur einmal geholt und gemerkt - das Lesen der .inp
        und die Nachbarsuche dauern bei feinen Netzen einige Sekunden.
        """
        if self._robust_daten is None:
            daten = {}
            if self.obj.InpFile and os.path.isfile(self.obj.InpFile):
                design = [name for name, rolle in self.domains.items() if rolle == dom.DESIGN]
                if design:
                    alle = list(self.elsets) or design
                    daten = radius_modul.gelesen(self.obj.InpFile, alle, design)
            self._robust_daten = daten
        if not self._robust_daten:
            return {}
        ergebnis = radius_modul.robust(self._robust_daten)
        ergebnis["mittel"] = self._robust_daten["mittel"]
        return ergebnis

    def _pruefe_radius(self, zeile):
        """Der Knopf an der Filterzeile: robusten Radius neu rechnen und anzeigen.

        Die Rechnung dauert bei feinen Netzen ein paar Sekunden, deshalb startet sie
        der Nutzer selbst (und nicht das Oeffnen des Dialogs).
        """
        self._robust_daten = None
        self._robust_ergebnis = None
        self._setze_status(uebersetze("Checking the robust filter radius with beso ... "
                                      "this can take a few seconds."), "info")
        QtWidgets.QApplication.processEvents()
        try:
            self._robust_ergebnis = self._robusten_radius()
        except Exception as exc:
            self._robust_ergebnis = {}
            App.Console.PrintError("TopoOpt: %s\n" % exc)
            self._setze_status(uebersetze("The robust radius could not be calculated: %s")
                               % exc, "fehler")
        if self._robust_ergebnis:
            self.obj.RobusterRadius = self._robust_ergebnis["radius"]
            self.obj.MittlereGroesse = self._robust_ergebnis["mittel"]
            self._setze_status(uebersetze("Robust filter radius: %.3f mm = %.1f x mean "
                                          "element size, %d element(s) without a neighbour.")
                               % (self._robust_ergebnis["radius"],
                                  self._robust_ergebnis["faktor"],
                                  self._robust_ergebnis["ohne_nachbarn"]), "ok")
        else:
            self._setze_status(uebersetze("The robust radius needs an input file and a "
                                          "design space - check step 1."), "fehler")
        for andere in self.filter_zeilen:
            if andere["radius_modus"].currentData() == "robust":
                self._radius_anzeige(andere)
        self.obj.Filters = format_filters(self._sammle_filter())

    def _radius_anzeige(self, zeile):
        """Schreibt das Ergebnis der Radius-Pruefung an die Filterzeile (kurz + Tooltip)."""
        if not self._robust_ergebnis:
            zeile["radius_info"].setText("?")
            zeile["radius_info"].setToolTip(uebersetze("not calculated"))
            return
        zeile["radius_info"].setText("%.3f mm" % self._robust_ergebnis["radius"])
        zeile["radius_info"].setToolTip(uebersetze("%.3f mm = %.1f x mean size, %d without "
                                                   "neighbour")
                                        % (self._robust_ergebnis["radius"],
                                           self._robust_ergebnis["faktor"],
                                           self._robust_ergebnis["ohne_nachbarn"]))

    def _sammle_filter(self):
        """The filters from the widgets, in the form beso uses."""
        liste = []
        for zeile in self.filter_zeilen:
            typ = zeile["typ"].currentData()
            if typ == "none":
                continue
            modus = zeile["radius_modus"].currentData()
            reichweite = (modus if modus in ("auto", "robust")
                          else round(zeile["radius_wert"].value(), 4))
            eintrag = [typ, reichweite]
            if typ == "casting":
                eintrag.append(zeile["richtung"].text().strip() or "(0, 0, 1)")
            liste.append(eintrag)
        return liste

    def _fuelle_filter(self):
        """Rebuild the rows from the filters stored in the object."""
        self._fuelle_laeuft = True
        try:
            for zeile in list(self.filter_zeilen):
                self._filter_entfernen(zeile)
            for eintrag in parse_filters(getattr(self.obj, "Filters", "")):
                richtung = str(eintrag[2]) if len(eintrag) > 2 else "(0, 0, 1)"
                self._filter_hinzufuegen(eintrag[0], eintrag[1], richtung)
        finally:
            self._fuelle_laeuft = False
        self._filter_geaendert()

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
        # a new look at the document: element data and radius are looked up again
        self._robust_daten = None
        self._robust_ergebnis = None
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
        self._fuelle_filter()

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
