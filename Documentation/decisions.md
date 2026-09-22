# Decisions

Short records of decisions that are not obvious from the code. Each one names the evidence
if it was measured.  Interface texts are quoted as they appear in the interface - German on a
German FreeCAD; the English source strings are in `core/i18n.py`.

## D1 - The optimization object belongs to the FEM analysis

The object is added to the analysis group (`analysis.addObject(obj)`), so it appears as a
child of the analysis, next to mesh, material and solver.

*Reason:* The analysis answers the question "which model does this optimization belong to?"
without any user interaction, and the object is found where a FEM user looks for it.
*Measured:* `Fem::FemAnalysis` is a group, `addObject` works, and deleting the analysis
keeps the child object (it is only removed from the group).

## D2 - The analysis is stored as a name, not as a link

`AnalysisName` is an `App::PropertyString`; there is deliberately **no** `App::PropertyLink`
back to the analysis.

*Reason:* the analysis contains the object, so a link back closes a cycle in the dependency
graph.
*Measured* in a throw-away document, three variants:

| variant | FreeCAD output |
|---|---|
| `PropertyLink` to the analysis | `The graph must be a DAG.` and `A#TopoOpt still touched after recompute` |
| object only inside the group | clean |
| `PropertyString` with the name | clean |

The analysis is looked up through the parent group (`obj.InList`, primary) and through the
stored name (fallback, e.g. after the user moved the object out of the analysis).

## D3 - An own workbench instead of a button in the FEM toolbar

The addon registers the workbench `TopoOpt` with its own toolbar and menu.

*Reason:* the FreeCAD Addon Index requires that an addon "confines its commands, toolbars,
menus, and other side effects to its own workbench, and does not modify, hide, or otherwise
interfere with FreeCAD's core interface or that of other addons". A button appended to the
FEM workbench would be such an interference and would risk the addon's acceptance.
*Precedent:* FEMbyGEN, which also extends FEM functionality, ships its own workbench.

## D4 - "Active analysis" instead of "selected analysis"

The command reads `FemGui.getActiveAnalysis()` and refuses to act when there is none.

*Reason:* identical to the behaviour of the FEM commands (an active analysis is required for
new FEM objects) and to the active body in PartDesign - no extra "select the analysis" step
in the assistant.
*Evidence:* FreeCAD itself uses the same functions (`Mod/Fem/femcommands/manager.py`), as
does FEMbyGEN.

## D5 - Modern namespaced layout

Code lives in `freecad/TopoOpt/`, not in `Init.py`/`InitGui.py` at the top level.

*Reason:* recommended for new addons, keeps the global namespace clean, no `sys.path`
manipulation.
*Measured:* FreeCAD 26.3 imports `freecad.TopoOpt.__init__` (always) and
`freecad.TopoOpt.init_gui` (GUI only) when the repository sits in the user `Mod` directory.

## D6 - License: LGPL-3.0-or-later for code, CC0-1.0 for assets

*Reason:* the addon ships beso, which is LGPLv3, so the code license has to be
LGPLv3-compatible. The Index requires an exact SPDX identifier in the manifest, the LICENSE
files and the file headers.

## D7 - English source texts, German translation in a dictionary

The UI texts in the code are English; `core/i18n.py` holds a German dictionary and is used
when FreeCAD runs in German (`uebersetze()`), so every other language falls back to English.

*Reason:* the addon is meant to be shared internationally, while the first users are German.
The usual Qt workflow (`.ts` file compiled to `.qm` with `lrelease`) is not available: the
FreeCAD 26.3 package ships neither `lrelease` nor `lupdate`. When the addon is translated by
the community, `core/i18n.py` is the single place to replace by the `.ts`/`.qm` mechanism.

## D8 - Reuse an existing input file, never write it silently

`fem.find_inp()` looks for the CalculiX `.inp` in three places (the FEM working directory
of the solver, FreeCAD's `%TEMP%/fcfem_*` directories, the addon's own working directory
of an older version) and copies a found file into the FEM working directory. Only if
nothing is found does the user write it - with a button, not automatically.

*Reason:* a file that was already written by the solver panel must not be
written a second time (redundant work). And writing it takes time - measured 2.3 s for
41,666 C3D10 elements - while FreeCAD is blocked; doing that silently when a dialog opens
looks like a freeze. The dialog now only looks around and says what is missing; the step is
called "Initialize" because it prepares the analysis case (input file plus element sets).

## D10 - The files live in the FEM working directory of the solver

`fem.arbeitsordner()` asks FreeCAD (`femtools.femutils.get_pref_working_dir()`) where the
solver would write, and uses that directory - so analysis, input file and the iteration
files of the optimizer sit together, and the user setting (temporary / beside the document
/ custom) is honoured. The directory is stored in the document object (`WorkingDir`) and
reused, because `get_temp_dir()` builds a new directory on **every** call (measured - it
does not cache anything).

*Reason:* the optimization object is a child of the FEM analysis, so its
files belong where the FEM files are. Before, the addon used a directory of its own under
`%TEMP%/TopoOpt`, which looked like a second, unrelated place.

## D11 - Localized texts: English source, German dictionary

See D7.  Additionally: the header line of the assistant lists the analysis case
(`Analysis`, `Mesh`, `Solver`) and shows missing parts in red, while the status line is
green as soon as everything is present, orange while the user has to act and red on errors.

*Reason:* a hint text that simply disappears hides the information; colours
show the state at a glance.

## D12 - The parameters are properties of the document object

Every parameter of step 2 is a property of the optimization object (mass goal ratio,
optimization base, iteration limit, tolerance, cores, speed of the mass change, filters,
save interval, result format), so the settings travel inside the `.FCStd` file and are
visible in the property editor. The default values are the ones beso ships in
`beso_conf.py` (0.4 / stiffness / auto / 1e-3 / 0 / normal / [["simple", "auto"]] / 1 /
"inp vtk") - nothing was invented.

*Reason:* the assistant must hand the settings to beso later (step 3 writes the
`beso_conf.py` for the run), and a user who stores a document expects the settings to be
in it.  Choices are `App::PropertyEnumeration`, so FreeCAD offers them as a drop-down.

