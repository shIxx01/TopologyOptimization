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
    "CalculiX input file (.inp)":
        "CalculiX-Eingabedatei (.inp)",
    "Domains - roles of the elements":
        "Domains - Rollen der Elemente",
    "all":
        "alle",
    "Cores for the solver; 'all' uses every core of the computer.":
        "Kerne f\u00fcr den Solver; \u201ealle\u201c nutzt jeden Kern des Rechners.",
    "Domains - which elements are optimized?":
        "Domains - welche Elemente werden optimiert?",
    "The optimizer writes its iteration files next to this file.":
        "Der Optimierer schreibt seine Iterationsdateien neben diese Datei.",
    "Element set":
        "Element-Set",
    "Role":
        "Rolle",
    "σ (MPa)":
        "σ (MPa)",
    "Allowable stress (von Mises) in MPa - leave empty to run without a failure index. The model needs real loads for it.":
        "Zulässige Spannung (von Mises) in MPa – leer lassen heißt: ohne Auslastungs-Index. Das Modell braucht dafür echte Lasten.",
    "TopoOpt: allowable stress taken from the material (MPa): %s\n":
        "TopoOpt: zulässige Spannung aus dem Material übernommen (MPa): %s\n",
    "TopoOpt: allowable stress for '%s' is %s MPa - the run reports a failure index.\n":
        "TopoOpt: zulässige Spannung für '%s' ist %s MPa – der Lauf gibt einen Auslastungs-Index aus.\n",
    "TopoOpt: no allowable stress for '%s' - the run works without a failure index.\n":
        "TopoOpt: keine zulässige Spannung für '%s' – der Lauf arbeitet ohne Auslastungs-Index.\n",
    "Allowable stress per element set (MPa): <set>|<value> - empty means no failure index":
        "Zulässige Spannung je Element-Set (MPa): <Set>|<Wert> – leer heißt: kein Auslastungs-Index",
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
    "How much of the material stays: 60 % means the optimized part keeps about 60 % of its mass.":
        "Wie viel vom Material \u00fcbrig bleibt: 60 % hei\u00dft, das optimierte Bauteil beh\u00e4lt "
        "etwa 60 % seiner Masse.",
    "Add filter":
        "Filter hinzuf\u00fcgen",
    "Remove this filter":
        "Diesen Filter entfernen",
    "beso applies the filters one after the other, for example first 'casting', then 'simple'.":
        "beso wendet die Filter nacheinander an, zum Beispiel erst \u201ecasting\u201c, dann "
        "\u201esimple\u201c.",
    "simple - smooths, keeps the part round":
        "simple - gl\u00e4ttet, h\u00e4lt das Bauteil rund",
    "erode - takes the smallest value in the radius":
        "erode - nimmt den kleinsten Wert im Radius",
    "dilate - takes the largest value in the radius":
        "dilate - nimmt den gr\u00f6\u00dften Wert im Radius",
    "open - removes small elements (erode, then dilate)":
        "open - entfernt kleine Elemente (erst erode, dann dilate)",
    "close - closes small holes (dilate, then erode)":
        "close - schlie\u00dft kleine L\u00f6cher (erst dilate, dann erode)",
    "open-close - open, then close":
        "open-close - erst open, dann close",
    "close-open - close, then open":
        "close-open - erst close, dann open",
    "combine - mean of erode and dilate":
        "combine - Mittel aus erode und dilate",
    "Optimization":
        "Optimierung",
    "Sensitivity filter (smoothing)":
        "Sensitivit\u00e4tsfilter (Gl\u00e4ttung)",
    "Filter %d":
        "Filter %d",
    "no filter":
        "kein Filter",
    "simple - smooth, no direction":
        "simple - gl\u00e4ttet, ohne Richtung",
    "casting - demouldable in one direction":
        "casting - in eine Richtung entformbar",
    "automatic":
        "automatisch",
    "robust (recommended)":
        "robust (empfohlen)",
    "automatic (as in beso)":
        "automatisch (wie in beso)",
    "'robust' asks beso for the smallest radius at which every element still has a neighbour (checked once, then the value is used). 'automatic (as in beso)' leaves beso's own value of 2 x mean element size, 'manual' uses your millimetres.":
        "\u201erobust\u201c fragt beso nach dem kleinsten Radius, bei dem jedes Element noch einen "
        "Nachbarn hat (einmal gepr\u00fcft, dann wird der Wert verwendet). \u201eautomatisch (wie in "
        "beso)\u201c \u00fcbernimmt besos eigenen Wert von 2 x mittlerer Elementgr\u00f6\u00dfe, "
        "\u201emanuell\u201c nutzt deine Millimeter.",
    "Checking the robust filter radius with beso ... this can take a few seconds.":
        "Der robuste Filterradius wird mit beso gepr\u00fcft ... das kann ein paar Sekunden dauern.",
    "Robust filter radius: %.3f mm = %.1f x mean element size, %d element(s) without a neighbour.":
        "Robuster Filterradius: %.3f mm = %.1f x mittlere Elementgr\u00f6\u00dfe, %d Element(e) ohne "
        "Nachbarn.",
    "The robust radius needs an input file and a design space - check step 1.":
        "F\u00fcr den robusten Radius werden eine Eingabedatei und ein Design-Raum gebraucht - "
        "siehe Schritt 1.",
    "not calculated":
        "nicht berechnet",
    "check":
        "pr\u00fcfen",
    "calculate":
        "berechnen",
    "robust: smallest radius at which every element still has a neighbour":
        "robust: kleinster Radius, bei dem jedes Element noch einen Nachbarn hat",
    "automatic: 2 x mean element size (as in beso)":
        "automatisch: 2 x mittlere Elementgr\u00f6\u00dfe (wie in beso)",
    "manual: your own value in millimetres":
        "manuell: eigener Wert in Millimetern",
    "Start optimization":
        "Optimierung starten",
    "Show history":
        "Verlauf anzeigen",
    "Open at start":
        "beim Start öffnen",
    "Open the history window when the run starts":
        "Das Verlaufsfenster beim Start des Laufs öffnen",
    "Opens the window with the four charts (mass, stress, overloaded elements, energy)":
        "Öffnet das Fenster mit den vier Diagrammen (Masse, Auslastung, überlastete Elemente, Energiedichte)",
    "0 % = the whole part, 100 % = the target mass":
        "0 % = das volle Bauteil, 100 % = die Zielmasse",
    "The plot module of FreeCAD is not available - the charts need 'Plot' in FreeCAD's module folder.":
        "Das Plot-Modul von FreeCAD ist nicht verfügbar - die Diagramme brauchen 'Plot' im Modulordner von FreeCAD.",
    "Cancel":
        "Abbrechen",
    "Mass per iteration":
        "Masse je Iteration",
    "Details":
        "Details",
    "Writes the beso configuration and starts beso as its own process - FreeCAD stays usable.":
        "Schreibt die beso-Konfiguration und startet beso als eigenen Prozess - FreeCAD bleibt "
        "bedienbar.",
    "Stop the run (CalculiX is stopped as well)":
        "Lauf stoppen (CalculiX wird mit beendet)",
    "Run started (%s) ...":
        "Lauf gestartet (%s) ...",
    "Run cancelled.":
        "Lauf abgebrochen.",
    "Iteration %d":
        "Iteration %d",
    "mass %.0f, target %.0f":
        "Masse %.0f, Ziel %.0f",
    "mass %.0f":
        "Masse %.0f",
    "CalculiX is running ...":
        "CalculiX rechnet ...",
    "Optimization finished after %d iteration(s).":
        "Optimierung nach %d Iteration(en) fertig.",
    "The run ended (code %s) - open the details.":
        "Der Lauf endete (Code %s) - Details \u00f6ffnen.",
    "The run could not be started: %s":
        "Der Lauf konnte nicht gestartet werden: %s",
    "There is no input file yet - see step 1.":
        "Es gibt noch keine Eingabedatei - siehe Schritt 1.",
    "No design space is marked - see step 1.":
        "Es ist kein Design-Raum markiert - siehe Schritt 1.",
    "The last lines of the run - the whole log file belongs to step 4.":
        "Die letzten Zeilen des Laufs - die vollst\u00e4ndige Logdatei geh\u00f6rt zu Schritt 4.",
    "For 'robust' press the arrow button once: beso then checks the radius and the value appears next to it.":
        "Bei \u201erobust\u201c einmal den Pfeil-Knopf dr\u00fccken: beso pr\u00fcft dann den Radius, "
        "der Wert erscheint daneben.",
    "Check the robust filter radius now":
        "Robusten Filterradius jetzt pr\u00fcfen",
    "not checked yet - use the arrow button":
        "noch nicht gepr\u00fcft - Knopf mit dem Pfeil nutzen",
    "%.3f mm = %.1f x mean size, %d without neighbour":
        "%.3f mm = %.1f x mittlere Gr\u00f6\u00dfe, %d ohne Nachbarn",
    "%.3f mm (saved value from the last check)":
        "%.3f mm (gemerkter Wert der letzten Pr\u00fcfung)",
    "manual":
        "manuell",
    "The filter smooths the result. 'simple' averages over all elements in the radius, 'casting' also keeps the part demouldable in one direction.":
        "Der Filter gl\u00e4ttet das Ergebnis. \u201esimple\u201c mittelt \u00fcber alle Elemente im "
        "Radius, \u201ecasting\u201c h\u00e4lt das Bauteil zus\u00e4tzlich in eine Richtung entformbar.",
    "'automatic' lets beso choose the radius from the element size, 'manual' uses the value in millimetres.":
        "\u201eautomatisch\u201c l\u00e4sst beso den Radius aus der Elementgr\u00f6\u00dfe w\u00e4hlen, "
        "\u201emanuell\u201c nutzt den Wert in Millimetern.",
    "Radius in millimetres - a larger radius gives thicker struts and fewer fine details. The filter needs a radius in which every element has a neighbour.":
        "Radius in Millimetern - ein gr\u00f6\u00dferer Radius ergibt dickere Stege und weniger feine "
        "Details. Der Filter braucht einen Radius, in dem jedes Element einen Nachbarn hat.",
    "Only for the casting filter: the direction in which the part has to be demouldable.":
        "Nur f\u00fcr den casting-Filter: die Richtung, in der das Bauteil entformbar sein muss.",
    "The filter averages the sensitivities over the elements inside the radius and keeps the result smooth. 'automatic' uses beso's own value (2 x mean element size).":
        "Der Filter mittelt die Sensitivit\u00e4ten \u00fcber die Elemente im Radius und h\u00e4lt das "
        "Ergebnis glatt. \u201eautomatisch\u201c nutzt besos eigenen Wert (2 x mittlere "
        "Elementgr\u00f6\u00dfe).",
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
