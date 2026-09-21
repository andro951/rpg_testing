# Research roadmap and unimplemented ideas

This document records research directions and design decisions discussed for the project that are **not yet implemented**. It is intentionally separate from the implementation ledger in `PLANNED_CHANGES.md`.

The first real general-state fixture, `inventory_net_stock_001`, already exists. The items below describe where the research should go next.

## 1. Research goal: general state management first

The first phase of the project should study **natural-language-to-structured-state updating in general**, not RPG-specific state.

The eventual application is Ember Adventures, but the underlying problem is broader:

- Given an existing structured state, what facts actually changed?
- Which facts were merely discussed, proposed, imagined, denied, or left unchanged?
- Can the system produce only the justified update?
- Can it do this repeatedly over time without accumulating state drift?
- Can it locate the relevant state when the full data store is much larger than one object?

Test scenarios should represent plausible real systems rather than artificial game statistics created only to make a benchmark. Useful domains include inventory, orders, project/task tracking, scheduling, smart-home/device state, and other real operational records.

The benchmark should cover realistic examples of:

- numeric updates and arithmetic,
- booleans and enums,
- strings,
- list additions and removals,
- nested objects,
- multiple simultaneous changes,
- explicit no-change cases,
- tempting false positives such as plans, possibilities, hypotheticals, and discussion of changes that were never committed.

## 2. Scale state selection separately from state updating

The first inventory fixture deliberately gives the model one already-selected product record. Future tests should increase the amount of available state so that locating the correct record becomes part of the problem.

### Planned progression

**Level A — selected record**

The correct record is already provided. Measure pure state-update ability.

**Level B — small collection**

Provide tens or hundreds of realistic records. The natural-language event identifies one of them by normal details such as model number, SKU, product name, customer, task ID, or other business identifiers.

**Level C — large collection**

Use a realistically large data store, potentially thousands or tens of thousands of records. At this level, do not assume the correct design is to stuff the entire database into model context.

**Level D — retrieval plus update system**

Evaluate practical retrieval architectures before state updating. Candidate approaches include conventional indexed/database lookup, keyword search, hierarchical lookup, embeddings, top-k candidate retrieval, or a separate model-assisted retrieval stage.

### Score the stages separately

Whenever possible, keep these measurements independent:

- **record-selection accuracy:** was the correct state object located?
- **update accuracy given correct retrieval:** once the right record was available, was it updated correctly?
- **collateral-damage rate:** were unrelated records or fields changed?
- **end-to-end exact state:** does the complete resulting data store exactly match the expected result?
- **latency and token cost:** what did the full pipeline require?

This separation is important because a retrieval failure and a state-reasoning failure are different engineering problems.

## 3. Longitudinal or "over-time" state tests

A major planned test family should evaluate state management across many turns rather than forcing an update on every request.

Real systems often have many observations or conversation turns where **nothing should change**.

A longitudinal scenario should be able to contain:

- several no-op turns,
- early discussion or hints about a possible change,
- intermediate questions and deliberation,
- unrelated intervening turns,
- an eventual explicit commitment or real-world event,
- more turns after the update.

Example pattern: a manager discusses lowering an inventory reorder point for several turns, asks questions about the consequences, tentatively agrees it sounds reasonable, but does not actually authorize the change until a later turn. The authoritative state must remain unchanged until the exact commitment point.

### Score every turn

Do not judge only the final state. A model that changes state too early and later happens to return to the correct final state still failed.

Planned metrics include:

- **no-op accuracy:** correctly producing no state change when none is justified,
- **premature-update rate:** committing a change before it becomes true or authorized,
- **missed-update rate:** failing to apply a change once it becomes established,
- **update-timing accuracy:** applying the change on exactly the correct turn,
- **state drift:** unintended changes accumulating over many turns,
- **final-state accuracy:** whether the final authoritative state is correct.

These tests should support runs in which most turns legitimately produce no patch.

## 4. Separate authoritative state from memory

The eventual system should not treat an ever-growing transcript as its memory system.

The planned architecture has at least three different information classes.

### Authoritative state

Structured facts that are currently true and should be updated precisely.

Examples: inventory count, current location, task status, door state, active order status.

### Working memory

Relevant unresolved context that matters now but is **not yet authoritative state**.

Examples: a proposed inventory change awaiting approval, a question being investigated, an intention that has not been acted on, or an unresolved conversation thread.

Working memory is especially important for longitudinal tests because the system must remember an unresolved issue without prematurely committing it to state.

### Long-term episodic memory

Older events or conversations that are no longer worth carrying in active context but may become relevant later.