The three speed settings map to the `mass_addition_ratio`/`mass_removal_ratio` pairs of the
beso GUI slider (1 %/2 %, 1.5 %/3 %, 3 %/6 %).

beso has **no symmetry option** - the closest thing is the "casting" filter with a
direction vector (it keeps the part demouldable in one direction).

## D13 - One page per step

The assistant keeps one page per step in a `QStackedWidget` and the buttons of the step
bar switch between them; steps that are not built yet keep a placeholder page and their
button stays disabled.  So a half-built step is never reachable but also never hidden.

## D14 - The panel must be narrowable

Combo boxes adjust to a few characters (`AdjustToMinimumContentsLengthWithIcon`,
`setMinimumContentsLength(6)` - the popup still shows the full text), labels wrap, and the
long titles of the group boxes were shortened. Measured minimum width of the whole panel:
**590 px before, 331 px after**.

*Reason:* the panel could not be made narrow without things disappearing.
Combo boxes are the main culprit: by default a combo wants as much room as its longest
entry.

Two details went in with it: the core count shows "all" instead of 0
(`setSpecialValueText`, which only works while the minimum is 0), and the save interval
starts at **10** instead of the beso default 1 (a saved iteration of a fine mesh can need
100 MB and more; the final result is what counts).

## D15 - beso ships with the addon

The beso files live in `freecad/TopoOpt/beso/` (beso_lib, beso_filters, beso_main,
beso_plots, beso_separate, the template beso_conf.py, LICENSE, README) and
`core/beso.py` loads them from the folder of the addon.  `sys.modules` is filled directly,
so nothing is added to `sys.path`; the modules keep their own names because beso imports
itself that way (`import beso_lib` inside `beso_filters`).

*Reason:* a user should install the workbench and start - without a second
download and without being asked for a path.  The folder is found relative to the addon
file, so it works wherever FreeCAD installed the addon.

Licence: beso is LGPL-3.0-or-later, the addon is LGPL-3.0-or-later too, the three changes
are marked in the sources and listed in `beso/CHANGES-TopoOpt.md`.  `beso_fc_gui.py`
(beso's own dialog) is not included - the assistant replaces it.

## D16 - The robust filter radius uses beso's own functions

`core/radius.py` reads the element sizes with `beso_lib.import_inp`,
`beso_lib.elm_volume_cg` and `beso_filters.find_size_elm` and tries the multiples
2.0 / 2.5 / 3.0 / 4.0 … of the mean element size with `beso_filters.prepare2s` until every
element of the design space has a neighbour.  The addon calculates nothing about elements
or neighbourhoods itself; it only chooses the radius that beso then uses.

*Reason:* beso's own `"auto"` is 2 x the mean size, which is not enough on graded meshes
(the largest elements are further apart) - single elements then stay without a neighbour
and the "simple" filter stops.  Measured with the bundled beso on the test input file:
radius 0.1 x mean -> 4 of 4 elements without a neighbour, 2.0 x mean -> 0.

**Speed matters here** (the check blocks the assistant).  Measured on a mesh with
58,871 TETRA10 and a mean element size of 2.4268 mm:

| step | time |
|---|---|
| `import_inp` + `elm_volume_cg` + `find_size_elm` (beso) | 2.79 s |
| `prepare2s` (beso, builds the whole neighbourhood: 11.8 million pairs) | 10.53 s |
| own grid check (same rule, nothing stored) | 0.97 s |

So `ohne_nachbarn()` asks only the question that is needed ("has every element a
neighbour?") and stops at the first neighbour, with a grid of cell size = radius (the
same grid beso uses, +-1 cell).  The result is identical - the test compares both
functions for several radii, and for the mesh above both give 0 elements without a
neighbour.  The whole check therefore costs 3.75 s instead of 12.7 s.

## D17 - A run gets its own small beso folder, the configuration builds on beso's template

`core/conf.py` copies the beso files into `<working directory>/topoopt_beso/` for a run and
writes `beso_conf.py` there, because **beso reads its configuration from the folder of
`beso_main.py`**: `exec(open(os.path.join(beso_dir, "beso_conf.py")).read())`.  The addon
folder itself is never written to, and several runs can sit next to each other.

The written configuration first executes beso's own template (copied as
`beso_conf_vorlage.py`) and then sets the values of the assistant - so every option we do
not touch keeps beso's own default, and a new beso option cannot break us.  Three details
that beso requires and a naive configuration would miss (all three were real errors while
building this):

* beso expects `domain_density`, `domain_material` and `domain_thickness` **per domain**
  (`KeyError: 'MaterialSolidSolid'`), so the template's example values are taken over for
  our domains.
* The template's example data for failure indices points at a domain called
  `all_available`, which our model does not have (`KeyError: 'all_available'`) - those
  dictionaries are cleared.
* `beso_main` calls `plt.show()` at the end; the configuration switches matplotlib to the
  `Agg` backend, so the run ends by itself instead of waiting for a closed window.

beso runs as its own process (`subprocess`), the output goes into `<input>_topoopt.log`
next to the input file.  **Measured** on the test model (401 C3D4, limit 2 iterations):
CalculiX ran, `file000/001/002.vtk` and `resulting_states.vtk` were written, the log shows
`mass = 19369.41` then `mass = 19110.75` after `mass = 20000` at the start.

## D18 - Step 3: one button, progress bar, live charts in an own window

* **One button**: "Start optimization" becomes "Cancel" while the run goes on.  Cancel
  kills the whole process tree (`taskkill /F /T`), so the CalculiX process beso started
  ends as well.
* **Nothing blocks**: beso runs as its own process (`subprocess.Popen`), a `QTimer` (1.5 s)
  reads the log files and updates the display.  FreeCAD never waits for the solver.
* **No console window**: `subprocess.Popen(..., creationflags=CREATE_NO_WINDOW)`.
  Without it Windows opens a console window for the run - an earlier version of this addon started
  beso in a way that did not show one, and the user noticed the difference.
* **Progress bar** like in an earlier version of this addon: 0 % = mass of the whole part, 100 % = target
  mass, `(start - mass) / (start * (1 - ratio)) * 100`.  It is not forced to 100 % when the
  run stops early (iteration limit) - it shows what really happened.
