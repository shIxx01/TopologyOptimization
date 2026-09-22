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

### The same on Linux with the FreeCAD Flatpak (tested)

The Flatpak is the recommended way on Linux: it is the same FreeCAD on every distribution and
brings `ccx` and `gmsh` with it.  FreeCAD decides the name of its user directory itself (it is
version dependent), so it is asked instead of guessed:

```bash
flatpak install --user -y flathub org.freecad.FreeCAD        # release; beta repo: flathub-beta
DACHDIR="$(flatpak run --command=FreeCADCmd org.freecad.FreeCAD -c \
          'import FreeCAD; print(FreeCAD.getUserAppDataDir())' | tail -1)"
MOD="${DACHDIR%/}/Mod"
mkdir -p "$MOD"
rsync -a --delete --exclude '.git' /path/to/TopologyOptimization/ "$MOD/TopologyOptimization/"
find "$MOD/TopologyOptimization" -name "__pycache__" -type d -exec rm -rf {} +
flatpak run org.freecad.FreeCAD                              # start it
```

Everything headless runs through the console interpreter of the same Flatpak:

```bash
flatpak run --command=FreeCADCmd org.freecad.FreeCAD \
    "$MOD/TopologyOptimization/tests/headless_test.py"
```

Measured inside the Flatpak (FreeCAD 26.3): `sys.executable` is `/app/bin/FreeCADCmd`,
`sys.prefix` is `/usr` and Python lives in `/usr/bin/python3` with numpy and matplotlib - the
addon finds both `python3` and `ccx` itself (see D39 in `decisions.md`; `python_pfad()` must
never return the FreeCAD program, because `-u` means "user parameter file" to FreeCAD).

## Test 1 - headless (no GUI)

Covers the namespace import, object creation, persistence, the `.inp` readers (element sets,
shell thicknesses, section materials, element types), the search order for an existing input
file, the beso configuration, the radius functions, the log reader and the VTK/state readers.

```bash
"<FreeCAD>/bin/freecadcmd.exe" tests/headless_test.py
```

It prints one line per check (`OK ...`) and a summary.  It must **not** print
`The graph must be a DAG.`  Reference result: **152 checks, no failures**, exit code 0
(measured 22.09.2026 in the FreeCAD 26.3 Flatpak).  The two recorded logs the suite reads
(`tests/data/beso_beispiel.log` and `tests/data/lauf_beispiel.log`) are test **inputs** and
therefore live in the repository - `.gitignore` excludes `tests/data/*.log` for the output of a
run and re-includes these two with `!`.

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
and that the command creates the object in the active analysis.  Reference: **15 checks** - last
measured on the maintainer's Windows installation; the GUI suites need a graphical session and
were not re-run in the Linux/Flatpak environment yet.

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
Reference: **124 checks** (last measured on the maintainer's Windows installation; needs a
graphical session).

## Test 4 - scenario matrix and comparison with upstream beso

`tests/make_szenario_inp.py` writes three tiny CalculiX models with real loads (8 hexahedra,
4 shell triangles, the same without `*SHELL SECTION`) - `freecadcmd` cannot save documents on
Windows, and beso only needs the `.inp`.  `tests/szenario_test.py` runs 17 scenarios on them:
filter types (simple, casting, all seven morphology filters), ranges (automatic, robust,
manual), target masses, 2D shell and 3D solid, and the error case of a missing shell
thickness.

For the comparison against upstream, clone the original once:

```bash
git clone --depth 1 https://github.com/calculix/beso.git "$TEMP/beso-original"
# or point BESO_ORIGINAL at an existing clone
"<FreeCAD>/bin/freecadcmd.exe" tests/szenario_test.py

# Linux (Flatpak) - same script, the environment variable goes into the sandbox:
flatpak run --env=BESO_ORIGINAL=/path/to/beso-original --command=FreeCADCmd \
    org.freecad.FreeCAD "$MOD/TopologyOptimization/tests/szenario_test.py"
```

