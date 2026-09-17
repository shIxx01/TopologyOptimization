# SPDX-License-Identifier: LGPL-3.0-or-later
"""View object of a topology optimization."""

from ..resources import icon


class TopologyViewProvider:
    """Icon, tooltip and the assistant dialog of the object."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object

    def attach(self, vobj):
        self.Object = vobj.Object
        return

    def getIcon(self):
        return icon("TopoOpt.svg")

    def setEdit(self, vobj, mode):
        """Double click / edit opens the assistant."""
        from ..gui.assistant import open_assistant
        open_assistant(vobj.Object)
        return True

    def doubleClicked(self, vobj):
        self.setEdit(vobj, None)
        return True

    def claimChildren(self):
        return []

    def dumps(self):
        return None

    def loads(self, state):
        return None
