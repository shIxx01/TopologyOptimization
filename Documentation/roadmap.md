# Roadmap

## Done

* **workbench and object** - modern addon layout (`package.xml`, licenses, icons), workbench
  with toolbar and menu, command that creates the optimization object inside the *active* FEM
  analysis and explains itself when there is none.
* **step "Initialize"** - finds the CalculiX input file (solver directory, FreeCAD's
  `fcfem_*` working directories, own working directory) and reuses it instead of writing a
  second one; writes it on a click only.  Lists the element sets and stores their role
  (design space / non-design space / ignore) in the object.
* **step "Parameters"** - mass goal, optimization base (`stiffness`, `failure_index`, `heat`),
  filter type and range, tolerance, number of saved iterations, mass change, result format,
  allowable stress per element set.  The robust filter range and the average element size are
  computed on request, shell thicknesses come from the input file.
* **step "Calculation"** - writes the beso configuration, runs beso in a separate process with
  a progress bar, a stop button and a history window, loads the iterations (VTK player) and
  the result mesh (`*_state1.inp`) into the document.
* **tests** - headless, assistant (GUI) and a scenario matrix with 17 runs, including a
  comparison against the unchanged beso from GitHub, plus a check that every difference of the
  bundled beso is documented.  Headless test and that check run automatically on every push.
* **documentation** - architecture, decisions with their measurements, development and test
  recipes, README.

## Next

* **publish** - gather feedback in the FreeCAD forum, then ask for inclusion in the Addon
  Index (an addon needs evidence of user testing before it is accepted).
* **offer the numpy 2 fix upstream** - `beso_lib.py` computed a triangle area with
  `np.linalg.linalg.norm`, which numpy 2 removed; every 2D (shell) model stops there.  The
  bundled copy is fixed, upstream is not (see D40).  A one word pull request.
* **observe** - collect reports about models that fail or look wrong and fix them with a
  measurement each time.

## Ideas, not scheduled

* presets for common parameter sets,
* translate the UI to further languages (the German dictionary is in `core/i18n.py`),
* an export of the result as a report (mass and failure-index curve as a table),
* **split `gui/assistant.py`** - it has grown to 1649 lines.  The three steps are already
  separate methods, but the file mixes them with the widgets.  Deferred on purpose: it is a
  mechanical move without a GUI test that covers it in CI, so it is done when there is a
  reason to touch the file anyway, not for its own sake.
* **English identifiers in `core/` and `gui/`** - the texts are English (D7), but many
  function names are German (`_lauf_starten`, `_zeige_schritt`, ...).  Renaming all of them is
  a large diff with no behaviour change; better: new functions English, rename the rest
  step by step during other work.
* **beso as a sub module with a patch file** instead of a copy - then drift between the fork
  and the copy is visible by itself.  Until then `tests/vergleiche_beso_kopie.py` reports it.