* **Charts in an own window**, as in an earlier version of this addon: `gui/verlauf.py` uses FreeCAD's
  `Plot` module (matplotlib as MDI child window) and draws four charts - mass in percent
  (with the target mass as a dashed line), `FI_mean`/`FI_max` (limit 1.0), overloaded
  elements and mean energy density.  A QTimer redraws every 1.5 s; before the first
  iteration the window says how long the run has been working, because building the filter
  neighbourhood takes minutes on fine meshes.
* **Source of the values is beso's own log file** `<mesh>.log`: it contains the table of
  iterations (`i mass ener_dens_mean` and, with a failure index, four more columns).
  `core/lauf.py` reads it.  The addon moves an old log file aside before the start, since
  beso appends to it.
* **Collapsible "Details"** shows the last 40 lines of our own log (`<mesh>_topoopt.log`,
  the CalculiX output); the whole log file belongs to step 4 (the whole log file is opened from the results).
* The status line reads `Iteration 12 | mass 15340, target 12000 | 3:20 min`.  No
  percentage: right after the start the mass is far above the target and "323 %" only looked
  like an error.

## D19 - Allowable stress per element set is what switches the failure index on

The failure-index charts do not depend on the optimization base:

* beso computes a failure index when `domain_FI` is filled: `beso_main.py` sets
  `domain_FI_filled = True` as soon as one domain has FI criteria (line 78-80), and with
  `stiffness` it reads the stress values from the CalculiX `.dat` file (line 415-418).
  So the FI charts work with every optimization base.
* An earlier layout had a column "zulässige Spannung" per domain and wrote
  `domain_FI[elset] = [[('stress_von_Mises', σ*1e6)], [('stress_von_Mises', σ)]]`
  (`bridge.py:235`).  A real run of it shows the values:
  `0.0434 FI_mean`, `0.3568 FI_max`, `0.00134 ener_dens_mean`.
* This addon had no such field, so `domain_FI` stayed empty and three of the four charts
  had no values.  That was a missing function, not a bug.

Therefore: **a column "σ (MPa)" next to every element set** in step 1,
stored in the object as `StressLimits` (`"<set>|<MPa>"`).  Empty means: no failure index.
The format is beso's own (inner tuples = separate indices, second list = second element
state).  A written configuration is executed in the test and really sets

    domain_FI = {"SetA": [[("stress_von_Mises", 235000000.0)], [("stress_von_Mises", 235.0)]]}

**Prerequisite, and beso says so itself**: the model needs real loads.  Without results in
the `.dat` file beso stops with `CalculiX results not found, check CalculiX for errors.`
(`beso_main.py:434`).  The energy density chart has the same reason: our test document has no
loads, so `ener_dens_mean` is 0.0 there.

**The empty field is deliberate.**  An earlier version filled it silently:
`build_domain(..., stress_limit=450.0, ...)` (`bridge.py:133`) and showed the value in its table
(`taskpanel.py:750`), so every run wrote `domain_FI = 450 MPa` - taken from beso's own example
configuration (`beso_conf.py`: `[[("stress_von_Mises", 450.0e6)], …]`).  It was never typed by hand
and did not know it was there; 450 MPa is far above the allowable stress of ordinary steel
(S235: 157 MPa at a safety factor of 1.5), so overloads would have been reported too late.
Decision (September 2026): **leave the field empty** and fill it deliberately - from
the material if the material carries a value, otherwise by typing it.  Do not "repair" this by
adding a default value.

## D20 - The allowable stress is suggested from the material, if the material has one

Can the allowable stress come from the material instead of being typed in?
the material.  Both checked:

* **beso asks for it as well**: `beso_fc_gui.py` has one text box per material,
  `'Von Mises stress [MPa] limit, when reached, material removing will stop.'`
  (lines 184-204) and writes exactly the same `domain_FI` (line 837).  A failure index is
  "stress / allowable value" - without a limit there is nothing to compute, and the limit
  is a design decision (yield strength / safety factor), not a material constant.
* **The material can carry it**: FreeCAD material cards have `YieldStrength` - the metals do
  (Aluminum-6061-T6: `276 MPa`, UltimateTensileStrength `310 MPa`), the plain steel cards do
  not (`Steel`, `CalculiX-Steel`: only E, ν, ρ and thermal data).  The user's model
  `TopologieOptimierung_KI-Workbench.FCStd` uses `CalculiX-Steel`, so it has no value.

Therefore: `core/material.py` reads `YieldStrength` (or `UltimateTensileStrength`,
`CompressiveStrength` as fallback) from the model's material objects, converts the text
("315 MPa", "2.1e+08 kg/(mm*s^2)" -> 210000 MPa) into MPa and the assistant **fills the
field in** - but only for sets that have no value yet.  A set whose field was
deliberately emptied is stored as `"<set>|0"`, so the suggestion does not come back.
The assignment material -> element set goes by name (`MaterialSolid` belongs to
`MaterialSolidSolid`); with exactly one material it applies to all sets.

## D21 - Run and results are one step "Calculation"

Run and results belong together: one step named "Berechnung", with a separate small VTK viewer.

* The step bar now has three steps: **Initialize | Parameters | Calculation**.  The
  calculation page holds a "Run" group (start/cancel, progress bar, status, history) and a
  "Results" group (iterations, log, folder).
* `core/vtk.py` is the reader of the earlier version, kept as it was - including the three traps it
  had to solve, each with the measurement in the docstring:
  * node numbers in `resulting_states.vtk` are **0-based**; subtracting 1 tears the mesh
    (measured in the test: largest edge 13.3 mm correct against 102.5 mm with -1),
  * the `LOOKUP_TABLE` line must not end a `SCALARS` section, otherwise the iterations stay
    empty,
  * the surface triangles must be turned outwards, otherwise half of them are lit from the
    wrong side and it looks like a hole.
* `gui/vtk_anzeige.py` shows the material that is left as **one** mesh object that is updated
  (`TopoOpt_Iteration`) - not one object per iteration.
