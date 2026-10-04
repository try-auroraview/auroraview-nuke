"""Source-only scheduling tests. This fake SDK is not real Nuke acceptance."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import types
import unittest
from unittest.mock import patch

from auroraview.utils.thread_dispatcher.base import ThreadDispatcherBackend

from auroraview_nuke import NukeDispatcherBackend


class FakeNuke:
    """Queue callbacks until the test's owner thread explicitly pumps them."""

    def __init__(self):
        self.owner = threading.get_ident()
        self.jobs = queue.Queue()
        self.enqueued = threading.Event()
        self.calls = []
        self.utils = types.ModuleType("nuke")
        self.utils.executeInMainThread = self.defer
        self.utils.executeInMainThreadWithResult = self.sync

    def defer(self, callback):
        self.calls.append(("deferred", threading.get_ident()))
        self.jobs.put((callback, None, None))
        self.enqueued.set()

    def sync(self, callback):
        self.calls.append(("sync", threading.get_ident()))
        if threading.get_ident() == self.owner:
            return callback()
        done = threading.Event()
        result = {}
        self.jobs.put((callback, done, result))
        self.enqueued.set()
        if not done.wait(2):
            raise AssertionError("test owner did not pump synchronous Nuke job")
        if "error" in result:
            raise result["error"]
        return result["value"]

    def pump(self):
        if threading.get_ident() != self.owner:
            raise AssertionError("only the fake Nuke owner may pump jobs")
        callback, done, result = self.jobs.get_nowait()
        if done is None:
            callback()
            return
        try:
            result["value"] = callback()
        except BaseException as error:
            result["error"] = error
        finally:
            done.set()