The script then computes every scenario a second time with the **unchanged** beso and reports
which scenarios differ.  Reference (measured 22.09.2026, FreeCAD 26.3 with numpy 2.4): 17 runs,
**13 of 17 scenarios identical**, and the four differences are exactly the intended fixes.  The
expected set is `BEKANNTE_ABWEICHUNGEN` in the script, and the check prints the expected **and**
the measured list:

| Scenario | bundled beso | unchanged beso |
|---|---|---|
| 3D simple auto / robust / casting / target mass 30 % | code 0, 8000 → 7000 | identical |
| all seven morphology filters | code 0, 8000 → 7000 | identical |
| range smaller than the element distance | code 1, clear message | code 0, computes on (division by zero) |
| 2D shell, simple and casting (`"auto"`) | code 0, 1000 → 750 | code 1, `AttributeError: numpy.linalg.linalg` |
| 2D without a shell thickness | code 1, names `domain_thickness` | code 1, only an `IndexError` (no mass either way, so the script does not count this as a deviation - the messages differ) |

The test fails if a scenario differs that is not in that set, so an unintended change in the
result is noticed.

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

## Test 6 - the bundled beso against upstream (documented changes)

Every difference between the bundled copy and upstream must carry a `TopoOpt:` comment - a
difference nobody marked is one nobody will find later.  This check needs no FreeCAD:

```bash
git clone --depth 1 https://github.com/calculix/beso.git /tmp/beso-original
python3 tests/vergleiche_beso_kopie.py          # or: <path> or BESO_ORIGINAL=<path>
```

It prints every difference per file (CRLF is not counted as a difference), names the hunks
without a marker and exits 1 if there is one.  Reference: 9 difference spots in three files
(`beso_filters.py` 5, `beso_lib.py` 2, `beso_main.py` 2) belonging to the six changes listed
in `freecad/TopoOpt/beso/CHANGES-TopoOpt.md`; `beso_fc_gui.py` is deliberately not bundled and
everything else is unchanged.  It runs on every push as its own job in
`.github/workflows/tests.yml`, so a change of upstream also shows up there.

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

## Three traps of the FreeCAD script interpreter (measured)

1. **`App.openDocument()` in a start script makes FreeCAD run the whole script a second
   time** (same process, milliseconds later).  A test that saves and reloads a document
   therefore runs twice - once with the document, once without - and results that depend on
   leftovers become flaky.  For a persistence check, read the saved file instead (open it as a
   zip archive and look at `Document.xml`).
2. **`sys.exit()` output is lost when stdout is redirected** AND the script may be re-run:
   `print(..., flush=True)` and `os._exit(code)` at the end are the safe way (see
   `tests/headless_test.py`).
3. **A script that stops with an exception leaves FreeCADCmd with exit code 0.**  Measured: a
   script that raises after two lines prints `Exception while processing file: ...` and the
   process still ends with status 0 - and because of trap 1 it runs a second time, so the output
   appears twice and looks like a finished run.  A test that trusts the exit code alone reports
   success for a run that never got to the end.  That is why `tests/headless_test.py` prints a
   summary line at the end and the CI checks **that line as well as** the exit code
   (`.github/workflows/tests.yml`).

## Test data must be unique per run

`femutils.get_temp_dir()` creates a **new** directory on every call (it does not cache
anything), and a FreeCAD start script may run twice.  Test fixtures therefore use a unique
name per run and an isolated directory (`tempfile.mkdtemp`), and they clean up after
themselves.  On Windows a directory that was just used is released with a delay - if a test
cannot delete its working directory, it takes a fresh name instead of failing.

## Test artefacts

The tests write their output next to themselves (`*_ausgabe.txt`, `szenario_bericht.md`,
`vergleich_varianten.md`).  They are ignored by git and can be deleted at any time.
