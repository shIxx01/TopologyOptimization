# Roadmap

Steps are done one at a time, each one tested before the next starts.

## Done

* **Step 0 - workbench skeleton**: modern addon layout, `package.xml`, licenses, README.
* **Step 1 - object in the active analysis**: workbench with toolbar and menu, command that
  creates the optimization object inside the *active* FEM analysis (with a hint when there
  is none), icon, persistence of the object, headless and GUI tests.

## Next

* **Step 2 - the assistant**: step 1 (design/non-design domains) is built: the element
  sets are read out of the CalculiX `.inp`, collector sets (`Eall`, `Evolumes`) are hidden,
  the role per set is stored in the document object and applied immediately.
  Still open: step 2 = parameters (mass goal, optimization base, filter range, tolerance),
  step 3 = run, step 4 = results. Reference behaviour exists in the author's experimental
  workbench; the analysis choice step is dropped (see `decisions.md`).
* **Step 3 - running beso**: ship a copy of the reviewed beso fork, write `beso_conf.py`,
  create the `.inp` with FreeCAD tools, run beso in a separate process with live progress and
  a stop button, import the result mesh into the document.
* **Step 4 - result display**: show the iteration states (VTK player) and the mass /
  failure-index curves; provide "open working directory" and "clean up" helpers.
* **Step 5 - publish**: push to GitHub, document the custom-repository installation, gather
  user feedback in the FreeCAD forum, then request inclusion in the Addon Index.

## Ideas, not scheduled

* presets for common settings,
* filter range assistant ("auto robust": enlarge the radius until every element of the design
  domain has a neighbour),
* translations (German texts are already wrapped in `translate`).
