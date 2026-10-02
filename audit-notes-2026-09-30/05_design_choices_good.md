# Design choices to preserve

- Source/ground-truth separation, exact final-state scoring and terminal incorrect answers protect accuracy from prompt leaks and selective rerolls. Keep explicit result oracles out of prompts.
- Checksummed atomic files are authoritative completion; deletion reopens a case without a hidden tracker. Preserve attempt histories and corruption visibility.
- Selected/full runs share IDs and context recipe. Adding repetitions or neighboring variants preserves old cases; pinned preservation checks make this concrete.
- GPU placement is qualified before cases; hybrid recovery has separate IDs/classes and finite attempts. Preserve unavailable/unknown evidence rather than guessing.
- Raw requests, responses, settings, source/runtime provenance and actual context survive evaluation. Comparable groups stay separate in analysis.
- Timing excludes scoring/disk/Git, and NVML sampling is explicitly device-wide. Preserve the limitations in UI and evidence.
- User-selected model roots, immutable Hub revisions, verified transfers, safe extraction and repo-local runtimes avoid hidden weight/driver installation.
- Loopback inference, private control binding, Host/Origin/bearer checks, CSP and text-only DOM rendering create a useful narrow control surface.
- Source changes restart a process before inference; fast-forward-only Git and narrow result branches preserve local edits/evidence.
- Unit, local HTTP/SSE, child-process and browser fixtures cover different integration edges and clearly label simulation. Keep the single-GPU allocation and no-real-inference distinction.
