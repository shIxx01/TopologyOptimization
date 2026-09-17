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

The optimization object lives **inside** the FEM analysis it works on. The analysis stays
the single source of truth for the model: the addon only reads from it.

## Components

| File | Responsibility |
|---|---|
| `workbench.py` | registers the workbench, its toolbar and menu |
| `commands/create_optimization.py` | the command: checks the **active** analysis, creates the object, shows a hint if there is none |
| `features/topology_object.py` | `App::FeaturePython` proxy, properties, `create_topology_object()`, `find_analysis()` |
| `features/topology_vp.py` | view provider: icon, later the assistant on double click |
| `resources/__init__.py` | absolute paths to icons (no `sys.path` tricks) |

## Why "active analysis" and not "selected analysis"

FreeCAD has a built-in notion of an active analysis - the same mechanism the FEM commands
use (`FemGui.getActiveAnalysis()` / `setActiveAnalysis()`, see
`Mod/Fem/femcommands/manager.py`, and FEMbyGEN uses it too). The active analysis is shown
in bold and is the container new FEM objects go into. Using it means:

* the user never has to answer "which analysis?" - the question is already answered by the
  document state, exactly like the active body in PartDesign;
* the command can refuse to act when there is no active analysis, instead of guessing.

## Planned flow of a run (next steps)

1. **Assistant dialog** (task panel) on the optimization object, in steps:
   design domain / non-design domain → parameters → run → results.
2. **`beso_conf.py` generation**: the addon writes the beso configuration (path, solver,
   `.inp` file, element sets, density, allowed stress, mass goal, filter range).
3. **`.inp` creation** with FreeCAD's own tools (`femtools.ccxtools.FemToolsCcx`), including
   the known pitfalls: `setup_ccx()` returns a *relative* solver path (make it absolute),
   `femutils.is_of_type()` does not recognise `Fem::FemAnalysisPython` (search the analysis
   by `TypeId.startswith("Fem::FemAnalysis")`), and the working directory must contain no
   spaces (CalculiX cuts the job name at the first space).
4. **Run beso** in a separate process (FreeCAD's bundled Python, `PYTHONUTF8=1`,
   `MPLBACKEND=Agg`), with live progress in the panel and a stop button.
5. **Result** into the document: import the state `.inp`/`.vtk` files, optionally as a
   VTK iteration player.

## Data model

The optimization object stores its parameters as FeaturePython properties, so they are
saved inside the `.FCStd` document (no side files). `ensure_properties()` adds missing
properties for objects written by older versions. The analysis is referenced by
`AnalysisName` (a plain string) - see `decisions.md` for the reason.

## Interaction with beso

beso is a plain Python program (`beso_main.py` + modules) that is driven by a configuration
file which it `exec`s. The addon therefore:

* ships a reviewed copy of beso (same code as https://github.com/shIxx01/beso),
* writes `beso_conf.py` into the working directory,
* starts `beso_main.py` with the bundled interpreter of FreeCAD,
* reads the iteration log for progress and the result files for the final state.

beso is LGPLv3; the copy keeps its license header and the README lists the changes compared
to upstream.
