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

## D9 - All tests use a self made test document

`tests/make_test_document.py` creates a small FEM document (box, material, coarse gmsh mesh
with about 400 elements, solver) in the temp directory; every test works on a copy of it.

*Reason (user request):* tests must not depend on a document of somebody's own project -
that mixes test data with real work and hides the fact that a fresh model behaves
differently. Found while switching: without a material *reference* (`References` to the
solid) FreeCAD writes no material ELSET at all, so the domains table stays empty. The test
document therefore assigns the material to the body.
