# CQL Query Generation: sh:in-based FILTER vs VALUES Heuristic

**Date:** 2025-11-26
**Status:** Planned
**Motivation:** Performance optimization via SPARQL engine-specific optimizations

## Overview

This document outlines the plan to update CQL query generation to use a heuristic based on the presence of `sh:in` constraints in queryables to determine whether to generate FILTER or VALUES clauses.

## Current Behavior

Currently, both `=` (equals) and `IN` operators always generate VALUES clauses:

```sparql
# For CQL: color = "red"
?focus_node :color ?color .
VALUES ?color { "red" }

# For CQL: color IN ("red", "blue")
?focus_node :color ?color .
VALUES ?color { "red" "blue" }
```

**Issues with current approach:**
- Missing opportunity for SPARQL engine optimizations
- No differentiation between constrained vocabularies and open-ended properties

## New Heuristic

The new approach uses the presence of `sh:in` constraints in queryable definitions to determine query generation strategy:

### Decision Logic

1. **SHACL queryable WITH sh:in** → Generate `FILTER IN`
   - Rationale: SPARQL engines (Jena Fuseki, GraphDB) optimize FILTER IN differently than VALUES when dealing with controlled vocabularies
   - Use case: Queryables with constrained enumerations (sampling methods, feature types, etc.)

2. **SHACL queryable WITHOUT sh:in** → Generate `VALUES`
   - Rationale: Better performance for open-ended values where exact literal matching is appropriate
   - Use case: Free-text fields, unconstrained properties

3. **Direct predicate/property (NOT a queryable)** → Generate `VALUES`
   - Rationale: Default safe behavior for rare edge cases
   - Use case: Advanced users querying by direct predicates (requires knowledge of data model)
   - Note: If performance issues arise, recommend creating a queryable with sh:in constraint

### Example Outputs

**Queryable WITH sh:in (e.g., sampling method):**
```sparql
# Input: samplingMethod = "core_diamond"
?focus_node :samplingMethod ?sm .
FILTER(?sm IN (<http://pid.geoscience.gov.au/def/voc/ga/samplingmethod/core_diamond>))

# Input: samplingMethod IN ("core_diamond", "outcrop_sampling")
?focus_node :samplingMethod ?sm .
FILTER(?sm IN (
  <http://pid.geoscience.gov.au/def/voc/ga/samplingmethod/core_diamond>,
  <http://pid.geoscience.gov.au/def/voc/ga/samplingmethod/outcrop_sampling>
))
```

**Queryable WITHOUT sh:in (e.g., file parent):**
```sparql
# Input: fileParent = "some-parent-id"
?focus_node :fileParent ?parent .
VALUES ?parent { "some-parent-id" }
```

**Direct predicate (non-queryable):**
```sparql
# Input: rdf:type = ex:SomeClass
?focus_node rdf:type ?type .
VALUES ?type { ex:SomeClass }
```

## Implementation Plan

### Phase 1: Add sh:in Detection to PropertyShape

**File:** `prez/services/query_generation/shacl.py`

Add a property to the `PropertyShape` class to detect `sh:in` constraints:

```python
@property
def has_sh_in(self) -> bool:
    """Check if this PropertyShape has an sh:in constraint.

    Returns:
        bool: True if sh:in predicate exists on this shape, False otherwise.
    """
    from rdflib.namespace import SH

    try:
        sh_in_value = next(self.graph.objects(self.uri, SH["in"]), None)
        return sh_in_value is not None
    except Exception as e:
        logger.warning(
            f"Error checking for sh:in on {self.uri}: {e}. "
            "Defaulting to has_sh_in=False"
        )
        return False
```

**Rationale:**
- Follows existing pattern (similar to `minCount`, `maxCount` properties)
- Encapsulates logic within PropertyShape class (clean separation of concerns)
- Automatic caching via `@property` decorator
- Graceful error handling with safe default

**Location:** Add after line 248 (after `maxCount` property)

### Phase 2: Make _create_filter_in() Public

**File:** `prez/services/query_generation/grammar_helpers.py`

Rename `_create_filter_in()` to `create_filter_in()` and update to handle single values:

```python
def create_filter_in(variable: Var, values: list[str] | str) -> GraphPatternNotTriples:
    """Create a FILTER(?var IN (...)) constraint.

    Args:
        variable: The SPARQL variable to filter
        values: Single value or list of values to match against

    Returns:
        GraphPatternNotTriples containing the FILTER IN constraint
    """
    # Normalize to list
    if not isinstance(values, list):
        values = [values]

    # Convert values to appropriate RDF terms
    right_primary_expressions = []
    for value in values:
        rdf_term = convert_value_to_rdf_term(value)
        if isinstance(rdf_term, IRI):
            content = IRIOrFunction(iri=rdf_term)
        else:
            content = rdf_term
        right_primary_expressions.append(PrimaryExpression(content=content))

    in_expr = Expression.create_in_expression(
        left_primary_expression=PrimaryExpression(content=variable),
        operator="IN",
        right_primary_expressions=right_primary_expressions,
    )

    return GraphPatternNotTriples(
        content=Filter(
            constraint=Constraint(content=BrackettedExpression(expression=in_expr))
        )
    )
```

