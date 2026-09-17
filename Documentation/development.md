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

Covers the namespace import, object creation and persistence.

```bash
"<FreeCAD>/bin/freecadcmd.exe" test_headless.py
```

What it must print: the module path, the object with `AnalysisName`, `find_analysis()`
finding the analysis both via the parent group and via the name after removing it from the
group, and a reload from a saved file with the proxy intact. It must **not** print
`The graph must be a DAG.`

## Test 2 - GUI

The GUI parts (workbench registration, toolbar, menu, icons, the command with and without
an active analysis) need a GUI session.

**Important:** GUI FreeCAD writes nothing to stdout - the test script has to write its
result into a **file**, and the call is started in the background:

```bash
rm -f gui_test_ausgabe.txt
("<FreeCAD>/bin/freecad.exe" "C:/path/gui_test.py" >/dev/null 2>&1 &)
for i in $(seq 1 40); do sleep 2; [ -f gui_test_ausgabe.txt ] && break; done
cat gui_test_ausgabe.txt
```

The script checks:

* `Gui.listWorkbenches()` contains `TopoOptWorkbench` (filter by the exact name - another,
  older workbench with a similar name may be installed),
* `Gui.activateWorkbench(...)` + `Gui.updateGui()`, then the toolbar `TopoOpt` and the menu
  `TopoOpt` exist in the Qt main window,
* the icon files exist (`os.path.isfile`),
* `active_analysis()` returns `None` without an active analysis and the analysis with one,
* `command.Activated()` creates the object and it appears in `analysis.Group`.

## Debugging notes

* `App.Console.PrintMessage/PrintError` in the addon code; `init_gui.py` catches all
  exceptions and prints them, so a broken addon never blocks the FreeCAD start.
* If a change seems to have no effect: check the copy in `Mod/`, not the source folder, and
  delete `__pycache__` (Python may use a stale bytecode cache).
* `FemGui` is only available with a GUI; in headless tests `getActiveAnalysis()` cannot be
  used - test the pure functions instead.
* Deleting an analysis keeps its children (they are only removed from the group), so a
  test document can be cleaned up without losing the optimization object.
