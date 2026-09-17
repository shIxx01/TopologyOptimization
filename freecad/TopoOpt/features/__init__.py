# SPDX-License-Identifier: LGPL-3.0-or-later
"""Document objects and their view providers."""

from .topology_object import TopologyObject, create_topology_object, ensure_properties, find_analysis

try:  # the view provider needs the GUI
    from .topology_vp import TopologyViewProvider
except ImportError:  # console mode
    TopologyViewProvider = None

__all__ = ["TopologyObject", "create_topology_object", "ensure_properties", "find_analysis",
           "TopologyViewProvider"]
