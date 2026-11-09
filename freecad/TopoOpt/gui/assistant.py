# SPDX-License-Identifier: LGPL-3.0-or-later
"""The assistant dialog of a topology optimization."""

import os
import subprocess
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from ..core import conf as conf_module
from ..core import domains as dom
from ..core import elsets as elset_reader
from ..core import fem
from ..core import lauf as log_module
from ..core import material as material_module
from ..core import netz as mesh_module
from ..core import radius as radius_module
from ..core.i18n import translate
from ..core.params import (BASES, FILTER_TYPES, FORMATS, MASS_CHANGE, format_filters,
                           parse_filters)
from ..features.topology_object import find_analysis, ensure_properties

STEPS = ("Initialize", "Parameters", "Calculation")

# steps that are built (the others show a placeholder)
BUILT_STEPS = (1, 2, 3)
STEP_TIPS = {
    1: "Prepare the analysis case: CalculiX input file and element sets",
    2: "Set target mass, filters and iteration limits",
    3: "Start the run, watch it and look at the result (iterations, log, folder)",
}

# range of the target-mass slider in percent (0 and 100 % make no sense)
MASS_MIN = 5
MASS_MAX = 95


def _narrow_combo(combo, chars=5):
    """A combo box may be narrow - the popup shows the full text anyway."""
    combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(chars)
    return combo


def _label_wrap(text):
    """A label that wraps instead of forcing the panel wide."""
    label = QtWidgets.QLabel(text)
    label.setWordWrap(True)
    return label


class _NumberField(QtWidgets.QDoubleSpinBox):
    """A number field without trailing zeros: 0.001 and not 0.00100."""

    def textFromValue(self, value):
        text = super(_NumberField, self).textFromValue(value)
        separator = "," if "," in text else "."
        if separator in text:
            text = text.rstrip("0").rstrip(separator)
        return text


