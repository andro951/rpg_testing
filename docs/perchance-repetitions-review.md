# Perchance independent repetitions — October 8, 2026

## Requirement and implementation review

The user changed the standing rule: ordinary configured repetitions must run independently even though Perchance seed behavior is unverified. Unsupported control sweeps still collapse to one representative within each repetition. This supersedes the earlier repetition-collapse rule in the integration preparation document.

- The planner includes repetition in observation identity and chooses representatives before seeing results. Each configured repetition has its own real provider request(s), saved response and score. Aliases never cross repetition boundaries.
- The worker forwards the requested repetition-derived seed experimentally. Evidence distinguishes requested and forwarded sampling from applied sampling, which remains null. Seed effect and reproducibility remain unverified. Temperature, cache and other unsupported controls are not forwarded or claimed as applied.
- Existing compatible baselines from the known prior adapter fulfill only repetition zero. Compatibility requires the recorded adapter hash, provider URL, epoch, workflow fingerprint, remote-model identity and captured effective definition to match. Unknown adapter versions or changed conditions are not silently reused.
- Old saved evidence is immutable. Its former repetition aliases cannot satisfy later repetitions or fill their matrix cells. Old and new trials for the same service conditions share a model column, while their original policy and adapter provenance remain available in evidence.
- Resume preserves terminal wrong answers and timeouts. Additional configured repetitions still run; they are not retries selected because a baseline failed. Cancellation/infrastructure handling preserves attempt evidence.
- Native identities and scoring, the 8 GB restriction, Perchance-last scheduling, the 300-second deadline, rejected-test blocking and the proven normal-browser/CDP transport remain intact.
- The detailed evaluator recognizes Perchance's `provider_completed` finish reason as complete; successful responses are not mistaken for truncated output.

## Counts and compatibility

The active suite requests 357 cases. The former planner produced 160 independent observations. The revised planner produces 312 independent observations and 45 aliases for unavailable-setting/metadata equivalents. Synthetic coverage with 160 compatible terminal baselines proves that exactly 152 fresh repetitions remain pending, with every original file unchanged. Different settings, adapter versions, changed definitions, rejected tests or incomplete baselines can change actual pending counts.

The local checkout has no saved Perchance observations from the user's latest run. Compatibility was tested with captured-policy fixtures, including terminal failures and timeouts, rather than claiming to have inspected or migrated that remote run. No live benchmark trials were started by this change.

## Validation

- Targeted provider, run-all, reporting and evaluator tests: 71 passed before the additional full-suite compatibility regression.
- Full-suite compatibility regression: 160 preserved baseline files, 152 pending independent trials; passed.
- Browser worker smoke: raw responses, chunks, cancellation, seed forwarding and unverified applied-sampling evidence; passed with a simulated plugin.
- Workbench browser smoke: Overview run-all, independent repetitions, evidence inspection and targeted resume; passed with simulated service transport.
- Results-table browser smoke: passed.
- Normal-browser/CDP smoke: separately launched browser, iframe worker, seed forwarding, raw text/chunks, disconnect and reconnect without relaunch; passed with a simulated hosted plugin. This does not establish live-service seed support.
- Existing native evidence manifest: all 1,428 files retain their size and modification timestamp. Native workflow fingerprint remains `56502881bc3c89f6b58c8f5e755b32f58cbd675274ed5363293b598aaddf9787`.
- Full unit suite: `python -m unittest discover -s tests -v` — **508 tests passed**, no skips or failures, in 538.178 seconds. Process-local PATH included the already installed Git Bash so shell checks ran. Log: `.local/perchance-repetitions-full.log`.
- Evaluation CLI smoke: replayed twice, identical passing assessment and unchanged synthetic evidence.