**Changes:**
- Rename from `_create_filter_in` to `create_filter_in` (remove underscore)
- Add handling for single values (for `=` operator)
- Update docstring

**Location:** Line 573 in `grammar_helpers.py`

### Phase 3: Update _handle_equals()

**File:** `prez/services/query_generation/cql.py`

Update the `_handle_equals()` method to use the heuristic:

```python
def _handle_equals(
    self,
    args: list[dict],
    existing_ggps: GroupGraphPatternSub | None = None,
):
    """Handle CQL equals operator using FILTER or VALUES based on sh:in heuristic.

    Heuristic:
    - SHACL queryable WITH sh:in → FILTER IN (SPARQL engine optimization)
    - SHACL queryable WITHOUT sh:in → VALUES (better for open-ended values)
    - Direct predicate (non-queryable) → VALUES (default behavior)
    """
    ggps, obj = self._add_tss_tssp(args, existing_ggps)
    prop = args[0].get("property")

    # Determine whether to use FILTER or VALUES
    use_filter = False
    if self.queryable_props and prop in self.queryable_props:
        # This is a SHACL queryable - check for sh:in
        property_shape = self.queryable_id_to_tssp(self.queryable_props[prop])
        if property_shape.has_sh_in:
            use_filter = True

    # Generate appropriate constraint
    if use_filter:
        filter_gpnt = create_filter_in(variable=obj, values=args[1])
        ggps.add_pattern(filter_gpnt)
    else:
        values_gpnt = create_values_constraint(variable=obj, values=[args[1]])
        ggps.add_pattern(values_gpnt)
```

**Key changes:**
- Check if property is a queryable
- If queryable, get PropertyShape and check `has_sh_in`
- Use `create_filter_in()` for queryables with sh:in
- Use `create_values_constraint()` otherwise
- Remove old TODO comment (issue now addressed)

**Location:** Replace lines 342-352

### Phase 4: Update _handle_in()

**File:** `prez/services/query_generation/cql.py`

Update the `_handle_in()` method with identical logic:

```python
def _handle_in(
    self,
    args: list[dict | list],
    existing_ggps: GroupGraphPatternSub | None = None
) -> None:
    """Handle CQL IN operator using FILTER or VALUES based on sh:in heuristic.

    Heuristic:
    - SHACL queryable WITH sh:in → FILTER IN (SPARQL engine optimization)
    - SHACL queryable WITHOUT sh:in → VALUES (better for open-ended values)
    - Direct predicate (non-queryable) → VALUES (default behavior)
    """
    ggps, obj = self._add_tss_tssp(args, existing_ggps)
    prop = args[0].get("property")

    # Determine whether to use FILTER or VALUES
    use_filter = False
    if self.queryable_props and prop in self.queryable_props:
        # This is a SHACL queryable - check for sh:in
        property_shape = self.queryable_id_to_tssp(self.queryable_props[prop])
        if property_shape.has_sh_in:
            use_filter = True

    # Generate appropriate constraint
    if use_filter:
        filter_gpnt = create_filter_in(variable=obj, values=args[1])
        ggps.add_pattern(filter_gpnt)
    else:
        values_clause_gpnt = create_values_constraint(obj, args[1])
        ggps.add_pattern(values_clause_gpnt)
```

**Location:** Replace lines 479-487

### Phase 5: Update Imports

**File:** `prez/services/query_generation/cql.py`

Add import for the newly public function:

```python
from prez.services.query_generation.grammar_helpers import (
    create_filter_in,  # Add this
    create_values_constraint,
    # ... other imports
)
```

**Location:** Around line 32-40 (import section)

## Testing Strategy

### Unit Tests

**File:** `tests/test_cql_queryable.py`

Add new test cases:

```python
def test_queryable_with_sh_in_generates_filter():
    """Test that queryables with sh:in use FILTER IN."""
    # Test with = operator
    cql_json = {
        "op": "=",
        "args": [
            {"property": "sm"},  # sampling method has sh:in
            "core_diamond"
        ]
    }
    parser = CQLParser(cql_json=cql_json, queryable_props=queryables_dict)
    parser.parse()
    sparql = parser.generate_sparql()

    assert "FILTER" in sparql
    assert "VALUES" not in sparql
    assert "IN" in sparql

def test_queryable_without_sh_in_generates_values():
    """Test that queryables without sh:in use VALUES."""
    cql_json = {
        "op": "=",
        "args": [
            {"property": "file-parent"},  # no sh:in
            "some-id"
        ]
    }
    parser = CQLParser(cql_json=cql_json, queryable_props=queryables_dict)
    parser.parse()
    sparql = parser.generate_sparql()

    assert "VALUES" in sparql
    assert "FILTER" not in sparql

def test_direct_predicate_generates_values():
    """Test that direct predicates (non-queryables) use VALUES."""
    cql_json = {
        "op": "=",
        "args": [
            {"property": "http://example.com/someProp"},
            "value"
        ]
    }
    parser = CQLParser(cql_json=cql_json, queryable_props={})
    parser.parse()
    sparql = parser.generate_sparql()

    assert "VALUES" in sparql
    assert "FILTER" not in sparql
```

