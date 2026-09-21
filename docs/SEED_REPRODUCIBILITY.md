# Seed reproducibility and repetition policy

## Automatic seed reproducibility diagnostic

Every successful model load runs a short stochastic diagnostic before benchmark cases.

The diagnostic uses the same open-ended five-sentence fiction prompt three times at nonzero temperature:

1. primary seed,
2. the exact same primary seed again,
3. a different seed.

The cache is cleared for every diagnostic generation. The workbench compares exact visible text plus reasoning text. Streaming chunk boundaries are deliberately ignored.

The result records:

- whether the two same-seed outputs are byte-for-byte identical,
- whether changing only the seed changes the output,
- SHA-256 fingerprints and character counts for all three outputs,
- the exact sampling settings and seeds,
- whether both behaviors were verified.

A mismatch is evidence about runtime/model reproducibility and is recorded; it does not silently retry or block unrelated benchmark cases. The diagnostic is outside measured benchmark-case timing. Simulated demo results are explicitly marked simulated.

## Benchmark repetitions

Fixture repetition zero uses the seed written in the step definition. Later repetitions automatically use distinct deterministic unsigned 32-bit seeds.

The schedule is:

base seed plus repetition number times hexadecimal 9E3779B1, modulo 2 to the 32.

This has two useful properties:

- repetition zero preserves existing fixtures and prior intent,
- for up to 2 to the 32 repetitions, a given base seed maps each repetition to a distinct seed.

Variants that use the same base seed receive the same effective seed for the same repetition number. This makes comparisons such as raw-array versus indexed-array presentation, or two temperatures, naturally paired by seed.

The effective seed used for every generation is preserved in the raw call evidence.
