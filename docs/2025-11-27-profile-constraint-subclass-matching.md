# Profile Constraint Subclass Matching

**Date:** 2025-11-27
**Status:** Implemented
**Motivation:** Allow profiles to constrain superclasses and automatically match subclass instances

## Overview

This document proposes extending the profile matching logic in `connegp_service.py` to support automatic subclass matching with a maximum distance of 1 hop. This would allow a single profile to serve multiple related resource classes without requiring explicit constraint declarations for each subclass.

## Current Behavior

### How Profile Matching Works Today

When determining which profile to use for a resource, the `_compose_select_query()` method in `connegp_service.py` generates a SPARQL query that:

1. Takes the resource's class(es) from `self.classes`
2. Validates the class is related to registered endpoint classes using `rdfs:subClassOf*`
3. **Requires exact match** on `altr-ext:constrainsClass`

```sparql
VALUES ?class { <ex:SpecificBorehole> }
?class rdfs:subClassOf* ?mid .
?mid rdfs:subClassOf* ?base_class .
VALUES ?base_class { /* endpoint target classes */ }
?profile altr-ext:constrainsClass ?class ;  # Must match exactly!
```

### What the Subclass Logic Currently Does

The existing `rdfs:subClassOf*` logic (lines 348-349) serves two purposes:

1. **Validation**: Ensures the resource class inherits from a registered endpoint class
2. **Prioritization**: The `count(?mid) as ?distance` metric ranks matches by specificity

**However**, line 353 still requires:
```sparql
?profile altr-ext:constrainsClass ?class ;
```

This means the profile must declare the **exact class**, not a superclass.

### Example: Current Limitation

Given:
```turtle
# Ontology
ex:DiamondDrillCoreSample rdfs:subClassOf sosa:Sample .
ex:RockChipSample rdfs:subClassOf sosa:Sample .
ex:SoilSample rdfs:subClassOf sosa:Sample .

# Profile
<formation-top-profile> altr-ext:constrainsClass sosa:Sample .

# Resource
<sample1> a ex:DiamondDrillCoreSample .
```

**Result**: The profile does NOT match because `altr-ext:constrainsClass sosa:Sample` doesn't match the resource's actual class `ex:DiamondDrillCoreSample`.

**Current workaround**: Explicitly list all subclasses:
```turtle
<formation-top-profile> altr-ext:constrainsClass
    sosa:Sample,
    ex:DiamondDrillCoreSample,
    ex:RockChipSample,
    ex:SoilSample,
    # ... potentially 20-30 classes
```

## Problem Statement

### Use Case: Search Results with Many Subclasses

When implementing search functionality, results may have 20-30 different specific classes that all inherit from a common base class like `prez:SearchResult`. Users want a single profile to describe all search results without manually listing every possible subclass.

### Separation of Concerns

There's an architectural distinction between:
- **Endpoints** (`sh:targetClass`) → "What resources live at this URL path" (focus node selection)
- **Profiles** (`altr-ext:constrainsClass`) → "How to describe/render this resource" (property selection)

Currently, these concerns are conflated in the query via `query_klasses` (line 323-324).

## Proposed Solution: Max Distance = 1

### Core Idea

Allow profiles to match resources whose class is a **direct subclass** (1 hop) of the constrained class, while still prioritizing exact matches.

### Benefits

✅ Solves the "many subclasses of SearchResult" problem
✅ Prevents deep hierarchy over-matching
✅ Allows specific overrides (exact match wins over superclass match)
✅ Minimal performance impact (no transitive closure)
✅ Predictable, understandable behavior

### Implementation

Modify the SPARQL query generation to use a UNION pattern:

```sparql
{
  # Direct match (distance = 0, highest priority)
  BIND(?class as ?matchClass)
  BIND(0 as ?constraint_distance)
} UNION {
  # Single-hop superclass match (distance = 1, lower priority)
  ?class rdfs:subClassOf ?matchClass .  # Non-transitive
  BIND(1 as ?constraint_distance)
}
?profile altr-ext:constrainsClass ?matchClass ;
         altr-ext:hasResourceFormat ?format ;
         dcterms:title ?title .
```

Update the ORDER BY clause to prioritize by constraint distance:

```sparql
ORDER BY
  DESC(?req_profile)           # Requested profile wins
  ASC(?constraint_distance)    # Exact match (0) before superclass (1)
  DESC(?distance)              # Specificity from endpoint validation
  DESC(?def_profile)           # Default profile preference
  DESC(?req_format)            # Requested format
  DESC(?def_format)            # Default format
  ASC(?alt_prof)               # Alternate profile last
```

