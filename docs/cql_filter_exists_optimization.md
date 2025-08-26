# CQL Filter EXISTS Optimization Plan

## Objective
Optimize CQL query performance by extracting `?focus_node` subject triples outside of FILTER EXISTS clauses while preserving logical semantics and maintaining the existing recursive structure.

## Current State
- Single FILTER EXISTS wrapper around entire combined pattern at top level
- FILTER NOT EXISTS used at various nesting levels for `NOT` operators
- All patterns (focus_node and non-focus_node) wrapped together in one FILTER EXISTS

## Proposed Changes

### Core Principle
At **each logical level**:
1. **Extract `?focus_node` subject triples** (property bindings only) to current level
2. **Put everything else into FILTER EXISTS** at that level:
   - Non-focus_node subject triples  
   - ALL FILTER statements
   - VALUES clauses
   - Nested logical structures

### Pattern Structure
```sparql
# Level N: Focus_node property bindings
?focus_node :property1 ?var1 .
?focus_node :property2 ?var2 .

# Level N: FILTER EXISTS containing everything else
FILTER EXISTS {
  # Non-focus_node triples
  ?var1 :someRelation ?other .
  
  # ALL filters and constraints
  FILTER(?var1 = "value") .
  VALUES ?var2 { "option1" "option2" }
  
  # Nested FILTER EXISTS for deeper levels
  FILTER EXISTS {
    # Next level patterns...
  }
}
```

### Implementation Approach
1. **Mirror existing FILTER NOT EXISTS pattern** - use similar recursive structure
2. **Modify logical operator handlers** (`_handle_and_operator`, `_handle_or_operator`) 
3. **At each level**: separate focus_node triples from other patterns
4. **Create nested FILTER EXISTS** for non-focus_node patterns + filters
5. **Preserve CQL logical structure** - no semantic changes

### Key Constraints
- **FILTER NOT EXISTS remains unchanged** (negation semantics must be preserved)
- **No selectivity analysis** - keep it structural and simple
- **Mirror CQL nesting structure** - avoid complex query rewriting

## Expected Benefits
- **Performance improvement** - focus_node property bindings available early for query optimization
- **Semantic preservation** - logical structure maintained at each level
- **Consistent with existing patterns** - follows established FILTER NOT EXISTS approach