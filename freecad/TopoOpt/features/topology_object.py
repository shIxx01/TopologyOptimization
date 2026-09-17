# SPDX-License-Identifier: LGPL-3.0-or-later
"""Document object of a topology optimization."""

import FreeCAD as App

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
                        "Name of the FEM analysis this optimization belongs to")
    if not hasattr(obj, "Domains"):
        obj.addProperty("App::PropertyStringList", "Domains", GROUP,
                        "Element sets and their role: <set>|<design|non_design|ignore>")
    if not hasattr(obj, "WorkingDir"):
        obj.addProperty("App::PropertyString", "WorkingDir", GROUP,
                        "Working directory of the optimization (no spaces)")
        obj.setEditorMode("WorkingDir", 1)          # read only in the property editor
    if not hasattr(obj, "InpFile"):
        obj.addProperty("App::PropertyString", "InpFile", GROUP,
                        "CalculiX input file the optimization is based on")
        obj.setEditorMode("InpFile", 1)


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