## Detailed Example

### Scenario Setup

```turtle
# Ontology
ex:BoreholeSearchResult rdfs:subClassOf prez:SearchResult .
ex:SampleSearchResult rdfs:subClassOf prez:SearchResult .
ex:ReportSearchResult rdfs:subClassOf prez:SearchResult .

# Profiles
<search-profile>
    altr-ext:constrainsClass prez:SearchResult ;
    dcterms:title "Search Results" .

<borehole-detail-profile>
    altr-ext:constrainsClass ex:BoreholeSearchResult ;
    dcterms:title "Detailed Borehole" .

# Resource
<result1> a ex:BoreholeSearchResult .
```

### Query Results with New Logic

The query would find TWO matches:

| Profile | matchClass | constraint_distance | Notes |
|---------|------------|---------------------|-------|
| `<borehole-detail-profile>` | `ex:BoreholeSearchResult` | 0 | Exact match |
| `<search-profile>` | `prez:SearchResult` | 1 | Superclass match |

**Winner**: `<borehole-detail-profile>` (distance 0 beats distance 1)

### If No Specific Profile Exists

```turtle
<result2> a ex:SampleSearchResult .  # No specific profile defined
```

| Profile | matchClass | constraint_distance | Notes |
|---------|------------|---------------------|-------|
| `<search-profile>` | `prez:SearchResult` | 1 | Superclass match |

**Winner**: `<search-profile>` (only match available)

## Risks and Mitigations

### Risk 1: rdfs:Resource Over-Matching

**Risk**: If someone declares:
```turtle
<generic-profile> altr-ext:constrainsClass rdfs:Resource .
```

And the graph contains:
```turtle
ex:MyClass rdfs:subClassOf rdfs:Resource .
```

This would match ALL resources (since everything is a subclass of `rdfs:Resource`).

**Likelihood**: Medium (only if `rdfs:subClassOf rdfs:Resource` is explicitly asserted)

**Mitigation Options**:
1. Document best practice: Don't constrain `rdfs:Resource` or `owl:Thing`
2. Add code filter to exclude `rdfs:Resource` from superclass matching
3. Accept the risk (user misconfiguration)

### Risk 2: Multiple Parent Classes

**Risk**: A class with multiple parents could match multiple profiles:
```turtle
ex:SpecialBorehole rdfs:subClassOf ex:Borehole, geo:Feature .
```

Profiles constraining either `ex:Borehole` OR `geo:Feature` would both match.

**Likelihood**: Medium

**Mitigation**: The ordering logic already handles this - the query will return both, and the first (by ORDER BY) wins. This is existing behavior, just more likely now.

### Risk 3: Breaking Change

**Risk**: Existing deployments might have intentionally scoped profiles to exact classes.

**Likelihood**: Low (most users would benefit from the new behavior)

**Mitigation**:
- Version this change appropriately
- Document in release notes
- Consider a config flag `ENABLE_PROFILE_SUBCLASS_MATCHING` (defaults to true for new installs)

### Risk 4: Performance Impact

**Risk**: Adding the UNION and extra join could slow down profile selection.

**Likelihood**: Low (single-hop `rdfs:subClassOf` is cheap, no transitive closure)

**Mitigation**: The query already does transitive closure for validation (lines 348-349), so this adds minimal overhead.

## Implementation Checklist

- [ ] Update `_compose_select_query()` in `prez/services/connegp_service.py`
- [ ] Add `?constraint_distance` UNION logic
- [ ] Update ORDER BY clause to include `ASC(?constraint_distance)`
- [ ] Update GROUP BY to include `?constraint_distance`
- [ ] Add unit tests for subclass matching scenarios
- [ ] Add integration tests for multi-level scenarios
- [ ] Test edge cases (rdfs:Resource, multiple parents)
- [ ] Update documentation
- [ ] Add release notes entry

## Alternative Approaches Considered

### Alternative 1: Transitive Closure (Rejected)

Use `rdfs:subClassOf*` to match any ancestor class:
```sparql
?class rdfs:subClassOf* ?matchClass .
?profile altr-ext:constrainsClass ?matchClass ;
```

**Rejected because**:
- Unpredictable in deep hierarchies
- Performance concerns with transitive closure
- Could match overly generic profiles

### Alternative 2: Explicit Opt-In (Possible Enhancement)

Add a property like `altr-ext:constrainsClassHierarchy true` to enable subclass matching per profile.

**Could add later if needed**, but max-distance=1 is conservative enough to enable by default.