* Controls: "Show iterations" (reads the file, jumps to the last iteration), a slider,
  back/forward, play/stop and the info line
  `Iteration 1 of 2 | 388 of 401 elements left (96.8 %)`.  Plus "Whole log" and "Folder"
  (the full log).

### Follow-up work in the same session

* The group of the run is called **"Berechnen"**, the fold-out "Details" belongs to it (the log
  lines are about the calculation).
* The chart button is called **"Diagramme anzeigen"** and sits in the **results** group; the
  check box "open at start" is gone - the diagram window always opens when a run starts.
* The folder button is called **"Arbeitsverzeichnis öffnen"**, the same wording as in step 1
  (both are `uebersetze("Open working directory")`).
* **The result is loaded automatically** when the run ends (`_lauf_aktualisieren` calls
  `_ergebnis_anzeigen()` on success) and there is a button **"Ergebnis laden"** that re-reads
  `resulting_states.vtk` and shows the finished network (last iteration) - deliberately read
  again, because a new run writes a new file.
* **Layout lesson**: FreeCAD's style gives every `QPushButton` a minimum width of about 106 px.
  Four widgets in one row (back, slider, forward, play) blew the panel up to 396 px though the
  panel is meant to stay at ~348 px.  The small control buttons get `min-width: 0px` in an own
  style sheet, that is measured again after every layout change.

## D22 - Panel layout: text step bar, own scroll area, navigation below

The step bar has to stay visible while the content scrolls, the navigation sits below, and a
scroll bar outside the panel or clickable step buttons were dropped.  The structure is:

    QVBoxLayout
      step bar   (one RichText QLabel: bold current step, " › " between, gray others)  fixed
      QScrollArea (setWidgetResizable, NoFrame) -> QStackedWidget (the pages)          scrolls
      navigation (["< Zurück"] ... ["Weiter >"], the outer button hides)               fixed

* The step bar is now such a label (`schritt_label`, RichText) instead of tool buttons -
  clicking a step is gone, the way forward is the navigation below.
* The pages sit in a `QScrollArea` with `setWidgetResizable(True)` and `NoFrame`, so the scroll
  bar belongs to the content area, not to the whole task panel.
* Below: `< Zurück` / `Weiter >` (`_schritt_zurueck`, `_schritt_weiter`); at the first step
  there is no "back", at the last none "forward" (the outer button hides).
* `_zeige_schritt` puts the scroll bar back to the top on every step change.
* Measured: the panel's minimum width dropped from **348 to 234 px** - the text bar and the
  navigation below need much less room than three toggle buttons in a row.

**The element-set table does not fill the step any more.**  The list in step 1 was too long
downwards: the table lay in the layout with stretch 1
(`layout.addWidget(self._domain_tabelle(), 1)`), so it grew over the whole free space - and with
the new scroll area over the whole scroll area.  Now it is added without stretch, the free space
is taken by a stretch below it, and `_tabelle_hoehe_anpassen()` sets the height to
header + rows (measured: **64 px** with one element set).  From twelve rows on it keeps that
height and scrolls inside itself, otherwise a model with many element sets would grow endlessly.

**Two separate result buttons**:

* **"Iterationen anzeigen"** - the VTK player (`core/vtk.py`): the surface of the material that
  is left, per iteration, for looking at it and for the film.
* **"Ergebnisnetz laden"** - the real result (`core/netz.py`): beso writes
  `<name>_state1.inp` per saved iteration (state 1 = element keeps material), and the newest of
  them is imported with FreeCAD's own `feminout.importInpMesh.import_inp` as an FEM mesh into
  the document.  Sorted by change time, not alphabetically - alphabetically the highest
  iteration number of an earlier run would be the "last" one.
* Measured in the panel test: `file001_state1.inp` is found and loaded, the document gets a new
  object.

**Third round of corrections:**

* The running time (`lauf_zeit`, gray) sits **right next to the start button** instead of in its
  own line; the status line below the progress bar hides itself while it has no text.
* The four result buttons form a **2x2 grid**:
  `Load result network | Show diagrams` over `Full log | Open working directory` (on a German
  FreeCAD these read `Ergebnisnetz laden | Diagramme anzeigen` and `Vollständiges Log |
  Arbeitsverzeichnis öffnen`).
  "Iterationen anzeigen" moved into the row with the slider.
