# Prez namespace audit

Generated at `2026-10-05T02:19:26+00:00` by `tools/audit_prez_namespace.py`.

This is an evidence inventory, not a canonical ontology. It records observed Prez IRIs and separates textual occurrences from RDF-role evidence. A term being observed, labelled, or typed does not by itself make its semantics normative.

## Scope

| Group | Scan root |
| --- | --- |
| BDR | `/Users/leskneebone/Projects/BDR` |
| IDN | `/Users/leskneebone/Projects/IDN` |
| Kurrawong | `/Users/leskneebone/Projects/Kurrawong` |

The scan inspected **14,947 files** in **62 Git repositories**, parsed **5,537 RDF files**, and observed **240 distinct Prez IRIs**.

Excluded directories include `.git`, dependency trees, virtual environments, caches, build outputs, and coverage outputs. Remaining files are classified as production, test, example, documentation, or generated evidence. The scanner is deliberately tolerant: RDF parse failures retain text evidence but cannot contribute RDF-role evidence.

## Reproduce

```shell
poetry run python tools/audit_prez_namespace.py \
  --root BDR=/Users/leskneebone/Projects/BDR --root IDN=/Users/leskneebone/Projects/IDN --root Kurrawong=/Users/leskneebone/Projects/Kurrawong \
  --output-directory docs/namespace-audit
```

## Definition status

Statuses are evidence levels: `observed` means usage only; `labelled` adds a recognised label; `described` adds a recognised description; and `typed` means the term is the subject of at least one `rdf:type` statement. `typed` does not imply that the type or semantics are correct.

| Status | Terms |
| --- | --- |
| typed | 83 |
| described | 0 |
| labelled | 26 |
| observed | 131 |

## Namespace areas

| Area | Terms |
| --- | --- |
| root namespace | 122 |
| configuration ontology | 44 |
| profile identifier | 25 |
| manifest resource roles | 16 |
| endpoint identifier | 14 |
| other Prez path | 14 |
| Jena Lucene configuration | 4 |
| manifest version types | 1 |

## Repository footprint

The count below is the number of distinct observed terms associated with each repository, not the number of occurrences.

| Repository | Distinct terms |
| --- | --- |
| Kurrawong/prez | 123 |
| IDN/prez-lite | 69 |
| Kurrawong/prez-lite | 68 |
| Kurrawong/semantic-background | 44 |
| Kurrawong/prezmanifest | 34 |
| BDR/eiatest-catalogue | 26 |
| Kurrawong/prez-ui | 26 |
| IDN/idn-prez4 | 23 |
| Kurrawong/docs | 20 |
| BDR/resources.bdr.gov.au-config | 18 |
| IDN/atns-preservation | 12 |
| BDR/bdr-reference-data-sync | 8 |
| IDN/briscoesmith | 8 |
| IDN/indigenous-data-catalogue | 8 |
| IDN/reference-resource-register | 7 |
| IDN/anufncatalogue | 6 |
| IDN/demo-catalogue | 5 |
| IDN/isu-catalogue | 5 |
| IDN/kp-catalogue | 5 |
| Kurrawong/ated | 5 |
| Kurrawong/demo-vocabs | 5 |
| Kurrawong/detsi-vocabs | 5 |
| Kurrawong/labelify | 5 |
| BDR/resources.bdr.gov.au-data | 4 |
| Kurrawong/ecass-etl | 1 |

## Priority definition gaps

These terms occur in files classified as production but have no recognised RDF type, label, or description in the scanned RDF. They are candidates for review, not automatic ontology additions.

