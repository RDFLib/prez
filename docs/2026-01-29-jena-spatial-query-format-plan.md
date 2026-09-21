# Jena Spatial Query Format Update Plan

**Date:** 2026-01-29

## Summary

Update the "geosparql" spatial query generation for Jena/Fuseki to use triple patterns with BIND instead of FILTER functions.

## Scope

This change applies to **both**:
- **bbox query parameter** - bounding box spatial filtering
- **CQL spatial functions** - s_intersects, s_within, s_contains, etc.

Both use the same `generate_spatial_filter_clause()` function, so a single change covers all spatial operations.

## Current Implementation

The current "geosparql" target generates:
```sparql
?focus_node geo:hasGeometry ?geom_bnode .
?geom_bnode geo:asWKT ?geom_var .
FILTER(geof:sfIntersects(?geom_var, "<CRS> POLYGON(...)"^^geo:wktLiteral))
```

## Desired Implementation

Generate the Jena-compatible triple pattern form:
```sparql
?focus_node geo:hasGeometry ?geom_bnode .
?geom_bnode geo:asWKT ?geom_var .
BIND("<CRS> POLYGON(...)"^^geo:wktLiteral AS ?spatial_wkt_input)
?spatial_wkt_input geo:sfIntersects ?geom_var .
```

Key changes:
1. Replace `FILTER(geof:sfIntersects(...))` with `?spatial_wkt_input geo:sfIntersects ?geom_var .` triple pattern
2. Use `BIND` to assign the WKT literal to a variable
3. Use `geo:sfIntersects` predicate (from `http://www.opengis.net/ont/geosparql#`) instead of `geof:sfIntersects` function
4. All CQL spatial operators map to their corresponding `geo:` predicates (sfWithin, sfContains, etc.)

## Files to Modify

### 1. `prez/services/query_generation/spatial_filter.py`

**Function: `generate_spatial_filter_clause()` (lines 164-196)**

Replace the GeoSPARQL FILTER-based implementation with:

```python
if target_system == "geosparql":
    if cql_operator not in cql_sparql_spatial_mapping:
        raise NotImplementedError(
            f"CQL operator {cql_operator} not supported for GeoSPARQL"
        )

    # Get the geo: predicate (e.g., geo:sfIntersects)
    # Use cql_graphdb_spatial_properties which already maps to GEO namespace
    spatial_predicate = cql_graphdb_spatial_properties[cql_operator]

    # Create BIND clause: BIND("POLYGON(...)"^^geo:wktLiteral AS ?bbox_var)
    bbox_var = Var(value="bbox_spatial")
    bind_gpnt = GraphPatternNotTriples(
        content=Bind(
            expression=Expression.from_primary_expression(
                primary_expression=PrimaryExpression(
                    content=RDFLiteral(
                        value=wkt_value,
                        datatype=IRI(value=str(GEO.wktLiteral)),
                    )
                )
            ),
            var=bbox_var,
        )
    )

    # Create triple: ?bbox_var geo:sfIntersects ?geom_wkt_lit_var
    spatial_triple = TriplesBlock(
        triples=TriplesSameSubjectPath.from_spo(
            bbox_var,
            IRI(value=str(spatial_predicate)),
            geom_wkt_lit_var,
        )
    )
    spatial_gpnt = GraphPatternNotTriples(
        content=GroupOrUnionGraphPattern(
            group_graph_patterns=[
                GroupGraphPattern(
                    content=GroupGraphPatternSub(
                        graph_patterns_or_triples_blocks=[
                            TriplesBlock(triples=spatial_triple)
                        ]
                    )
                )
            ]
        )
    )

    return [bind_gpnt, spatial_gpnt]
```

**New imports needed in `spatial_filter.py`:**
```python
from sparql_grammar_pydantic import Bind
from prez.reference_data.cql.geo_function_mapping import cql_graphdb_spatial_properties
```

**Function: `generate_bbox_filter()` (lines 410-447)**

Update the geosparql branch to use the new triple pattern format (no additional changes needed as it calls `generate_spatial_filter_clause()`).

### 2. `prez/services/query_generation/cql.py`

**Function: `_handle_spatial()` (lines 503-513)**

The function already calls `generate_spatial_filter_clause()` for geosparql target, so no changes needed here beyond what's done in `spatial_filter.py`.

### 3. `prez/reference_data/cql/geo_function_mapping.py`

No changes needed - `cql_graphdb_spatial_properties` already maps CQL operators to `GEO.sfIntersects` etc.

## Implementation Details

### Variable Names
- Keep existing variable names for consistency:
  - `?focus_node` - the subject
  - `?geom_bnode` or `?geom_bnode_bbox` - geometry blank node
  - `?geom_var` or `?geom_var_bbox` - WKT literal from database
  - `?spatial_wkt_input` - new variable for BIND (the injected polygon/geometry)

### Namespace
- `geo:sfIntersects` uses `http://www.opengis.net/ont/geosparql#` (rdflib's `GEO`)
- NOT `geof:sfIntersects` which is `http://www.opengis.net/def/function/geosparql/`

### Other Spatial Operators
All CQL spatial operators should use the same pattern:
- `s_intersects` → `geo:sfIntersects`
- `s_within` → `geo:sfWithin`
- `s_contains` → `geo:sfContains`
- etc.

These mappings already exist in `cql_graphdb_spatial_properties`.

## Testing

1. Run existing spatial tests:
   ```bash
   pytest tests/test_cql_spatial_graphdb.py -v
   pytest tests/test_ogc_features_manual.py -v
   ```

2. Create new test for GeoSPARQL/Jena format verification:
   - Verify generated query contains `BIND(...^^geo:wktLiteral AS ?spatial_wkt_input)`
   - Verify generated query contains `?spatial_wkt_input geo:sfIntersects ?geom_var`
   - Verify no `FILTER(geof:sfIntersects(...))` in output

3. Manual test with Jena/Fuseki:
   - Deploy with spatial data
   - Test bbox query parameter
   - Test CQL spatial filter

## Verification

After implementation, verify the generated SPARQL matches:
```sparql
?focus_node geo:hasGeometry ?geom_bnode .
?geom_bnode geo:asWKT ?geom_var .
BIND("<CRS> POLYGON(...)"^^geo:wktLiteral AS ?spatial_wkt_input)
?spatial_wkt_input geo:sfIntersects ?geom_var .
```