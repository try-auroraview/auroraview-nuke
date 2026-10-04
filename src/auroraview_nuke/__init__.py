# -*- coding: utf-8 -*-
"""Opt-in Nuke adapter. Importing this package never registers a backend."""

from __future__ import annotations

from .dispatcher import NukeDispatcherBackend
from .host import NukeHostAdapter

__all__ = ["NukeDispatcherBackend", "NukeHostAdapter", "register"]


def register() -> None:
    """Select this implementation in AuroraView's existing registries.

    The bundled implementation remains available through legacy imports.
    Initialize builtins before replacing their Nuke entries; otherwise the
    first discovery call would restore the bundled backend over this one.
    Repeated calls are safe. Other DCC registrations remain intact.
    """
    from auroraview.adapter import AdapterPriority, get_host_registry
    from auroraview.utils.thread_dispatcher import registry
    from auroraview.utils.thread_dispatcher.backends.nuke import (
        NukeDispatcherBackend as BundledNuke,
    )

    registry.list_dispatcher_backends()
    for spec in (
        BundledNuke,
        "auroraview.utils.thread_dispatcher.backends.nuke:NukeDispatcherBackend",
        "auroraview_nuke.dispatcher:NukeDispatcherBackend",
    ):
        while registry.unregister_dispatcher_backend(spec):
            pass
    registry.register_dispatcher_backend(
        NukeDispatcherBackend, priority=registry.DispatcherPriority.NUKE, name="Nuke"
    )
    hosts = get_host_registry()
    hosts.register(NukeHostAdapter, priority=AdapterPriority.NUKE, name="nuke")
