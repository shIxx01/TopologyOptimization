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

The files were taken from the maintainer's beso fork, which fixes four defects of the
upstream master.  Every change is marked in the source with a `TopoOpt:` comment and is
offered upstream as a pull request (calculix/beso#57, #58, #59, #60):

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
4. **`beso_main.py`** - the casting filter with the range `"auto"` stops with
   `NameError: name 'filtered_dn' is not defined`.  The branch for a casting filter
   without a domain list (`len(ft) == 3`) uses `filtered_dn` in
   `get_filter_range(...)` but never sets it; the line `filtered_dn = domains_from_config`
   is missing, exactly as it exists in the branch below for the other filters.  Measured
   with `filter_list = [["casting", "auto", (0, 0, 1)]]`: before the fix beso stopped after
   after 0.7 s without a single iteration, afterwards it runs with the automatic filter range.
   Offered upstream as calculix/beso#60.
5. **`beso_lib.py`, `save_FI`** - an element without a failure criterion stops the run with
   `KeyError: <element number>`.  The other two places that read `criteria_elm` guard against
   a missing entry (`if en in criteria_elm`), this one did not; it now uses
   `criteria_elm.get(en, [])`.  Measured with two domains of which only one has an allowable
   stress: before, the run stopped with `KeyError: 27004`, afterwards it reports what beso
   actually needs ("Check if each domain contains at least one failure criterion").  Not
   offered upstream - the four pull requests #57...#60 are enough for now, and the case is
   rare there (the original dialog writes a criterion for every domain as soon as one value
   is entered).

Licence note: beso is LGPL-3.0-or-later, this addon is LGPL-3.0-or-later as well, and the
changes are listed here and marked in the sources - the conditions for redistributing a
modified LGPL work are met.
