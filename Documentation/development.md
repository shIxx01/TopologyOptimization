# Development

## Install for testing

The addon is loaded only when FreeCAD starts, so a change always needs a restart.

```bash
# copy the repository into the user Mod directory (like the Addon Manager does)
MOD="$APPDATA/FreeCAD/v26-3/Mod/TopologyOptimization"
rm -rf "$MOD"; mkdir -p "$MOD"
cd /path/to/TopologyOptimization
tar cf - --exclude=.git . | (cd "$MOD" && tar xf -)
find "$MOD" -name "__pycache__" -type d -exec rm -rf {} +
```

Then start FreeCAD, switch to the workbench *TopoOpt* (the Addon Manager name is
`TopoOptWorkbench`) and use the toolbar button.

## Test 1 - headless (no GUI)

Covers the namespace import, object creation, persistence, the `.inp` readers (element sets,
shell thicknesses, section materials, element types), the search order for an existing input
file, the beso configuration, the radius functions, the log reader and the VTK/state readers.

```bash
"<FreeCAD>/bin/freecadcmd.exe" tests/headless_test.py
```

It prints one line per check (`OK ...`) and a summary.  It must **not** print
`The graph must be a DAG.`  Reference result: **134 checks, no failures**.

## Test 2 - the workbench and its command (GUI)

```bash
rm -f tests/gui_test_ausgabe.txt
("<FreeCAD>/bin/freecad.exe" "C:/path/tests/gui_test.py" >/dev/null 2>&1 &)
for i in $(seq 1 40); do sleep 2; [ -f tests/gui_test_ausgabe.txt ] && break; done
cat tests/gui_test_ausgabe.txt
```

**Important:** GUI FreeCAD writes nothing to stdout, so every GUI test writes its result into
a file and is started in the background.  The script checks that `Gui.listWorkbenches()`
contains `TopoOptWorkbench`, that the toolbar and menu exist, that the icon files are there,
and that the command creates the object in the active analysis.  Reference: **15 checks**.

## Test 3 - the assistant (GUI, needs the test document)

Build the test document once, then run the assistant test on it:

```bash
"<FreeCAD>/bin/freecadcmd.exe" tests/make_test_document.py     # builds the model
cat tests/make_test_document_ausgabe.txt                       # check: mesh and path

rm -f tests/panel_test_ausgabe.txt
export TOPOOPT_TEST_DOKUMENT="C:/.../Temp/TopoOpt_Test/modell.FCStd"
("<FreeCAD>/bin/freecad.exe" "C:/.../tests/panel_test.py" >/dev/null 2>&1 &)
for i in $(seq 1 60); do sleep 3; [ -f tests/panel_test_ausgabe.txt ] && break; done
cat tests/panel_test_ausgabe.txt
```

FreeCAD does not pass script arguments through `sys.argv`, the document therefore goes into
the environment variable `TOPOOPT_TEST_DOKUMENT`.

The test walks through all three steps: the input file is written into the working directory,
the element sets are listed with their sizes (collector sets `Eall`/`Evolumes` hidden and a
design space suggested), a change in the table is stored in the object straight away, the
parameter fields and the filter rows behave, the radius button computes a value, the σ column
stays empty while the note below the list explains it, and a real mini run is started and
cancelled.  It also covers the four error cases: without mesh, without solver, without input
file and without a design space the run must not start and the status must name the reason.
Reference: **124 checks**.

## Test 4 - scenario matrix and comparison with upstream beso

`tests/make_szenario_inp.py` writes three tiny CalculiX models with real loads (8 hexahedra,
4 shell triangles, the same without `*SHELL SECTION`) - `freecadcmd` cannot save documents on
Windows, and beso only needs the `.inp`.  `tests/szenario_test.py` runs 16 scenarios on them:
filter types (simple, casting, all seven morphology filters), ranges (automatic, robust,
manual), target masses, 2D shell and 3D solid, and the error case of a missing shell
thickness.

