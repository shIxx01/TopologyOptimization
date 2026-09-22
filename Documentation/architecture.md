# Architecture

## Overview

```
FreeCAD                          TopoOpt addon                    external process
--------                         -------------                    ----------------
FEM workbench                    TopoOpt workbench
  analysis (group)  <-- contains --  Topologie-Optimierung  --writes-->  beso_conf.py
    mesh, material,                  (App::FeaturePython)   --starts-->  beso_main.py
    constraints, loads                Proxy + ViewProvider  <--reads---  log, results
    solver                                          |
                                          result mesh back into the document
```

The optimization object lives **inside** the FEM analysis it works on.  The analysis stays the
single source of truth for the model; the addon only reads from it and writes the result back
as a new mesh object.

## Components

| File | Responsibility |
|---|---|
| `workbench.py` | registers the workbench, its toolbar and menu |
| `commands/create_optimization.py` | the command: checks the **active** analysis, creates the object, explains itself when there is none |
| `features/topology_object.py` | `App::FeaturePython` proxy, properties, `create_topology_object()`, `find_analysis()` |
| `features/topology_vp.py` | view provider: icon, opens the assistant on double click |
| `core/fem.py` | analysis, mesh, solver, input file - finding and writing it |
| `core/elsets.py` | element sets, shell thicknesses and the material of a set, read from the `.inp` |
| `core/domains.py` | roles (design / non-design / ignore) and the allowable stress per set |
| `core/params.py` | parameters, filter list, mass change, defaults |
| `core/radius.py` | element sizes, neighbour check, the robust filter range |
| `core/material.py` | materials of the document, yield strength in MPa |
| `core/conf.py` | writes `beso_conf.py`, keeps beso's configuration mechanics |
| `core/beso.py` | locates the bundled beso copy and its modules |
| `core/lauf.py` | reads progress out of beso's log |
| `core/netz.py` | imports the result state (`*_state1.inp`) as a FEM mesh |
| `core/vtk.py` | reads the iteration states (`resulting_states.vtk`) |
| `gui/assistant.py` | the task panel with the three steps |
| `gui/verlauf.py` | the history window (mass and failure-index curves) |
| `gui/vtk_anzeige.py` | the VTK iteration viewer |
| `core/i18n.py` | English source texts and the German dictionary |
| `resources/` | absolute paths to icons (no `sys.path` tricks) |

## Why "active analysis" and not "selected analysis"

FreeCAD has a built-in notion of an active analysis - the same mechanism the FEM commands use
(`FemGui.getActiveAnalysis()` / `setActiveAnalysis()`, see `Mod/Fem/femcommands/manager.py`).
The active analysis is shown in bold and is the container new FEM objects go into.  Using it
means the user never has to answer "which analysis?" and the command can refuse to act when
there is no active analysis instead of guessing.

## The three steps of the assistant

1. **Initialize** - find or write the input file and set the role of every element set.
2. **Parameters** - mass goal, optimization base, filters and ranges, tolerance, saved
   iterations, allowable stress.
3. **Calculation** - run beso, watch the progress, load the result.

Every step writes into properties of the document object, so a saved document carries the
whole setup.

## Data model

Parameters are FeaturePython properties of the optimization object, so they are saved inside
the `.FCStd` document (no side files).  `ensure_properties()` adds missing properties for
objects written by older versions.  The analysis is referenced by `AnalysisName`, a plain
string - a `PropertyLink` back to the group that contains the object would make the dependency
graph cyclic (see `decisions.md`).

The element sets are stored as `["<set>|<role>", ...]` and the allowable stresses as
`["<set>|<MPa>", ...]`; the document is the single source of truth, the table only shows it
and writes changes straight back.

## How a run works

1. `core/conf.py` writes `beso_conf.py` into a run folder next to the input file.  The values
   come from the object's properties; the element sets, the shell thicknesses and the material
   of each set are read from the `.inp` instead of being guessed.
2. beso runs in a separate process with FreeCAD's own interpreter.  Its stdout goes to a log
   file, its progress table is read from beso's own log for the progress bar and the curves.
3. The result files (`file00X.vtk`, `resulting_states.vtk`, `<name>_state1.inp`) are read back
   when the user asks for them: iterations as a VTK player, the final state as a FEM mesh.

## Interaction with beso

beso is a plain Python program (`beso_main.py` plus modules) driven by a configuration file
which it `exec`s.  The addon therefore:

* ships a reviewed copy of beso in `freecad/TopoOpt/beso/` - upstream plus the changes listed
  in `CHANGES-TopoOpt.md`, each marked with a `TopoOpt:` comment in the source and checked by
  `tests/vergleiche_beso_kopie.py`, so nothing has to be downloaded,
* writes `beso_conf.py` into the run folder,
* starts `beso_main.py` with FreeCAD's Python and `-u` (unbuffered, D34).  Neither the interpreter
  nor `ccx` is assumed: both are searched next to the FreeCAD program, in `sys.prefix/bin` and
  finally in the search path of the system.  In FreeCAD's Flatpak that is `/usr/bin/python3`
  (with numpy and matplotlib) and `/app/bin/ccx`; when no Python is found the run is refused with
  a message instead of starting the wrong program (D39),
* reads the iteration log for progress and the result files for the final state.

beso is LGPLv3; the copy keeps its license header and its README, and the changes are
documented in `CHANGES-TopoOpt.md`.
