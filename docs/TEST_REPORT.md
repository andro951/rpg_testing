# Workbench validation report

## Tested committed source

Code commit: `13554b40d1337dc02d92696233b019c2a4886c5c`.

GitHub Actions run: https://github.com/andro951/rpg_testing/actions/runs/35556535167

All three jobs completed successfully:

- **Linux: 179 unit/smoke tests passed**, Python 3.12.14, Ubuntu runner. Test duration 19.537 seconds.
- **Windows: 179 unit/smoke tests passed**, Python 3.12.10, Windows Server runner. Test duration 43.791 seconds.
- **Browser: Chromium end-to-end smoke passed**, using actual browser-to-loopback networking in GitHub Actions.

Unit jobs include both the retained prototype tests and the new workbench tests. These are software tests, not model benchmarks. Documentation-only commits following this code commit do not change the tested implementation.

## What was exercised

The unit/smoke suite covers strict JSON comparison and both patch representations; schema and workflow validation; conditional/loop steps; ground-truth exclusion; model metadata/scanning/shards; assigned-plus-adjacent VRAM scheduling; the 11 GB exception; file-based completion; checksum/corruption checks; deletion and rerun; completed models without installed weights; manual preflight actions; controller run/resume/cancellation; OS-held locks; mock model lifecycle; actual localhost HTTP and SSE streaming; missing finish reasons and HTTP errors; separate reasoning/visible text; per-request seed/temperature; output-cap omission; native cache reset/request contracts; invalid cache measurements; Git publishing against temporary bare repositories; and Unity shell/allocation guards.

Browser smoke covers pairing, preflight without inference, eight-case simulated run, completed-run skip, result inspection, deletion and one-case rerun, model listing, persistence of a VRAM dropdown across polling, cached-workflow import, export download, host-folder browsing, preservation of unsaved setup fields, pairing-key display and responsive layout.

Security-oriented checks cover missing/wrong authentication, unexpected Host/Origin, public-bind refusal, safe paths, local-only inference endpoints, forbidden arbitrary API commands, unsafe schema references and refusal to stage unrelated Git files. This is not a comprehensive security audit or public-hosting certification.

## Local validation

The locally available workbench subset passed **101 tests** under Python 3.13. The entire committed source was tested separately by the Windows/Linux CI jobs above. JavaScript syntax and Python compilation checks also passed.

A local Chromium smoke passed through an explicit Python HTTP bridge because the hosted browser environment restricted direct loopback networking. That local bridge run did NOT establish browser networking; the successful GitHub browser job did.

The separate local demo ran eight cases and a second run created zero new cases. A screenshot, one sample result and a full evidence ZIP were produced from this SIMULATED run. Canned response correctness and synthetic per-call timing must not be used as Qwen results or performance measurements.

## Defects found and corrected during validation

- UI status polling could reset a VRAM dropdown or unsaved setup edits.
- Remote shutdown needed to close the owning worker server, not only the remote listener.
- Automatic context estimation initially omitted a large explicitly shared prefix.
- An overly broad ignore rule could hide nested published result files.
- Corrupt result files prevented exporting otherwise useful logs; exports now retain raw corrupt files and list them.
- An imported function named `load_tests` collided with unittest's discovery hook.
- Windows tests needed canonical path comparison and a working Bash rather than an unconfigured WSL launcher.

The fixes were followed by additional regression tests and the final successful full CI run.

## Not established here

No actual model weights were run on a GPU. The GTX 1080, installed LM Studio runtime, real Tailscale laptop-to-desktop route and Unity allocation were unavailable. Windows CI validates portable code, not a Windows 10 interactive desktop session with LM Studio.

Actual model load success, GGUF/backend architecture compatibility, complete GPU residency, real peak VRAM, cache counters on an installed llama-server, throughput and latency require hardware smoke runs. Peak VRAM remains null/unavailable, full residency remains unverified, and catalog VRAM requirements remain estimates. Native cache tests reject/flag missing evidence instead of reporting imagined reuse.

The graphical bootstrap/VBS launchers, firewall permissions, desktop sleep behavior and real account authentication still need first-use verification on the user's computer. University authorization and installation cannot be certified by local preparation checks. Context remains finite even though there is no user-configurable/artificial output cap.

No claim of exhaustive testing, guaranteed correctness, or production hardening is made.
