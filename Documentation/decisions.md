# Decisions

Short records of decisions that are not obvious from the code. Each one names the evidence
if it was measured.

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

*Reason (user request):* a file that was already written by the solver panel must not be
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

*Reason (user request):* the optimization object is a child of the FEM analysis, so its
files belong where the FEM files are. Before, the addon used a directory of its own under
`%TEMP%/TopoOpt`, which looked like a second, unrelated place.

## D11 - Localized texts: English source, German dictionary

See D7.  Additionally: the header line of the assistant lists the analysis case
(`Analysis`, `Mesh`, `Solver`) and shows missing parts in red, while the status line is
green as soon as everything is present, orange while the user has to act and red on errors.

*Reason (user request):* a hint text that simply disappears hides the information; colours
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

*Reason (user request):* the panel could not be made narrow without things disappearing.
Combo boxes are the main culprit: by default a combo wants as much room as its longest
entry.

Two small user requests went in with it: the core count shows "all" instead of 0
(`setSpecialValueText`, which only works while the minimum is 0), and the save interval
starts at **10** instead of the beso default 1 (a saved iteration of a fine mesh can need
100 MB and more; the final result is what counts).

## D15 - beso ships with the addon

The beso files live in `freecad/TopoOpt/beso/` (beso_lib, beso_filters, beso_main,
beso_plots, beso_separate, the template beso_conf.py, LICENSE, README) and
`core/beso.py` loads them from the folder of the addon.  `sys.modules` is filled directly,
so nothing is added to `sys.path`; the modules keep their own names because beso imports
itself that way (`import beso_lib` inside `beso_filters`).

*Reason (user request):* a user should install the workbench and start - without a second
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

**Speed matters here** (the user has to wait for the check).  Measured on a mesh with
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
  Without it Windows opens a console window for the run - the first prototype started
  beso in a way that did not show one, and the user noticed the difference.
* **Progress bar** like in the first prototype: 0 % = mass of the whole part, 100 % = target
  mass, `(start - mass) / (start * (1 - ratio)) * 100`.  It is not forced to 100 % when the
  run stops early (iteration limit) - it shows what really happened.
* **Charts in an own window**, as in the first prototype: `gui/verlauf.py` uses FreeCAD's
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
  the CalculiX output); the whole log file belongs to step 4 (as the user asked).
* The status line reads `Iteration 12 | mass 15340, target 12000 | 3:20 min`.  No
  percentage: right after the start the mass is far above the target and "323 %" only looked
  like an error.

## D19 - Allowable stress per element set is what switches the failure index on

The user asked why the first prototype showed the failure index charts even with
`optimization_base = "stiffness"`, and this addon did not.  The reason is not the
optimization base:

* beso computes a failure index when `domain_FI` is filled: `beso_main.py` sets
  `domain_FI_filled = True` as soon as one domain has FI criteria (line 78-80), and with
  `stiffness` it reads the stress values from the CalculiX `.dat` file (line 415-418).
  So the FI charts work with every optimization base.
* The first prototype had a column "zulässige Spannung" per domain and wrote
  `domain_FI[elset] = [[('stress_von_Mises', σ*1e6)], [('stress_von_Mises', σ)]]`
  (`bridge.py:235`).  A real run of it shows the values:
  `0.0434 FI_mean`, `0.3568 FI_max`, `0.00134 ener_dens_mean`.
* This addon had no such field, so `domain_FI` stayed empty and three of the four charts
  had no values.  That was a missing function, not a bug.

Therefore (as the user decided): **a column "σ (MPa)" next to every element set** in step 1,
stored in the object as `StressLimits` (`"<set>|<MPa>"`).  Empty means: no failure index.
The format is beso's own (inner tuples = separate indices, second list = second element
state).  A written configuration is executed in the test and really sets

    domain_FI = {"SetA": [[("stress_von_Mises", 235000000.0)], [("stress_von_Mises", 235.0)]]}

**Prerequisite, and beso says so itself**: the model needs real loads.  Without results in
the `.dat` file beso stops with `CalculiX results not found, check CalculiX for errors.`
(`beso_main.py:434`).  The energy density chart has the same reason: our test document has no
loads, so `ener_dens_mean` is 0.0 there.

**The empty field is deliberate - the first prototype filled it silently.**  The prototype had
`build_domain(..., stress_limit=450.0, ...)` (`bridge.py:133`) and showed the value in its table
(`taskpanel.py:750`), so every run wrote `domain_FI = 450 MPa` - taken from beso's own example
configuration (`beso_conf.py`: `[[("stress_von_Mises", 450.0e6)], …]`).  The user never typed it
and did not know it was there; 450 MPa is far above the allowable stress of ordinary steel
(S235: 157 MPa at a safety factor of 1.5), so overloads would have been reported too late.
The user decided (September 2026): **leave the field empty** and fill it deliberately - from
the material if the material carries a value, otherwise by typing it.  Do not "repair" this by
adding a default value.

