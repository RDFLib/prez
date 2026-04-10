# Updating gswa-prez-config facet profiles to use Lucene facets

## Background

Prez now supports defining facet profiles that target the Jena Lucene index directly, bypassing the old SPARQL-based `sh:property / sh:union` path-walking approach. Instead of describing SHACL property paths, a facet profile simply references the Lucene **field IRIs** already defined in the Fuseki `config.ttl`.

This is faster (Lucene does the facet counting natively) and avoids maintaining the complex path unions that duplicate knowledge already captured in the index configuration.

## New predicates

Add these prefixes to each profile file:

```turtle
@prefix luc:   <https://prez.dev/jena-lucene/> .
@prefix field: <urn:jena:lucene:field#> .
```

Then replace the `sh:property [ sh:path [ sh:union (...) ] ]` block with:

- **`luc:flatFacets`** — for simple category facets (one triple per field IRI)
- **`luc:rangeFacets`** — for numeric/date range facets (blank node with `luc:field` + `luc:bucketBoundaries`)

## Field IRI reference

Current facetable fields in the index (`idx:facetable true` in config.ttl):

| field IRI                    | idx:fieldName        |
|------------------------------|----------------------|
| `field:entityType`           | entityType           |
| `field:identifierType`       | identifierType       |
| `field:identifierValueExact` | identifierValueExact |
| `field:status`               | status               |
| `field:targetCommodity`      | targetCommodity      |
| `field:about`                | about                |
| `field:distribution`         | distribution         |
| `field:partOf`               | partOf               |
| `field:dataType`             | dataType             |
| `field:sourceSystem`         | sourceSystem         |
| `field:additionalType`       | additionalType       |
| `field:subType`              | subType              |
| `field:category`             | category             |
| `field:relationshipTab`      | relationshipTab      |

## Migration examples

### Simple single-facet profile

**Old format** (commodity.ttl):
```turtle
<https://prez.dev/profile/commodity>
    a prof:Profile, prez:ListingProfile, prez:ObjectProfile ;
    dcterms:identifier "commodity"^^xsd:token ;
    dcterms:title "Facet on commodity" ;
    sh:property [
        sh:path [
            sh:union (
                [ sh:path gswa:hasTargetCommodity ;
                  shext:pathAlias label:commodity ]
            )
        ]
    ] .
```

**New format**:
```turtle
@prefix luc:   <https://prez.dev/jena-lucene/> .
@prefix field: <urn:jena:lucene:field#> .

<https://prez.dev/profile/commodity>
    a prof:Profile, prez:ListingProfile, prez:ObjectProfile ;
    dcterms:identifier "commodity"^^xsd:token ;
    dcterms:title "Facet on commodity" ;
    luc:flatFacets field:targetCommodity .
```

### Multi-facet profile

**Old format** (filter_facet.ttl — many path unions):
```turtle
<https://prez.dev/profile/filter-facet>
    sh:property [
        sh:path [
            sh:union (
                [ sh:path schema:additionalType ; shext:pathAlias label:reportType ]
                ...many path variants for reportType...
                [ sh:path gswa:sourceSystem ; shext:pathAlias label:sourceSystem ]
                [ sh:path gswa:hasDisplayTable ; shext:pathAlias label:dataType ]
                ...data format paths...
                ...commodity paths...
            )
        ]
    ] .
```

**New format**:
```turtle
<https://prez.dev/profile/filter-facet>
    a prof:Profile, prez:ListingProfile, prez:ObjectProfile ;
    dcterms:identifier "filter-facet"^^xsd:token ;
    dcterms:title "Facet on filter facet" ;
    luc:flatFacets
        field:additionalType ,  # was reportType
        field:sourceSystem ,    # was sourceSystem
        field:dataType ,        # was dataType / data-type
        field:distribution ,    # was dataFormat / data-format
        field:targetCommodity . # was commodity
```

### Range facet example (if needed for numeric/date fields)

```turtle
<https://prez.dev/profile/date-range>
    a prof:Profile, prez:ListingProfile, prez:ObjectProfile ;
    dcterms:identifier "date-range"^^xsd:token ;
    luc:rangeFacets [
        luc:field field:dateCreated ;
        luc:bucketBoundaries "[null, 2020, 2022, 2024, null]"
    ] .
```

## Mapping: old pathAlias → Lucene field

| Old shext:pathAlias          | → Lucene field IRI      | Notes                                                    |
|------------------------------|-------------------------|----------------------------------------------------------|
| `label:commodity`            | `field:targetCommodity` | All hasTargetCommodity / hasCommodity path variants       |
| `label:reportType`           | `field:additionalType`  | schema:additionalType + dcterms:type variants             |
| `label:sourceSystem`         | `field:sourceSystem`    | Direct                                                    |
| `label:dataType`             | `field:dataType`        | gswa:hasDisplayTable                                      |
| `label:data-type`            | `field:dataType`        | Same as above                                             |
| `label:data-format`          | `field:distribution`    | All the dcat:mediaType path variants                      |
| `label:report-types`         | `field:additionalType`  | dcterms:type path variants (subset of reportType)         |
| `label:Type` (site_object)   | `field:entityType`      | rdf:type                                                  |
| `label:WellLogFacet`         | *(no direct field)*     | May need a new Lucene field in config.ttl if still needed |
| `label:ResourceFormat`       | `field:distribution`    | altr-ext:hasResourceFormat                                |
| `label:SampleOf`             | `field:sampleOf`        | `[ sh:inversePath sosa:isSampleOf ] / rdf:type` (note: `field:sampleOf` must have `idx:facetable true` added to config.ttl before this works) |

## Per-file update summary

| File               | Replace `sh:property` block with                                                                   |
|--------------------|----------------------------------------------------------------------------------------------------|
| `commodity.ttl`    | `luc:flatFacets field:targetCommodity .`                                                           |
| `data_format.ttl`  | `luc:flatFacets field:distribution .`                                                              |
| `data_type.ttl`    | `luc:flatFacets field:dataType .`                                                                  |
| `display_table.ttl`| `luc:flatFacets field:dataType .`                                                                  |
| `report_types.ttl` | `luc:flatFacets field:additionalType .`                                                            |
| `type.ttl`         | `luc:flatFacets field:entityType .`                                                                |
| `sample_of.ttl`    | `luc:flatFacets field:sampleOf .` ⚠️ Requires adding `idx:facetable true` to `field:sampleOf` in config.ttl first |
| `site_object.ttl`  | `luc:flatFacets field:entityType, field:distribution .` (check if WellLogFacet needs its own field)|
| `filter_facet.ttl` | `luc:flatFacets field:additionalType, field:sourceSystem, field:dataType, field:distribution, field:targetCommodity .` |

## Notes

- Remove the `shext:` prefix and all `shext:pathAlias` triples — no longer needed.
- Add `@prefix field:` and `@prefix luc:` to each file.
- The old `sh:property` format still works for non-Lucene SPARQL-based faceting. Prez auto-detects: if a profile has `luc:flatFacets`/`luc:rangeFacets`, it uses Lucene native faceting; otherwise it falls back to the SPARQL union path.
- **WellLogFacet** in `site_object.ttl` has no matching facetable Lucene field for `gswa:hasWellLog`. If still needed, add a corresponding field to `config.ttl` with `idx:facetable true`.
- `luc:flatFacets` and `luc:rangeFacets` can coexist on the same profile.