For the comparison against upstream, clone the original once:

```bash
git clone --depth 1 https://github.com/calculix/beso.git "$TEMP/beso-original"
# or point BESO_ORIGINAL at an existing clone
"<FreeCAD>/bin/freecadcmd.exe" tests/szenario_test.py
```

The script then computes every scenario a second time with the **unchanged** beso and reports
which scenarios differ.  Reference: 16 runs, **13 of 16 scenarios identical**, and the three
differences are exactly the intended fixes:

| Scenario | bundled beso | unchanged beso |
|---|---|---|
| 3D simple auto / robust / casting / target mass 30 % | code 0, 8000 → 7000 | identical |
| all seven morphology filters | code 0, 8000 → 7000 | identical |
| 2D shell, simple | code 0, 1000 → 750 | identical |
| range smaller than the element distance | code 1, clear message | code 0, computes on (division by zero) |
| 2D without a shell thickness | code 1, names `domain_thickness` | code 1, only an `IndexError` |
| 2D casting with `"auto"` | code 0, 1000 → 750 | code 1, `NameError: filtered_dn` |

The test fails if a scenario differs that is not one of these three, so an unintended change
in the result is noticed.

## Test 5 - performance against upstream beso

`tests/vergleich_varianten.py` measures the preparation work (reading the mesh, volumes and
centres of gravity, element sizes, the neighbour grid) of the bundled copy against the
unchanged upstream copy on the same model:

```bash
"<FreeCAD>/bin/python.exe" tests/vergleich_varianten.py            # largest mesh in %TEMP%
"<FreeCAD>/bin/python.exe" tests/vergleich_varianten.py model.inp ELSET
```

Measured on 84,395 elements with 22.5 million neighbour pairs: 26.8 s (bundled) against 27.6 s
(upstream) for the neighbour grid, both finding the same average element size and the same
number of pairs - the fixes cost no computing time.

## Debugging notes

* `App.Console.PrintMessage/PrintError` in the addon code; `init_gui.py` catches all
  exceptions and prints them, so a broken addon never blocks the FreeCAD start.
* If a change seems to have no effect: check the copy in `Mod/`, not the source folder, and
  delete `__pycache__` (Python may use a stale bytecode cache).
* `FemGui` is only available with a GUI; in headless tests `getActiveAnalysis()` cannot be
  used - test the pure functions instead.
* Deleting an analysis keeps its children (they are only removed from the group), so a test
  document can be cleaned up without losing the optimization object.
* Never wait on a `subprocess` pipe you do not read: beso writes a lot to stdout, and a full
  pipe buffer blocks it.  Redirect to a file instead (this cost an afternoon once).

## Two traps of the FreeCAD script interpreter (measured)

1. **`App.openDocument()` in a start script makes FreeCAD run the whole script a second
   time** (same process, milliseconds later).  A test that saves and reloads a document
   therefore runs twice - once with the document, once without - and results that depend on
   leftovers become flaky.  For a persistence check, read the saved file instead (open it as a
   zip archive and look at `Document.xml`).
2. **`sys.exit()` output is lost when stdout is redirected** AND the script may be re-run:
   `print(..., flush=True)` and `os._exit(code)` at the end are the safe way (see
   `tests/headless_test.py`).

## Test data must be unique per run

`femutils.get_temp_dir()` creates a **new** directory on every call (it does not cache
anything), and a FreeCAD start script may run twice.  Test fixtures therefore use a unique
name per run and an isolated directory (`tempfile.mkdtemp`), and they clean up after
themselves.  On Windows a directory that was just used is released with a delay - if a test
cannot delete its working directory, it takes a fresh name instead of failing.

## Test artefacts

The tests write their output next to themselves (`*_ausgabe.txt`, `szenario_bericht.md`,
`vergleich_varianten.md`).  They are ignored by git and can be deleted at any time.
