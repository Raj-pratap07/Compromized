# ADR-010: SSS library selection

**Status:** Pending spike  
**Decision owner:** Firefly team

## Context
Firefly requires Shamir Secret Sharing over secret bytes with 5 shares and threshold 3. It must support a 4 KiB maximum user secret and use cryptographically secure randomness. Implementing finite-field/polynomial operations from scratch is out of scope.

## Evaluation checklist
- Actively maintained package/repository and release cadence.
- License suitable for hackathon/demo use.
- Supported Python version and operating systems.
- Arbitrary byte input support at the required size, or documented safe framing.
- User-configurable total shares and threshold.
- Cryptographically secure RNG documented and implemented.
- Correct duplicate/malformed share handling.
- Tests or reviewable reference implementation.
- Reconstruct behavior and error behavior are explicit.

## Decision
Do not finalize a package until the above is checked. The implementation agent should propose one package, cite its documentation/source, add a pinned dependency and tests, then request human approval before merging the choice.

## Consequences
No custom SSS math. The wrapper exposes only split/rebuild operations with fixed configuration.