* The running time sits **right next to the start button** in the "Berechnen" group.  An
  attempt to put it into the panel's top line (next to the step bar) was wrong - 
  "warum ist die zeit wieder irgendwo wo sie nicht dazugehört" (German: "why is the time suddenly
  somewhere it does not belong").  The time belongs to the run, not
  to the frame of the panel.
* The **slider got its own row** with the full width (measured 640 px in a 640 px panel).
* The **play speed** sits in the row of the control buttons :
  combo box 0.5 s / 1 s / 2 s / 3 s  (`_takt_geaendert` sets the timer
  interval; measured: index 2 -> 2000 ms).
* **No invisible empty row**: the status line was a row of its own and stayed empty (and thus
  invisible but place-consuming) as long as no run was going - a blank strip was visible.  It
  now shares the row with the fold-out "Details" button (left button, right status, gray).
* **No scroll bar in the short steps**: one common `QScrollArea` around the `QStackedWidget` is
  always as tall as the *longest* page, so every step showed a scroll bar.  Each page now has its
  own scroll area (`self.rollen`); measured: the scroll bar range in step 1 is 0 (nothing to
  scroll), in step 3 it scrolls.  The panel stays 234 px wide.

## D23 - Shell thickness comes from the input file, per element set

The user compared a 2D shell case with a 3D volume case and suspected the shell thickness was
missing.  He was right, and it was the dangerous kind of mistake:

* beso's own template has `domain_thickness[elset_name] = [1.0, 1.0]`, and the addon copied that
  example value for every domain.  **No error, no warning** - the 2D run finished and reported a
  mass of **2000 instead of 20000** (measured, limit 1 iteration).
* FreeCAD knows the value (`Fem::ElementGeometry2D`, here 10 mm) and writes it into the `.inp`
  as its own card per element set:

      *SHELL SECTION, ELSET=MaterialSolidElementGeometry2D, MATERIAL=MaterialSolid, OFFSET=0
      10

  So the assignment element set -> thickness is **in the file** and nothing has to be guessed
  (with several thicknesses there are several cards).
* `core/elsets.py: read_shell_thicknesses()` reads those cards, `conf_text()` writes
  `domain_thickness[<set>] = [d, d]` for the sets of the model, and step 1 shows a gray line
  "Shell thickness from the input file: <set> = <d> mm" so one sees which set gets which
  thickness.
* **Proof with a real run** (2D analysis from a test document, 4,614 shell elements):
  before the fix `domain_thickness = [1.0, 1.0]`, mass 2000; with the fix
  `domain_thickness = [10.0, 10.0]`, mass **20000 -> 19396**.  The 3D case gives **20000 -> 19399**
  - the two models meet within 0.02 %, which confirms 10 mm is the right value.
* Cost of the comparison: the 3D case with 84,395 volume elements needed **232 s** for one
  iteration (surface 12.8 MB `.inp`), the 2D case 6 s - a factor of about 39.

## D24 - Scenario matrix: error cases, filters, 2D/3D and the comparison with original beso

`tests/make_szenario_inp.py` creates three tiny models (8 hexahedra, 4 triangles, the same without
`*SHELL SECTION`) with real loads; `tests/szenario_test.py` computes 15 scenarios from them - filter
(simple with auto/robust/manual, casting, all seven morphology filters), target masses (60/30 %),
2D shell and 3D volume - **and the same once more with the original beso from GitHub**
(`vendor/beso`, without our fixes).

Result (measured):

| Case | bundled beso | original beso |
|---|---|---|
| 3D simple auto / robust / casting / target mass 30 % | code 0, masses 8000 -> 7000 | identical |
| 3D all seven morphology filters | code 0, masses 8000 -> 7000 | identical |
| 2D shell simple | code 0, masses 1000 -> 750 | identical |
| 3D simple 1.5 and simple manual 1.0 (radius < element distance) | **code 1**, clear message | code 0 (keeps computing silently) |
| 2D without shell thickness | **code 1**, clear message "domain_thickness is missing" | code 1 (IndexError) |
| 2D casting with "auto" | code 0, masses 1000 -> 750 | code 1, `NameError: filtered_dn` |

* **13 of 16 scenarios deliver identical masses** - so the fixes do not change the computation,
  they only make errors visible.
* The three deviations are exactly the intended fixes: too small filter range and missing
  shell thickness lead to a **clear message** with the bundled beso (instead of silent
  continued computation with division by 0), and casting with "auto" **runs** with it, while the
  original aborts there with `NameError`.
* **Fix 4 (fixed):** `filter_list = [["casting", "auto", vektor]]` aborted in beso with
  `NameError: name 'filtered_dn' is not defined` - `beso_main.py` uses `filtered_dn` in
  `get_filter_range(...)`, but never sets the variable in the casting branch without a domain list.
  One line `filtered_dn = domains_from_config` (exactly as in the branch below for the other filters)
  fixes it; documented in `beso/CHANGES-TopoOpt.md` as Fix 4. Measured with the scenario
  `2D shell casting auto`: before code 1 after 0.7 s, now code 0 with masses 1000 -> 750 -> 750,
  while the original beso still aborts there.  The fix is in the fork `shIxx01/beso`
  (branch `fix/casting-auto-filter-range`, also on `master`) and is offered upstream as
  calculix/beso#60.  Counter-checked with the scenario matrix against the fork:
  **16 of 16 scenarios identical** (before 13 of 16, because there only the casting case still
  deviated).
* The error cases of the assistant (without mesh, without solver, without .inp, without design space)
  are now checked by `tests/panel_test.py`: the run does not start at all and the status names the
  reason.

*Addendum 22.09.2026:* The numbers above apply to the comparison against the **fork**.  Computed
against the unchanged original, the scenario matrix with 17 scenarios delivers **13 identical
results and four documented deviations** - the two radius cases and both 2D shell scenarios,
because the original aborts there with numpy 2 (see D40).  Measured with FreeCAD 26.3 and numpy 2.4.

## D38 - The test data live in the repository, the suites run from start to finish

What caused `tests/headless_test.py` to abort from a fresh clone (22.09.2026)?

* `.gitignore` excluded with `tests/data/*.log` the two recordings that the test needs as input:
  beso's iteration table (`beso_beispiel.log`) and its own run log (`lauf_beispiel.log`).  They were
  missing in the clone, `tabelle_lesen`/`verlauf_lesen` returned empty values, and the table is now
  rebuilt from beso's own format (header like `beso_main.py`, rows with the same column widths).
  Both files are re-included with `!` exceptions - test inputs belong in the repository, outputs do
  not.
* Two checks continued with `f["masse"]`/`f["ziel"]` without checking for `None`.  Instead of error
  messages there was a `TypeError` - measured, the suite aborted at check 98 of 152, the VTK and
  state checks after it never ran.  Now a missing file reports its name, and the checks continue.
* Measured in the Flatpak (FreeCAD 26.3): **152 checks, 0 errors**, exit 0.

## D39 - Python and ccx are searched for robustly (Flatpak)

Does the start of beso also work when FreeCAD is installed as a Flatpak?

* In the Flatpak, `sys.executable` = `/app/bin/FreeCADCmd`, `sys.prefix` = `/usr`, and FreeCAD has
  no `__file__` (compiled in).  The old `python_pfad()` therefore found no Python and returned
  `sys.executable` - that is, **FreeCAD itself**.
* Measured: `conf.starte()` passes `-u` (unbuffered).  To FreeCADCmd, `-u` is FreeCAD's own option
  (user parameter file) - the file was **overwritten** (a test script then contained an XML
  parameter document) and the run failed.
* New order: `sys.executable` only if "python" is in the name, then `python3`/`python`/`python.exe`
  next to it, then `sys.prefix/bin`, finally the search path of the system (`shutil.which`).
  `calculix_pfad()` looks first next to the FreeCAD program (in the Flatpak `/app/bin/ccx`).  If no
  Python is found, **`starte()` refuses the run** (clear message, translated in the dialog), instead
  of starting a wrong process.
* Measured in the Flatpak: `python_pfad()` -> `/usr/bin/python3` (numpy 2.4.4, matplotlib 3.9.4),
  `calculix_pfad()` -> `/app/bin/ccx`.  The headless test checks both and additionally that the
  interpreter is never FreeCAD itself.

## D40 - beso: np.linalg.linalg replaced by np.linalg.norm (numpy 2)

Why did every 2D model (shell) abort in the Flatpak before the first iteration?

* Measured with numpy 2.4.4: `2D shell simple auto` and `2D shell casting auto` ended with
  `AttributeError: module 'numpy.linalg' has no attribute 'linalg'`.  The place is
  `beso_lib.elm_volume_cg` -> `tria_area_cg`, that is the area and mass computation of the
  triangle elements; `np.linalg.linalg` was removed in numpy 2.0.  The same line is in the
  original beso, **2D models do not compute there at all with current numpy**.
* Fix: one word.  Measured afterwards: `2D shell simple auto` code 0, masses 1000 -> 750;
  `2D shell casting auto` code 0, masses 1000 -> 750 -> 750 - while the unchanged original
  still aborts at this place.  The expected deviation count of the scenario matrix thus grows
  from 3 to 4 entries (see `BEKANNTE_ABWEICHUNGEN`).
* therefore `beso_lib.py` now carries a `TopoOpt:` comment at the line - and likewise at every
  other change: `tests/vergleiche_beso_kopie.py` compares the bundled copy with the original and
  **fails when a difference carries no such comment**.

## D41 - Automatic test run on every push

The suites ran only when someone started them by hand; the aborted suite (D38) therefore went
unnoticed.  `.github/workflows/tests.yml` now runs on every push and every pull request in two jobs:

* **headless** - install FreeCAD as a Flatpak (the same FreeCAD on every distribution, with
  `ccx` and `gmsh`), copy the addon into FreeCAD's `Mod` folder (the folder is queried from FreeCAD,
  it is version-dependent), syntax check of all Python files and then `tests/headless_test.py`.