### Integration Tests

Run existing test suites to ensure no regressions:
- `tests/test_cql.py` - Core CQL parsing tests
- `tests/test_cql_queryable.py` - Queryable-specific tests
- `tests/test_cql_time.py` - Temporal operator tests
- `tests/test_cql_spatial_graphdb.py` - Spatial tests

### Manual Testing

Test with real queryable definitions:
1. `/home/david/PycharmProjects/prez/queryables.ttl` - Sampling method (has sh:in)
2. `/home/david/PycharmProjects/prez/prez/reference_data/queryables/file_to_generic_parent.ttl` - File parent (no sh:in)

## Edge Cases

### Empty sh:in List

```turtle
<#Queryable> sh:in () .
```

**Behavior:** Treat as "has sh:in" (use FILTER)
**Rationale:** Intent is to constrain values (even if list is currently empty)

### Multiple sh:in Predicates

```turtle
<#Queryable> sh:in ( "a" "b" ) ;
             sh:in ( "c" "d" ) .
```

**Behavior:** Log warning, use first sh:in found, treat as "has sh:in"
**Rationale:** Invalid SHACL, but gracefully handle with warning

### RDF Graph Query Failure

**Behavior:** Default to `has_sh_in = False` (use VALUES)
**Rationale:** Safe fallback, log warning for debugging

### Queryable Not Found in System Graph

**Behavior:** Handled by existing code in `queryable_id_to_tssp()`
**No changes needed**

## Performance Considerations

### Caching

- `PropertyShape.has_sh_in` is a `@property`, computed once per instance
- PropertyShape instances are created per query (no cross-query caching)
- RDFlib graph queries are fast for single predicate lookups

### Query Performance Impact

**Expected improvements:**
- FILTER IN on constrained vocabularies: Better SPARQL engine optimization
- VALUES on open-ended properties: Maintains current performance

**Measurement approach:**
- Benchmark queries before/after on production-like data
- Monitor SPARQL endpoint query times
- Focus on queries with large result sets

## Migration Path

### Backward Compatibility

This change affects SPARQL query generation but maintains semantic correctness:
- Queries return the same results
- SPARQL syntax differs (FILTER vs VALUES)
- No API changes
- No configuration changes required

### Rollback Plan

If issues arise:
1. **Simple rollback:** Git revert the changes
2. **Feature flag option:** Add config flag to enable/disable heuristic
3. **Per-queryable override:** Add custom annotation to force FILTER or VALUES

## Future Enhancements

### Filter Ordering Optimization

As mentioned by the user, the next step after this implementation is to optimize the ordering of filters. This could involve:
- Executing FILTER constraints last (after VALUES bindings)
- Reordering graph patterns for optimal query execution
- See: Future doc on SPARQL query optimization strategies

### Performance Monitoring

Add telemetry to track:
- Query generation time
- SPARQL execution time by pattern type
- Cache hit rates

### Extended Heuristics

Potential future enhancements:
- Consider datatype (dates, booleans) in decision logic
- Consider cardinality (minCount/maxCount) for optimization hints
- Consider query complexity in decision

## References

- **Current issue:** `docs/cql_values_vs_filter_in_issue.md`
- **CQL specification:** [OGC API - Features - Part 3: CQL2](http://www.opengis.net/doc/IS/cql2/1.0)
- **SPARQL specification:** [W3C SPARQL 1.1](https://www.w3.org/TR/sparql11-query/)
- **SHACL specification:** [W3C SHACL](https://www.w3.org/TR/shacl/)

## Critical Files

1. `prez/services/query_generation/shacl.py` - Add `has_sh_in` property
2. `prez/services/query_generation/cql.py` - Update `_handle_equals()` and `_handle_in()`
3. `prez/services/query_generation/grammar_helpers.py` - Make `create_filter_in()` public
4. `tests/test_cql_queryable.py` - Add new test cases
5. `docs/cql_values_vs_filter_in_issue.md` - Mark as resolved by this work

## Approval & Next Steps

**Status:** Awaiting approval
**Estimated effort:** 11-16 hours (approximately 2 working days)
**Risk level:** Low (isolated changes, backward compatible, comprehensive testing)

Once approved:
1. Implement Phase 1-5 sequentially
2. Run full test suite
3. Manual validation with real queryables
4. Update documentation
5. Mark `docs/cql_values_vs_filter_in_issue.md` as resolved