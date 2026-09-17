# SPDX-License-Identifier: LGPL-3.0-or-later
"""Document object of a topology optimization."""

import FreeCAD as App

from ..core.i18n import uebersetze
from ..core.params import (BASES, DEFAULT_FILTERS, FORMATS, MASS_CHANGE,
                           format_filters)

GROUP = "TopoOpt"


def ensure_properties(obj):
    """Add properties that are missing (new objects and objects from older files).

    addProperty() has no parameter for a default value - the value has to be set
    afterwards.
    """
    if not hasattr(obj, "AnalysisName"):
        # a plain string, NOT a PropertyLink: the analysis is a group that contains
        # this object, so a link back to it would make the dependency graph cyclic
        # ("The graph must be a DAG", "still touched after recompute")
        obj.addProperty("App::PropertyString", "AnalysisName", GROUP,
                        uebersetze("FEM analysis this optimization belongs to"))
    if not hasattr(obj, "Domains"):
        obj.addProperty("App::PropertyStringList", "Domains", GROUP,
                        uebersetze("Element sets and their role: "
                                   "<set>|<design|non_design|ignore>"))
    if not hasattr(obj, "WorkingDir"):
        obj.addProperty("App::PropertyString", "WorkingDir", GROUP,
                        uebersetze("Working directory of the optimization (no spaces)"))
        obj.setEditorMode("WorkingDir", 1)          # read only in the property editor
    if not hasattr(obj, "InpFile"):
        obj.addProperty("App::PropertyString", "InpFile", GROUP,
                        uebersetze("CalculiX input file the optimization is based on"))
        obj.setEditorMode("InpFile", 1)

    # --- parameters of the optimization (step 2) ---------------------------
    # The default values are the ones beso itself ships in beso_conf.py, the
    # values the text of every property explains.
    if not hasattr(obj, "MassGoalRatio"):
        obj.addProperty("App::PropertyFloat", "MassGoalRatio", GROUP,
                        uebersetze("Target mass as a fraction of the full mass "
                                   "(0.6 = 60 % of the material stays)"))
        obj.MassGoalRatio = 0.6
    if not hasattr(obj, "OptimizationBase"):
        obj.addProperty("App::PropertyEnumeration", "OptimizationBase", GROUP,
                        uebersetze("What is optimized: stiffness (usual), buckling, "
                                   "heat or failure_index"))
        obj.OptimizationBase = list(BASES)
        obj.OptimizationBase = "stiffness"
    if not hasattr(obj, "IterationsLimit"):
        obj.addProperty("App::PropertyString", "IterationsLimit", GROUP,
                        uebersetze("Maximum number of iterations or 'auto'"))
        obj.IterationsLimit = "auto"
    if not hasattr(obj, "Tolerance"):
        obj.addProperty("App::PropertyFloat", "Tolerance", GROUP,
                        uebersetze("Stop when the mean stress changes less than this "
                                   "value in the last 5 iterations"))
        obj.Tolerance = 1e-3
    if not hasattr(obj, "CpuCores"):
        obj.addProperty("App::PropertyInteger", "CpuCores", GROUP,
                        uebersetze("Processor cores for the solver (0 = all)"))
        obj.CpuCores = 0
    if not hasattr(obj, "MassChange"):
        obj.addProperty("App::PropertyEnumeration", "MassChange", GROUP,
                        uebersetze("How much material is added or removed per iteration"))
        obj.MassChange = list(MASS_CHANGE)
        obj.MassChange = "normal"
    if not hasattr(obj, "Filters"):
        obj.addProperty("App::PropertyString", "Filters", GROUP,
                        uebersetze("Sensitivity filters, Python list: "
                                   "[[type, range, domain, ...], ...]"))
        obj.Filters = format_filters(DEFAULT_FILTERS)
    if not hasattr(obj, "SaveIterations"):
        obj.addProperty("App::PropertyInteger", "SaveIterations", GROUP,
                        uebersetze("Save intermediate results every n-th iteration "
                                   "(0 = only the final result)"))
        # 10 and not the beso default of 1: every saved iteration of a fine mesh can
        # need 100 MB and more, and the final result is what the user wants
        obj.SaveIterations = 10
    if not hasattr(obj, "ResultFormat"):
        obj.addProperty("App::PropertyEnumeration", "ResultFormat", GROUP,
                        uebersetze("File format of the resulting meshes"))
        obj.ResultFormat = list(FORMATS)
        obj.ResultFormat = "inp vtk"
    if not hasattr(obj, "RobusterRadius"):
        # result of the robust filter radius (beso needs a value, not "robust")
        obj.addProperty("App::PropertyFloat", "RobusterRadius", GROUP,
                        uebersetze("Calculated robust filter radius in mm (0 = not calculated)"))
        obj.setEditorMode("RobusterRadius", 1)      # read only in the property editor
    if not hasattr(obj, "MittlereGroesse"):
        obj.addProperty("App::PropertyFloat", "MittlereGroesse", GROUP,
                        uebersetze("Mean element size of the design space in mm"))
        obj.setEditorMode("MittlereGroesse", 1)


def read_domains(obj):
    """{"elset": role} as stored in the object."""
    from ..core.domains import parse_domains
    return parse_domains(getattr(obj, "Domains", []))


class TopologyObject:
    """FeaturePython proxy - keeps the data of the optimization."""

    def __init__(self, obj):
        obj.Proxy = self

    def onDocumentRestored(self, obj):
        # a file written by an older version may miss properties
        ensure_properties(obj)

    def execute(self, obj):
        # nothing to compute yet - the optimization runs in beso (external process)
        pass

    def dumps(self):
        return None

    def loads(self, state):
        return None


def find_analysis(obj):
    """The FEM analysis this object belongs to, or None.

    First choice is the group in the tree, the stored name is the fallback for the
    case that the object was moved out of the analysis by the user.
    """
    for parent in obj.InList:
        if parent.TypeId.startswith("Fem::FemAnalysis"):
            return parent
    name = getattr(obj, "AnalysisName", "")
    if name:
        doc = obj.Document
        analysis = doc.getObject(name) if doc else None
        if analysis is not None and analysis.TypeId.startswith("Fem::FemAnalysis"):
            return analysis
    return None


def create_topology_object(doc, analysis, name="TopologieOptimierung"):
    """Create the object and put it into the (active) analysis container."""
    obj = doc.addObject("App::FeaturePython", name)
    TopologyObject(obj)
    if obj.ViewObject is not None:
        from .topology_vp import TopologyViewProvider
        TopologyViewProvider(obj.ViewObject)
    ensure_properties(obj)
    obj.Label = "Topologie-Optimierung"
    obj.AnalysisName = analysis.Name
    analysis.addObject(obj)
    return obj