## D20 - The allowable stress is suggested from the material, if the material has one

The user asked why he has to type the allowable stress at all and whether it can come from
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
field in** - but only for sets that have no value yet.  A set whose field the user has
deliberately emptied is stored as `"<set>|0"`, so the suggestion does not come back.
The assignment material -> element set goes by name (`MaterialSolid` belongs to
`MaterialSolidSolid`); with exactly one material it applies to all sets.

## D21 - Steps 3 and 4 are one step "Calculation" with the viewer of the prototype

The user asked to put run and results together in one tab named "Berechnung" and to take the
VTK viewer from the first prototype, "because it runs cleanly and nicely".

* The step bar now has three steps: **Initialize | Parameters | Calculation**.  The
  calculation page holds a "Run" group (start/cancel, progress bar, status, history) and a
  "Results" group (iterations, log, folder).
* `core/vtk.py` is the reader of the prototype, kept as it was - including the three traps it
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
  (the user's wish for the full log).

### Nacharbeit des Nutzers (gleiche Sitzung)

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

## D22 - Panel layout like the prototype: text step bar, own scroll area, navigation below

The user compared with the first prototype again: the clickable step buttons were not nice, the
scroll bar sat outside the panel, and the prototype keeps the step bar visible while scrolling
with back/next at the bottom.  The prototype's structure (`taskpanel.py:130-166`) is:

    QVBoxLayout
      step bar   (one RichText QLabel: bold current step, " › " between, gray others)  fixed
      QScrollArea (setWidgetResizable, NoFrame) -> QStackedWidget (the pages)          scrolls
      navigation (["< Zurück"] ... ["Weiter >"], the outer button hides)               fixed

* The step bar is now such a label (`schritt_label`, RichText) instead of tool buttons -
  clicking a step is gone, the way forward is the navigation below (as in the prototype).
* The pages sit in a `QScrollArea` with `setWidgetResizable(True)` and `NoFrame`, so the scroll
  bar belongs to the content area, not to the whole task panel.
* Below: `< Zurück` / `Weiter >` (`_schritt_zurueck`, `_schritt_weiter`); at the first step
  there is no "back", at the last none "forward" (the outer button hides, as in the prototype).
* `_zeige_schritt` puts the scroll bar back to the top on every step change.
* Measured: the panel's minimum width dropped from **348 to 234 px** - the text bar and the
  navigation below need much less room than three toggle buttons in a row.

**The element-set table does not fill the step any more.**  The user asked why the list in step 1
was so long downwards: the table lay in the layout with stretch 1
(`layout.addWidget(self._domain_tabelle(), 1)`), so it grew over the whole free space - and with
the new scroll area over the whole scroll area.  Now it is added without stretch, the free space
is taken by a stretch below it, and `_tabelle_hoehe_anpassen()` sets the height to
header + rows (measured: **64 px** with one element set).  From twelve rows on it keeps that
height and scrolls inside itself, otherwise a model with many element sets would grow endlessly.

**Two separate result buttons** (the user's point: "Ergebnis anzeigen" only loaded the VTK):

* **"Iterationen anzeigen"** - the VTK player (`core/vtk.py`): the surface of the material that
  is left, per iteration, for looking at it and for the film.
* **"Ergebnisnetz laden"** - the real result (`core/netz.py`): beso writes
  `<name>_state1.inp` per saved iteration (state 1 = element keeps material), and the newest of
  them is imported with FreeCAD's own `feminout.importInpMesh.import_inp` as an FEM mesh into
  the document.  Sorted by change time, not alphabetically - alphabetically the highest
  iteration number of an **earlier** run would be the "last" one.  The prototype did the same
  (`taskpanel.py`: `_ergebnis_laden`).
* Measured in the panel test: `file001_state1.inp` is found and loaded, the document gets a new
  object.

**Third round of the user's corrections:**

* The running time (`lauf_zeit`, gray) sits **right next to the start button** instead of in its
  own line; the status line below the progress bar hides itself while it has no text.
* The four result buttons form a **2x2 grid**:
  `Ergebnisnetz laden | Diagramme anzeigen` over `Vollständiges Log | Arbeitsverzeichnis öffnen`.
  "Iterationen anzeigen" moved into the row with the slider.
* The running time sits **right next to the start button** in the "Berechnen" group.  An
  attempt to put it into the panel's top line (next to the step bar) was wrong - the user:
  "warum ist die zeit wieder irgendwo wo sie nicht dazugehört".  The time belongs to the run, not
  to the frame of the panel.
* The **slider got its own row** with the full width (measured 640 px in a 640 px panel).
* The **play speed** sits in the row of the control buttons (the user wanted it one row higher):
  combo box 0.5 s / 1 s / 2 s / 3 s as in the prototype (`_takt_geaendert` sets the timer
  interval; measured: index 2 -> 2000 ms).
* **No invisible empty row**: the status line was a row of its own and stayed empty (and thus
  invisible but place-consuming) as long as no run was going - the user saw a blank strip.  It
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
  "Shell thickness from the input file: <set> = <d> mm" so the user sees which set gets which
  thickness.
* **Proof with a real run** (2D analysis from the user's document, 4,614 shell elements):
  before the fix `domain_thickness = [1.0, 1.0]`, mass 2000; with the fix
  `domain_thickness = [10.0, 10.0]`, mass **20000 -> 19396**.  The 3D case gives **20000 -> 19399**
  - the two models meet within 0.02 %, which confirms 10 mm is the right value.
* Cost of the comparison: the 3D case with 84,395 volume elements needed **232 s** for one
  iteration (surface 12.8 MB `.inp`), the 2D case 6 s - a factor of about 39.

## D24 - Szenario-Matrix: Fehlerfaelle, Filter, 2D/3D und der Vergleich mit Original-beso

`tests/make_szenario_inp.py` erzeugt drei winzige Modelle (8 Hexaeder, 4 Dreiecke, dasselbe ohne
`*SHELL SECTION`) mit echten Lasten; `tests/szenario_test.py` rechnet daraus 15 Szenarien - Filter
(simple mit auto/robust/manuell, casting, alle sieben Morphologie-Filter), Zielmassen (60/30 %),
2D-Schale und 3D-Volumen - **und dasselbe noch einmal mit dem originalen beso des Prototyps**
(`vendor/beso`, ohne unsere Fixes).

Ergebnis (gemessen):

| Fall | gebuendeltes beso | originales beso |
|---|---|---|
| 3D simple robust / casting / Zielmasse 30 % | code 0, Massen 8000 -> 7000 | identisch |
| 3D alle sieben Morphologie-Filter | code 0, Massen 8000 -> 7000 | identisch |
| 2D Schale simple | code 0, Massen 1000 -> 750 | identisch |
| 3D simple auto | **code 1**, "filter range is too small ..." | code 0 (rechnet still weiter) |
| 3D simple manuell 1.0 (Radius < Elementabstand) | **code 1**, klare Meldung | code 0 (rechnet still weiter) |
| 2D ohne Schalendicke | **code 1**, klare Meldung "domain_thickness is missing" | code 1 (IndexError) |
| 2D casting mit "auto" | code 1, `NameError: filtered_dn` | code 1, derselbe Fehler |

* **13 von 15 Szenarien liefern identische Massen** - die Fixes aendern die Rechnung also nicht,
  sie machen nur Fehler sichtbar.
* Die zwei Abweichungen sind genau die beabsichtigten Fixes: zu kleiner Filterradius und fehlende
  Schalendicke fuehren beim gebuendelten beso zu einer **klaren Meldung**, beim Original zu einem
  stillen Weiterrechnen (Division durch 0) bzw. zu einem IndexError.
* **Neuer Fund (offen):** `filter_list = [["casting", "auto", vektor]]` bricht in beso mit
  `NameError: name 'filtered_dn' is not defined` ab - `beso_main.py` setzt `filtered_dn` nur im
  else-Zweig, benutzt es aber in `get_filter_range(...)`, wenn der Rahmen "auto" ist. Betrifft
  beide beso-Versionen (auch upstream) - Kandidat fuer einen weiteren PR und fuer einen Schutz im
  Addon (casting-Rahmen immer als Zahl schreiben).
* Die Fehlerfaelle des Assistenten (ohne Netz, ohne Solver, ohne .inp, ohne Design-Raum) pruefen
  jetzt `tests/panel_test.py`: der Lauf startet gar nicht und der Status nennt den Grund.

## D9 - All tests use a self made test document

`tests/make_test_document.py` creates a small FEM document (box, material, coarse gmsh mesh
with about 400 elements, solver) in the temp directory; every test works on a copy of it.

*Reason (user request):* tests must not depend on a document of somebody's own project -
that mixes test data with real work and hides the fact that a fresh model behaves
differently. Found while switching: without a material *reference* (`References` to the
solid) FreeCAD writes no material ELSET at all, so the domains table stays empty. The test
document therefore assigns the material to the body.
