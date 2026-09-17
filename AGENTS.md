# AGENTS.md

Guidance for AI coding agents (and humans) working on this repository.
Read this file first, then the files in `Documentation/`.

## What this addon is

`TopoOpt` is a FreeCAD addon that runs a **BESO topology optimization** on a finished
FEM analysis. The optimizer is [beso](https://github.com/calculix/beso) by František
Löffelmann (LGPLv3); the solver is CalculiX, which ships with FreeCAD.

The addon does **not** replace the FEM workbench: mesh, materials, constraints and
loads are created there, the optimization only adds a document object to the analysis
and (later) runs beso in an external process.

## Layout

```
package.xml                          manifest read by the Addon Manager
README.md                            user documentation
AGENTS.md                            this file
Documentation/                       architecture, development, roadmap, decisions
LICENSE-Code, LICENSE-Assets         LGPL-3.0-or-later / CC0-1.0
freecad/TopoOpt/
    __init__.py                      loaded in every mode (also console)
    init_gui.py                      loaded only with GUI, calls Install() of everything
    workbench.py                     the workbench "TopoOpt"
    commands/                        one module per command
    features/                        FeaturePython objects and their view providers
    resources/                       icon lookup, later icons and translations
```

## Rules that must not be broken

1. **Never put a `PropertyLink` from the optimization object back to the analysis.**
   The analysis is the group that contains the object, so a link back makes the
   dependency graph cyclic. FreeCAD then prints `The graph must be a DAG.` and
   `<obj> still touched after recompute`. Use the parent group (`obj.InList`) and the
   stored `AnalysisName` string instead. Verified by measurement - see
   `Documentation/decisions.md`.
2. **Do not add commands, toolbars or menus to other workbenches** (for example the FEM
   workbench). The FreeCAD Addon Index requires addons to keep their UI inside their own
   workbench. That is why `TopoOpt` is a separate workbench with its own toolbar.
3. **No `sys.path` manipulation and no top-level module names.** Everything lives inside
   the `freecad.TopoOpt` namespace package.
4. **Use the FreeCAD Qt wrappers** (`from PySide import QtWidgets, ...`,
   `App.Qt.translate`), never a directly imported PySide6.
5. **SPDX header in every Python file**: `# SPDX-License-Identifier: LGPL-3.0-or-later`.
   The license string must stay identical in `package.xml`, the LICENSE files and the
   headers (the Index requires this).
6. **Keep the addon fast and silent at import time.** No network, no heavy work at
   startup; do that when the user invokes a command.

## How to work on it

* Install for a test the same way the Addon Manager does: copy the repository folder to
  `%APPDATA%\FreeCAD\<version>\Mod\TopologyOptimization` (without `.git`), delete all
  `__pycache__` folders, then **restart FreeCAD** - the addon is loaded only at start.
* Test recipes (headless and GUI, including the trick that GUI FreeCAD writes no stdout)
  are in `Documentation/development.md`. Always report real output, not expectations.
* FeaturePython objects need `dumps`/`loads` in the proxy (persistence) and
  `ensure_properties()` must be called on every entry point for objects from older files.
* UI texts are wrapped in `translate("TopoOpt", ...)`; they are currently German because
  the first users are German, English translations can be added later.

## Related projects

* `beso` fork with reviewed fixes: https://github.com/shIxx01/beso (the addon will ship a
  copy of it; upstream is https://github.com/calculix/beso)

## Test document

`tests/make_test_document.py` builds a small FEM document from scratch (box, material with
a solid reference, coarse gmsh mesh with about 400 elements, CalculiX solver).  All tests
use it - never a document of somebody's own project.  Its output goes to
`%TEMP%/TopoOpt_Test/modell.FCStd` (or the path in `TOPOOPT_TEST_DOKUMENT`).

## Definition of done for a change

1. Addon installs and loads in FreeCAD without warnings or tracebacks.
2. Headless test and GUI test in `Documentation/development.md` pass.
3. Documentation updated (`Documentation/`, `README.md`, this file if rules changed).
4. Commit message says what changed, why, and which run proved it.
