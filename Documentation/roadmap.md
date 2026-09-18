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
* **tests** - headless, assistant (GUI) and a scenario matrix with 16 runs, including a
  comparison against the unchanged beso from GitHub.
* **documentation** - architecture, decisions with their measurements, development and test
  recipes, README.

## Next

* **publish** - gather feedback in the FreeCAD forum, then ask for inclusion in the Addon
  Index (an addon needs evidence of user testing before it is accepted).
* **observe** - collect reports about models that fail or look wrong and fix them with a
  measurement each time.

## Ideas, not scheduled

* presets for common parameter sets,
* translate the UI to further languages (the German dictionary is in `core/i18n.py`),
* an export of the result as a report (mass and failure-index curve as a table).
