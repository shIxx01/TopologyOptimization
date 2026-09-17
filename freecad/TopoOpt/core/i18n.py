# SPDX-License-Identifier: LGPL-3.0-or-later
"""UI texts: English source, German translation when FreeCAD runs in German.

The usual Qt workflow would be a `.ts` file compiled with `lrelease` into a
`.qm`.  FreeCAD 26.3 ships neither `lrelease` nor `lupdate`, so that workflow is
not available for the addon.  Instead the texts in the code are English - the
fallback for every language - and a dictionary translates them to German.  If
the addon is ever translated by the community, this module is the single place
to replace with the `.ts`/`.qm` mechanism.
"""

import FreeCAD as App

DEUTSCH = {
    # workbench and command
    "Topology optimization with CalculiX (beso)":
        "Topologieoptimierung mit CalculiX (beso)",
    "Topology Optimization":
        "Topologie-Optimierung",
    "Create a topology optimization in the active FEM analysis":
        "Neue Topologie-Optimierung in der aktiven FEM-Analyse anlegen",
    "No active analysis":
        "Keine aktive Analyse",
    "Please activate a FEM analysis in the tree first (double click, or right click > "
    "Activate analysis).\n\nThe topology optimization is added to that analysis.":
        "Bitte zuerst eine FEM-Analyse im Modellbaum aktivieren (Doppelklick oder "
        "Rechtsklick > Analyse aktivieren).\n\nDie Topologie-Optimierung wird dieser "
        "Analyse hinzugefuegt.",
    "TopoOpt: '%s' was added to the analysis '%s'.\n":
        "TopoOpt: '%s' wurde der Analyse '%s' hinzugefuegt.\n",

    # dialog
    "Analysis: %s   |   Mesh: %s":
        "Analyse: %s   |   Netz: %s",
    "Initialize":
        "Initialisieren",
    "Parameters":
        "Parameter",
    "Run":
        "Lauf",
    "Results":
        "Ergebnisse",
    "This step is not built yet.":
        "Dieser Schritt ist noch nicht eingebaut.",
    "Prepare the analysis case: CalculiX input file and element sets":
        "Analysefall vorbereiten: CalculiX-Eingabedatei und Element-Sets",
    "CalculiX input file (basis of the optimization)":
        "CalculiX-Eingabedatei (Grundlage der Optimierung)",
    "Domains - which elements are optimized?":
        "Domains - welche Elemente werden optimiert?",
    "The optimizer writes its iteration files next to this file.":
        "Der Optimierer schreibt seine Iterationsdateien neben diese Datei.",
    "Element set":
        "Element-Set",
    "Role":
        "Rolle",
    "Elements":
        "Elemente",
    "Design space (optimized)":
        "Design-Raum (wird optimiert)",
    "Non-design space (kept)":
        "Nicht-Design-Raum (bleibt stehen)",
    "ignore":
        "ignorieren",
    "Write input file":
        "Eingabedatei erzeugen",
    "Rewrite input file":
        "Eingabedatei neu erzeugen",
    "Write the .inp from the FEM model (mesh, material, boundary conditions).\n"
    "Takes a few seconds for fine meshes, FreeCAD is blocked while it runs.":
        "Schreibt die .inp aus dem FEM-Modell neu (Netz, Material, Randbedingungen).\n"
        "Dauert bei feinen Netzen einige Sekunden, FreeCAD ist so lange blockiert.",
    "no file yet":
        "noch keine Datei",
    "Close":
        "Schliessen",
    "Working directory of the solver":
        "Arbeitsordner des Solvers",
    "FEM working directory of FreeCAD":
        "FEM-Arbeitsordner von FreeCAD",
    "Working directory of TopoOpt":
        "Arbeitsordner von TopoOpt",
    "written":
        "neu erzeugt",

    # status messages
    "Looking for the analysis, the mesh and an existing CalculiX input file ...":
        "Suche Analyse, Netz und vorhandene CalculiX-Eingabedatei ...",
    "No FEM analysis found. Please put the object into an analysis (active analysis) "
    "or restore the analysis.":
        "Keine FEM-Analyse gefunden. Bitte das Objekt in eine Analyse legen (aktive "
        "Analyse) oder die Analyse wiederherstellen.",
    "The analysis needs a mesh and a solver (FEM workbench: create mesh and solver).":
        "Die Analyse braucht ein Netz und einen Solver (FEM-Arbeitsbereich: Netz und "
        "Solver anlegen).",
    "There is no CalculiX input file for the analysis '%s' yet. Click 'Write input file' "
    "so that the element sets can be read.":
        "Es gibt noch keine CalculiX-Eingabedatei fuer die Analyse '%s'. Klick auf "
        "'Eingabedatei erzeugen', damit die Element-Sets gelesen werden koennen.",
    "Input file used (source: %s). %d element set(s), element type %s. The design space "
    "is optimized, the non-design space is kept.":
        "Eingabedatei verwendet (Quelle: %s). %d Element-Set(s), Elementtyp %s. Der "
        "Design-Raum wird optimiert, der Nicht-Design-Raum bleibt stehen.",
    "Input file written in %.1f s. %d element set(s), element type %s.":
        "Eingabedatei in %.1f s erzeugt. %d Element-Set(s), Elementtyp %s.",
    "Writing the CalculiX input file from the FEM model ... FreeCAD is blocked while "
    "it runs.":
        "Erzeuge die CalculiX-Eingabedatei aus dem FEM-Modell ... FreeCAD ist so lange "
        "blockiert.",
    "The input file could not be written: %s":
        "Die Eingabedatei konnte nicht erzeugt werden: %s",
    "Without analysis, mesh and solver no input file can be written.":
        "Ohne Analyse, Netz und Solver kann keine Eingabedatei erzeugt werden.",
    "TopoOpt: '%s' is now %s.\n":
        "TopoOpt: '%s' ist jetzt %s.\n",

    # property descriptions
    "FEM analysis this optimization belongs to":
        "FEM-Analyse, zu der diese Optimierung gehoert",
    "Element sets and their role: <set>|<design|non_design|ignore>":
        "Element-Sets und ihre Rolle: <Set>|<design|non_design|ignore>",
    "Working directory of the optimization (no spaces)":
        "Arbeitsordner der Optimierung (ohne Leerzeichen)",
    "CalculiX input file the optimization is based on":
        "CalculiX-Eingabedatei, auf der die Optimierung aufbaut",
}


def sprache():
    """Language FreeCAD uses, as a two letter code ('de', 'en', ...) or ''."""
    try:
        einstellung = App.ParamGet(
            "User parameter:BaseApp/Preferences/General").GetString("Language", "")
    except Exception:
        einstellung = ""
    if not einstellung:                      # empty = follow the system language
        try:
            from PySide import QtCore
            einstellung = QtCore.QLocale.system().name()
        except Exception:
            einstellung = ""
    return einstellung.split("_")[0].split("-")[0].lower()


def uebersetze(text):
    """German text when FreeCAD runs in German, otherwise the English source."""
    if sprache() == "de":
        return DEUTSCH.get(text, text)
    return text
