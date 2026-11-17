# OpenAI study preparation (not deployed)

Based on pinned justified-review candidate 42451026. No active desktop or Unity
checkout changed. No credential copied, no paid API call, no new study result.

## Model and billing verification

Official model pages checked 2026-11-16:
- https://developers.openai.com/api/docs/models/gpt-6.1-sol
- https://developers.openai.com/api/docs/models/gpt-6-luna

Standard per million input/cached-input/output tokens: Sol 2/.10/10 USD;
Luna .10/.01/.50 USD. Input >272k doubles input/cache prices and increases output
price by 1.5. Reasoning tokens are included in billed output, not added twice.
The newest documented Luna is GPT-6 Luna. Account model access and the user's
reported credit balance still need verification. No API key exists in this cloud
process environment. Never substitute an internal agent model for API access.

## Prepared, not a runnable full-study integration

`workbench.openai_api` is a separate low-level Responses client, not registered
with the controller. It permits only the two named models, explicit reasoning
effort, text, the official HTTPS host, Standard service, and no stored Responses.
It does not send native sampling knobs, silently retry a request, redirect a key,
or impose a new output token cap. Full provider-native ceilings are reserved
before each call, then observed billed usage settles the durable budget. Unknown
billing freezes new spending; unresolved requests require explicit reconciliation.

`prepare_scope` copies the full matrix and switches every enabled retry variant
to justified-v2, retaining no-review controls. Legacy review scopes are rejected.
Scope is 8,640 observations/model: 4,320 no-review and 4,320 justified-review.
Each on case uses 2 to 8 calls (answer/review, up to three replacements and reviews),
so 12,960 to 38,880 calls/model before any separately authorized transport retry.

## Remaining launch gates

- User-approved combined spending limit, independent of reported available credit.
- Authorized credential/account access and GET models verification.
- Explicit experimental identity/controls: local native 14,336 context and seed,
  top_k/min_p/cache erasure cannot be claimed applied to GPT. Reasoning effort must
  be chosen and recorded; do not silently introduce model-default variability.
- Controller/result-store integration, immutable raw-call evidence and interrupted
  result handling, result-sync enrollment, isolated coverage identity and resume.
- Persist uncertain response evidence before terminating, avoid double payment on
  resume, and reconcile outstanding budget reservations rather than rerun blindly.
- Compare estimated input/output/review tokens with completed journal evidence,
  allowing new review prose and GPT hidden reasoning variation. A local-model cost
  extrapolation is NOT an actual GPT bill or guarantee.
- Preserve original studies. Deploy only after the existing desktop batch finishes;
  Unity completion is not a prerequisite. Never launch old yes/no GPT conditions.

Offline tests are preparation, not evidence of account access or model inference.

## First observed volume anchor

Completed Qwen VL8B batch receipt validated 8,640 records with zero hash
mismatches: 13,365 calls; 22,178,776 prompt tokens and 147,619 completion tokens.
Three calls lacked token usage, so totals are lower bounds. 4,522 reviews,
203 replacements; 18,922,907 cached tokens reported by local runtime. These are
Qwen-tokenizer, old yes/no data. Do NOT assume that cache hit volume transfers.
Repricing uncached volume at Standard is $45.83 Sol + $2.29 Luna = $48.13.
This is an anchor, not a forecast: justified prose and hidden reasoning can
increase output substantially. Extra 1,000 output tokens on each of 13,365 calls
costs another $140.33 across both models at Standard. $100 completion is not
established. Controlled pause/resume on budget exhaustion is mandatory.

Official subscription credit guidance:
https://developers.openai.com/api/docs/guides/chatgpt-api-credits
Eligible Pro $100 tier receives $100 monthly API credits after linking its owned
API organization. Responses API usage is covered; signed-in Codex limits and
Codex API-key usage are not. This verifies the benefit, not this user's balance.

Offline validation: 56 focused tests passed across new client/budget and existing
self-review/comparison suites. After final exception-evidence change, 23 new
client/budget tests passed again. Full regression and live integration unrun.

## Isolated controller integration