| IRI | Kind evidence | Production files | Repositories | All files |
| --- | --- | --- | --- | --- |
| <https://prez.dev/ObjectProfile> | class candidate | 16 | 8 | 40 |
| <https://prez.dev/ont/ListingEndpoint> | class candidate | 10 | 7 | 15 |
| <https://prez.dev/ont/ObjectEndpoint> | class candidate | 10 | 7 | 15 |
| <https://prez.dev/ListingProfile> | class candidate | 10 | 6 | 21 |
| <https://prez.dev/SearchResult> | class candidate | 10 | 5 | 19 |
| <https://prez.dev/ont/hierarchyLevel> | property candidate | 9 | 6 | 14 |
| <https://prez.dev/ont/relevantShapes> | property candidate | 9 | 6 | 13 |
| <https://prez.dev/CQLFilterResult> | resource | 8 | 6 | 10 |
| <https://prez.dev/ont/apiPath> | property candidate | 7 | 7 | 11 |
| <https://prez.dev/IndexProfile> | class candidate | 7 | 4 | 7 |
| <https://prez.dev/ont/DynamicEndpoint> | class candidate | 6 | 6 | 10 |
| <https://prez.dev/CatPrez> | resource | 5 | 4 | 5 |
| <https://prez.dev/label> | property candidate | 5 | 4 | 1065 |
| <https://prez.dev/Catalog> | class candidate | 5 | 2 | 17 |
| <https://prez.dev/descriptionSource> | property candidate | 5 | 2 | 25 |
| <https://prez.dev/generateDescription> | property candidate | 5 | 2 | 23 |
| <https://prez.dev/generateIdentifier> | property candidate | 5 | 2 | 19 |
| <https://prez.dev/generateLabel> | property candidate | 5 | 2 | 23 |
| <https://prez.dev/labelSource> | property candidate | 5 | 2 | 25 |
| <https://prez.dev/linkTemplate> | property candidate | 5 | 2 | 17 |
| <https://prez.dev/FocusNode> | resource | 4 | 4 | 1046 |
| <https://prez.dev/description> | property candidate | 4 | 4 | 1053 |
| <https://prez.dev/SPARQLQuery> | resource | 4 | 2 | 4 |
| <https://prez.dev/catalog> | property candidate | 4 | 2 | 16 |
| <https://prez.dev/generateFocusNode> | property candidate | 4 | 2 | 18 |
| <https://prez.dev/generateLink> | property candidate | 4 | 2 | 18 |
| <https://prez.dev/generateMembers> | property candidate | 4 | 2 | 18 |
| <https://prez.dev/membersTemplate> | property candidate | 4 | 2 | 12 |
| <https://prez.dev/ont/JenaFTSPropertyShape> | class candidate | 4 | 2 | 6 |
| <https://prez.dev/simpleView> | property candidate | 4 | 2 | 6 |
| <https://prez.dev/ont/OGCFeaturesEndpoint> | class candidate | 3 | 3 | 4 |
| <https://prez.dev/provenance> | property candidate | 2 | 4 | 454 |
| <https://prez.dev/SystemGraph> | resource | 2 | 3 | 4 |
| <https://prez.dev/identifier> | property candidate | 2 | 3 | 1049 |
| <https://prez.dev/type> | property candidate | 2 | 3 | 1043 |
| <https://prez.dev/ProfilesGraph> | resource | 2 | 2 | 2 |
| <https://prez.dev/WorkspaceConfig> | class candidate | 2 | 2 | 4 |
| <https://prez.dev/generateProvenance> | property candidate | 2 | 2 | 14 |
| <https://prez.dev/icon> | property candidate | 2 | 2 | 4 |
| <https://prez.dev/ont/SystemEndpoint> | class candidate | 2 | 2 | 2 |
| <https://prez.dev/provenanceSource> | property candidate | 2 | 2 | 10 |
| <https://prez.dev/refreshFrom> | property candidate | 2 | 2 | 4 |
| <https://prez.dev/searchResultURI> | property candidate | 2 | 2 | 11 |
| <https://prez.dev/slug> | property candidate | 2 | 2 | 4 |
| <https://prez.dev/sourcePredicate> | resource | 2 | 2 | 6 |
| <https://prez.dev/sync> | property candidate | 2 | 2 | 3 |
| <https://prez.dev/workspace> | property candidate | 2 | 2 | 4 |
| <https://prez.dev/Object> | resource | 2 | 1 | 2 |
| <https://prez.dev/ont/JenaFTSUnionShape> | resource | 2 | 1 | 3 |
| <https://prez.dev/systemGraph> | resource | 2 | 1 | 2 |

## Complete inventory