### Alternative 3: Configurable Max Distance (Future Work)

Allow configuration of max hops (0, 1, 2, or unlimited).

**Deferred**: Start with hard-coded 1, make configurable if use cases emerge.

## Questions and Open Issues

1. Should we filter out `rdfs:Resource` and `owl:Thing` from superclass matching?
2. Should this be a configurable feature flag?
3. Do we need to update the debug table output in `_do_query()` to show constraint distance?

## References

- `prez/services/connegp_service.py` lines 320-368
- W3C PROF Conneg-by-AP: https://w3c.github.io/dx-connegp/connegp/
- Related: Endpoint class selection uses `rdfs:subClassOf*` for focus node selection

---

## Implementation Notes

### Configuration

The feature is configured via the `profile_constraint_max_distance` setting in `prez/config.py`.

**Environment Variable:**
```bash
PROFILE_CONSTRAINT_MAX_DISTANCE="1"  # Default
```

**In Code:**
```python
from prez.config import settings
distance = settings.profile_constraint_max_distance
```

**Valid Values:**
- `0` - Exact match only (reverts to original behavior, no superclass matching)
- `1` - Match resource class or its direct parent (DEFAULT, recommended)
- `2+` - Match N hops up the class hierarchy
- `-1` - Unlimited (match any ancestor via `rdfs:subClassOf*` transitive closure)

### Implementation Details

**Modified Files:**
1. `prez/config.py` - Added configuration field with validator
2. `prez/services/connegp_service.py` - Added helper method and modified SPARQL query
3. `.env-full-template` - Documented environment variable
4. `test_data/profile_subclass_test.ttl` - Test data for validation
5. `tests/test_connegp_subclass.py` - Comprehensive test suite

**SPARQL Query Changes:**
- Added `?constraint_distance` variable to track match precision
- Modified ORDER BY: `ASC(?constraint_distance)` ensures exact matches beat superclass matches
- Uses UNION pattern for distance 1-N, transitive closure for distance -1

**Debug Output:**
When `LOG_LEVEL=DEBUG`, the profile selection debug table includes a "Constraint Distance" column showing:
- `0` = exact match
- `1+` = N-hop superclass match

### Best Practices

#### 1. Avoid Over-General Constraints

**DO NOT** constrain overly broad classes when distance > 0:
```turtle
# ❌ BAD: Will match ALL resources if rdfs:subClassOf relations exist
<generic-profile> altr-ext:constrainsClass rdfs:Resource .
<generic-profile> altr-ext:constrainsClass owl:Thing .
```

**Instead:**
```turtle
# ✓ GOOD: Constrain specific domain classes
<sample-profile> altr-ext:constrainsClass sosa:Sample .
<feature-profile> altr-ext:constrainsClass geo:Feature .
```

#### 2. Distance Recommendations

| Use Case | Recommended Distance | Rationale |
|----------|---------------------|-----------|
| Strict type safety | `0` | Only exact matches, no surprises |
| Common subclassing | `1` (default) | Handles single-level hierarchies (e.g., `sosa:Sample` → specific sample types) |
| Deep domain hierarchies | `2-3` | Biological taxonomies, complex class structures |
| Catch-all fallback | `-1` | Use sparingly, can match overly generic profiles |

#### 3. Profile Design Strategy

**Layered Approach:**
1. Create **specific profiles** for concrete classes you control:
   ```turtle
   <diamond-drill-core-profile> altr-ext:constrainsClass ex:DiamondDrillCoreSample .
   ```

2. Create **generic profiles** for abstract base classes:
   ```turtle
   <sample-profile> altr-ext:constrainsClass sosa:Sample .
   ```

3. Rely on the ORDER BY logic to prioritize specific over generic:
   - `ASC(?constraint_distance)` ensures exact matches win
   - Users can override with `?_profile=` query parameter

### Performance Considerations

**Distance 0-3:** Minimal overhead
- Uses property path quantifiers (`rdfs:subClassOf{N}`)
- No transitive closure computation
- Query planner can optimize fixed-length paths

**Distance -1 (Unlimited):** Potential performance impact
- Uses transitive closure (`rdfs:subClassOf*`)
- May be slower on large ontologies with deep hierarchies
- Consider materializing class hierarchies in SPARQL engine
- Monitor query response times if using unlimited distance

**Optimization Tips:**
- Use distance=1 for most use cases (good balance)
- Reserve distance=-1 for small datasets or where needed
- Profile SPARQL query performance with your specific data

### Troubleshooting

#### Profile Not Matching

