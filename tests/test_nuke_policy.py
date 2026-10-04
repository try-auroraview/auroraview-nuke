"""Nuke-specific API guards and existing Core registry behavior."""

from __future__ import annotations

import sys
import threading
import unittest
from unittest.mock import patch

from auroraview.adapter import get_host_registry
from auroraview.utils.thread_dispatcher import registry
from test_dispatcher import FakeNuke

from auroraview_nuke import NukeDispatcherBackend, NukeHostAdapter, register


class NukePolicyTests(unittest.TestCase):
    def setUp(self):
        self.sdk = FakeNuke()
        modules = patch.dict(sys.modules, {"nuke": self.sdk.utils})
        modules.start()
        self.addCleanup(modules.stop)
        self.backend = NukeDispatcherBackend()

    def test_module_without_deferred_api_is_unavailable(self):
        del self.sdk.utils.executeInMainThread
        self.assertFalse(self.backend.is_available())
        self.assertFalse(NukeHostAdapter().detect())

    def test_sync_api_absence_preserves_original_detection_and_error_policy(self):
        del self.sdk.utils.executeInMainThreadWithResult
        self.assertTrue(self.backend.is_available())
        with self.assertRaises(AttributeError):
            self.backend.run_sync(lambda: None)

    def test_main_thread_identity_is_core_behavior_without_nuke_specific_api(self):
        self.assertTrue(self.backend.is_main_thread())
        values = []
        worker = threading.Thread(target=lambda: values.append(self.backend.is_main_thread()))
        worker.start()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(values, [False])

    def test_host_version_remains_unknown_in_existing_contract(self):
        self.assertIsNone(NukeHostAdapter().version())

    def test_custom_backend_with_same_display_name_is_preserved(self):
        class CustomBackend(NukeDispatcherBackend):
            pass

        registry.clear_dispatcher_backends()
        self.addCleanup(registry.clear_dispatcher_backends)
        registry.list_dispatcher_backends()
        registry.register_dispatcher_backend(CustomBackend, priority=500, name="Nuke")
        register()
        self.assertIs(type(registry.get_dispatcher_backend()), CustomBackend)
        self.assertEqual(
            len([item for item in registry.list_dispatcher_backends() if item[1] == "Nuke"]), 2
        )

    def test_legacy_host_string_uses_existing_same_id_slot_replacement(self):
        hosts = get_host_registry()
        self.addCleanup(hosts.clear)
        hosts.register("auroraview.adapter.hosts:NukeHostAdapter", priority=180, name="nuke")
        register()
        self.assertEqual(hosts.names().count("nuke"), 1)
        self.assertIs(type(hosts.detect(env_override="nuke").value), NukeHostAdapter)
