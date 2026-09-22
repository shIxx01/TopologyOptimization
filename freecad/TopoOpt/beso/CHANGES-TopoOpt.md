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

The files were taken from the maintainer's beso fork, which fixes defects of the upstream
master.  **Every change is marked in the source with a `TopoOpt:` comment** - and that is
checked, not just claimed: `tests/vergleiche_beso_kopie.py` compares this copy with a clone
of upstream and fails when a difference carries no such comment.  Four of the changes are
offered upstream as pull requests (calculix/beso#57, #58, #59, #60):

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
6. **`beso_lib.py`, `elm_volume_cg`/`tria_area_cg`** - the area of a triangle was computed
   with `np.linalg.linalg.norm`.  `numpy.linalg.linalg` is a private sub module of numpy 1 and
   was **removed in numpy 2.0**, so every 2D (shell) model stopped there with
   `AttributeError: module 'numpy.linalg' has no attribute 'linalg'` before the first
   iteration - with the numpy that ships with FreeCAD today.  Measured with numpy 2.4.4
   (FreeCAD 26.3, Flatpak): the scenarios `2D Schale simple auto` and `2D Schale casting auto`
   ended with exit code 1 and without a single iteration; after the change both run
   (`1000 -> 750`, and `1000 -> 750 -> 750`), while the unchanged upstream copy still stops
   there.  This is the change worth offering upstream first - it hits **every** 2D model, not
   an edge case.  (In the same run the missing `domain_thickness` message above proved itself:
   `2D ohne Dicke` ends with the clear message instead of an `IndexError`.)

Licence note: beso is LGPL-3.0-or-later, this addon is LGPL-3.0-or-later as well, and the
changes are listed here and marked in the sources - the conditions for redistributing a
modified LGPL work are met.