Long-term memory should be searchable. If a later event relates to an old location, person, supplier, task, or decision, the system should be able to retrieve the appropriate older memory instead of carrying every historical token forever.

## 5. Memory consolidation and forgetting

Long-term memory should eventually support a consolidation stage.

Instead of retaining every old transcript verbatim in active context, the system may produce a smaller structured or bullet-like memory containing the important facts, people, outcomes, unresolved threads, and references needed to recover more detail later.

Planned questions include:

- What information should survive consolidation?
- How much compression is possible before later reasoning becomes worse?
- Should the original detailed transcript remain archived for retrieval?
- When should old working memory become long-term memory?
- When is forgetting low-value detail acceptable or beneficial?
- Can the system retrieve an older relevant episode after many unrelated turns?

A useful baseline for these experiments is the simple but expensive approach of providing the entire conversation history. Managed-memory approaches can then be compared against that baseline for correctness, latency, and token usage.

## 6. Fixed "round cache" policy

The default cache policy should **not** be an endlessly growing conversation cache.

A cache is an optimization for a deliberately selected starting context, not the authoritative memory of the system.

### Planned rule

At the start of a round, create a **fixed base cache** from the information intentionally selected for that round.

During the round:

- the base cache remains unchanged,
- individual inference calls append temporary prompt suffixes,
- intermediate decisions from earlier calls are passed explicitly in later prompts when needed,
- those temporary suffixes must not silently become the persistent base cache,
- independent branches should be able to begin from the same base snapshot.

For example, if one call decides that a state change occurred, a later call can be told that result in its ordinary prompt and then ask which field changed. The persistent base cache does not need to grow.

### Round boundary

At an explicit boundary, the system may:

1. commit justified authoritative state updates,
2. update working memory,
3. retrieve or consolidate long-term memory,
4. discard the old base cache,
5. build a new base cache from the newly selected information.

Cache replacement should therefore be an intentional operation rather than an automatic side effect of conversation length.

### Future cache experiments

Compare policies such as:

- rebuild every turn,
- rebuild only when authoritative state changes,
- rebuild when working memory changes substantially,
- rebuild every fixed number of rounds,
- keep a stable base for multiple rounds.

Measure correctness, cache-rebuild cost, prompt-processing time, total latency, and memory use.

## 7. Multi-stage state reasoning

The project should continue testing alternatives to one large "produce the patch" request.

Candidate workflows include:

- direct patch,
- analyze then patch,
- semantic operations,
- first ask whether anything changed,
- determine which entity or record changed,
- determine which field/category changed,
- determine the exact new value,
- verify the proposed update before committing it.

With the fixed round-cache policy, later stages can receive earlier decisions explicitly in their temporary prompt while all stages share the same immutable base context.

The goal is to determine whether decomposition improves correctness enough to justify extra inference calls, especially when prefix caching makes those calls inexpensive.

## 8. Core benchmark versus practical system experiments

The project should intentionally support both rigorous benchmark results and broader engineering experiments.

### Core benchmark

Prefer deterministic fixtures with explicit expected state and fully automatic scoring.

These results should support strong claims about exact-match accuracy, unsupported changes, missed changes, invalid output, timing, caching, and model/workflow differences.

### Practical system experiments

Larger retrieval, memory, organization, and consolidation experiments introduce more architectural choices and therefore more possible confounds.

They are still valuable. Score objective parts automatically wherever possible, document the architecture clearly, and use manual evaluation only when the question genuinely cannot be reduced to an exact expected state.

Do not discard a practical experiment merely because it is less clean than the core benchmark. The purpose of the project is to learn how to build a useful state-management system, not to invent artificial problems solely because they are easy to publish.

## 9. Eventual Ember Adventures application

RPG-specific testing should come after the general state and memory work is understood.

At that point, Ember Adventures becomes a demanding application of the same mechanisms:

- authoritative world and character state,
- many turns with no state change,
- intentions and dialogue that must not be mistaken for completed actions,
- unresolved working-memory threads,
- old locations, people, and events retrieved from long-term memory,
- deliberate consolidation of older history,
- fixed round caches rather than an endlessly growing transcript.

The RPG layer should demonstrate the usefulness of the general system rather than define the research narrowly around games.

## Immediate next research-fixture candidates

1. A realistic list-add/list-remove state update with substantial unchanged metadata.
2. A realistic boolean or enum transition with misleading discussion of alternatives.
3. A multi-field update with both changed and explicitly unchanged fields.
4. A small multi-record inventory test requiring record selection before updating.
5. The first longitudinal no-op/premature-update test, scored at every turn.
6. A fixed-cache multi-stage workflow using the same base cache for every decision within one round.