**Symptom:** Expected profile doesn't match a subclass resource

**Diagnosis:**
1. Check `profile_constraint_max_distance` setting
2. Count hops: How many `rdfs:subClassOf` steps between resource class and constrained class?
3. Enable debug logging: `LOG_LEVEL=DEBUG` to see constraint distance values

**Solutions:**
- Increase `profile_constraint_max_distance` if hierarchy is deeper than configured
- Verify `rdfs:subClassOf` relations exist in your ontology
- Check that profile uses `altr-ext:constrainsClass` (not `sh:targetClass`)

#### Wrong Profile Selected

**Symptom:** Generic profile matches instead of specific one

**Diagnosis:**
1. Check if specific profile exists for resource class
2. Verify specific profile has correct `altr-ext:constrainsClass`
3. Review debug output to see all matches and constraint distances

**Solutions:**
- Ensure specific profile is loaded in system graph
- Verify profile is correct type (`prez:ObjectProfile` vs `prez:ListingProfile`)
- Check if requested profile via `?_profile=` parameter is overriding

#### Performance Degradation

**Symptom:** Slow profile selection with distance=-1

**Diagnosis:**
1. Check ontology size and hierarchy depth
2. Profile SPARQL query execution time
3. Examine transitive closure computation

**Solutions:**
- Use distance=1-3 instead of -1 if possible
- Materialize class hierarchies in triplestore
- Consider caching profile selections
- Add indexes on `rdfs:subClassOf` predicate

### Migration from Previous Behavior

**Previous Behavior (Before Implementation):**
- Profiles required **exact match** on `altr-ext:constrainsClass`
- No subclass matching capability
- Users had to explicitly list all subclasses

**New Behavior (Default distance=1):**
- Profiles match resource class OR its direct parent
- Exact matches prioritized over parent matches
- Reduces configuration verbosity

**Breaking Changes:** NONE
- Default distance=1 is backwards compatible
- Existing exact-match profiles continue to work
- Exact matches always win over superclass matches

**To Revert to Old Behavior:**
```bash
PROFILE_CONSTRAINT_MAX_DISTANCE="0"
```

### Examples

#### Example 1: Search Results

**Scenario:** 20 different search result subclasses, one generic profile

**Before:**
```turtle
<search-profile> altr-ext:constrainsClass
    prez:BoreholeSearchResult,
    prez:SampleSearchResult,
    prez:ReportSearchResult,
    # ... 17 more classes
```

**After (with distance=1):**
```turtle
<search-profile> altr-ext:constrainsClass prez:SearchResult .
```

All 20 subclasses automatically match via 1-hop parent relationship.

#### Example 2: Specific Override

**Scenario:** Generic sample profile, but special handling for drill cores

**Profiles:**
```turtle
<sample-profile> altr-ext:constrainsClass sosa:Sample .
<drill-core-profile> altr-ext:constrainsClass ex:DiamondDrillCoreSample .
```

**Behavior:**
- `ex:DiamondDrillCoreSample` resource → matches `drill-core-profile` (exact, distance=0) ✓
- `ex:RockChipSample` resource → matches `sample-profile` (1-hop parent, distance=1) ✓

Specific profile wins due to `ASC(?constraint_distance)` in ORDER BY.

### Testing

Comprehensive tests are available in `tests/test_connegp_subclass.py`:
- Distance=0 (exact match only)
- Distance=1 (single-hop, default)
- Distance=2+ (multi-hop)
- Distance=-1 (unlimited)
- Priority: exact beats superclass
- Configuration validation
- Backwards compatibility

Run tests:
```bash
pytest tests/test_connegp_subclass.py -v
```

### Future Enhancements

Potential future work:
1. **Per-profile distance override:** Allow individual profiles to specify their own max distance
2. **Performance metrics:** Add instrumentation to track profile selection time
3. **Admin UI:** Visualize class hierarchies and profile matching logic
4. **Query optimization:** Cache transitive closures for distance=-1

### Questions Resolved

**1. Should we filter out `rdfs:Resource` and `owl:Thing` from superclass matching?**
- **Decision:** Document best practice only, no code filter
- **Rationale:** Users would need to (1) define profile constraining these broad classes AND (2) have the relations in their graph. Very unlikely by accident.

**2. Should this be a configurable feature flag?**
- **Decision:** No feature flag, always enabled with distance=0 as "disabled" state
- **Rationale:** Simpler config model, backwards compatible by default

**3. Do we need to update the debug table output?**
- **Decision:** Yes, implemented
- **Rationale:** Essential for troubleshooting and understanding profile selection