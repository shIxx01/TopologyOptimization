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
    "Analysis":
        "Analyse",
    "Mesh":
        "Netz",
    "Solver":
        "Solver",
    "not available":
        "nicht vorhanden",
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
    "Write input file (.inp)":
        "Eingabedatei (.inp) erzeugen",
    "Rewrite input file (.inp)":
        "Eingabedatei (.inp) neu erzeugen",
    "Open working directory":
        "Arbeitsverzeichnis \u00f6ffnen",
    "No .inp file yet.":
        "Keine .inp vorhanden.",
    "%d element set(s), element type %s.":
        "%d Element-Set(s), Elementtyp %s.",
    "Source: %s":
        "Quelle: %s",
    "input file written in %.1f s":
        "Eingabedatei in %.1f s erzeugt",
    "Possible as soon as the analysis has a mesh and a solver.":
        "Erst m\u00f6glich, wenn die Analyse ein Netz und einen Solver hat.",
    "Show this directory in the file manager: %s":
        "Diesen Ordner im Dateimanager anzeigen: %s",
    "There is no working directory yet.":
        "Es gibt noch kein Arbeitsverzeichnis.",
    "The directory could not be opened (%s): %s":
        "Der Ordner konnte nicht ge\u00f6ffnet werden (%s): %s",
    "Write the .inp from the FEM model (mesh, material, boundary conditions).\n"
    "Takes a few seconds for fine meshes, FreeCAD is blocked while it runs.":
        "Schreibt die .inp aus dem FEM-Modell neu (Netz, Material, Randbedingungen).\n"
        "Dauert bei feinen Netzen einige Sekunden, FreeCAD ist so lange blockiert.",
    "no file yet":
        "noch keine Datei",
    "Target mass":
        "Zielmasse",
    "How much of the material stays: 40 % means the optimized part keeps about 40 % of its mass.":
        "Wie viel vom Material \u00fcbrig bleibt: 40 % hei\u00dft, das optimierte Bauteil beh\u00e4lt "
        "etwa 40 % seiner Masse.",
    "Optimization":
        "Optimierung",
    "What is optimized":
        "Was wird optimiert",
    "Stiffness - the part becomes as stiff as possible (usual)":
        "Steifigkeit - das Bauteil wird so steif wie m\u00f6glich (\u00fcblich)",
    "Buckling - the part becomes resistant against buckling":
        "Knickung - das Bauteil wird widerstandsf\u00e4hig gegen Knicken",
    "Heat conduction - the heat flows as well as possible":
        "W\u00e4rmeleitung - die W\u00e4rme flie\u00dft so gut wie m\u00f6glich",
    "Failure index - stresses stay below a limit":
        "Versagenskriterium - Spannungen bleiben unter einer Grenze",
    "Maximum iterations":
        "Maximale Iterationen",
    "'auto' lets beso estimate the number of iterations, a number stops after it.":
        "\u201eauto\u201c l\u00e4sst beso die Anzahl der Iterationen sch\u00e4tzen, eine Zahl stoppt "
        "danach.",
    "Stop tolerance":
        "Abbruch-Toleranz",
    "The optimization stops when the mean stress changes less than this value in the last 5 iterations (beso: 0.001).":
        "Die Optimierung endet, wenn sich die mittlere Spannung in den letzten 5 Iterationen um "
        "weniger als dieser Wert \u00e4ndert (beso: 0,001).",
    "Material change per iteration":
        "Material\u00e4nderung pro Iteration",
    "gentle (1 % / 2 % per iteration)":
        "sanft (1 % / 2 % pro Iteration)",
    "normal (1.5 % / 3 % per iteration)":
        "normal (1,5 % / 3 % pro Iteration)",
    "fast (3 % / 6 % per iteration)":
        "schnell (3 % / 6 % pro Iteration)",
    "How much material beso adds or removes per iteration.":
        "Wie viel Material beso pro Iteration zuf\u00fcgt oder wegnimmt.",
    "Processor cores":
        "Prozessorkerne",
    "Cores for the solver; 0 uses all of them.":
        "Kerne f\u00fcr den Solver; 0 nutzt alle.",
    "Result files":
        "Ergebnisdateien",
    "Save every n-th iteration":
        "Jede n-te Iteration speichern",
    "0 saves only the final result. Every saved iteration needs disk space (a fine mesh can need 100 MB and more).":
        "0 speichert nur das Endergebnis. Jede gespeicherte Iteration braucht Platz auf der "
        "Festplatte (ein feines Netz kann 100 MB und mehr brauchen).",
    "Format of the result meshes":
        "Format der Ergebnis-Netze",
    "Prepare the analysis case: CalculiX input file and element sets":
        "Analysefall vorbereiten: CalculiX-Eingabedatei und Element-Sets",
    "Set target mass, filters and iteration limits":
        "Zielmasse, Filter und Iterationsgrenzen einstellen",
    "Run the optimization with CalculiX":
        "Die Optimierung mit CalculiX rechnen",
    "Look at the result and compare it with the FEM result":
        "Ergebnis ansehen und mit dem FEM-Ergebnis vergleichen",
    "Close":
        "Schliessen",
    "Working directory of the solver":
        "Arbeitsordner des Solvers",
    "FEM working directory of the solver":
        "FEM-Arbeitsordner des Solvers",
    "another FEM working directory":
        "ein anderer FEM-Arbeitsordner",
    "own working directory (old version)":
        "eigener Arbeitsordner (alte Fassung)",
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
