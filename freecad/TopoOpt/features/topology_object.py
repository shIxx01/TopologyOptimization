# SPDX-License-Identifier: LGPL-3.0-or-later
"""Document object of a topology optimization."""

import FreeCAD as App

GROUP = "TopoOpt"


def ensure_properties(obj):
    """Add properties that are missing (new objects and objects from older files).

    addProperty() has no parameter for a default value - the value has to be set
    afterwards.  For a property that is a length the editor mode has to be set.
    """
    if not hasattr(obj, "Analysis"):
        obj.addProperty("App::PropertyLink", "Analysis", GROUP,
                        "FEM analysis this optimization belongs to")


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


def create_topology_object(doc, analysis, name="TopologieOptimierung"):
    """Create the object and put it into the (active) analysis container.

    Returns the new object.  The object keeps a link to the analysis, so it stays
    usable even if it is moved somewhere else in the tree.
    """
    obj = doc.addObject("App::FeaturePython", name)
    TopologyObject(obj)
    if obj.ViewObject is not None:
        from .topology_vp import TopologyViewProvider
        TopologyViewProvider(obj.ViewObject)
    ensure_properties(obj)
    obj.Label = "Topologie-Optimierung"
    obj.Analysis = analysis
    analysis.addObject(obj)
    return obj
