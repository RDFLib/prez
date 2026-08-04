# ODRL Agreement presentation profile prototype

The exploratory `odrl-agreement` object profile presents an `odrl:Agreement` and each linked, named `odrl:Permission` as a nested RDF subgraph. It is generic ODRL support; none of its paths depend on ATNS predicates or identifiers. It lives under `examples/profiles` and is not loaded as a built-in Prez profile.

## Comparable Prez patterns

This spike combines mechanisms which already exist elsewhere in Prez:

- `test_data/animal_profiles.ttl` uses sequence paths plus `pathAlias` to make deliberately flattened facet values. That is the useful counterexample for ODRL, where flattening would discard rule membership.
- `tests/test_property_selection_shacl.py` already verifies that an unaliased sequence such as `( prov:qualifiedDerivation prov:hadRole )` emits the intermediate triples in the CONSTRUCT graph. A named Permission is the same qualified-relation pattern.
- The open-object and OGC profiles use `shext:bNodeDepth` for blank-node expansion. It is not applicable here because a Permission is intentionally a named resource.
- Existing annotated response processing supplies `prez:label` for IRIs after the profile query; the ODRL spike reuses that rather than inventing an ODRL-specific label property.

## Why the profile uses sequence paths without aliases

Paths such as `( odrl:permission odrl:target )` are sufficient to select the target and, with Prez's current profile query generator, reconstruct both triples in the response:

```turtle
<agreement> odrl:permission <permission-1> .
<permission-1> odrl:target <target-1> .
```

The same pattern is used for `rdf:type`, labels, action, assigner, assignee and target. Because the intermediate term is the original Permission IRI, two or more permissions remain separate and their values cannot be mixed up.

`shext:pathAlias` is intentionally absent. With `USE_PATH_ALIASES=true`, an alias on a sequence path changes the CONSTRUCT result into a direct Agreement predicate, for example `<agreement> <target-alias> <target-1>`. That flattened view loses which target belongs to which Permission. Aliases are useful for shortcut views, but not for this nested rule presentation.

## API shape consumed by PrezUI

The annotated Turtle response has the following significant structure (the JSON-LD response is an equivalent RDF graph):

```turtle
<agreement>
    a odrl:Agreement ;
    prez:label "Telstra Ngaanyatjarra ILUA — demonstration ODRL Agreement" ;
    odrl:permission <permission-access>, <permission-read> .

<permission-access>
    a odrl:Permission ;
    prez:label "Use of the Telstra Ngaanyatjarra ILUA agreement area" ;
    odrl:action odrl:use ;
    odrl:assigner <signatories> ;
    odrl:assignee <telstra> ;
    odrl:target <WI2004-006> .

odrl:use prez:label "Use" .
<signatories> prez:label "Ngaanyatjarra signatory parties" .
<telstra> prez:label "Telstra Corporation Limited" .
<WI2004-006> prez:label "Telstra Ngaanyatjarra ILUA registered area" .
```

Prez's annotated media types obtain `prez:label` values in a separate annotation query using the configured label predicates (`skos:prefLabel`, `dcterms:title`, `rdfs:label`, and `schema:name` by default). Consequently the profile selects Permission `schema:name` explicitly, while linked action, party, and target labels are handled by the existing annotation mechanism.

## Backend and UI responsibilities

No Prez backend change is needed for the nested Permission graph shown above: unaliased sequence paths already select and reconstruct named intermediate resources. PrezUI does need a presentation rule which recognizes `odrl:permission`, renders each object as a Permission panel, and places that Permission's action, assigner, assignee and target inside it.

A compact target geometry preview is separate functionality. The Agreement profile deliberately stops at the target IRI. Following `geo:hasGeometry` would couple a generic ODRL profile to one kind of Asset and can make responses large. PrezUI should link to the target and may fetch its normal resource/feature representation on demand for a preview.

## Named graphs

The Permission triples must be visible to the profile query in the repository's active/default graph, as they are in the IDN policy graph. Target labels in a separate named graph can be found by Prez's normal annotation query only when the SPARQL backend exposes named-graph triples through its default/union graph. The test fixture demonstrates both modes: flattening the dataset to a union default graph makes the normal profile query work, while an untouched Pyoxigraph dataset requires an explicit `GRAPH` query to find the target label. Prez does not currently emit an explicit `GRAPH ?g` traversal for profiles or annotations.

That union behavior is useful for a small label and link. Deep target expansion is neither required nor generally desirable. Supporting repositories whose default graph is not a union would require a Prez backend option/change to make annotation lookup graph-aware; it is not a PrezUI concern.
