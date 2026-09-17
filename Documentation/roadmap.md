# Roadmap

Steps are done one at a time, each one tested before the next starts.

## Done

* **Step 0 - workbench skeleton**: modern addon layout, `package.xml`, licenses, README.
* **Step 1 - object in the active analysis**: workbench with toolbar and menu, command that
  creates the optimization object inside the *active* FEM analysis (with a hint when there
  is none), icon, persistence of the object, headless and GUI tests.
* **Step 2 (first part) - step "Initialize"**: the dialog looks for an existing CalculiX
  input file (solver panel, FreeCAD's `fcfem_*` directories, own working directory), reuses
  it instead of writing a second one, and offers a button to write it - never silently.
  Below that the element sets of the analysis are listed and their role is chosen (design /
  non-design / ignore), stored in the document object right away.  UI texts are English with
  a German translation when FreeCAD runs in German.

## Next

* **Step 2 (second part) - step "Parameters"**: mass goal, optimization base (`stiffness`,
  `failure_index`, `heat`), filter type and range, tolerance, number of saved iterations -
  as properties of the document object, with tooltips that name concrete numbers.
* **Step 3 - step "Run"**: ship a copy of the reviewed beso fork, write `beso_conf.py`, run
  beso in a separate process with live progress and a stop button.
* **Step 4 - step "Results"**: show the iteration states (VTK player) and the mass /
  failure-index curves; provide "open working directory" and "clean up" helpers.
* **Step 5 - publish**: document the custom-repository installation, gather user feedback in
  the FreeCAD forum, then request inclusion in the Addon Index.

## Ideas, not scheduled

* presets for common settings,
* filter range assistant ("auto robust": enlarge the radius until every element of the design
  domain has a neighbour),
* translations (German texts are already wrapped in `translate`).
