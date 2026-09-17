# beso
Python code for a topology optimization using CalculiX FEM solver. `beso` stands for a method coined:

**B**i-directional  
**E**volutionary  
**S**tructural  
**O**ptimization 
 
 An in-depth description of beso and its capabilities are available on the [dedicated beso wiki](https://github.com/calculix/beso/wiki/Basic-description).

![fine mesh](https://github.com/fandaL/beso/raw/master/wiki_files/example_3/results-fine_mesh.png)
![initial smooth](https://github.com/fandaL/beso/raw/master/wiki_files/example_3/results-initial_smooth.png)
![](https://github.com/fandaL/beso/raw/master/wiki_files/example_2/resulting_mesh.png)
![](https://github.com/fandaL/beso/raw/master/wiki_files/example_2/resulting_mesh_FI.png)

## Prerequisites

* CalculiX >= v2.17
* numpy
* FreeCAD >= v0.18

## Installation


## Usage

Description with a simple example are in [wiki](https://github.com/fandaL/beso/wiki).

* [Example 1](https://github.com/calculix/beso/wiki/Example-1:-simply-supported-2D-beam) Simply supported 2D beam
* [Example 2](https://github.com/calculix/beso/wiki/Example-2:-engine-bracket) Engine bracket
* [Example 3](https://github.com/calculix/beso/wiki/Example-3:-airplane-bearing-bracket) Airplane bearing bracket
* [Example 4](https://github.com/calculix/beso/wiki/Example-4:-GUI-in-FreeCAD) GUI in FreeCAD

## Notes for Windows

* Set `PYTHONUTF8=1` (or `PYTHONIOENCODING=utf-8`) before running beso. Otherwise Python uses the
  system code page (for example cp1252) and reading a file written in UTF-8 stops with
  `UnicodeDecodeError: 'charmap' codec can't decode byte ...`.
* Use a working directory (`path` in `beso_conf.py`) without spaces. CalculiX cuts the name of the
  result file at the first space, so no `.dat` file is written and beso stops with
  "CalculiX result file not found".
* Give the solver as an absolute path in `path_calculix`. The CalculiX path returned by FreeCAD
  (`FemToolsCcx.setup_ccx()`) is relative (`.\ccx.EXE`), and beso starts the solver with the working
  directory set to `path`, where this relative path does not point to the solver.

## Changes compared to the upstream master

This fork is based on the upstream master (commit `5056d30`) and contains three small, independent
fixes. Everything else is unchanged.

1. **`beso_filters.prepare2s` - sector keys of the `simple` filter** (neighbourhood search).
   The sectors were addressed by their centre coordinates rounded to 6 significant digits. These
   keys are not reliable: the loop that builds the grid (`x += r_min`) can end one cell too early,
   and the same cell centre computed in two different ways can be rounded to two different keys.
   In both cases an element was not found in `sector_elm` and the run stopped with
   `KeyError`. The sectors are now addressed by integer grid indices, and only the occupied cells
   are stored, so no cell can be missing.
   *Measured* on a mesh with 41,666 C3D10 elements (r_min = 7.4684509885691091 mm): upstream stops
   with `KeyError (63.5661, 4.3587, -3.82098)`, the fixed version runs through. For radii where the
   upstream works (r_min = 2.3214 and 4.6428 mm) the neighbourhood is identical (same number of
   neighbours for every element, same number of pairs) and a complete run of 3 iterations gives
   exactly the same mass and failure-index values.
2. **`beso_filters.run1`/`run2` - element without neighbour** (filter range too small for a graded
   mesh). This is reported in the log and the run stops with exit code 1. Before, the failure was
   silent: the sensitivity numbers were returned unfiltered, the checkerboard effect appeared and
   the run did not converge (the assignment to a local variable `filter_on_sensitivity` had no
   effect at all).
3. **`beso_main` - missing shell thickness.** For shell (2D) elements `domain_thickness` is needed
   to compute the mass. If it is missing, beso now stops with a clear message instead of
   `IndexError: list index out of range`.

## Developer

[@fandaL](https;//github.com/fandaL)

## License

LGPLv3 ([LICENSE](LICENSE))