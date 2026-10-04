# AuroraView Nuke

Nuke dispatcher and host metadata extracted from public AuroraView history.
Version `0.0.0.dev0` is a local development candidate; no package release or
real Nuke acceptance is claimed.

## Dependency and behavior

The sole runtime dependency is `auroraview>=0.5.11,<0.6.0`; Python 3.7+ is
supported by this pure Python package. Core retains the host/renderer contracts,
registries, Qt integration, WebView bridge, dispatcher ABC and wrappers.
Nuke supplies its own `nuke` SDK module. This package never vendors Core, Qt,
a renderer or a native binary.

`NukeDispatcherBackend` retains the original lazy detection and delegates:
`executeInMainThread` for deferred work and
`executeInMainThreadWithResult` for blocking work. Arguments, result objects and
exceptions follow the original API. Detection checks the deferred API only;
an incomplete SDK missing the blocking API still raises on `run_sync`.
Thread identity uses the shared Core implementation. Host version and parent
handle remain `None`; embedding capabilities retain Core's Qt metadata and do
not constitute implemented Nuke parent discovery or dock ownership.

```python
from auroraview_nuke import NukeDispatcherBackend, NukeHostAdapter, register

register()
from auroraview import create_webview
```

Importing the package neither loads the SDK nor registers candidates.
`register()` initializes builtins, replaces only known bundled/canonical Nuke
dispatcher class/string specs, and uses Core's existing `nuke` host-id slot
replacement. Both priorities remain Nuke's original 180. Repeated calls retain
one owned dispatcher entry and invalidate stale selection through Core's API.
Other host ids and custom backend classes remain intact, including custom
classes with the same display name. The legacy bundled imports remain available
in Core 0.5.11; a later Core compatibility facade is separate work.

## Verification

Set `AURORAVIEW_TEST_PYTHON` to an existing interpreter and
`AURORAVIEW_CORE_SOURCE` to the checkout matching `PROVENANCE.json`.
Development dependencies are installed into task-local environments, never
globally. Recipes select the actual requested interpreter, disable tool auto
installation, and use portable paths.

```sh
vx just check
vx just package-check
```

| Gate | Evidence and limit |
| --- | --- |
| Source | Pinned public Core files, Python 3.7 grammar, queued fake Nuke delegates, import orders, actual registry priorities and replacement behavior |
| Installed package | Wheel/sdist metadata, MIT license, payload identity and isolated adapter install using explicitly pinned source Core |
| Official Core wheel | Fresh environment, checksum-verified public Core 0.5.11 wheel, installed adapter, strict native module import and API tests with no Core source/PYTHONPATH |
| Real Nuke/native bridge | Not run: requires actual host versions, owner thread, parent/dock behavior, JS round trips, close/restart and deadlines before release |

`scripts/published_smoke.py --core-wheel <official-wheel> --core-sha256 <sha256>`
installs existing wheels in a new local environment. It never downloads a Core
wheel or accepts a missing native import as success. Supply a Python 3.7
`typing_extensions` wheel alongside Core when needed. CI's separate Windows
released-Core jobs install only binary Core 0.5.11 from the public PyPI index;
source jobs cover Windows and Linux with Python 3.7, 3.11 and 3.12.
CI has read-only permissions and no publisher, host license or secret setup.

The historical `migration/manual/test_nuke_ipc.py` skips without Nuke and
requires clicking its UI button; it is preserved as optional manual evidence,
excluded from automated contract gates. Its existence is not a native pass.

## Public history

The source is main `11b3a29ad95a46cb22aaa604614de16da16bfc22`, with 1,623
ancestors and nine retained commits after filtering. The precise whitelist is
the MIT license, monolithic dispatcher predecessor, current Nuke dispatcher,
shared host-adapter source and Nuke IPC test. Current host source is narrowed to
Nuke; historical shared code remains in filtered Git history for attribution.
`migration/commit-map.txt` maps original commits to rewritten hashes; zero
hashes indicate pruned commits. The retained filtered HEAD can differ from the
source tip because later commits change none of the selected paths.

`scripts/extract_history.py` reproduces the filter from a complete local public
clone into a new destination. It refuses overwrites, validates the pinned source
and cloned HEAD before filtering, and verifies the expected filtered result.
It neither modifies the source clone nor commits, publishes or pushes.

Core issue numbers and release tags remain at
[Core issues](https://github.com/try-auroraview/auroraview/issues) and
[Core releases](https://github.com/try-auroraview/auroraview/releases).
This package has rewritten, filtered history and copies neither GitHub issues
nor Core release tags. See `PROVENANCE.json` for source hashes and mappings.