class _ClickLabel(QtWidgets.QLabel):
    """A label that can be clicked - used for "berechnen" at the filter row."""

    def __init__(self, text=""):
        super(_ClickLabel, self).__init__(text)
        self._action = None

    def set_action(self, action):
        self._action = action
        if action is not None:
            self.setCursor(QtCore.Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if self._action is not None:
            self._action()
        super(_ClickLabel, self).mousePressEvent(event)

# labels of the choices - the stored values are the strings beso knows
BASE_LABELS = {
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
TIP_MASS = ("How much of the material stays: 60 % means the optimized part keeps about "
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
FILTER_OPTIONS = tuple([("none", "no filter")]
                       + [(filter_type, FILTER_LABELS.get(filter_type, filter_type))
                           for filter_type in FILTER_TYPES])
RADIUS_MODES = (("robust", "robust (recommended)"), ("auto", "automatic (as in beso)"),
                ("manual", "manual"))
TIP_RADIUS = ("'robust' asks beso for the smallest radius at which every element still has a "
              "neighbour (checked once, then the value is used). 'automatic (as in beso)' "
              "leaves beso's own value of 2 x mean element size, 'manual' uses your "
              "millimetres.")
TIP_FILTER = ("The filter smooths the result. 'simple' averages over all elements in the "
              "radius, 'casting' also keeps the part demouldable in one direction.")

# where a found input file came from (keys used by fem.find_inp)
SOURCE_TEXTS = {
    "fem": "FEM working directory of the solver",
    "other": "another FEM working directory",
    "own": "own working directory (old version)",
    "written": "written",
}

# tooltip of the button that writes the input file
TIP_INP = ("Write the .inp from the FEM model (mesh, material, boundary conditions).\n"
           "Takes a few seconds for fine meshes, FreeCAD is blocked while it runs.")

# colours of the status line
COLOR_ERROR = "#b04040"      # something is wrong
COLOR_ACTION = "#b07000"     # the user has to do something
COLOR_OK = "#2e7d32"         # everything is ready
COLOR_GREY = "#808080"       # side note (size and date of the file)
COLOR_NOTE = "#b07000"       # orange note: something to decide
_active_panels = {}          # keep the panel instances alive (otherwise the GC collects them)


def panel_for(name):
    return _active_panels.get(name)


def open_assistant(obj):
    """Open the assistant for an optimization object (called by the view provider)."""
    if obj is None:
        return
    if panel_for(obj.Name) is not None:
        App.Console.PrintMessage("TopoOpt: the assistant for '%s' is already open.\n" % obj.Label)
        return
    ensure_properties(obj)                 # an object from an older file may miss properties
    panel = AssistantPanel(obj)
    _active_panels[obj.Name] = panel
    try:
        Gui.Control.showDialog(panel)
    except Exception as exc:
        _active_panels.pop(obj.Name, None)
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
        self.stress = {}           # elset -> allowable stress in MPa (0/empty = no FI)
        self.stress_possible = {}  # elset -> what the material would allow (MPa)
        self.stress_cleared = set()    # elset whose field was deliberately cleared
        self.elsets = {}           # elset -> number of elements
        self.analysis = None
        self.mesh = None
        self.solver = None
        self._closed = False
        self._loaded = False      # the first look at the document has happened
        self._step = 1
        self._robust_data = None      # element data from the .inp (fetched once)
        self._robust_result = None   # result of the robust radius search (once)
        self._filling = False    # no recalculation while filling
        self._run_process = None      # the running beso process (or None)
        self._run_log = ""            # our log (CalculiX output)
        self._run_beso_log = ""       # beso's table with the iteration values
        self._run_start = 0.0        # start time of the run

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(translate("Topology Optimization"))
        outer = QtWidgets.QVBoxLayout(self.form)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # the step bar sits on top and stays put, only the content scrolls in a
        # separate area (so the scroll bar is on the inside, not on the whole
        # task panel), back and next are at the bottom.
        self.step_label = QtWidgets.QLabel("")
        self.step_label.setTextFormat(QtCore.Qt.RichText)
        self.step_label.setWordWrap(True)
        outer.addWidget(self.step_label)

        # every page gets its own scroll area: a shared one would always be as tall
        # as the longest page and would therefore show a scroll bar in the short
        # steps too (that is how it was at first).
        self.pages = QtWidgets.QStackedWidget()
        self.scroll_areas = []
        pages = [self._initialize_page(), self._params_page(),
                 self._calculation_page()]
        pages += [self._placeholder_page() for _ in range(len(STEPS) - 3)]
        for page in pages:
            scroll_area = QtWidgets.QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
            scroll_area.setWidget(page)
            self.pages.addWidget(scroll_area)
            self.scroll_areas.append(scroll_area)
        outer.addWidget(self.pages, 1)

        nav = QtWidgets.QHBoxLayout()
        self.back_button = QtWidgets.QPushButton(translate("< Back"))
        self.back_button.clicked.connect(self._step_back)
        self.next_button = QtWidgets.QPushButton(translate("Next >"))
        self.next_button.clicked.connect(self._step_forward)
        nav.addWidget(self.back_button)
        nav.addStretch(1)
        nav.addWidget(self.next_button)
        outer.addLayout(nav)

        self._show_step(1)

        # the panel looks at the document by itself when it opens - but only once:
        # a load() that already happened (a test calls it right away) must not be
        # repeated later by the timer, it would overwrite the current status line.
        QtCore.QTimer.singleShot(50, self._load_if_needed)

    # ------------------------------------------------------------------ UI
    def _show_step(self, number):
        """Switch to a step: text on top, show the page, scroll bar to the top.

        The current step is bold, the others grey - so the bar looks:
        bold for the current step, grey for the others.
        """
        self._step = number
        self.pages.setCurrentIndex(number - 1)
        parts = []
        for index, name in enumerate(STEPS, start=1):
            text = "%d %s" % (index, translate(name))
            if index == number:
                parts.append("<b>%s</b>" % text)
            else:
                parts.append("<span style='color:gray'>%s</span>" % text)
        self.step_label.setText(" › ".join(parts))
        try:
            self.scroll_areas[number - 1].verticalScrollBar().setValue(0)
        except Exception:
            pass
        # at the edges the respective button disappears
        self.back_button.setVisible(number > 1)
        self.next_button.setVisible(number < len(STEPS))

    def _step_back(self):
        self._show_step(max(1, self._step - 1))

    def _step_forward(self):
        self._show_step(min(len(STEPS), self._step + 1))

    def _placeholder_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        label = _label_wrap(translate("This step is not built yet."))
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _initialize_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        # the header line (analysis, mesh, solver) belongs to this step only
        self.header = QtWidgets.QLabel("")
        self.header.setTextFormat(QtCore.Qt.RichText)
        self.header.setWordWrap(True)
        layout.addWidget(self.header)
        layout.addWidget(self._input_section())
        layout.addWidget(self._domain_table())
        layout.addStretch(1)          # free space below, not inside the table
        return page

    def _params_page(self):
        """Step 2: the parameters of the optimization (defaults from beso_conf.py)."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- target mass -------------------------------------------------
        frame = QtWidgets.QGroupBox(translate("Target mass"))
        form = QtWidgets.QGridLayout(frame)
        self.mass_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.mass_slider.setRange(MASS_MIN, MASS_MAX)
        self.mass_slider.setMinimumWidth(80)
        self.mass_slider.setToolTip(translate(TIP_MASS))
        self.mass_field = QtWidgets.QSpinBox()
        self.mass_field.setRange(MASS_MIN, MASS_MAX)
        self.mass_field.setSuffix(" %")
        self.mass_field.setToolTip(translate(TIP_MASS))
        self.mass_slider.valueChanged.connect(self._mass_changed)
        self.mass_field.valueChanged.connect(self._mass_changed)
        form.addWidget(self.mass_slider, 0, 0)
        form.addWidget(self.mass_field, 0, 1)
        layout.addWidget(frame)

        # --- the optimization itself -------------------------------------
        frame = QtWidgets.QGroupBox(translate("Optimization"))
        form = QtWidgets.QGridLayout(frame)
        row = 0
        form.addWidget(_label_wrap(translate("What is optimized")), row, 0)
        self.base_combo = _narrow_combo(QtWidgets.QComboBox())
        for value in BASES:
            self.base_combo.addItem(translate(BASE_LABELS.get(value, value)), value)
        self.base_combo.currentIndexChanged.connect(self._params_changed)
        form.addWidget(self.base_combo, row, 1)

        row += 1
        form.addWidget(_label_wrap(translate("Maximum iterations")), row, 0)
        self.iterations_field = QtWidgets.QLineEdit()
        self.iterations_field.setToolTip(translate("'auto' lets beso estimate the number of "
                                                    "iterations, a number stops after it."))
        self.iterations_field.editingFinished.connect(self._params_changed)
        form.addWidget(self.iterations_field, row, 1)

        row += 1
        form.addWidget(_label_wrap(translate("Stop tolerance")), row, 0)
        self.tolerance_field = _NumberField()
        self.tolerance_field.setDecimals(6)
        self.tolerance_field.setRange(0.000001, 1.0)
        self.tolerance_field.setSingleStep(0.0005)
        self.tolerance_field.setToolTip(translate("The optimization stops when the mean stress "
                                                   "changes less than this value in the last "
                                                   "5 iterations (beso: 0.001)."))
        self.tolerance_field.valueChanged.connect(self._params_changed)
        form.addWidget(self.tolerance_field, row, 1)

        row += 1
        form.addWidget(_label_wrap(translate("FI tolerance")), row, 0)
        self.fi_tolerance_field = _NumberField()
        self.fi_tolerance_field.setDecimals(0)
        self.fi_tolerance_field.setRange(1, 10000)
        self.fi_tolerance_field.setSingleStep(1)
        self.fi_tolerance_field.setToolTip(translate(
            "With an allowable stress beso freezes the mass as soon as this many more "
            "elements than at the start exceed the limit - beso's default is 1, so a "
            "single outlier can stop the run early. Raise it if your mesh has sharp "
            "corners or thin webs."))
        self.fi_tolerance_field.valueChanged.connect(self._params_changed)
        form.addWidget(self.fi_tolerance_field, row, 1)

        row += 1
        form.addWidget(_label_wrap(translate("Material change per iteration")), row, 0)
        self.mass_change_combo = _narrow_combo(QtWidgets.QComboBox())
        for key in MASS_CHANGE:
            self.mass_change_combo.addItem(
                translate(MASS_CHANGE_LABELS.get(key, key)), key)
        self.mass_change_combo.setToolTip(translate("How much material beso adds or "
                                                     "removes per iteration."))
        self.mass_change_combo.currentIndexChanged.connect(self._params_changed)
        form.addWidget(self.mass_change_combo, row, 1)

        row += 1
        form.addWidget(_label_wrap(translate("Processor cores")), row, 0)
        self.cores_field = QtWidgets.QSpinBox()
        self.cores_field.setRange(0, 128)
        # 0 shows as "all" - setSpecialValueText() works because the minimum is 0
        self.cores_field.setSpecialValueText(translate("all"))
        self.cores_field.setToolTip(translate("Cores for the solver; 'all' uses every core "
                                               "of the computer."))
        self.cores_field.valueChanged.connect(self._params_changed)
        form.addWidget(self.cores_field, row, 1)
        layout.addWidget(frame)          # optimization

        layout.addWidget(self._filter_section())

        # --- result files ------------------------------------------------
        frame = QtWidgets.QGroupBox(translate("Result files"))
        form = QtWidgets.QGridLayout(frame)
        form.addWidget(_label_wrap(translate("Save every n-th iteration")), 0, 0)
        self.save_field = QtWidgets.QSpinBox()
        self.save_field.setRange(0, 100)
        self.save_field.setToolTip(translate("0 saves only the final result. Every saved "
                                              "iteration needs disk space (a fine mesh "
                                              "can need 100 MB and more)."))
        self.save_field.valueChanged.connect(self._params_changed)
        form.addWidget(self.save_field, 0, 1)
        form.addWidget(_label_wrap(translate("Format of the result meshes")), 1, 0)
        self.format_combo = _narrow_combo(QtWidgets.QComboBox())
        for value in FORMATS:
            self.format_combo.addItem(value, value)
        self.format_combo.currentIndexChanged.connect(self._params_changed)
        form.addWidget(self.format_combo, 1, 1)
        layout.addWidget(frame)
        layout.addStretch(1)
        return page

    def _filter_section(self):
        """Step 2: the sensitivity filters - as many rows as the user needs.

        beso takes a list of filters and applies them one after the other
        (e.g. first "casting", then "simple"), so the number of rows is free.
        """
        frame = QtWidgets.QGroupBox(translate("Filter"))
        outer = QtWidgets.QVBoxLayout(frame)

        self.filter_layout = QtWidgets.QVBoxLayout()
        self.filter_layout.setSpacing(2)
        outer.addLayout(self.filter_layout)
        self.filter_rows = []

        button_line = QtWidgets.QHBoxLayout()
        button_line.addStretch(1)               # the button sits on the right
        self.add_filter_button = QtWidgets.QToolButton()
        self.add_filter_button.setText("+")
        self.add_filter_button.setToolTip(translate("Add filter") + " - "
                                          + translate("beso applies the filters one after the "
                                                       "other, for example first 'casting', then "
                                                       "'simple'."))
        self.add_filter_button.clicked.connect(lambda: self._add_filter())
        button_line.addWidget(self.add_filter_button)
        outer.addLayout(button_line)

        note = _label_wrap(translate("robust: smallest radius at which every element "
                                      "still has a neighbour") + "\n"
                           + translate("automatic: 2 x mean element size (as in beso)")
                           + "\n"
                           + translate("manual: your own value in millimetres"))
        note.setStyleSheet("color: %s;" % COLOR_GREY)
        outer.addWidget(note)
        return frame

    def _add_filter(self, filter_type="none", reach="auto", direction="(0, 0, 1)"):
        """Add a filter row (also used when the dialog shows the stored filters)."""
        row = self._filter_row()
        row["type"].setCurrentIndex(max(0, row["type"].findData(filter_type)))
        if reach in ("auto", "robust"):
            row["radius_mode"].setCurrentIndex(
                max(0, row["radius_mode"].findData(reach)))
        elif isinstance(reach, (int, float)):
            row["radius_mode"].setCurrentIndex(
                max(0, row["radius_mode"].findData("manual")))
            row["radius_value"].setValue(float(reach))
        row["direction"].setText(str(direction))
        row["radius_info"].set_action(lambda z=row: self._check_radius(z))
        self.filter_layout.addWidget(row["widget"])
        self.filter_rows.append(row)
        self._number_filters()
        self._filter_changed()
        return row

    def _remove_filter(self, row):
        """Remove one filter row (the "minus" button)."""
        if row not in self.filter_rows:
            return
        self.filter_rows.remove(row)
        self.filter_layout.removeWidget(row["widget"])
        row["widget"].setParent(None)
        row["widget"].deleteLater()
        self._number_filters()
        self._filter_changed()

    def _number_filters(self):
        for number, row in enumerate(self.filter_rows, start=1):
            row["label"].setText(translate("Filter %d") % number)

    def _filter_row(self):
        """The widgets of one filter row (not yet added to the layout)."""
        row = {}
        row["widget"] = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row["widget"])
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        row["label"] = _label_wrap("")
        layout.addWidget(row["label"])

        row["type"] = _narrow_combo(QtWidgets.QComboBox(), 4)
        for value, text in FILTER_OPTIONS:
            row["type"].addItem(translate(text), value)
        row["type"].setToolTip(translate(TIP_FILTER))
        row["type"].currentIndexChanged.connect(self._filter_changed)
        layout.addWidget(row["type"], 1)

        row["radius_mode"] = _narrow_combo(QtWidgets.QComboBox(), 4)
        for value, text in RADIUS_MODES:
            row["radius_mode"].addItem(translate(text), value)
        row["radius_mode"].setToolTip(translate(TIP_RADIUS))
        row["radius_mode"].currentIndexChanged.connect(self._filter_changed)
        layout.addWidget(row["radius_mode"])

        row["radius_value"] = QtWidgets.QDoubleSpinBox()
        row["radius_value"].setRange(0.001, 1000.0)
        row["radius_value"].setDecimals(3)
        row["radius_value"].setSuffix(" mm")
        row["radius_value"].setValue(2.0)
        row["radius_value"].setToolTip(translate("Radius in millimetres - a larger radius "
                                                 "gives thicker struts and fewer fine "
                                                 "details. The filter needs a radius in "
                                                 "which every element has a neighbour."))
        row["radius_value"].valueChanged.connect(self._filter_changed)
        layout.addWidget(row["radius_value"])

        # the computed radius sits here - or "berechnen" as long as there is none
        row["radius_info"] = _ClickLabel("")
        row["radius_info"].setWordWrap(True)
        # ignored: the field does not determine the minimum width of the panel (the
        # tooltip has the full text) - otherwise the panel would get wide again
        row["radius_info"].setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                         QtWidgets.QSizePolicy.Preferred)
        layout.addWidget(row["radius_info"], 1)

        # the check takes a few seconds on fine meshes - so the user starts it
        row["check"] = QtWidgets.QToolButton()
        row["check"].setText("\u21bb")       # circular arrow
        row["check"].setToolTip(translate("Check the robust filter radius now"))
        row["check"].clicked.connect(lambda _checked=False, z=row: self._check_radius(z))
        layout.addWidget(row["check"])

        row["direction"] = QtWidgets.QLineEdit("(0, 0, 1)")
        row["direction"].setMinimumWidth(50)
        row["direction"].setVisible(False)     # only the casting filter needs it
        row["direction"].setToolTip(translate("Only for the casting filter: the direction in "
                                              "which the part has to be demouldable."))
        row["direction"].editingFinished.connect(self._filter_changed)
        layout.addWidget(row["direction"])

        row["remove"] = QtWidgets.QToolButton()
        row["remove"].setText("\u2212")        # minus sign
        row["remove"].setToolTip(translate("Remove this filter"))
        row["remove"].clicked.connect(lambda _checked=False, z=row: self._remove_filter(z))
        layout.addWidget(row["remove"])
        return row

    def _filter_changed(self):
        """Enable what belongs to the chosen filter type and store the filters."""
        for row in self.filter_rows:
            filter_type = row["type"].currentData()
            active = filter_type != "none"
            casting = filter_type == "casting"
            mode = row["radius_mode"].currentData()
            row["radius_mode"].setEnabled(active)
            # only show what is needed: a hidden widget does not make the panel wider
            row["radius_value"].setVisible(active and mode == "manual")
            row["direction"].setVisible(casting)
            row["direction"].setEnabled(casting)
            if active and mode == "robust":
                # the button belongs only to "robust"; "berechnen" in the field does the same
                row["check"].setVisible(True)
                if self._robust_result is not None:
                    self._show_radius(row)
                elif self.obj.RobusterRadius > 0:
                    # no calculation when the dialog opens - show the remembered value
                    self._radius_text(row, "%.3f mm" % self.obj.RobusterRadius, COLOR_GREY,
                                      translate("%.3f mm (saved value from the last check)")
                                      % self.obj.RobusterRadius)
                else:
                    self._radius_text(row, translate("calculate"), COLOR_ACTION,
                                      translate("Check the robust filter radius now"))
            else:
                row["check"].setVisible(False)
                self._radius_text(row, "", "")
        self.obj.Filters = format_filters(self._collect_filters())

    def _radius_text(self, row, text, color, tooltip=""):
        """Set text, colour and tooltip of the radius field at a filter row."""
        row["radius_info"].setText(text)
        row["radius_info"].setStyleSheet("color: %s;" % color if color else "")
        row["radius_info"].setToolTip(tooltip)

    def _robust_radius(self):
        """The robust radius, computed by beso (see core/radius.py).

        The element data is fetched and remembered only once - reading the .inp
        and the neighbour search take a few seconds on fine meshes.
        """
        if self._robust_data is None:
            data = {}
            if self.obj.InpFile and os.path.isfile(self.obj.InpFile):
                design = [name for name, role in self.domains.items() if role == dom.DESIGN]
                if design:
                    all_sets = list(self.elsets) or design
                    data = radius_module.read_data(self.obj.InpFile, all_sets, design)
            self._robust_data = data
        if not self._robust_data:
            return {}
        result = radius_module.robust(self._robust_data)
        result["mean"] = self._robust_data["mean"]
        return result

    def _check_radius(self, row):
        """The button at the filter row: recompute the robust radius and show it.

        The calculation takes a few seconds on fine meshes, which is why a click
        starts it (and not the opening of the dialog).
        """
        self._robust_data = None
        self._robust_result = None
        self._set_status(translate("Checking the robust filter radius with beso ... "
                                    "this can take a few seconds."), "info")
        QtWidgets.QApplication.processEvents()
        try:
            self._robust_result = self._robust_radius()
        except Exception as exc:
            self._robust_result = {}
            App.Console.PrintError("TopoOpt: %s\n" % exc)
            self._set_status(translate("The robust radius could not be calculated: %s")
                             % exc, "fehler")
        if self._robust_result:
            self.obj.RobusterRadius = self._robust_result["radius"]
            self.obj.MittlereGroesse = self._robust_result["mean"]
            self._set_status(translate("Robust filter radius: %.3f mm = %.1f x mean "
                                        "element size, %d element(s) without a neighbour.")
                             % (self._robust_result["radius"],
                                  self._robust_result["factor"],
                                  self._robust_result["without_neighbours"]), "ok")
        else:
            self._set_status(translate("The robust radius needs an input file and a "
                                        "design space - check step 1."), "fehler")
        for other in self.filter_rows:
            if other["radius_mode"].currentData() == "robust":
                self._show_radius(other)
        self.obj.Filters = format_filters(self._collect_filters())

    def _show_radius(self, row):
        """Write the result of the radius check to the filter row (short text + tooltip)."""
        if not self._robust_result:
            self._radius_text(row, translate("calculate"), COLOR_ACTION,
                              translate("Check the robust filter radius now"))
            return
        self._radius_text(row, "%.3f mm" % self._robust_result["radius"], COLOR_OK,
                          translate("%.3f mm = %.1f x mean size, %d without neighbour")
                          % (self._robust_result["radius"],
                             self._robust_result["factor"],
                             self._robust_result["without_neighbours"]))

    def _collect_filters(self):
        """The filters from the widgets, in the form beso uses."""
        collected = []
        for row in self.filter_rows:
            filter_type = row["type"].currentData()
            if filter_type == "none":
                continue
            mode = row["radius_mode"].currentData()
            reach = (mode if mode in ("auto", "robust")
                     else round(row["radius_value"].value(), 4))
            entry = [filter_type, reach]
            if filter_type == "casting":
                entry.append(row["direction"].text().strip() or "(0, 0, 1)")
            collected.append(entry)
        return collected

    def _fill_filters(self):
        """Rebuild the rows from the filters stored in the object."""
        self._filling = True
        try:
            for row in list(self.filter_rows):
                self._remove_filter(row)
            for entry in parse_filters(getattr(self.obj, "Filters", "")):
                direction = str(entry[2]) if len(entry) > 2 else "(0, 0, 1)"
                self._add_filter(entry[0], entry[1], direction)
        finally:
            self._filling = False
        self._filter_changed()

    def _calculation_page(self):
        """Step 3: start the optimization, watch it and look at the result.

        Run and results belong together in one step "Calculation".
        """
        from .verlauf import History

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- computing: start, cancel, progress, details ---
        run_frame = QtWidgets.QGroupBox(translate("Calculate"))
        run_layout = QtWidgets.QVBoxLayout(run_frame)

        row = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton(translate("Start optimization"))
        self.start_button.setToolTip(translate("Writes the beso configuration and starts beso "
                                               "as its own process - FreeCAD stays usable."))
        self.start_button.clicked.connect(self._run_button)
        row.addWidget(self.start_button)
        row.addStretch(1)
        # the runtime sits right of the button - it belongs to the run, not to the panel
        self.run_time = QtWidgets.QLabel("")
        self.run_time.setToolTip(translate("How long the solver has been running"))
        self.run_time.setStyleSheet("color: gray;")
        row.addWidget(self.run_time)
        run_layout.addLayout(row)

        # progress: 0 % = start mass, 100 % = target mass
        self.bar = QtWidgets.QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setToolTip(translate("0 % = the whole part, 100 % = the target mass"))
        run_layout.addWidget(self.bar)

        # collapsible field for the last log lines ("Detail") - belongs to computing.
        # The status sits in the same line: a line of its own would be invisibly empty
        # as long as nothing runs (otherwise an empty line would remain).
        header_line = QtWidgets.QHBoxLayout()
        self.detail_button = QtWidgets.QToolButton()
        self.detail_button.setText(translate("Details"))
        self.detail_button.setCheckable(True)
        self.detail_button.setArrowType(QtCore.Qt.RightArrow)
        self.detail_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.detail_button.clicked.connect(self._toggle_detail)
        header_line.addWidget(self.detail_button)
        self.run_status = _label_wrap("")
        self.run_status.setStyleSheet("color: gray;")
        # give the label the rest of the line: otherwise it only gets its (small)
        # preferred width although there is room on the right, and wraps onto two lines
        header_line.addWidget(self.run_status, 1)
        run_layout.addLayout(header_line)

        self.detail = QtWidgets.QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setVisible(False)
        self.detail.setMaximumHeight(150)
        self.detail.setToolTip(translate("The last lines of the run - 'Whole log' opens "
                                          "the complete file."))
        run_layout.addWidget(self.detail)
        layout.addWidget(run_frame)

        # --- the results: mesh and charts ---
        results_frame = QtWidgets.QGroupBox(translate("Results"))
        results_box = QtWidgets.QVBoxLayout(results_frame)

        # the four buttons form a 2x2 grid:
        #   load result mesh | show charts
        #   full log         | open working directory
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(6)
        self.load_mesh_button = QtWidgets.QPushButton(translate("Load result network"))
        self.load_mesh_button.setToolTip(translate("Loads the network of the last iteration "
                                                   "(_state1.inp) as a real FEM mesh into the "
                                                   "document - that is the result to work with"))
        self.load_mesh_button.clicked.connect(self._load_result_mesh)
        grid.addWidget(self.load_mesh_button, 0, 0)
        self.show_charts_button = QtWidgets.QPushButton(translate("Show diagrams"))
        self.show_charts_button.setToolTip(translate("Opens the window with the four charts "
                                                     "(mass, stress, overloaded elements, energy)"))
        self.show_charts_button.clicked.connect(self._show_history)
        grid.addWidget(self.show_charts_button, 0, 1)
        self.log_button = QtWidgets.QPushButton(translate("Whole log"))
        self.log_button.setToolTip(translate("Opens the log file of the run"))
        self.log_button.clicked.connect(self._open_log)
        grid.addWidget(self.log_button, 1, 0)
        self.open_results_button = QtWidgets.QPushButton(translate("Open working directory"))
        self.open_results_button.setToolTip(translate("Opens the working directory with all files"))
        self.open_results_button.clicked.connect(self._open_folder)
        grid.addWidget(self.open_results_button, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        results_box.addLayout(grid)

        # "Iterationen anzeigen" (VTK player) belongs to the slider below
        self.iterations_button = QtWidgets.QPushButton(translate("Show iterations"))
        self.iterations_button.setToolTip(translate("Reads resulting_states.vtk and shows the "
                                                    "material that is left in the part "
                                                    "(the film of the run)"))
        self.iterations_button.clicked.connect(self._result_button)

        self.result_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.result_slider.setMinimum(1)
        self.result_slider.setMaximum(1)
        self.result_slider.setMinimumWidth(40)
        self.result_slider.setToolTip(translate("Iteration to show"))
        self.result_slider.valueChanged.connect(self._show_iteration)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.iterations_button)
        row.addStretch(1)
        self.previous_button = QtWidgets.QPushButton("\u25c0")
        self.previous_button.setToolTip(translate("One iteration back"))
        self.previous_button.clicked.connect(lambda: self._result_step(-1))
        self.forward_button = QtWidgets.QPushButton("\u25b6")
        self.forward_button.setToolTip(translate("One iteration forward"))
        self.forward_button.clicked.connect(lambda: self._result_step(1))
        self.play_button = QtWidgets.QPushButton(translate("Play"))
        self.play_button.setCheckable(True)
        self.play_button.setToolTip(translate("Show one iteration after the other"))
        self.play_button.clicked.connect(self._play_result)
        for button in (self.previous_button, self.forward_button, self.play_button):
            # FreeCAD's style gives every button a minimum width of about 106 px -
            # several widgets side by side blow up the narrow panel (measured: 396 px).
            # For these small buttons the default does not apply.
            button.setStyleSheet("min-width: 0px; padding: 2px 6px;")
            row.addWidget(button)
        # the playback speed belongs to the control buttons
        self.pace_combo = QtWidgets.QComboBox()
        self.pace_combo.addItems([translate("0.5 s"), translate("1 s"),
                                  translate("2 s"), translate("3 s")])
        self.pace_combo.setToolTip(translate("Pause between two pictures of the film"))
        self.pace_combo.setStyleSheet("min-width: 0px;")
        self.pace_combo.currentIndexChanged.connect(self._pace_changed)
        row.addWidget(self.pace_combo)
        results_box.addLayout(row)

        # the slider stands alone in its line and gets the full width
        results_box.addWidget(self.result_slider)

        self.result_info = _label_wrap("")
        results_box.addWidget(self.result_info)


        layout.addWidget(results_frame)
        layout.addStretch(1)

        self.history = History(target_mass=getattr(self.obj, "MassGoalRatio", None))
        self.player = None                    # VTK player as soon as results are loaded
        self.run_timer = QtCore.QTimer()
        self.run_timer.setInterval(1500)
        self.run_timer.timeout.connect(self._update_run)
        self.result_timer = QtCore.QTimer()
        self.result_timer.setInterval(500)     # 0.5 s per frame
        self.result_timer.timeout.connect(lambda: self._result_step(1, from_timer=True))
        return page

    def _show_history(self):
        """Open the window with the four charts (or bring it to the front)."""
        window = self.history.show()
        if window is None:
            self._set_status(translate("The plot module of FreeCAD is not available - "
                                        "the charts need 'Plot' in FreeCAD's module folder."),
                             "fehler")
        return window

    def _result_path(self):
        """The file with the iterations in the working directory of the run.

        When the run is finished, ``resulting_states.vtk`` with **all** iterations
        lies there.  During the run beso writes one ``fileNNN.vtk`` per saved
        iteration (each with a part of the states) - the newest of them shows the
        current intermediate state.  Sorting is by modification time, not
        alphabetically: otherwise the highest number of an earlier run wins.
        """
        folder = getattr(self.obj, "WorkingDir", "")
        if not folder:
            return ""
        complete = os.path.join(folder, "resulting_states.vtk")
        if os.path.isfile(complete):
            return complete
        existing = [os.path.join(folder, name) for name in os.listdir(folder)
                    if name.startswith("file") and name.endswith(".vtk")]
        if not existing:
            return ""
        return max(existing, key=os.path.getmtime)

    @staticmethod
    def _is_final_state(path):
        """True when it is the complete result (not an intermediate state)."""
        return os.path.basename(path) == "resulting_states.vtk"

    @staticmethod
    def _result_iteration(path):
        """The iteration number from the file name (file030.vtk -> 30, otherwise 0)."""
        digits = "".join(z for z in os.path.basename(path) if z.isdigit())
        return int(digits) if digits else 0

    def _update_results(self):
        """Is a result there already?  Then enable the button and show the state."""
        path = self._result_path()
        present = bool(path) and os.path.isfile(path)
        self.iterations_button.setEnabled(present)
        self.log_button.setEnabled(bool(self._logfile_path()))
        self.open_results_button.setEnabled(bool(getattr(self.obj, "WorkingDir", "")))
        if not present:
            self.result_info.setText(translate("No result file yet - it is written when "
                                               "the run is finished."))
            return
        if self.player is None and not self.result_info.text():
            if self._is_final_state(path):
                self.result_info.setText(translate("resulting_states.vtk is there - "
                                                   "'Show iterations' reads it."))
            else:
                # intermediate state: during the run beso writes one file per saved
                # iteration with a part of the states
                self.result_info.setText(
                    translate("Interim result of iteration %d - 'Show iterations' reads it. "
                               "The complete result is written when the run is finished.")
                    % self._result_iteration(path))

    def _load_result_mesh(self):
        """Load the real result mesh of the last iteration as an FEM mesh.

        This is beso's state file state1 (elements with material), imported with
        FreeCAD's own FEM import - to keep working with, not just to look at.
        """
        folder = getattr(self.obj, "WorkingDir", "")
        state_file = mesh_module.latest_state1(folder)
        if not state_file:
            self.result_info.setText(translate("No state file (_state1.inp) in the working "
                                               "directory yet."))
            return ""
        try:
            mesh_module.load(state_file, self.obj.Document)
        except Exception as exc:
            self.result_info.setText(translate("The result network could not be loaded: %s")
                                     % exc)
            return ""
        self.result_info.setText(translate("Result network loaded: %s")
                                 % os.path.basename(state_file))
        App.Console.PrintMessage(translate("TopoOpt: result network loaded from %s") % state_file)
        return state_file

    def _result_button(self):
        """Button 'load result': read the file again and show the finished mesh.

        Deliberately re-read - after another run the file is a different one.
        """
        self.player = None
        return self._show_result()

    def _show_result(self):
        """Read resulting_states.vtk and show the last iteration."""
        path = self._result_path()
        if not path or not os.path.isfile(path):
            self.result_info.setText(translate("No resulting_states.vtk in the working "
                                               "directory yet."))
            return None
        if self.player is None:
            from .vtk_anzeige import Player
            try:
                self.player = Player.load(path, self.obj.Document,
                                          label=translate("TopoOpt iteration"))
            except Exception as exc:
                self.result_info.setText(translate("The result file could not be read: %s")
                                         % exc)
                return None
            self.result_slider.setRange(1, self.player.count)
            self.result_slider.setValue(self.player.count)   # last iteration
        self._show_iteration(self.result_slider.value())
        return self.player

    def _show_iteration(self, number):
        """Show iteration ``number`` (from the slider or from the timer)."""
        if self.player is None:
            return
        data = self.player.show(number)
        if self.result_slider.value() != data["number"]:
            self.result_slider.blockSignals(True)
            self.result_slider.setValue(data["number"])
            self.result_slider.blockSignals(False)
        self.result_info.setText(
            translate("Iteration %d of %d | %s of %s elements left (%.1f %%)")
            % (data["number"], data["count"],
               "{:,}".format(data["cells"]).replace(",", "."),
               "{:,}".format(data["total"]).replace(",", "."), data["percent"]))

    def _result_step(self, direction, from_timer=False):
        """One iteration forward or back."""
        if self.player is None:
            if from_timer:
                self._play_result(False)
            return
        next_number = self.result_slider.value() + direction
        if next_number > self.player.count or next_number < 1:
            if from_timer:
                self._play_result(False)      # reached the end
            return
        self.result_slider.setValue(next_number)

    def _pace_changed(self, *_):
        """Take the pause between two frames from the choice."""
        pace = self.pace_combo.currentText().replace(",", ".").replace(" s", "").strip()
        try:
            self.result_timer.setInterval(int(float(pace) * 1000))
        except ValueError:
            self.result_timer.setInterval(500)

    def _play_result(self, play=None):
        """Show all iterations one after the other."""
        if play is None:
            play = self.play_button.isChecked()
        if play and self.player is None:
            self._show_result()
        if play and self.player is not None:
            if self.result_slider.value() >= self.player.count:
                self.result_slider.setValue(1)      # from the start
            self.play_button.setChecked(True)
            self.play_button.setText(translate("Stop"))
            self.result_timer.start()
        else:
            self.result_timer.stop()
            self.play_button.setChecked(False)
            self.play_button.setText(translate("Play"))

    def _logfile_path(self):
        """Our log file - taken from the run or derived from the input file."""
        if self._run_log and os.path.isfile(self._run_log):
            return self._run_log
        inp = getattr(self.obj, "InpFile", "")
        if inp:
            path = conf_module.log_path(inp)
            if os.path.isfile(path):
                return path
        return ""

    def _open_log(self):
        """Open the complete log in the default program."""
        path = self._logfile_path()
        if not path:
            self.result_info.setText(translate("There is no log file yet."))
            return
        try:
            if os.name == "nt":
                os.startfile(path)
            # xdg-open only exists on Linux; Qt opens the file on macOS and Linux alike
            elif not QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path)):
                raise RuntimeError(path)
        except Exception as exc:
            self.result_info.setText(translate("The log file could not be opened: %s") % exc)

    def _toggle_detail(self):
        visible = self.detail_button.isChecked()
        self.detail.setVisible(visible)
        self.detail_button.setArrowType(QtCore.Qt.DownArrow if visible
                                        else QtCore.Qt.RightArrow)
        if visible:
            self._fill_detail()
            self._update_run()

    # ------------------------------------------------------------- the run
    def _run_button(self):
        """One button: start, and cancel while the run goes on."""
        if self._run_process is not None and self._run_process.poll() is None:
            self._cancel_run()
        else:
            self._start_run()

    def _start_run(self):
        if not self.obj.InpFile or not os.path.isfile(self.obj.InpFile):
            # show the step first, then the message: switching to step 1 writes the
            # .inp info into the same line and would otherwise delete it
            self._show_step(1)
            self._set_status(translate("There is no input file yet - see step 1."), "fehler")
            return
        domains = dict(self.domains)
        if not [name for name, role in domains.items() if role == dom.DESIGN]:
            self._show_step(1)
            self._set_status(translate("No design space is marked - see step 1."), "fehler")
            return
        if getattr(self.solver, "SplitInputWriter", False):
            # the writer then spreads the model over several files - the optimization
            # needs the one complete .inp (reported from the field, see D46)
            self._show_step(1)
            self._set_status(translate("The solver writes a split input file ('Split input write')"
                                       " - there is no complete .inp then. Set it to 'no' in the "
                                       "CalculiX solver and write the input file again."), "fehler")
            return
        try:
            process, log, conf = conf_module.start(self.obj, self.obj.InpFile, domains,
                                                   self.obj.WorkingDir or
                                                   os.path.dirname(self.obj.InpFile))
        except Exception as exc:
            # translate the error message too - it comes from the core
            self._set_status(translate("The run could not be started: %s")
                             % translate(str(exc)), "fehler")
            return
        self._run_process = process
        self._run_log = log
        self._run_beso_log = conf_module.beso_log_path(self.obj.InpFile)
        self._run_start = time.time()
        self.history.target_mass = getattr(self.obj, "MassGoalRatio", None)
        self.history.reset()
        self.history.running = True
        self.history._start_time = self._run_start
        self.bar.setValue(0)
        self.run_time.setText("0:00 min")
        self.player = None                    # a new run has new results
        self.result_slider.setRange(1, 1)
        self._update_results()
        self.start_button.setText(translate("Cancel"))
        self.start_button.setToolTip(translate("Stop the run (CalculiX is stopped as well)"))
        self._set_status(translate("Run started (%s) ...") % os.path.basename(conf), "info")
        self._show_history()      # charts always open on start
        self.run_timer.start()
        self._update_run()

    def _cancel_run(self):
        process = self._run_process
        if process is None or process.poll() is not None:
            return
        try:
            if os.name == "nt":
                # /T also ends CalculiX, which beso started
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                               capture_output=True)
            else:
                process.terminate()
        except Exception as exc:
            App.Console.PrintWarning("TopoOpt: %s\n" % exc)
        self._set_status(translate("Run cancelled."), "auftrag")
        self._update_run()

    def _update_run(self):
        """Called by the timer: read the log files, follow up the display (nothing blocks)."""
        if not self._run_log:
            return
        # the values are in beso's own table, the last lines in our log
        data = log_module.progress(self._run_beso_log,
                                   getattr(self.obj, "MassGoalRatio", None))
        self.history.set_values(data["values"])
        self.history.draw()
        running = self._run_process is not None and self._run_process.poll() is None

        self.bar.setValue(int(log_module.ratio(data["start"], data["mass"],
                                               getattr(self.obj, "MassGoalRatio", None))))
        parts = []
        if data["mass"] is not None:
            parts.append(translate("Iteration %d") % data["iteration"])
            if data["target"]:
                parts.append(translate("mass %.0f, target %.0f")
                             % (data["mass"], data["target"]))
            else:
                parts.append(translate("mass %.0f") % data["mass"])
        elif running:
            parts.append(translate("CalculiX is running ..."))
        if self._run_start:
            seconds = int(time.time() - self._run_start)
            self.run_time.setText("%d:%02d min" % (seconds // 60, seconds % 60))
        if parts:
            self.run_status.setText(" | ".join(parts))
        # an empty status line only costs space
        self.run_status.setVisible(bool(parts))

        # release the last intermediate state during the run: beso writes a
        # fileNNN.vtk every few iterations - the result button does not have to wait
        # for the end of the run
        if running:
            self._update_results()

        if self.detail.isVisible():
            self._fill_detail()

        if not running:
            self.run_timer.stop()
            self.history.running = False
            self.history.close()
            self.history.draw()
            self.start_button.setText(translate("Start optimization"))
            self.start_button.setToolTip(translate("Writes the beso configuration and starts beso "
                                                   "as its own process - FreeCAD stays usable."))
            code = self._run_process.returncode if self._run_process else None
            history = log_module.read_history(self._run_log)
            complete = history["done"]
            if code == 0 and complete:
                self._set_status(translate("Optimization finished after %d iteration(s).")
                                 % data["iteration"], "ok")
                self._update_results()
                self._show_result()          # show the finished mesh right away
            else:
                library = log_module.missing_library(history["text"])
                if library:
                    # the .inp asks for a solver this ccx was not built with - that is an
                    # instruction, not a broken model (see D46)
                    self._set_status(translate("CalculiX cannot use the %s solver: this ccx was "
                                               "built without it. Set the solver type to 'default' "
                                               "in the FEM solver, or set a ccx with %s under "
                                               "Preferences > FEM > CalculiX.")
                                     % (library, library), "fehler")
                else:
                    self._set_status(translate("The run ended (code %s) - open the details.")
                                     % code, "fehler")
                # expand and fill the text ONCE: a call of _toggle_detail() would from
                # there call _update_run() again and circle endlessly on an error
                # (RecursionError)
                if not self.detail_button.isChecked():
                    self.detail_button.setChecked(True)
                    self.detail.setVisible(True)
                    self.detail_button.setArrowType(QtCore.Qt.DownArrow)
                self._fill_detail()

    def _fill_detail(self):
        """Write the last lines of our own protocol into the detail field."""
        if not self._run_log:
            return
        text = log_module.read_history(self._run_log)["text"]
        self.detail.setPlainText("\n".join(text.splitlines()[-40:]))
        scroll_bar = self.detail.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def _input_section(self):
        frame = QtWidgets.QGroupBox(translate("CalculiX input file (.inp)"))
        layout = QtWidgets.QGridLayout(frame)

        # row 0: the path and the button that opens the folder in the file manager
        self.path_field = QtWidgets.QLineEdit()
        self.path_field.setReadOnly(True)
        self.path_field.setMinimumWidth(100)
        self.path_field.setToolTip(translate("The optimizer writes its iteration files "
                                               "next to this file."))
        layout.addWidget(self.path_field, 0, 0)
        self.open_folder_button = QtWidgets.QPushButton(translate("Open working directory"))
        self.open_folder_button.clicked.connect(self._open_folder)
        self.open_folder_button.setEnabled(False)   # enabled as soon as the directory is known
        layout.addWidget(self.open_folder_button, 0, 1)

        # row 1: size and date of the file (nothing else - what happened is in the hint)
        self.info = QtWidgets.QLabel("")
        self.info.setStyleSheet("color: %s;" % COLOR_GREY)
        layout.addWidget(self.info, 1, 0, 1, 2)

        # row 2: button on the left, hint on the right
        self.inp_button = QtWidgets.QPushButton(translate("Write input file (.inp)"))
        self.inp_button.setToolTip(translate(TIP_INP))
        self.inp_button.clicked.connect(self._write_inp)
        layout.addWidget(self.inp_button, 2, 0)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status, 2, 1)

        # row 3: what is wrong with the file itself (incomplete, set without material)
        self.inp_note = QtWidgets.QLabel("")
        self.inp_note.setWordWrap(True)
        self.inp_note.setStyleSheet("color: %s;" % COLOR_ERROR)
        self.inp_note.setVisible(False)
        layout.addWidget(self.inp_note, 3, 0, 1, 2)
        layout.setColumnStretch(1, 1)
        return frame

    def _check_inp(self):
        """Report clearly when the input file cannot be used for a run.

        Two cases that otherwise only beso reports - and there in a way that is
        hard to understand ("CalculiX results not found"):

        * the file was cut off while writing (no *MATERIAL/*STEP/*BOUNDARY),
        * an element set has no section card, so CalculiX computes its elements
          without material and leaves them out.
        """
        if not hasattr(self, "inp_note"):
            return
        result = elset_reader.check_inp(getattr(self.obj, "InpFile", ""), sorted(self.elsets))
        parts = []
        if result["missing_cards"]:
            parts.append(translate("The input file is incomplete (%s missing) - write it again.")
                         % ", ".join(result["missing_cards"]))
        if result["without_material"]:
            parts.append(translate("CalculiX has no material for these element sets (no section "
                                    "card): %s - their elements are left out of the calculation.")
                         % ", ".join(result["without_material"]))
        # material without a Young's modulus: FreeCAD aborts while writing and leaves
        # a half-finished .inp behind - this has to be noticed here, not as a KeyError
        missing = material_module.missing_values(material_module.find_materials(self.analysis))
        if missing:
            parts.append(translate("These materials are missing values CalculiX needs: %s - "
                                    "complete them in the material editor.")
                         % ", ".join("%s (%s)" % (name, ", ".join(values))
                                     for name, values in sorted(missing.items())))
        # the solver type of the FEM solver ends up in the .inp; a ccx without that
        # library stops with "library is not linked" - say it before the run
        solver_name = elset_reader.solver_keyword(getattr(self.obj, "InpFile", ""))
        if solver_name in ("PASTIX", "PARDISO"):
            parts.append(translate("The input file asks for the %s solver - if the ccx in use "
                                    "was built without it, CalculiX stops with 'library is not "
                                    "linked'. Then set the solver type to 'default' or set a ccx "
                                    "with %s under Preferences > FEM > CalculiX.")
                         % (solver_name, solver_name))
        if self.solver is not None and getattr(self.solver, "SplitInputWriter", False):
            parts.append(translate("The solver writes a split input file ('Split input write')"
                                    " - the optimization needs the one complete .inp."))
        self.inp_note.setText(" ".join(parts))
        self.inp_note.setVisible(bool(parts))

    def _domain_table(self):
        frame = QtWidgets.QGroupBox(translate("Domains - roles of the elements"))
        layout = QtWidgets.QVBoxLayout(frame)
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([translate("Element set"), translate("Role"),
                                              translate("Elements"),
                                              translate("σ (MPa)")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        layout.addWidget(self.table)
        # which domain gets which shell thickness (from the .inp, not guessed)
        self.thickness_note = _label_wrap("")
        self.thickness_note.setStyleSheet("color: gray;")
        self.thickness_note.setVisible(False)
        layout.addWidget(self.thickness_note)
        # without an allowable stress there is no failure index - that has to be visible
        self.stress_note = _label_wrap("")
        self.stress_note.setStyleSheet("color: %s;" % COLOR_NOTE)
        self.stress_note.setVisible(False)
        layout.addWidget(self.stress_note)
        return frame

    def _show_stress_note(self):
        """Red/orange below the list: without σ there is no failure index."""
        if not hasattr(self, "stress_note"):
            return
        # ignored element sets do not matter for the optimization - they need no
        # allowable stress either and are not reported here
        active = dom.active(self.domains)
        without_stress = [name for name in sorted(self.elsets)
                          if name in active and name not in self.stress]
        if not without_stress:
            self.stress_note.setVisible(False)
            return
        with_stress = [name for name in sorted(self.elsets)
                       if name in active and name in self.stress]
        if with_stress:
            # beso forms one FI_max per domain and aborts when a domain has no
            # criterion - as soon as an allowable stress is set anywhere, all of them
            # need one.  That is a reason to abort, hence red.
            self.stress_note.setText(
                translate("The failure index needs an allowable stress in EVERY domain - "
                           "still missing in: %s. The run stops without it.")
                % ", ".join(without_stress))
            self.stress_note.setStyleSheet("color: %s;" % COLOR_ERROR)
            self.stress_note.setVisible(True)
            return
        self.stress_note.setStyleSheet("color: %s;" % COLOR_NOTE)
        text = translate("Without an allowable stress (sigma) no failure index is computed.")
        possible = getattr(self, "stress_possible", {}) or {}
        values = ["%s = %g MPa" % (name, possible[name])
                  for name in without_stress if name in possible]
        if values:
            text += " " + translate("From the material: %s - enter it in the sigma column "
                                     "if you want the utilisation.") % ", ".join(values)
        elif without_stress:
            text += " " + translate("No yield strength is stored in the material - enter the "
                                     "value you want to allow.")
        self.stress_note.setText(text)
        self.stress_note.setVisible(True)

    # ---------------------------------------------------------------- data
    def _set_header(self):
        """Header line: every part of the analysis case - present in green, missing in red."""
        parts = []
        for title, value in (("Analysis", self.analysis), ("Mesh", self.mesh),
                             ("Solver", self.solver)):
            if value is None:
                parts.append('<span style="color:%s">%s: %s</span>'
                             % (COLOR_ERROR, translate(title), translate("not available")))
            else:
                parts.append('<span style="color:%s">%s: %s</span>'
                             % (COLOR_OK, translate(title), value.Label))
        self.header.setText(" &nbsp;|&nbsp; ".join(parts))

    def _load_if_needed(self):
        """Look at the document when the panel opens - but not a second time.

        The timer fires 50 ms after the panel was built.  If load() has already
        run by then (a test does that right away), the second look would only
        overwrite the status line of the check.
        """
        if not self._loaded:
            self.load()

    def load(self):
        """Look at analysis, mesh and an existing input file. Writes nothing."""
        self._loaded = True
        QtWidgets.QApplication.processEvents()
        self._set_status(translate("Looking for the analysis, the mesh and an existing "
                                    "CalculiX input file ..."))
        self.analysis = find_analysis(self.obj)
        self.mesh = fem.find_mesh(self.analysis) if self.analysis is not None else None
        self.solver = fem.find_solver(self.analysis) if self.analysis is not None else None
        self._set_header()
        # a new look at the document: element data and radius are looked up again
        self._robust_data = None
        self._robust_result = None
        self._fill_parameters()
        if self.analysis is None or self.mesh is None or self.solver is None:
            # what is missing is in the header line; this hint is about the file
            self._adopt_inp("", "")
            self._set_status(translate("No .inp file yet."), "auftrag")
            return
        self.obj.WorkingDir = fem.working_dir(self.solver, self.obj.Document.Name, self.mesh,
                                              remembered=self.obj.WorkingDir)

        path, source = fem.find_inp(self.solver, self.mesh, self.obj.Document.Name,
                                    remembered=self.obj.WorkingDir)
        if not path:
            self._adopt_inp("", "")
            self._set_status(translate("No .inp file yet."), "auftrag")
            return

        copy = fem.adopt_inp(path, self.solver, self.obj.Document.Name, self.mesh,
                             remembered=self.obj.WorkingDir)
        self._adopt_inp(copy, source)
        types = ", ".join(elset_reader.element_types(copy)) or "?"
        self._set_status(translate("%d element set(s), element type %s.")
                         % (len(self.elsets), types), "ok")

    def _adopt_inp(self, path, source):
        """Set the input file in the object and fill the table from it."""
        self.obj.InpFile = path
        self.path_field.setText(path or "")
        self.path_field.setCursorPosition(0)
        # where the file came from is a side note - the hint stays short
        tip = translate("The optimizer writes its iteration files next to this file.")
        if path and source:
            tip = ("%s\n%s" % (translate("Source: %s") % translate(
                SOURCE_TEXTS.get(source, source)), tip))
        self.path_field.setToolTip(tip)
        # size and date only - where the file came from is part of the hint
        self.info.setText(fem.file_info(path) if path else translate("no file yet"))
        self.inp_button.setText(translate("Write input file (.inp)" if not path
                                           else "Rewrite input file (.inp)"))
        folder = os.path.dirname(path) if path else self.obj.WorkingDir
        present = bool(folder) and os.path.isdir(folder)
        self.open_folder_button.setEnabled(present)
        self.open_folder_button.setToolTip(translate("Show this directory in the file manager: %s")
                                           % folder if present
                                           else translate("There is no working directory yet."))
        # writing an input file needs the whole analysis case
        ready = self.analysis is not None and self.mesh is not None and self.solver is not None
        self.inp_button.setEnabled(ready)
        if ready:
            self.inp_button.setToolTip(TIP_INP)
        else:
            self.inp_button.setToolTip(translate("Possible as soon as the analysis has a mesh "
                                                  "and a solver."))

        if not path or not os.path.isfile(path):
            self.elsets = {}
            self.table.setRowCount(0)
            return
        self.elsets = dom.visible_elsets(elset_reader.read_elsets(path))
        self.thicknesses = elset_reader.read_shell_thicknesses(path)
        stored = dom.parse_domains(self.obj.Domains)
        self.stress = dom.parse_stress(getattr(self.obj, "StressLimits", []))
        self.stress_cleared = dom.blank_stress(getattr(self.obj, "StressLimits", []))
        if stored:
            # new element sets (after a model change) are design space again -
            # "ignorieren" is the exception that is set on purpose
            self.domains = dom.roles_for(self.elsets, stored)
        else:
            self.domains = dom.roles_for(self.elsets)
            self._save_domains()
        self._fill_table()
        self._material_suggestion()
        self._update_results()
        self.obj.Document.recompute()

    def _material_suggestion(self):
        """Remember from the material which allowable stress would be possible.

        The σ column stays empty by default: whoever enters no allowable stress
        computes without a failure index (and should do so on purpose).  So that
        the number is still at hand, it stands in the hint below the list.
        """
        missing = [name for name in self.elsets
                   if name in dom.active(self.domains) and name not in self.stress]
        self.stress_possible = {}
        if missing:
            values = material_module.yield_strength(
                material_module.find_materials(self.analysis), missing,
                elset_reader.read_section_materials(getattr(self.obj, "InpFile", "")))
            self.stress_possible = {name: value for name, value in values.items()
                                    if name in missing}
        self._show_stress_note()

    def _fill_table(self):
        self.table.setRowCount(0)
        if hasattr(self, "thickness_note"):
            entries = ["%s = %g mm" % (name, value)
                       for name, value in sorted(getattr(self, "thicknesses", {}).items())]
            self.thickness_note.setText(
                translate("Shell thickness from the input file: %s") % ", ".join(entries)
                if entries else "")
            self.thickness_note.setVisible(bool(entries))
        self.stress_fields = {}
        self._filling = True
        for name in sorted(self.elsets):
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
            choice = _narrow_combo(QtWidgets.QComboBox())
            order = (dom.DESIGN, dom.NON_DESIGN, dom.IGNORE)
            for role in order:
                choice.addItem(translate(dom.ROLE_LABELS[role]), role)
            choice.setCurrentIndex(order.index(self.domains.get(name, dom.IGNORE)))
            choice.currentIndexChanged.connect(
                lambda _index, field=choice, set_name=name: self._role_changed(set_name, field))
            self.table.setCellWidget(row, 1, choice)
            element_count = QtWidgets.QTableWidgetItem(
                "{:,}".format(self.elsets[name]).replace(",", "."))
            element_count.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.table.setItem(row, 2, element_count)
            # allowable stress (MPa) - leaving it empty means: no failure index
            sigma = QtWidgets.QLineEdit()
            sigma.setValidator(QtGui.QDoubleValidator(0.0, 100000.0, 2, sigma))
            sigma.setPlaceholderText("–")
            sigma.setMaximumWidth(58)
            sigma.setToolTip(translate("Allowable stress (von Mises) in MPa - leave empty to "
                                        "run without a failure index. The model needs real "
                                        "loads for it."))
            value = self.stress.get(name)
            if value:
                sigma.setText(("%g" % value).replace(".", ","))
            sigma.textChanged.connect(
                lambda _text, field=sigma, set_name=name: self._stress_changed(set_name, field))
            self.table.setCellWidget(row, 3, sigma)
            self.stress_fields[name] = sigma
        self._filling = False
        self._show_stress_note()
        self._check_inp()
        self._fit_table_height()

    def _fit_table_height(self):
        """The domain table as tall as its content.

        Without that it stretches over the whole space (stretch) and the step looks
        as if it were empty.  From twelve rows on it stays put and scrolls inside -
        otherwise it grows endlessly with many element sets.
        """
        header = self.table.horizontalHeader().height()
        rows = sum(self.table.rowHeight(r) for r in range(self.table.rowCount()))
        frame = 2 * self.table.frameWidth() + 4
        height = header + rows + frame
        limit = header + 12 * 24 + frame
        self.table.setFixedHeight(min(height, limit))

    def _stress_changed(self, elset, field):
        if self._filling:
            return
        text = field.text().strip().replace(",", ".")
        try:
            value = float(text) if text else 0.0
        except ValueError:
            value = 0.0
        if value > 0:
            self.stress[elset] = value
            self.stress_cleared.discard(elset)
        else:
            self.stress.pop(elset, None)
            if text:
                self.stress_cleared.discard(elset)
            else:
                self.stress_cleared.add(elset)     # deliberately empty - no more suggestion
        self.obj.StressLimits = dom.format_stress(self.stress, self.stress_cleared)
        self._show_stress_note()
        if value > 0:
            App.Console.PrintMessage(translate("TopoOpt: allowable stress for '%s' is %s MPa - "
                                                "the run reports a failure index.\\n")
                                     % (elset, text))
        else:
            App.Console.PrintMessage(translate("TopoOpt: no allowable stress for '%s' - "
                                                "the run works without a failure index.\\n")
                                     % elset)

    def _role_changed(self, elset, field):
        role = field.itemData(field.currentIndex())
        self.domains[elset] = role
        self._save_domains()
        App.Console.PrintMessage(translate("TopoOpt: '%s' is now %s.\n")
                                 % (elset, translate(dom.ROLE_LABELS.get(role, role))))

    def _save_domains(self):
        self.obj.Domains = dom.format_domains(self.domains)

    # ------------------------------------------------------------- actions
    def _write_inp(self):
        """Write a new input file - only on an explicit click (can take seconds)."""
        if self.analysis is None or self.mesh is None or self.solver is None:
            self._set_status(translate("Without analysis, mesh and solver no input file can "
                                         "be written."), "fehler")
            return
        if getattr(self.solver, "SplitInputWriter", False):
            # the writer would spread the model over several files - a .inp that the
            # optimization can read cannot be produced that way
            self._set_status(translate("The solver writes a split input file ('Split input write')"
                                       " - there is no complete .inp then. Set it to 'no' in the "
                                       "CalculiX solver first."), "fehler")
            return
        self.inp_button.setEnabled(False)
        self._set_status(translate("Writing the CalculiX input file from the FEM model ... "
                                    "FreeCAD is blocked while it runs."), "info")
        try:
            path, duration = fem.create_inp(self.analysis, self.solver, self.mesh,
                                            self.obj.Document.Name, remembered=self.obj.WorkingDir)
        except Exception as exc:
            self._set_status(translate("The input file could not be written: %s") % exc,
                             "fehler")
            self.inp_button.setEnabled(True)
            return
        self._adopt_inp(path, "written")
        types = ", ".join(elset_reader.element_types(path)) or "?"
        self._set_status(translate("%d element set(s), element type %s.")
                         % (len(self.elsets), types), "ok")
        App.Console.PrintMessage("TopoOpt: %s\n" % translate("input file written in %.1f s")
                                 % duration)
        self.inp_button.setEnabled(True)

    def _open_folder(self):
        """Show the working directory in the file manager of the system."""
        folder = os.path.dirname(self.obj.InpFile) if self.obj.InpFile else self.obj.WorkingDir
        if not folder or not os.path.isdir(folder):
            self._set_status(translate("There is no working directory yet."), "fehler")
            return
        try:
            os.startfile(folder)                      # Windows
        except Exception:
            try:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))
            except Exception as exc:
                self._set_status(translate("The directory could not be opened (%s): %s")
                                 % (exc, folder), "fehler")

    # -------------------------------------------------- step 2: parameters
    def _mass_changed(self, value):
        """Slider and spin box show the same value, the object stores the fraction."""
        for widget in (self.mass_slider, self.mass_field):
            if widget.value() != value:
                widget.blockSignals(True)
                widget.setValue(value)
                widget.blockSignals(False)
        self._params_changed()

    def _params_changed(self):
        """Every change goes straight into the object (like the domain roles)."""
        self.obj.MassGoalRatio = round(self.mass_field.value() / 100.0, 4)
        self.obj.OptimizationBase = self.base_combo.currentData()
        text = self.iterations_field.text().strip()
        self.obj.IterationsLimit = text if text else "auto"
        self.obj.Tolerance = self.tolerance_field.value()
        self.obj.FIViolatedTolerance = int(self.fi_tolerance_field.value())
        self.obj.MassChange = self.mass_change_combo.currentData()
        self.obj.CpuCores = self.cores_field.value()
        self.obj.SaveIterations = self.save_field.value()
        self.obj.ResultFormat = self.format_combo.currentData()

    def _fill_parameters(self):
        """Show the parameters of the object in the widgets (without writing back)."""
        fields = (self.mass_slider, self.mass_field, self.base_combo, self.iterations_field,
                  self.tolerance_field, self.fi_tolerance_field, self.mass_change_combo,
                  self.cores_field, self.save_field, self.format_combo)
        for field in fields:
            field.blockSignals(True)
        try:
            percent = int(round(float(getattr(self.obj, "MassGoalRatio", 0.4)) * 100))
            percent = min(max(percent, MASS_MIN), MASS_MAX)
            self.mass_slider.setValue(percent)
            self.mass_field.setValue(percent)
            self.base_combo.setCurrentIndex(max(
                0, self.base_combo.findData(getattr(self.obj, "OptimizationBase", "stiffness"))))
            self.iterations_field.setText(str(getattr(self.obj, "IterationsLimit", "auto")))
            self.tolerance_field.setValue(min(max(float(getattr(self.obj, "Tolerance", 1e-3)),
                                                  0.00001), 1.0))
            self.fi_tolerance_field.setValue(
                min(max(int(getattr(self.obj, "FIViolatedTolerance", 1)), 1), 10000))
            self.mass_change_combo.setCurrentIndex(max(
                0, self.mass_change_combo.findData(getattr(self.obj, "MassChange", "normal"))))
            self.cores_field.setValue(int(getattr(self.obj, "CpuCores", 0)))
            self.save_field.setValue(int(getattr(self.obj, "SaveIterations", 1)))
            self.format_combo.setCurrentIndex(max(
                0, self.format_combo.findData(getattr(self.obj, "ResultFormat", "inp vtk"))))
        finally:
            for field in fields:
                field.blockSignals(False)
        self._fill_filters()

    def _set_status(self, text, kind="info"):
        """Status line: red for problems, orange while the user has to act, green when ready."""
        self.status.setText(text)
        color = {"fehler": COLOR_ERROR, "auftrag": COLOR_ACTION, "ok": COLOR_OK}.get(kind, "")
        self.status.setStyleSheet("color: %s;" % color if color else "")
        QtWidgets.QApplication.processEvents()

    # ------------------------------------------------------ task panel API
    def getStandardButtons(self):
        # .value because an int is expected (PySide6: the enum cannot be cast with int())
        return QtWidgets.QDialogButtonBox.Ok.value | QtWidgets.QDialogButtonBox.Close.value

    def _close(self):
        """Close the task dialog (FreeCAD calls accept()/reject() but does not close)."""
        if self._closed:
            return
        self._closed = True
        try:
            self.run_timer.stop()      # the run itself keeps going
            self.result_timer.stop()
            self.history.close()
        except Exception:
            pass
        _active_panels.pop(self.obj.Name, None)
        try:
            Gui.Control.closeDialog()
        except Exception as exc:
            App.Console.PrintWarning("TopoOpt: dialog could not be closed (%s)\n" % exc)

    def accept(self):
        self._close()

    def reject(self):
        self._close()
