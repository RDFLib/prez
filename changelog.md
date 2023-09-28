## Changes for 2023-09-27

### Features

- Default search added. This is a simple search that will search for terms across all annotation predicates Prez has configured. By default in prez/config.py these are set to:
  - label_predicates = [SKOS.prefLabel, DCTERMS.title, RDFS.label, SDO.name]
  - description_predicates = [SKOS.definition, DCTERMS.description, SDO.description]
  - provenance_predicates = [DCTERMS.provenance]  
  These are configurable via environment variables using the Pydantic BaseSettings functionality but will need to be properly escaped as they are a list.
  
  More detail on adding filters to search is provided in the readme.
- Timeout for httpx AsyncClient and Client instances is set on the shared instance to 30s. Previously this was set in some individual calls resulting in inconsistent behaviour, as the default is otherwise 5s.
- Updated `purge-tbox-cache` endpoint functionality. This reflects that prez now
  includes a number of common ontologies by default (prez/reference_data/context_ontologies), and on startup will load
  annotation triples (e.g. x rdfs:label y) from these. As such, the tbox or annotation cache is no longer completely
  purged but can be reset to this default state instead.