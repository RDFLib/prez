import logging

from textwrap import dedent

from prez.reference_data.prez_ns import PREZ

log = logging.getLogger(__name__)


def generate_insert_context(settings, prez: str):
    """ """
    topmost_classes = settings.top_level_classes[prez]
    collection_classes = settings.collection_classes[prez]
    member_relation = {
        "SpacePrez": "?instance_of_main_class rdfs:member ?member",
        "VocPrez": """{?instance_of_main_class ^skos:inScheme ?member }
                        UNION
      		          { ?instance_of_main_class skos:member ?member }""",
        "CatPrez": "?instance_of_main_class dcterms:hasPart ?member",
        "Profiles": "?instance_of_main_class rdfs:member ?member",
    }
    insert = dedent(
        f"""PREFIX dcat: <http://www.w3.org/ns/dcat#>
        PREFIX dcterms: <http://purl.org/dc/terms/>
        PREFIX prez: <https://prez.dev/>
        PREFIX prof: <http://www.w3.org/ns/dx/prof/>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        INSERT {{
            GRAPH prez:{prez.lower()}-system-graph {{
                ?support_graph_uri prez:hasContextFor ?instance_of_main_class .
                ?collectionList rdfs:member ?instance_of_top_class .
                ?instance_of_main_class dcterms:identifier ?prez_id .
            }}
            GRAPH ?support_graph_uri {{ ?member dcterms:identifier ?prez_mem_id . }}
        }}
        WHERE {{
          {{
            ?instance_of_main_class a ?collection_class .
                VALUES ?collection_class {{ {(chr(10) + 2 * chr(9)).join('<' + str(uri) + '>' for uri in collection_classes)} }}
            OPTIONAL {{?instance_of_top_class a ?topmost_class
                VALUES ?topmost_class {{ {(chr(10) + 2 * chr(9)).join('<' + str(uri) + '>' for uri in topmost_classes)} }}
            }}
            MINUS {{ GRAPH prez:{prez.lower()}-system-graph {{?a_context_graph prez:hasContextFor ?instance_of_main_class}}
            }}
            OPTIONAL {{?instance_of_main_class dcterms:identifier ?id
                BIND(DATATYPE(?id) AS ?dtype_id)
                FILTER(?dtype_id = xsd:token)
                }}
            OPTIONAL {{ {member_relation[prez]}
                OPTIONAL {{?member dcterms:identifier ?mem_id
                    BIND(DATATYPE(?mem_id) AS ?dtype_mem_id)
                    FILTER(?dtype_mem_id = xsd:token) }} }}
            }}
            BIND(
                IF(?topmost_class=prez:SpacePrezProfile, prez:SpacePrezProfileList,
                    IF(?topmost_class=prez:VocPrezProfile, prez:VocPrezProfileList,
                        IF(?topmost_class=prez:CatPrezProfile, prez:CatPrezProfileList,
                            IF(?topmost_class=prof:Profile, prez:ProfilesList,
                                IF(?topmost_class=dcat:Dataset, prez:DatasetList,
                                    IF(?topmost_class=dcat:Catalog,prez:CatalogList,
                                        IF(?topmost_class=skos:ConceptScheme,prez:SchemesList,
                                            IF(?topmost_class=skos:Collection,prez:VocPrezCollectionList,""))))))))
                                            AS ?collectionList)
            BIND(STRDT(COALESCE(STR(?id),MD5(STR(?instance_of_main_class))), prez:slug) AS ?prez_id)
            BIND(STRDT(COALESCE(STR(?mem_id),MD5(STR(?member))), prez:slug) AS ?prez_mem_id)
            BIND(URI(CONCAT(STR(?instance_of_main_class),"/support-graph")) AS ?support_graph_uri)
        }}"""
    )
    return insert


def ask_system_graph(prez_flavour: str):
    """
    Checks if the system graph exists in the triple store.
    """
    return f"ASK {{ GRAPH <{PREZ[prez_flavour.lower() + '-system-graph']}> {{ ?s ?p ?o }} }} LIMIT 1"
