# AGENTS.md

Guidance for anyone - human or AI assistant - working on this repository.  Read this file
first, then the files in `Documentation/`.

## What this addon is

`TopoOpt` is a FreeCAD addon that runs a BESO topology optimization on a finished FEM
analysis.  The optimizer is [beso](https://github.com/calculix/beso) by František Löffelmann
(LGPLv3), the solver is CalculiX, which ships with FreeCAD.  The addon is a **small front end
for beso**: it collects the parameters, writes the beso configuration, starts the run and
brings the result back into the document.  It is not a fork of beso and not a place for
special cases.

## Rules for the code

1. **Follow the FreeCAD guidelines for addons and workbenches.**  The relevant sources are
   the [Addon Academy](https://freecad.github.io/Addon-Academy/) (structure, manifest,
   metadata, icons), the developer documentation on
   [workbenches](https://wiki.freecad.org/Workbench_creation),
   [commands](https://wiki.freecad.org/Command) and
   [scripted objects](https://wiki.freecad.org/Scripted_objects), and the
   [Addon Index requirements](https://github.com/FreeCAD/FreeCAD-addons).  The rules that
   matter most here:
   * the addon keeps its commands, toolbars and menus **inside its own workbench** and does
     not touch the interface of FreeCAD or of other addons,
   * translate UI text with `translate("TopoOpt", ...)`; write it in English and keep the
     translations in one dictionary,
   * use FreeCAD's Qt wrappers (`PySide`), never a directly imported PySide6,
   * no `sys.path` manipulation; everything lives in the `freecad.TopoOpt` namespace,
   * do not use `App::PropertyLink` from an object to the group that contains it - the
     dependency graph has to stay acyclic.  Use the container (`obj.InList`) and a plain
     string property (see `decisions.md`).
2. **Use beso's own functions instead of re-implementing them** (`beso_lib`, `beso_filters`)
   and keep beso's names for beso's concepts (filters, casting, `mass_goal_ratio`).  The less
   of beso is duplicated, the less can drift apart.  The bundled copy is upstream plus the
   changes listed in `freecad/TopoOpt/beso/CHANGES-TopoOpt.md`; add a change only with a
   measured case, mark it in the source and document it there.
3. **Keep the addon fast and silent at import time.**  No network, no heavy work when the
   module is loaded - do that when the user invokes a command.
4. **SPDX header in every Python file**: `# SPDX-License-Identifier: LGPL-3.0-or-later`.
   The license string must stay identical in `package.xml`, the license files and the
   headers.
5. **FeaturePython objects** need `dumps`/`loads` in the proxy for persistence, and
   `ensure_properties()` has to be called on every entry point so that objects from older
   documents start working again.

## Rules for changes

1. **Say what a change is for and how it was proven.**  Every entry in
   `Documentation/decisions.md` names the measurement or the user-visible reason behind a
   decision; a commit should do the same.  Report real output, not expectations.
2. **Prefer the smallest understandable version.**  Add something only when there is a
   measured or clearly described need, and keep it close to beso and to FreeCAD.
3. **Everything visible is a user decision.**  Labels, layout, defaults and colours are
   shown as described variants first; the maintainer decides.

## Layout

```
package.xml                          manifest read by the Addon Manager
README.md                            user documentation
AGENTS.md                            this file
Documentation/                       architecture, development, decisions, roadmap
LICENSE-Code, LICENSE-Assets         LGPL-3.0-or-later / CC0-1.0
freecad/TopoOpt/
    __init__.py                      loaded in every mode (also console)
    init_gui.py                      loaded only with a GUI, installs everything
    workbench.py                     the workbench "TopoOpt"
    commands/                        one module per command
    features/                        FeaturePython objects and their view providers
    core/                            the working parts: input file, element sets, parameters,
                                     beso configuration and process, radius, materials
    gui/                             the assistant, the history window, the VTK viewer
    resources/                       icon lookup, icons, translations
    beso/                            the reviewed beso copy
tests/                               the test suite (see Documentation/development.md)
```

## How to work on it

* Install for a test the way the Addon Manager does: copy the repository folder to
  `%APPDATA%\FreeCAD\<version>\Mod\TopologyOptimization` (without `.git`), remove
  `__pycache__` folders, then **restart FreeCAD** - the addon is loaded only at start.
* Test recipes (headless and GUI, including the traps of GUI FreeCAD) are in
  `Documentation/development.md`.  Report real output.
* Tests must not use a document of a real project; `tests/make_test_document.py` builds one.

## Definition of done for a change

1. the addon installs and loads in FreeCAD without warnings or tracebacks,
2. the tests in `Documentation/development.md` pass (headless, assistant, GUI),
3. documentation is updated (`Documentation/`, `README.md`, this file if a rule changed),
4. the commit message says what changed, why, and which run proved it.