* **beso-copy** - clone the original beso and check that every difference of the copy is documented.
  If upstream changes something, it shows up here.

The scenario matrix remains manual work: it computes with the unchanged beso from GitHub and
should not turn red on every change from upstream.

## D37 - "Show iterations" already shows the intermediate state during the run

The button was greyed out until the end of the run, because it waited for `resulting_states.vtk` - which
beso writes only at the very end.  During the run, however, there are intermediate states: beso writes
a `fileNNN.vtk` per saved iteration (measured on a run with 38 iterations:
`file010.vtk` through `file038.vtk`).  They have **the same format** as the final result, only with
fewer states (measured: `file030.vtk` 5 blocks versus `resulting_states.vtk` 38).

`_ergebnis_pfad()` now returns the final state if it exists, otherwise the **newest**
`fileNNN.vtk` by modification time (not alphabetically - otherwise the highest number of an
earlier run wins).  The hint under the button names the iteration in that case ("intermediate state of
iteration 30 - ... the complete result is created at the end of the run."), and
`_lauf_aktualisieren()` releases the button during the run as soon as the first intermediate stage is
there.

Measured: `tests/panel_test.py` creates a `file030.vtk` and checks that the button is active,
that the iteration is read from the name, and that the final state takes precedence.

## D36 - The run status shares the line without wrapping

The status ("Iteration 2 | Mass 57836, target 36319") sits next to the expandable "Details" - but it
wrapped onto two lines, although there was room on the right.  The cause was the layout: before the label
there was `addStretch(1)`, which gave the wrapping label only its (small) preferred width, and it wrapped.

Now the label gets the rest of the line (`addWidget(self.lauf_status, 1)`), the stretch space
in front of it is dropped.  Measured in the panel test at 560 px panel width: label **447 px** at 193 px
text width, height 25 px - thus **one** line (line height 16 px).  Assistant 135/135.

## D35 - New element sets are design space by default

When building with two materials it stood out: the domain list was completely on "ignore" - only
when exactly **one** set remained was it defaulted as design space.  With several sets
everything was thus initially excluded, and the run ended in "no design space marked".

Now the design space is the default: `domains.vorschlag()` sets every offered set to
design space, and `domains.rollen_fuer()` likewise gives design space to a set that only comes in
after a model change.  Stored roles continue to apply unchanged - "non-design"
(region is retained) and "ignore" (does not appear in the optimization) are
decisions that one sets deliberately.

headless checks that without a default all sets are design space and that a newly added
set gets design space, while stored values apply.

## D34 - The run starts unbuffered (-u)

Bars and diagrams read beso's iteration table from `<mesh>.log`; the detail field, in contrast, shows
our log file `<mesh>_topoopt.log`, into which the output of the run is redirected.  The run was
started without `-u` and without `PYTHONUNBUFFERED` - Python's stdout is then **block-buffered**, so the
file stayed empty until the process ended.  Symptom: during the computation the detail field showed
nothing, only after the job the last iterations.

Measured on a child process that writes five lines with 0.4 s pause each: without `-u` the
log file stays at **0 bytes** and contains everything only after the process ends; with `-u` it
grows step by step (9, 18, 18, 27, 36, 45 bytes).

`conf.starte()` now starts the run with `-u` and `PYTHONUNBUFFERED=1` in the environment
(`PYTHONUTF8` stays set if not already present).  The **progress bar** was affected by the
cause from D33 and is thus fixed at the same time - evidence: a log cut off at iteration 3 or 7
yields 14.7 % or 28.5 %, at the end 100 %.

headless 145/145 (the new test checks the arguments of the process start).

## D33 - The diagrams read beso's table via the header row

beso's iteration table changes its number of columns with the model.  With Failure Index it gets one
column FI_violated and FI_max per domain - with more than one domain additionally an
aggregate column "all" - as well as FI_mean and FI_mean_without_state0.  Our reader expected **exactly
four** extra columns and anchored the match at the end of the row.  As soon as a run had an
allowable stress - thus exactly the case for which the Failure Index is intended - no row matched any
more: diagrams and progress bar stayed empty, while the run itself continued flawlessly.

`tabelle_lesen()` now reads the column positions from the header row of the table (beso writes exactly
one token per column) and fetches the values via their name.  Every variant thus matches:
3 columns without Failure Index, 4 with Failure Index and one domain, 6 or 8 with several domains.

Measured: `tests/data/beso_beispiel.log` (two tables, one with Failure Index) still yields
6 rows and 11.12 % progress; a running run with two domains yields 34 points including
FI values.  headless 142/142, Assistant 133/133.

## D32 - "ignore" really means: the set does not appear in the optimization

When building with two materials it stood out: a domain on "ignore" still ended up in the
beso configuration (`domain_optimized = {name: (name in design) for name in domains}` took
**all** sets) - thus for beso the same as non-design: included in the computation, evaluated, and therefore
also with a claim to an allowable stress.  Asked whether a set should "not occur at all",
this thus in fact meant "like non-design".

Now `domains.aktive()` filters out the ignored sets before the configuration is created:

* `core/conf.py` now writes only design and non-design domains (`domain_optimized`,
  `domain_density`, `domain_material`, `domain_thickness`),
* the hint about missing allowable stresses in the panel skips ignored sets - they
  do not need any,
* the material check of the input file (D29) still applies to **all** sets: CalculiX computes
  every element in the model, also that of an ignored set, and needs a material for it.

Measured: `tests/headless_test.py` checks that an ignored set appears neither in `domain_optimized`
nor elsewhere in the configuration (142 checks), `tests/panel_test.py` checks that it
does not require a stress (132).

## D31 - No more RecursionError when a run ends with an error

After a run that ends with an error code, the user interface ran into an endless recursion:
`_lauf_aktualisieren()` expanded the detail field in the error case (`knopf_detail.setChecked(True)`
and `_detail_umschalten()`), and `_detail_umschalten()` calls `_lauf_aktualisieren()` again when the detail is visible -
which reaches the error case again.  FreeCAD's console filled with
`RecursionError: maximum recursion depth exceeded while calling a Python object`.

Fixed: the filling of the detail text is now in `_detail_fuellen()`.  The error case sets
visibility and arrow directly and calls `_detail_fuellen()` **once** - without the detour via
`_detail_umschalten()`, which calls back.  Measured: `tests/panel_test.py` reproduces the error case
(run over, detail collapsed) and checks that the call returns and the field is open
(132 checks).

## D30 - The failure index needs an allowable stress in every domain

A run with a domain without sigma aborted with `KeyError: 27004` (`beso_lib.save_FI`).
Re-measured: `criteria_elm` is filled only from `domain_FI` (thus only for domains **with**
stress), and `save_FI` accessed it - unlike the two other places, which check `if en in
criteria_elm` - without a check.  With `criteria_elm.get(en, [])` it continues, and beso
then reports what it really needs: "FI_max computing failed. Check if each domain contains at
least one failure criterion."

That is beso logic and stays so: the failure index is formed **per domain**, so every
domain needs a criterion as soon as one is set at all.  The allowable stress is with us
**optional** (D27) - therefore new:

* Panel: **red** when sigma is set for only part of the domains ("The failure index needs
  an allowable stress in EVERY domain - it is still missing for: ...") and, as before, orange,
  when none is set at all.  Red, because the run aborts otherwise.
* **Fix 5** in the bundled beso: an element without a criterion is skipped instead of
  crashing with `KeyError`.  **Not** offered upstream - the four PRs #57...#60 suffice, and
  the original GUI writes a criterion only where the user enters a value
  (re-measured: `beso_fc_gui.py:836 if von_mises:`), the case is thus possible there too, but
  rarer.
* Test case: `tests/szenarien/modell_2sets.inp` (two element sets with their own material) and the
  scenario "3D two sets, one without sigma".  Measured: 17 scenarios, 14 identical, the three
  deviations are the known fixes; the new case aborts with both beso versions,
  ours with the clear message.
## D29 - The input file is checked before the run starts

A run with two materials and two element sets ended with
`AssertionError: CalculiX results not found`, although beso worked correctly.  Re-measured on
the files: the `.inp` was **truncated** while writing - it ended after the first
`*MATERIAL`, `*SOLID SECTION`, `*STEP`, `*BOUNDARY` and `*CLOAD` were missing.  CalculiX therefore
computed nothing (result file 0 bytes) and beso reported completely correctly that there are no
results.  A second case: an element set had **no** section card, because its material lay on
four **faces of a chamfer** instead of on a solid - from that FreeCAD writes no
volume set, and CalculiX omits these elements without material.

Both become apparent only late and with an incomprehensible message.  Therefore
`elsets.pruefe_inp()` now checks the file in step 1, and `AssistantPanel._pruefe_inp()` shows the
result in red above the domain list:

* missing cards (`*MATERIAL` or `*STEP`) - "The input file is incomplete (`*STEP` is missing) -
  please regenerate it."
* element sets without a section card - "For these element sets the material assignment is missing
  (no section card): ... - their elements are not included in the computation."

Boundary conditions are **not** checked: a model can also be written without them (the
test model of the test suite has none).  Measured: `tests/headless_test.py` checks the truncated
file, the file with a set without section and the inconspicuous case (138 checks);
`tests/panel_test.py` checks that the hint appears and disappears again (127).

**Addendum - the cause of the truncation itself:** A material with the card `Default` had only
a density, but **no** Young's modulus.  FreeCAD's writer then aborts with
`KeyError: 'YoungsModulus'` and leaves exactly such a half-finished file behind (the panel showed
only "The input file could not be generated: 'YoungsModulus'").  Therefore
`material.fehlende_werte()` checks all materials of the analysis for `YoungsModulus` and `PoissonRatio`,
and `AssistantPanel._pruefe_inp()` names them in the same red hint:
"These materials are missing values that CalculiX needs: <Material> (YoungsModulus) - please add
them in the material editor."  Measured: headless 140 checks (material without Young's modulus,
material without Poisson's ratio, complete material), assistant 129 (hint names material and value,
disappears after the values are added).

## D28 - The optimization object has no switchable eye in the tree

Visibility is not a property of the object, but of the scene graph of its view provider.
Our provider supplies icon, double click and tooltip and draws nothing into the 3D view -
therefore FreeCAD greys out the eye symbol.  The other FEM objects have it, because material,
solver and mesh draw something (measured in the document: `MaterialSolid` and `SolverCalculiX` with
FreeCAD's own providers, our object with `TopologyViewProvider`).

This is intentional: the object is a **control object**, the results lie as their own
objects in the tree (VTK iterations, result mesh) and have their own eye there.

Rejected: linking the eye to the last iteration (duplicate representation next to the
result objects) and making the eye switchable with an empty node only (visible as with
other objects, but without effect).

## D27 - The sigma column stays empty, a hint explains the failure index (replaces D20)

Up to here (D20) the allowable stress was filled automatically from the material when a
yield strength was given there.  That is superseded: the column stays **empty** by default, and
under the list there is a hint in orange.

Reasoning:

* The **yield strength** of a material card (e.g. Aluminum-6061-T6 = 276 MPa, measured in the
  cards of FreeCAD 26.3) is a material property.  The **allowable** stress is a
  decision (safety factor, load case).  An automatically entered value looks like
  a dimensioning, but is not one - and one does not notice that it still has to be made.
* Of the 208 material cards in FreeCAD 26.3, only **125** bring a yield strength; the
  simple cards (CalculiX-Steel, Steel, Aluminum) have none.  In the test model there is
  therefore none - the 235 in a domain list was a value stored in the object
  (`StressLimits`), not a value from the material.
* The failure index is an additional evaluation: without a value beso simply computes without FI.

Behavior now: column empty.  Under the list there is in orange "Without allowable stress (sigma)
no failure index is computed."  If a value is stored in the material, the hint **names**
it ("From the material: <set> = 315 MPa - enter the value into the sigma column if you want to see
the utilization"), but does not enter it.  As soon as a value stands in the column,
the hint disappears - also when the field was deliberately emptied, because exactly then "no
FI" is the important information.  Where the named material value comes from is governed by D26
(assignment from the input file).

## D26 - No material or thickness selection in the user interface

The question (18.09.2026) was whether one should be able to select the **material** and the
**shell thickness** per element set in the domain table - a model with two materials,
but only one element set suggested that the assignment was missing.

Looked up in the real input file: FreeCAD writes both in completed form, e.g.

    *SOLID SECTION, ELSET=MaterialSolidSolid, MATERIAL=MaterialSolid
    *SHELL SECTION, ELSET=MaterialSolidElementGeometry2D, MATERIAL=MaterialSolid, OFFSET=0
    10

So there is nothing to assign - the assignment arises already in the FEM analysis, and
CalculiX computes with exactly these specifications.  A model with two materials, of which only
one is used, has a section card for this one only and thus also only one
domain.  A selection list in our panel would therefore not only be superfluous, it
could even claim something different from what CalculiX actually computes.

**What was wrong, however:** The suggestion for the allowable stress fetched the material
via the **name prefix** ('MaterialSolid' belongs to 'MaterialSolidSolid').  That works
by coincidence as long as the set is named after its material - and is wrong as soon as in
the input file a different material is entered (`MATERIAL=MaterialSolid001` with
a set named `MaterialSolidSolid` would have delivered the yield strength of the wrong material).
Now `elsets.read_section_materials` reads the attribute value `MATERIAL` of the
`*SOLID SECTION`/`*SHELL SECTION` cards, `material.streckgrenze` uses it first and
falls back to the name prefix only when the input file does not yet contain anything
(not yet generated).  Measured: `tests/headless_test.py` checks both - with assignment
276 MPa (MaterialSolid001), without assignment 235 MPa (name prefix).
The shell thickness still comes exclusively from the input file (D20 family,
commit `4e7d261`).

**Addendum (re-measured in `beso-original/beso_fc_gui.py`):** The original beso GUI could do that
very well - it had **per domain** a material selection *and* a thickness selection: a selection field
of the `ElementGeometry2D` objects (`combo0t`…`combo2t`, line 125 ff., "Thickness object to specify
if domain is for shells") plus a number field whose tooltip says *"Thickness [mm] of shell
elements in the domain. This value overwrites thickness defined in FreeCAD"* (line 149 ff.).  From
material name and thickness object it builds the elset name (line 612).  The 1 mm value in the
configuration template is therefore only an example value, not the behavior of the GUI.

Why the addon nevertheless lets nothing be selected: the assignment is unique with the section card
and already lies in the file with which CalculiX computes (D26).  Whoever deliberately wants to compute **differently**
than the model says changes the thickness in the model (or the `ElementGeometry2D` object)
and rewrites the input file - then model, computation and optimization match again.
## D9 - All tests use a self made test document

`tests/make_test_document.py` creates a small FEM document (box, material, coarse gmsh mesh
with about 400 elements, solver) in the temp directory; every test works on a copy of it.

*Reason:* tests must not depend on a document of somebody's own project -
that mixes test data with real work and hides the fact that a fresh model behaves
differently. Found while switching: without a material *reference* (`References` to the
solid) FreeCAD writes no material ELSET at all, so the domains table stays empty. The test
document therefore assigns the material to the body.

## D25 - Performance comparison with the unchanged beso from GitHub

Does the bundled beso compute as fast as the original and does it deliver the same numbers?
`tests/vergleich_varianten.py` measures the preparation work of both copies on the same model,
`tests/szenario_test.py` computes the same scenarios with both and compares the masses.

* Preparation on 84,395 volume elements / 22.5 million neighbour pairs: original 27.6 s,
  **bundled 26.8 s**.  Both find the same mean element size (1.3343 mm) and the same number of
  neighbour pairs.
* A complete run on a model with 58,871 elements (3 iterations): original 97.2 s,
  bundled 95.7 s, with **bit-identical masses** (5.233986579481923e-05,
  5.076871505084876e-05, 5.0006983356593286e-05, 4.925693374653859e-05).
* Result: the addon computes **exactly like the original macro** and just as fast.  The four
  fixes cost no computing time; they only change what happens with a model that cannot be
  computed (see D24).
