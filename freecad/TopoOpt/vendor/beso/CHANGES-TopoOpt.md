# beso inside TopoOpt

This directory contains [beso](https://github.com/calculix/beso) by František Löffelmann,
so that a user can install the workbench and start right away - no second download, no
path to configure.  The addon uses these files:

| file | used for |
|---|---|
| `beso_main.py` | the optimization itself (started as its own process in step 3) |
| `beso_lib.py` | reading the `.inp`, writing result files |
| `beso_filters.py` | sensitivity filters, element sizes, neighbourhood search |
| `beso_plots.py`, `beso_separate.py` | imports of `beso_main.py` |
| `beso_conf.py` | template; the addon writes the real `beso_conf.py` for every run |
| `LICENSE` | beso is LGPL-3.0-or-later (same licence as this addon) |
| `README.md` | beso's own documentation, unchanged |

`beso_fc_gui.py` (beso's own FreeCAD dialog) is **not** included - the assistant of this
addon takes its place.

## Changes compared to beso upstream

The files were taken from the maintainer's beso fork, which fixes three defects of the
upstream master.  Every change is marked in the source with a `TopoOpt:` comment and is
offered upstream as a pull request (calculix/beso#57, #58, #59):

1. **`beso_filters.py`, `prepare2s`** - the sector key of a grid cell is built from the
   integer cell index instead of a coordinate rounded to 6 significant digits.  At a
   rounding border the grid loop and the lookup produced different keys
   (`-32.1747` against `-32.1746`), so `prepare2s` stopped with `KeyError`.  Measured on a
   mesh with 10,804 C3D10 elements and `r_min = 4.2439 mm`: 3,495 of 10,804 elements were
   affected.
2. **`beso_filters.py`, `run1`/`run2`** - an element without a neighbour in the filter
   radius stops the run with a clear message instead of dividing by zero silently (the
   sensitivities stayed unfiltered and beso reported convergence at the end).
3. **`beso_main.py`** - a shell element without `domain_thickness` gives a clear message
   instead of an `IndexError`.

Licence note: beso is LGPL-3.0-or-later, this addon is LGPL-3.0-or-later as well, and the
changes are listed here and marked in the sources - the conditions for redistributing a
modified LGPL work are met.