`OpenAIStudyController` now uses existing `workflows.execute`, independent scorer,
`ResultStore`, and `@sync_run` exact-path publication receipts. No desktop/native
controller registration or CLI auto-start was added. Production execution rejects
foreign or dirty tracked source checkouts. The immutable coverage manifest pins
scope, source commit, API code fingerprint, provider/effort/cache/context controls
and shared budget location identity. Source/control changes require a new coverage
identity. Completed checksummed results skip without inference. Every request gets
a durable private in-flight journal before network; raw responses are fsynced
before the next call. Any unfinished paid case blocks automatic replay and must be
reconciled, not silently charged again. Completed result files embed raw calls.

Setup after authorization:
1. Verify existing desktop legacy batch complete and preserve its evidence.
2. Use an isolated committed checkout and separate coverage ID; do not edit active
   workers. Load the existing 1,440 test definitions. Full copied GPT scope is
   4,320 off plus 4,320 justified variants/model.
3. Supply the linked organization's key through approved secret/environment setup,
   never chat or source control. `OpenAITransport(os.environ['OPENAI_API_KEY'])`
   verifies exact requested models with GET /v1/models before inference.
4. Create ONE `BudgetLedger` for both models with the explicitly approved USD cap.
   The user's reported available credit is not automatically spending approval.
5. Set explicit effort (medium is the documented model default) and acknowledge
   API control differences in the controller config. This is an operator check,
   not a reason to ask the user about routine technical knobs. Keep provider-native
   output limits, no hidden truncation, implicit cache/30m TTL, Standard service.
6. Call the isolated controller. Failed/aborted cases and completed cases sync via
   exact receipts; never broad-stage unrelated work. If sync fails, use existing
   result-sync retry, not another inference run. Review unfinished journals before
   any paid replay; the current controller deliberately refuses automatic replay.

Billing correction from current official prompt-caching guide: default implicit
cache writes incur1.25x input rate for30m lifetime. Usage distinguishes cached,
ordinary and written input, including TTL-specific write counts. The ledger now
counts these without double charging, fails closed on incomplete write evidence,
and reserves input at worst long-context30m-write rate plus model-native128k output.
Per-call maximum reservation is $7.17 Sol or $0.3585 Luna. Successful metering releases
unused reservation; unknown charges halt new spending. This is intentionally much
more conservative than expected call cost and means it may stop with a safety
margin still unspent. No guessed output length can compromise the approved cap.
The earlier $48.13 anchor would be about $59.77 if all its input incurred cache
writes; future explanation/reasoning costs remain unmeasured.

## Owner-authorized launch plan (November16)

Isaac explicitly approved up to USD100 TOTAL across both models, including paid
validation, stopping safely if the full suite does not fit. His authorized desktop
key was checked in place: GET /v1/models returned HTTP200 and both requested model
IDs are available. No credential was transferred or logged; no paid call occurred.
The coordinator chose Luna first, then Sol, with medium effort and the shared cap.
The prior desktop-completion gate still applies. At23:21UTC2B was still running;
therefore deployment/inference remains blocked on completion, not approval.

Explicit launcher (execute only in the isolated committed desktop checkout after
the coordinator verifies completion):

```
python -m workbench.openai_study_run --key-file "<authorized Downloads key file>" --budget-usd 100 --coverage-id "csc592-gpt-justified-v2-20261116" --desktop-legacy-completion-receipt "<verified completion receipt.json>"
```

Receipt must contain `all_desktop_models_and_perchance_complete: true` and an
`evidence` list of verified completion receipts. The launcher refuses missing
completion evidence and any cap above100. It reads key bytes directly in memory,
never saves them, and sanitizes failures. No independent paid test/probe is needed:
first actual conditions are normal study results charged to the same ledger.

Controller audit fixes: preserve the original source pin across result-only sync
commits; source-tree changes require separate study identity. Persist raw response,
request and budget call ID before settlement, including anomalous billing and
incomplete responses. Simulated mode requires explicitly simulated transport.
Recheck source identity at dispatch.48 new focused tests pass, including launcher
order/cap/gate and credential-redaction assertions. Full regression pending.
