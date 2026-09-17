# TopoOpt

Topology optimization for FreeCAD, based on [beso](https://github.com/calculix/beso)
(Bi-directional Evolutionary Structural Optimization) and the CalculiX solver.

The addon works on a finished FEM analysis of the FEM workbench: the optimization
object is added to that analysis and the result is written back into the document.
No extra workbench for pre- and postprocessing is needed - the mesh, the materials,
the constraints and the loads stay where they are.

## Status

**Early stage.** What works today:

* the workbench and its toolbar/menu entry,
* creating a `Topologie-Optimierung` object inside the **active** FEM analysis
  (same rule as the FEM commands themselves: no active analysis, no object).

What is still missing (next steps):

* the assistant dialog (design domain, parameters, progress, results),
* the run of beso including the postprocessing of the result mesh.

## Requirements

* FreeCAD 1.0 or newer (tested with 26.3)
* the FEM workbench of FreeCAD and its CalculiX solver (shipped with FreeCAD)
* Python 3 with `numpy` (comes with FreeCAD)

## Installation

### With the Addon Manager (recommended)

1. Open *Tools → Addon manager*.
2. Open *Configuration* (top right) and add the repository URL to the
   *Custom repositories*:
   `https://github.com/shIxx01/TopologyOptimization`
3. Install *TopoOpt* from the list and restart FreeCAD.

### Manually

Copy this folder into the `Mod` directory of your FreeCAD user directory, so that
`Mod/TopologyOptimization/package.xml` exists, and restart FreeCAD.

## Usage

1. Create a FEM analysis with mesh, material, constraints and loads, as usual.
2. Make sure the analysis is **active** in the tree (double click, or right click →
   *Activate analysis*). The active analysis is shown in bold.
3. Switch to the *TopoOpt* workbench and click *Topologie-Optimierung*.
4. The new object appears inside the active analysis and keeps a link to it.

## Documentation

* [`AGENTS.md`](AGENTS.md) - rules and workflows for AI coding agents (and humans)
* [`Documentation/architecture.md`](Documentation/architecture.md) - how the addon is built
  and how a run will work
* [`Documentation/development.md`](Documentation/development.md) - install for testing, test
  recipes (headless and GUI), debugging notes
* [`Documentation/decisions.md`](Documentation/decisions.md) - why things are the way they are
* [`Documentation/roadmap.md`](Documentation/roadmap.md) - what is done and what comes next

Tests live in [`tests/`](tests/): `headless_test.py` (console interpreter) and
`gui_test.py` (writes its result to a file, see development.md).

## License

* Code: LGPL-3.0-or-later (`LICENSE-Code`)
* Icons and other assets: CC0-1.0 (`LICENSE-Assets`)

`beso` is written by František Löffelmann and published under LGPLv3
(https://github.com/calculix/beso).

## Author

shIxx (https://github.com/shIxx01) - not a programmer; the addon is developed with
the support of an AI assistant and tested on real models.