| IRI | Area | Kind evidence | Status | Files | Repos | Prod | Test | Example | Docs | Generated |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <https://prez.dev/AltProfilesList> | root namespace | resource | observed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/AtnsEntityProfile> | root namespace | profile; node shape | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/CQLFilterResult> | root namespace | resource | observed | 10 | 6 | 8 | 0 | 2 | 0 | 0 |
| <https://prez.dev/CSV> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/CatPrez> | root namespace | resource | observed | 5 | 4 | 5 | 0 | 0 | 0 | 0 |
| <https://prez.dev/Catalog> | root namespace | class candidate | observed | 17 | 2 | 5 | 2 | 8 | 2 | 0 |
| <https://prez.dev/CatalogList> | root namespace | resource | labelled | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ConceptSchemeDefault> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/ConceptSchemeProfile> | root namespace | resource | observed | 3 | 2 | 1 | 0 | 0 | 2 | 0 |
| <https://prez.dev/ConceptSchemesListProfile> | root namespace | profile; node shape | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/CustomCQLListProfile> | root namespace | profile | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/CustomFeatureListProfile> | root namespace | profile; node shape | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/CustomFeatureObjectProfile> | root namespace | profile; node shape | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/CustomIndexProfile> | root namespace | profile | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/DatasetList> | root namespace | resource | labelled | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/DefaultConceptProfile> | root namespace | profile; node shape | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/DefaultProfile> | root namespace | profile | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/DefaultSchemeProfile> | root namespace | profile; node shape | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/FacetProfile> | root namespace | profile; node shape | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/FeatureCollectionList> | root namespace | resource | labelled | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/FeatureList> | root namespace | resource | labelled | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/FocusNode> | root namespace | resource | observed | 1046 | 4 | 4 | 0 | 962 | 1 | 79 |
| <https://prez.dev/GAVocabListProfile> | root namespace | profile | typed | 2 | 2 | 0 | 0 | 2 | 0 | 0 |
| <https://prez.dev/GAVocabsProfile> | root namespace | profile | typed | 2 | 2 | 0 | 0 | 2 | 0 | 0 |
| <https://prez.dev/GGICVocabsProfile> | root namespace | profile | typed | 2 | 2 | 0 | 0 | 2 | 0 | 0 |
| <https://prez.dev/GSWAVocabsProfile> | root namespace | profile | typed | 4 | 2 | 2 | 0 | 2 | 0 | 0 |
| <https://prez.dev/IndexProfile> | root namespace | class candidate | observed | 7 | 4 | 7 | 0 | 0 | 0 | 0 |
| <https://prez.dev/JSON> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/JSONLD> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/ListingProfile> | root namespace | class candidate | observed | 21 | 6 | 10 | 6 | 2 | 3 | 0 |
| <https://prez.dev/Manifest> | root namespace | class | typed | 91 | 17 | 40 | 38 | 5 | 6 | 2 |
| <https://prez.dev/ManifestResourceRoles> | root namespace | resource | typed | 6 | 3 | 4 | 0 | 0 | 2 | 0 |
| <https://prez.dev/ManifestResourceRoles/1.0.0> | manifest resource roles | resource | labelled | 3 | 3 | 2 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestResourceRoles/CatalogueAndResourceModel> | manifest resource roles | concept | typed | 45 | 12 | 15 | 20 | 0 | 10 | 0 |
| <https://prez.dev/ManifestResourceRoles/CatalogueData> | manifest resource roles | concept | typed | 81 | 17 | 31 | 32 | 3 | 13 | 2 |
| <https://prez.dev/ManifestResourceRoles/CatalogueModel> | manifest resource roles | concept | typed | 4 | 4 | 3 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestResourceRoles/CompleteCatalogueAndResourceLabels> | manifest resource roles | concept | typed | 48 | 12 | 14 | 23 | 0 | 9 | 2 |
| <https://prez.dev/ManifestResourceRoles/CompleteContainerAndContentLabels> | manifest resource roles | resource | observed | 2 | 1 | 1 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestResourceRoles/ContainerAndContentModel> | manifest resource roles | resource | observed | 2 | 1 | 1 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestResourceRoles/ContainerData> | manifest resource roles | resource | observed | 2 | 1 | 1 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestResourceRoles/ContainerModel> | manifest resource roles | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestResourceRoles/ContentData> | manifest resource roles | resource | observed | 2 | 1 | 1 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestResourceRoles/ContentModel> | manifest resource roles | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestResourceRoles/IncompleteCatalogueAndResourceLabels> | manifest resource roles | concept | typed | 39 | 12 | 26 | 3 | 4 | 6 | 0 |
| <https://prez.dev/ManifestResourceRoles/IncompleteContainerAndContentLabels> | manifest resource roles | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestResourceRoles/ResourceData> | manifest resource roles | concept | typed | 95 | 17 | 34 | 41 | 5 | 13 | 2 |
| <https://prez.dev/ManifestResourceRoles/ResourceModel> | manifest resource roles | concept | typed | 4 | 4 | 3 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestResourceRoles/containerAndContentModel> | manifest resource roles | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ManifestVersionTypes/GitCommitHash> | manifest version types | resource | observed | 4 | 1 | 1 | 3 | 0 | 0 | 0 |
| <https://prez.dev/MyVocabsProfile> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/OGCDataCatalogProfile> | root namespace | profile; node shape | typed | 4 | 2 | 2 | 0 | 2 | 0 | 0 |
| <https://prez.dev/OGCFeaturesAllProps> | root namespace | profile; node shape | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/OGCFeaturesMinimalProps> | root namespace | profile; node shape | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/OGCFeaturesProfile> | root namespace | profile | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/OGCItemProfile> | root namespace | profile; node shape | typed | 29 | 4 | 4 | 1 | 24 | 0 | 0 |
| <https://prez.dev/OGCListingProfile> | root namespace | profile; node shape | typed | 4 | 2 | 3 | 1 | 0 | 0 | 0 |
| <https://prez.dev/OGCRecordsProfile> | root namespace | profile | typed | 3 | 2 | 2 | 1 | 0 | 0 | 0 |
| <https://prez.dev/OGCSKOSCollectionObjectProfile> | root namespace | profile; node shape | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/OGCSchemesListProfile> | root namespace | profile; node shape | typed | 4 | 4 | 2 | 0 | 2 | 0 | 0 |
| <https://prez.dev/OGCSchemesObjectProfile> | root namespace | profile; node shape | typed | 1011 | 5 | 5 | 0 | 934 | 2 | 70 |
| <https://prez.dev/Object> | root namespace | resource | observed | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ObjectProfile> | root namespace | class candidate | observed | 40 | 8 | 16 | 2 | 16 | 6 | 0 |
| <https://prez.dev/OdrlAgreementProfile> | root namespace | profile; node shape | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ProfilesGraph> | root namespace | resource | observed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/Queryable> | root namespace | resource | observed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/QueryablesList> | root namespace | resource | observed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/RDFXML> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/RiCORecordProfile> | root namespace | profile; node shape | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/SPARQLQuery> | root namespace | resource | observed | 4 | 2 | 4 | 0 | 0 | 0 | 0 |
| <https://prez.dev/SchemesList> | root namespace | resource | labelled | 4 | 3 | 2 | 0 | 2 | 0 | 0 |
| <https://prez.dev/SchemesListing> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/SearchResult> | root namespace | class candidate | observed | 19 | 5 | 10 | 8 | 0 | 1 | 0 |
| <https://prez.dev/SearchResultMatch> | root namespace | class candidate | observed | 5 | 2 | 0 | 5 | 0 | 0 | 0 |
| <https://prez.dev/SomethingElse> | root namespace | resource | observed | 2 | 2 | 0 | 2 | 0 | 0 | 0 |
| <https://prez.dev/SystemGraph> | root namespace | resource | observed | 4 | 3 | 2 | 0 | 1 | 1 | 0 |
| <https://prez.dev/Turtle> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/VocPrezCollectionList> | root namespace | resource | labelled | 4 | 3 | 2 | 0 | 2 | 0 | 0 |
| <https://prez.dev/VocPrezProfile> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 2 | 0 | 0 |
| <https://prez.dev/WorkspaceConfig> | root namespace | class candidate | observed | 4 | 2 | 2 | 2 | 0 | 0 | 0 |
| <https://prez.dev/catalog> | root namespace | property candidate | observed | 16 | 2 | 4 | 2 | 8 | 2 | 0 |
| <https://prez.dev/childrenCount> | root namespace | property candidate | observed | 2 | 2 | 0 | 0 | 2 | 0 | 0 |
| <https://prez.dev/count> | root namespace | resource | labelled | 10 | 3 | 6 | 3 | 0 | 1 | 0 |
| <https://prez.dev/currentProfile> | root namespace | property candidate | observed | 1010 | 2 | 0 | 0 | 940 | 0 | 70 |
| <https://prez.dev/defaultPageSize> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/deliversClasses> | root namespace | resource | labelled | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/description> | root namespace | property candidate | observed | 1053 | 4 | 4 | 4 | 962 | 4 | 79 |
| <https://prez.dev/descriptionSource> | root namespace | property candidate | observed | 25 | 2 | 5 | 4 | 8 | 8 | 0 |
| <https://prez.dev/endpoint/data-types> | endpoint identifier | resource | observed | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/extended-ogc-records/cql-get> | endpoint identifier | resource | typed | 3 | 2 | 3 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/extended-ogc-records/cql-post> | endpoint identifier | resource | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/extended-ogc-records/narrowers> | endpoint identifier | resource | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/extended-ogc-records/narrowers-post> | endpoint identifier | resource | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/extended-ogc-records/search> | endpoint identifier | resource | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/extended-ogc-records/search-post> | endpoint identifier | resource | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/extended-ogc-records/top-concepts> | endpoint identifier | resource | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/extended-ogc-records/top-concepts-post> | endpoint identifier | resource | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/system/object> | endpoint identifier | resource | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/system/object-post> | endpoint identifier | resource | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/system/profile-listing> | endpoint identifier | resource | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/system/profile-listing-post> | endpoint identifier | resource | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpoint/system/profile-object> | endpoint identifier | resource | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/endpointTemplate> | root namespace | resource | labelled | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/facetCount> | root namespace | resource | observed | 5 | 2 | 1 | 3 | 0 | 1 | 0 |
| <https://prez.dev/facetName> | root namespace | resource | observed | 5 | 2 | 1 | 3 | 0 | 1 | 0 |
| <https://prez.dev/facetValue> | root namespace | resource | observed | 5 | 2 | 1 | 3 | 0 | 1 | 0 |
| <https://prez.dev/focusNode> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/focusToParentRelation> | root namespace | resource | labelled | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/generate> | root namespace | resource | observed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/generateDescription> | root namespace | property candidate | observed | 23 | 2 | 5 | 4 | 8 | 6 | 0 |
| <https://prez.dev/generateFocusNode> | root namespace | property candidate | observed | 18 | 2 | 4 | 2 | 8 | 4 | 0 |
| <https://prez.dev/generateIdentifier> | root namespace | property candidate | observed | 19 | 2 | 5 | 2 | 8 | 4 | 0 |
| <https://prez.dev/generateLabel> | root namespace | property candidate | observed | 23 | 2 | 5 | 4 | 8 | 6 | 0 |
| <https://prez.dev/generateLink> | root namespace | property candidate | observed | 18 | 2 | 4 | 4 | 8 | 2 | 0 |
| <https://prez.dev/generateMembers> | root namespace | property candidate | observed | 18 | 2 | 4 | 4 | 8 | 2 | 0 |
| <https://prez.dev/generateProvenance> | root namespace | property candidate | observed | 14 | 2 | 2 | 2 | 8 | 2 | 0 |
| <https://prez.dev/hasChildren> | root namespace | resource | observed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/hasSearchMatch> | root namespace | property candidate | observed | 8 | 2 | 1 | 6 | 0 | 1 | 0 |
| <https://prez.dev/icon> | root namespace | property candidate | observed | 4 | 2 | 2 | 2 | 0 | 0 | 0 |
| <https://prez.dev/identifier> | root namespace | property candidate | observed | 1049 | 3 | 2 | 0 | 962 | 6 | 79 |
| <https://prez.dev/jena-lucene/bucketBoundaries> | Jena Lucene configuration | resource | observed | 2 | 1 | 0 | 1 | 0 | 1 | 0 |
| <https://prez.dev/jena-lucene/field> | Jena Lucene configuration | resource | observed | 2 | 1 | 0 | 1 | 0 | 1 | 0 |
| <https://prez.dev/jena-lucene/flatFacets> | Jena Lucene configuration | resource | observed | 2 | 1 | 0 | 1 | 0 | 1 | 0 |
| <https://prez.dev/jena-lucene/rangeFacets> | Jena Lucene configuration | resource | observed | 2 | 1 | 0 | 1 | 0 | 1 | 0 |
| <https://prez.dev/label> | root namespace | property candidate | observed | 1065 | 4 | 5 | 9 | 966 | 4 | 81 |
| <https://prez.dev/labelSource> | root namespace | property candidate | observed | 25 | 2 | 5 | 4 | 8 | 8 | 0 |
| <https://prez.dev/link> | root namespace | property candidate | labelled | 1063 | 6 | 7 | 5 | 966 | 4 | 81 |
| <https://prez.dev/linkTemplate> | root namespace | property candidate | observed | 17 | 2 | 5 | 4 | 6 | 2 | 0 |
| <https://prez.dev/manifest-model> | root namespace | ontology | typed | 3 | 1 | 3 | 0 | 0 | 0 | 0 |
| <https://prez.dev/manifest-validator> | root namespace | ontology | typed | 5 | 3 | 4 | 0 | 0 | 1 | 0 |
| <https://prez.dev/manifest-validator/0.5.0> | other Prez path | resource | labelled | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/manifest-validator/1.0.0> | other Prez path | resource | labelled | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/manifest-validator/ShapeN01> | other Prez path | node shape | typed | 3 | 3 | 2 | 0 | 0 | 1 | 0 |
| <https://prez.dev/manifest-validator/ShapeN02> | other Prez path | node shape | typed | 3 | 3 | 2 | 0 | 0 | 1 | 0 |
| <https://prez.dev/manifest-validator/ShapeN03> | other Prez path | node shape | typed | 3 | 3 | 2 | 0 | 0 | 1 | 0 |
| <https://prez.dev/manifest-validator/ShapeN04> | other Prez path | node shape | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/manifest-validator/ShapeP01> | other Prez path | resource | typed | 3 | 3 | 2 | 0 | 0 | 1 | 0 |
| <https://prez.dev/manifest-validator/ShapeP02> | other Prez path | resource | typed | 3 | 3 | 2 | 0 | 0 | 1 | 0 |
| <https://prez.dev/manifest-validator/ShapeP03> | other Prez path | resource | typed | 3 | 3 | 2 | 0 | 0 | 1 | 0 |
| <https://prez.dev/manifest-validator/ShapeP04> | other Prez path | resource | typed | 3 | 3 | 2 | 0 | 0 | 1 | 0 |
| <https://prez.dev/manifest-validator/ShapeP05> | other Prez path | resource | typed | 3 | 3 | 2 | 0 | 0 | 1 | 0 |
| <https://prez.dev/manifest-validator/ShapeP06> | other Prez path | resource | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/manifest-validator/ShapeP07> | other Prez path | resource | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/manifest-validator/ShapeP08> | other Prez path | resource | typed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/maxPageSize> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/members> | root namespace | property candidate | labelled | 1048 | 5 | 4 | 1 | 960 | 4 | 79 |
| <https://prez.dev/membersTemplate> | root namespace | property candidate | observed | 12 | 2 | 4 | 0 | 6 | 2 | 0 |
| <https://prez.dev/ont> | root namespace | ontology | typed | 3 | 1 | 3 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ont/1.0.0> | configuration ontology | resource | labelled | 4 | 1 | 4 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ont/CQLFilterResult> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/CatPrez> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/DynamicEndpoint> | configuration ontology | class candidate | observed | 10 | 6 | 6 | 2 | 2 | 0 | 0 |
| <https://prez.dev/ont/JenaFTSPropertyShape> | configuration ontology | class candidate | observed | 6 | 2 | 4 | 1 | 0 | 1 | 0 |
| <https://prez.dev/ont/JenaFTSUnionShape> | configuration ontology | resource | observed | 3 | 1 | 2 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/ListingEndpoint> | configuration ontology | class candidate | observed | 15 | 7 | 10 | 2 | 2 | 1 | 0 |
| <https://prez.dev/ont/ListingProfile> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/OGCFeaturesEndpoint> | configuration ontology | class candidate | observed | 4 | 3 | 3 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/OGCItemProfile> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/OGCListingProfile> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/OGCRecordsProfile> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/OGCSchemesListProfile> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/OGCSchemesObjectProfile> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/ObjectEndpoint> | configuration ontology | class candidate | observed | 15 | 7 | 10 | 2 | 2 | 1 | 0 |
| <https://prez.dev/ont/ObjectProfile> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/SearchResult> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/SystemEndpoint> | configuration ontology | class candidate | observed | 2 | 2 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ont/TemplateQuery> | configuration ontology | resource | observed | 2 | 1 | 1 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/apiPath> | configuration ontology | property candidate | observed | 11 | 7 | 7 | 2 | 2 | 0 | 0 |
| <https://prez.dev/ont/count> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/defaultSearch> | configuration ontology | resource | observed | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| <https://prez.dev/ont/deliversClasses> | configuration ontology | resource | labelled | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ont/description> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/endpointTemplate> | configuration ontology | resource | labelled | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ont/facetCount> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/facetName> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/facetValue> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/facetable> | configuration ontology | resource | observed | 4 | 1 | 1 | 2 | 0 | 1 | 0 |
| <https://prez.dev/ont/focusToParentRelation> | configuration ontology | resource | labelled | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ont/forEndpoint> | configuration ontology | resource | observed | 2 | 1 | 1 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/hierarchyLevel> | configuration ontology | property candidate | observed | 14 | 6 | 9 | 3 | 2 | 0 | 0 |
| <https://prez.dev/ont/indexed> | configuration ontology | resource | observed | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| <https://prez.dev/ont/label> | configuration ontology | resource | observed | 2 | 1 | 0 | 1 | 0 | 1 | 0 |
| <https://prez.dev/ont/luceneFieldType> | configuration ontology | resource | observed | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| <https://prez.dev/ont/multiValued> | configuration ontology | resource | observed | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| <https://prez.dev/ont/parentEndpoint> | configuration ontology | resource | labelled | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ont/parentToFocusRelation> | configuration ontology | resource | labelled | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/ont/provenance> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/relevantShapes> | configuration ontology | property candidate | observed | 13 | 6 | 9 | 2 | 2 | 0 | 0 |
| <https://prez.dev/ont/searchPredicate> | configuration ontology | property candidate | observed | 3 | 2 | 1 | 1 | 0 | 1 | 0 |
| <https://prez.dev/ont/searchResultWeight> | configuration ontology | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/ont/sortable> | configuration ontology | resource | observed | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| <https://prez.dev/ont/stored> | configuration ontology | resource | observed | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| <https://prez.dev/outputFormat> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 0 | 2 | 0 |
| <https://prez.dev/parentEndpoint> | root namespace | resource | labelled | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/parentToFocusRelation> | root namespace | resource | labelled | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/profile> | root namespace | resource | observed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/profile/animal-facets> | profile identifier | profile | typed | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| <https://prez.dev/profile/animal-search> | profile identifier | profile | typed | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| <https://prez.dev/profile/cqlgeo> | profile identifier | profile | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/profile/eia-feature-listing> | profile identifier | profile | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/profile/facet-by-commodity> | profile identifier | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/profile/facet-by-date> | profile identifier | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/profile/facet-by-type> | profile identifier | profile | typed | 4 | 1 | 1 | 2 | 0 | 1 | 0 |
| <https://prez.dev/profile/formation-top> | profile identifier | resource | observed | 2 | 1 | 0 | 2 | 0 | 0 | 0 |
| <https://prez.dev/profile/occurrence-object> | profile identifier | profile | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/profile/open> | profile identifier | profile | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/profile/open-object> | profile identifier | profile | typed | 3 | 1 | 2 | 1 | 0 | 0 | 0 |
| <https://prez.dev/profile/pivot-assoc> | profile identifier | resource | observed | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| <https://prez.dev/profile/pivotAlternativePath> | profile identifier | profile | typed | 2 | 1 | 0 | 2 | 0 | 0 | 0 |
| <https://prez.dev/profile/pivotInversePath> | profile identifier | profile | typed | 2 | 1 | 0 | 2 | 0 | 0 | 0 |
| <https://prez.dev/profile/pivotOneOrMorePath> | profile identifier | profile | typed | 2 | 1 | 0 | 2 | 0 | 0 | 0 |
| <https://prez.dev/profile/pivotPath> | profile identifier | profile | typed | 2 | 1 | 0 | 2 | 0 | 0 | 0 |
| <https://prez.dev/profile/pivotSequencePath> | profile identifier | profile | typed | 2 | 1 | 0 | 2 | 0 | 0 | 0 |
| <https://prez.dev/profile/pivotTwoPivots> | profile identifier | profile | typed | 2 | 1 | 0 | 2 | 0 | 0 | 0 |
| <https://prez.dev/profile/pivotUnion> | profile identifier | profile | typed | 2 | 1 | 0 | 2 | 0 | 0 | 0 |
| <https://prez.dev/profile/pivotValueSequence> | profile identifier | profile | typed | 2 | 1 | 0 | 2 | 0 | 0 | 0 |
| <https://prez.dev/profile/prez> | profile identifier | profile | typed | 2 | 1 | 1 | 1 | 0 | 0 | 0 |
| <https://prez.dev/profile/profiles> | profile identifier | profile | typed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/profile/rico-place> | profile identifier | profile | typed | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| <https://prez.dev/profile/rico-record> | profile identifier | profile | typed | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| <https://prez.dev/profile/site-object-facet> | profile identifier | resource | observed | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| <https://prez.dev/profiles> | root namespace | resource | observed | 2 | 2 | 0 | 0 | 2 | 0 | 0 |
| <https://prez.dev/provenance> | root namespace | property candidate | observed | 454 | 4 | 2 | 0 | 450 | 2 | 0 |
| <https://prez.dev/provenanceSource> | root namespace | property candidate | observed | 10 | 2 | 2 | 0 | 6 | 2 | 0 |
| <https://prez.dev/refreshFrom> | root namespace | property candidate | observed | 4 | 2 | 2 | 2 | 0 | 0 | 0 |
| <https://prez.dev/schemeLabel> | root namespace | resource | observed | 13 | 2 | 0 | 0 | 8 | 0 | 5 |
| <https://prez.dev/searchResultMatch> | root namespace | property candidate | labelled | 13 | 3 | 5 | 7 | 0 | 1 | 0 |
| <https://prez.dev/searchResultPredicate> | root namespace | property candidate | labelled | 13 | 3 | 5 | 7 | 0 | 1 | 0 |
| <https://prez.dev/searchResultURI> | root namespace | property candidate | observed | 11 | 2 | 2 | 8 | 0 | 1 | 0 |
| <https://prez.dev/searchResultWeight> | root namespace | property candidate | labelled | 12 | 3 | 5 | 6 | 0 | 1 | 0 |
| <https://prez.dev/simpleView> | root namespace | property candidate | observed | 6 | 2 | 4 | 2 | 0 | 0 | 0 |
| <https://prez.dev/slug> | root namespace | property candidate | observed | 4 | 2 | 2 | 2 | 0 | 0 | 0 |
| <https://prez.dev/sourcePredicate> | root namespace | resource | observed | 6 | 2 | 2 | 0 | 4 | 0 | 0 |
| <https://prez.dev/sparqlEndpointEnabled> | root namespace | resource | observed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/sync> | root namespace | property candidate | observed | 3 | 2 | 2 | 1 | 0 | 0 | 0 |
| <https://prez.dev/systemGraph> | root namespace | resource | observed | 2 | 1 | 2 | 0 | 0 | 0 | 0 |
| <https://prez.dev/testprof> | root namespace | resource | observed | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| <https://prez.dev/type> | root namespace | property candidate | observed | 1043 | 3 | 2 | 0 | 962 | 0 | 79 |
| <https://prez.dev/uri> | root namespace | resource | observed | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| <https://prez.dev/version> | root namespace | resource | observed | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| <https://prez.dev/workspace> | root namespace | property candidate | observed | 4 | 2 | 2 | 2 | 0 | 0 | 0 |

## Interpretation cautions

- A URL under `prez.dev` may identify documentation, a profile, a graph, an endpoint, a controlled-vocabulary concept, or an ontology term.
- `property candidate` means the IRI appeared in predicate position; `class candidate` means it appeared as the object of `rdf:type`. Neither is a proposed formal declaration.
- Counts are affected by cloned fixtures and generated exports. Category columns make those sources visible rather than silently discarding them.
- Compact IRIs are resolved from in-file `PREFIX` or `@prefix` declarations. Python `rdflib.Namespace` attribute and item access is also recognised. Other dynamically constructed IRIs may require a future language-specific extractor.
- The Turtle output uses a private `urn:prez-namespace-audit:vocab/` reporting vocabulary so the audit does not mint additional public Prez terms.
