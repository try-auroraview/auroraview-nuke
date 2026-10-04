# -*- coding: utf-8 -*-
"""Nuke metadata using the existing AuroraView Qt host contract."""

from __future__ import annotations

from auroraview.adapter.hosts import DispatcherBackedHostAdapter, QtHostAdapterMixin


class NukeHostAdapter(QtHostAdapterMixin, DispatcherBackedHostAdapter):
    """Foundry Nuke (Qt host). SDK imports remain lazy."""

    dispatcher_spec = "auroraview_nuke.dispatcher:NukeDispatcherBackend"
    id = "nuke"
    display_name = "Foundry Nuke"
