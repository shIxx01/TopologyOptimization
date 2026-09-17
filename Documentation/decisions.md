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
