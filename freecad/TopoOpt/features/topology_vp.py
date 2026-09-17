# SPDX-License-Identifier: LGPL-3.0-or-later
"""View object of a topology optimization."""

from ..resources import icon


class TopologyViewProvider:
    """Icon, tooltip and (later) the assistant dialog of the object."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object

    def attach(self, vobj):
        self.Object = vobj.Object
        return

    def getIcon(self):
        return icon("TopoOpt.svg")

    def setEdit(self, vobj, mode):
        # the assistant is added in the next step - for now: do not open an editor
        return False

    def doubleClicked(self, vobj):
        return False

    def claimChildren(self):
        return []

    def dumps(self):
        return None

    def loads(self, state):
        return None
