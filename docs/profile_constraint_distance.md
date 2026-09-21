# Profile constraint distance behaviour

This document records the current behaviour for profile selection based on constrained classes.

## Current logic
- If `PROFILE_CONSTRAINT_ALLOW_SUBCLASS` is `false`: only exact class matches are considered (distance = 0).
- If `PROFILE_CONSTRAINT_ALLOW_SUBCLASS` is `true`: exact (distance = 0) and single-hop superclass (distance = 1) matches are considered. Distances beyond 1 are not evaluated.
- Ordering prefers requested profile (if any), then lower `constraint_distance` (0 over 1), then default profile/format flags, then alt-profile last.

## Differences from earlier behaviour
- Previously only exact matches were supported. This change introduces a single-hop superclass fallback controlled by `PROFILE_CONSTRAINT_ALLOW_SUBCLASS`.
- Earlier experiments attempted multi-hop/unlimited matching; these were removed to avoid complexity and non-deterministic ranking.

## Known limitations
- Profiles constrained to ancestors more than one hop away will not be selected; such resources fall back to the open-object profile.
- `PROFILE_CONSTRAINT_ALLOW_SUBCLASS=true` only enables single-hop matching; deeper inheritance is ignored.
- Test subclass profiles are bundled in the reference data for automated tests; ensure deployments override `PREZ_REFERENCE_DATA_DIR` if those profiles should not be loaded.