class DispatcherTests(unittest.TestCase):
    def setUp(self):
        self.sdk = FakeNuke()
        self.modules = patch.dict(sys.modules, {"nuke": self.sdk.utils})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.environment = patch.dict(os.environ, {"AURORAVIEW_DISPATCHER": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.backend = NukeDispatcherBackend()

    def worker(self, callback):
        outcome = {}

        def run():
            try:
                outcome["value"] = callback()
            except BaseException as error:
                outcome["error"] = error

        thread = threading.Thread(target=run)
        thread.start()
        return thread, outcome

    def finish(self, thread, outcome):
        thread.join(3)
        self.assertFalse(thread.is_alive(), "test worker did not finish")
        return outcome

    def test_shared_base_and_independently_owned_implementation(self):
        from auroraview.utils.thread_dispatcher.backends.nuke import (
            NukeDispatcherBackend as BundledNuke,
        )

        self.assertIsInstance(self.backend, ThreadDispatcherBackend)
        self.assertIsNot(NukeDispatcherBackend, BundledNuke)
        self.assertEqual(NukeDispatcherBackend.run_sync.__module__, "auroraview_nuke.dispatcher")
        self.assertEqual(self.backend.get_name(), "Nuke")

    def test_sdk_available_without_renderer(self):
        self.assertTrue(self.backend.is_available())

    def test_missing_sdk_is_unavailable(self):
        with patch.dict(sys.modules, {"nuke": None}):
            self.assertFalse(self.backend.is_available())

    def test_deferred_worker_call_keeps_arguments_and_waits_for_owner(self):
        calls = []
        value = object()

        def callback(arg, *, option):
            calls.append((arg, option, threading.get_ident()))

        thread, outcome = self.worker(
            lambda: self.backend.run_deferred(callback, value, option="preserved")
        )
        self.finish(thread, outcome)
        self.assertEqual(outcome, {"value": None})
        self.assertEqual(calls, [])
        self.assertEqual(self.sdk.calls[0][0], "deferred")
        self.assertNotEqual(self.sdk.calls[0][1], self.sdk.owner)
        self.sdk.pump()
        self.assertEqual(calls, [(value, "preserved", self.sdk.owner)])

    def test_deferred_exception_remains_in_owner_callback(self):
        error = ValueError("deferred failure")

        def fail():
            raise error

        self.assertIsNone(self.backend.run_deferred(fail))
        with self.assertRaises(ValueError) as raised:
            self.sdk.pump()
        self.assertIs(raised.exception, error)

    def test_sync_worker_blocks_until_owner_and_returns_same_object(self):
        value = object()
        calls = []

        def callback(arg, *, option):
            calls.append((arg, option, threading.get_ident()))
            return arg

        thread, outcome = self.worker(
            lambda: self.backend.run_sync(callback, value, option="preserved")
        )
        self.assertTrue(self.sdk.enqueued.wait(1), "sync job was not scheduled")
        self.assertTrue(thread.is_alive())
        self.assertEqual(outcome, {})
        self.assertEqual(calls, [])
        self.sdk.pump()
        self.finish(thread, outcome)
        self.assertEqual(calls, [(value, "preserved", self.sdk.owner)])
        self.assertIs(outcome["value"], value)
        self.assertEqual(self.sdk.calls[0][0], "sync")
        self.assertNotEqual(self.sdk.calls[0][1], self.sdk.owner)

    def test_sync_owner_call_uses_sdk_and_preserves_return_value(self):
        value = object()
        self.assertIs(self.backend.run_sync(lambda: value), value)
        self.assertEqual(self.sdk.calls, [("sync", self.sdk.owner)])
        self.assertTrue(self.sdk.jobs.empty())

    def test_sync_exception_propagates_back_to_worker(self):
        error = ValueError("sync failure")

        def fail():
            raise error

        thread, outcome = self.worker(lambda: self.backend.run_sync(fail))
        self.assertTrue(self.sdk.enqueued.wait(1))
        self.sdk.pump()
        self.finish(thread, outcome)
        self.assertIs(outcome["error"], error)

    def test_sdk_submission_error_is_not_suppressed(self):
        error = RuntimeError("SDK rejected submission")

        def reject(_callback):
            raise error

        self.sdk.utils.executeInMainThread = reject
        with self.assertRaises(RuntimeError) as raised:
            self.backend.run_deferred(lambda: None)
        self.assertIs(raised.exception, error)

    def test_existing_core_registration_can_replace_legacy_without_duplicates(self):
        from auroraview.utils.thread_dispatcher import registry
        from auroraview.utils.thread_dispatcher.backends.nuke import (
            NukeDispatcherBackend as BundledNuke,
        )

        registry.clear_dispatcher_backends()
        self.addCleanup(registry.clear_dispatcher_backends)
        registry.list_dispatcher_backends()  # Initialize builtins before replacing.
        legacy_spec = "auroraview.utils.thread_dispatcher.backends.nuke:NukeDispatcherBackend"
        registry.register_dispatcher_backend(legacy_spec, priority=180, name="Nuke")
        registry.unregister_dispatcher_backend(BundledNuke)
        registry.unregister_dispatcher_backend(legacy_spec)
        registry.register_dispatcher_backend(NukeDispatcherBackend, priority=180, name="Nuke")
        registry.register_dispatcher_backend(NukeDispatcherBackend, priority=180, name="Nuke")
        names = [name for _, name, _ in registry.list_dispatcher_backends()]
        self.assertEqual(names.count("Nuke"), 1)
        self.assertIs(type(registry.get_dispatcher_backend()), NukeDispatcherBackend)


class ImportOrderTests(unittest.TestCase):
    def run_fresh(self, script):
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_canonical_first_with_bundled_old_core(self):
        self.run_fresh(
            "from auroraview_nuke import NukeDispatcherBackend as New\n"
            "from auroraview.utils.thread_dispatcher import NukeDispatcherBackend as Old\n"
            "from auroraview.utils.thread_dispatcher.base import ThreadDispatcherBackend\n"
            "from auroraview.utils.thread_dispatcher import registry\n"
            "assert New is not Old and issubclass(New, ThreadDispatcherBackend)\n"
            "registry.list_dispatcher_backends()\n"
            "assert not any(spec is New for _, spec, _ in registry._DISPATCHER_BACKENDS)\n"
        )

    def test_old_import_first_and_no_import_registration(self):
        self.run_fresh(
            "from auroraview.utils.thread_dispatcher import NukeDispatcherBackend as Old\n"
            "from auroraview.utils.thread_dispatcher import registry\n"
            "before = registry.list_dispatcher_backends()\n"
            "from auroraview_nuke import NukeDispatcherBackend as New\n"
            "assert New is not Old\n"
            "assert registry.list_dispatcher_backends() == before\n"
        )

    def test_core_only_does_not_import_candidate(self):
        self.run_fresh(
            "import sys\n"
            "from auroraview.utils.thread_dispatcher import registry\n"
            "assert 'auroraview_nuke' not in sys.modules\n"
            "names = [name for _, name, _ in registry.list_dispatcher_backends()]\n"
            "assert names.count('Nuke') == 1\n"
        )
