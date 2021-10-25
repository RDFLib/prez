from typing import Optional

from rdflib.namespace import RDFS, DCAT, DCTERMS, XSD

from config import *
from services.sparql_utils import *

# all queries query against a union of content & system graph(s)


# get dataset by ID


async def get_dataset():
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX rdfs: <{RDFS}>
        SELECT *
        WHERE {{
            ?dataset a dcat:Dataset ;
                ?p1 ?o1 .
            OPTIONAL {{
                ?p1 rdfs:label ?p1Label .
                FILTER(lang(?p1Label) = "" || lang(?p1Label) = "en")
            }}
            OPTIONAL {{
                ?o1 rdfs:label ?o1Label .
                FILTER(lang(?o1Label) = "" || lang(?o1Label) = "en")
            }}
        }}
    """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def list_schemes():
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        SELECT ?cs ?id ?label
        WHERE {{
            ?cs a skos:ConceptScheme ;
                dcterms:identifier ?id ;
                skos:prefLabel ?label .
        }}
    """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def get_scheme(scheme_id: str, include_inferencing: bool = True):
    if include_inferencing:
        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdf: <{RDF}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT *
            WHERE {{
                ?cs dcterms:identifier ?cs_id ;
                    a skos:ConceptScheme ;
                    ?p1 ?o1 .
                FILTER (STR(?cs_id) = "{scheme_id}")
                OPTIONAL {{
                    ?p1 rdfs:label ?p1Label .
                    FILTER(lang(?p1Label) = "" || lang(?p1Label) = "en")
                }}
                OPTIONAL {{
                    ?o1 rdfs:label ?o1Label .
                    FILTER(lang(?o1Label) = "" || lang(?o1Label) = "en")
                }}
            }}
        """
    else:
        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdf: <{RDF}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT *
            WHERE {{
                ?cs dcterms:identifier ?cs_id ;
                    a skos:ConceptScheme .
                FILTER (STR(?cs_id) = "{scheme_id}")
                GRAPH ?cs {{
                    ?cs ?p1 ?o1 .
                }}
                OPTIONAL {{
                    ?p1 rdfs:label ?p1Label .
                    FILTER(lang(?p1Label) = "" || lang(?p1Label) = "en")
                }}
                OPTIONAL {{
                    ?o1 rdfs:label ?o1Label .
                    FILTER(lang(?o1Label) = "" || lang(?o1Label) = "en")
                }}
            }}
        """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def list_collections():
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        SELECT ?cs ?id ?label
        WHERE {{
            ?cs a skos:Collection ;
                dcterms:identifier ?id ;
                skos:prefLabel ?label .
        }}
    """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def get_collection(collection_id: str):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        SELECT *
        WHERE {{
            ?collection dcterms:identifier ?coll_id ;
                a skos:Collection ;
                ?p1 ?o1 .
            FILTER (STR(?coll_id) = "{collection_id}")
            OPTIONAL {{
                ?p1 rdfs:label ?p1Label .
                FILTER(lang(?p1Label) = "" || lang(?p1Label) = "en")
            }}
            OPTIONAL {{
                ?o1 rdfs:label ?o1Label .
                FILTER(lang(?o1Label) = "" || lang(?o1Label) = "en")
            }}
        }}
    """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


# get concept
async def get_concept(
    scheme_id: str, concept_id: str, include_inferencing: bool = True
):
    if include_inferencing:
        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT *
            WHERE {{
                ?c dcterms:identifier ?c_id ;
                    a skos:Concept ;
                    skos:inScheme ?cs ;
                    ?p1 ?o1 .
                FILTER (STR(?c_id) = "{concept_id}")
                ?cs dcterms:identifier ?cs_id ;
                    skos:prefLabel ?csLabel .
                FILTER (STR(?cs_id) = "{scheme_id}")
                OPTIONAL {{
                    ?p1 rdfs:label ?p1Label .
                    FILTER(lang(?p1Label) = "" || lang(?p1Label) = "en")
                }}
                OPTIONAL {{
                    ?o1 rdfs:label ?o1Label .
                    FILTER(lang(?o1Label) = "" || lang(?o1Label) = "en")
                }}
            }}
        """
    else:
        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX rdfs: <{RDFS}>
            PREFIX skos: <{SKOS}>
            SELECT *
            WHERE {{
                ?cs dcterms:identifier ?cs_id ;
                    skos:prefLabel ?csLabel .
                FILTER (STR(?cs_id) = "{scheme_id}")
                GRAPH ?cs {{
                    ?c dcterms:identifier ?c_id ;
                        a skos:Concept ;
                        skos:inScheme ?cs ;
                        ?p1 ?o1 .
                    FILTER (STR(?c_id) = "{concept_id}")
                }}
                OPTIONAL {{
                    ?p1 rdfs:label ?p1Label .
                    FILTER(lang(?p1Label) = "" || lang(?p1Label) = "en")
                }}
                OPTIONAL {{
                    ?o1 rdfs:label ?o1Label .
                    FILTER(lang(?o1Label) = "" || lang(?o1Label) = "en")
                }}
            }}
        """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def get_collection_concepts(collection_id: str):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        SELECT DISTINCT ?c ?label ?id ?cs_id
        WHERE {{
            ?collection dcterms:identifier ?coll_id ;
                a skos:Collection ;
                skos:member ?c .
            FILTER (STR(?coll_id) = "{collection_id}")
            ?c a skos:Concept ;
                skos:prefLabel ?label ;
                dcterms:identifier ?id ;
                skos:inScheme|skos:topConceptOf ?cs .
            ?cs dcterms:identifier ?cs_id .
        }}
    """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def get_concept_hierarchy(scheme_id: str, include_inferencing: bool = True):
    if include_inferencing:
        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT ?c ?label ?id ?narrower ?broader
            WHERE {{
                ?cs dcterms:identifier ?cs_id ;
                    a skos:ConceptScheme .
                FILTER (STR(?cs_id) = "{scheme_id}")

                {{
                    ?c skos:inScheme ?cs .
                }}
                UNION
                {{
                    ?c skos:topConceptOf ?cs .
                }}
                UNION
                {{
                    ?cs skos:hasTopConcept ?c .
                }}

                ?c a skos:Concept ;
                    skos:prefLabel ?label ;
                    dcterms:identifier ?id .
                
                OPTIONAL {{
                    ?c skos:narrower ?narrower .
                }}

                OPTIONAL {{
                    ?c skos:broader ?broader .
                }}
            }}
        """
    else:
        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT ?c ?label ?id ?narrower ?broader
            WHERE {{
                ?cs dcterms:identifier ?cs_id ;
                    a skos:ConceptScheme .
                FILTER (STR(?cs_id) = "{scheme_id}")
                GRAPH ?cs {{
                    {{
                        ?c skos:inScheme ?cs .
                    }}
                    UNION
                    {{
                        ?c skos:topConceptOf ?cs .
                    }}
                    UNION
                    {{
                        ?cs skos:hasTopConcept ?c .
                    }}

                    ?c a skos:Concept ;
                        skos:prefLabel ?label ;
                        dcterms:identifier ?id .
                    
                    OPTIONAL {{
                        ?c skos:narrower ?narrower .
                    }}

                    OPTIONAL {{
                        ?c skos:broader ?broader .
                    }}
                }}
            }}
        """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def get_broader_concepts(concept_id: str, include_inferencing: bool = True):
    if include_inferencing:
        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT ?broader ?id ?cs_id ?label
            WHERE {{
                ?c dcterms:identifier ?c_id ;
                    a skos:Concept ;
                    skos:inScheme|skos:topConceptOf ?cs ;
                    skos:broader ?broader .
                ?cs dcterms:identifier ?cs_id .
                FILTER (STR(?c_id) = "{concept_id}")
                ?broader a skos:Concept ;
                    dcterms:identifier ?id ;
                    skos:prefLabel ?label ;
            }}
        """
    else:
        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT ?broader ?id ?cs_id ?label
            WHERE {{
                ?c dcterms:identifier ?c_id ;
                    a skos:Concept ;
                    skos:inScheme|skos:topConceptOf ?cs .
                ?cs dcterms:identifier ?cs_id .
                FILTER (STR(?c_id) = "{concept_id}")
                GRAPH ?cs {{
                    ?c skos:broader ?broader .
                    ?broader a skos:Concept ;
                        dcterms:identifier ?id ;
                        skos:prefLabel ?label ;
                }}
            }}
        """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def get_narrower_concepts(concept_id: str, include_inferencing: bool = True):
    if include_inferencing:
        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT ?narrower ?id ?cs_id ?label
            WHERE {{
                ?c dcterms:identifier ?c_id ;
                    a skos:Concept ;
                    skos:inScheme|skos:topConceptOf ?cs ;
                    skos:narrower ?narrower .
                ?cs dcterms:identifier ?cs_id .
                FILTER (STR(?c_id) = "{concept_id}")
                ?narrower a skos:Concept ;
                    dcterms:identifier ?id ;
                    skos:prefLabel ?label ;
            }}
        """
    else:
        q = f"""
            PREFIX dcterms: <{DCTERMS}>
            PREFIX skos: <{SKOS}>
            SELECT DISTINCT ?narrower ?id ?cs_id ?label
            WHERE {{
                ?c dcterms:identifier ?c_id ;
                    a skos:Concept ;
                    skos:inScheme|skos:topConceptOf ?cs .
                ?cs dcterms:identifier ?cs_id .
                FILTER (STR(?c_id) = "{concept_id}")
                GRAPH ?cs {{
                    ?c skos:narrower ?narrower .
                    ?narrower a skos:Concept ;
                        dcterms:identifier ?id ;
                        skos:prefLabel ?label ;
                }}
            }}
        """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


def query_by_graph(query: str, graph: str, include_inferencing: bool):
    """Conditionally wraps query with a GRAPH statement if inferencing is disabled"""
    if include_inferencing:
        return query
    else:
        return f"""
            GRAPH {graph} {{
                {query}
            }}
        """


async def get_scheme_construct(
    scheme_id: Optional[str] = None,
    scheme_uri: Optional[str] = None,
    include_inferencing: bool = True,
):
    if scheme_id is None and scheme_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        ?cs dcterms:identifier ?cs_id ;
            a skos:ConceptScheme .
        FILTER (STR(?cs_id) = "{scheme_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{scheme_uri}> as ?cs)
        ?cs a skos:ConceptScheme .
    """
    # data which may contain inferencing 
    query_in_graph = f"""
        ?cs ?p1 ?o1 .
        ?c skos:inScheme ?cs ;
            a skos:Concept ;
            ?p2 ?o2 .
    """

    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        CONSTRUCT {{
            ?cs ?p1 ?o1 .
            ?p1 rdfs:label ?p1Label .
            ?o1 rdfs:label ?o1Label .

            ?c ?p2 ?o2 .
            ?p2 rdfs:label ?p2Label .
            ?o2 rdfs:label ?o2Label .
        }}
        WHERE {{
            {query_by_id if scheme_id is not None else query_by_uri}
            {query_by_graph(query_in_graph, "?cs", include_inferencing)}
            OPTIONAL {{
                ?p1 rdfs:label ?p1Label .
                FILTER(lang(?p1Label) = "" || lang(?p1Label) = "en")
            }}
            OPTIONAL {{
                ?o1 rdfs:label ?o1Label .
                FILTER(lang(?o1Label) = "" || lang(?o1Label) = "en")
            }}
            OPTIONAL {{
                ?p2 rdfs:label ?p2Label .
                FILTER(lang(?p2Label) = "" || lang(?p2Label) = "en")
            }}
            OPTIONAL {{
                ?o2 rdfs:label ?o2Label .
                FILTER(lang(?o2Label) = "" || lang(?o2Label) = "en")
            }}
        }}
    """
    r = await sparql_construct(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")

async def get_concept_construct(
    concept_id: Optional[str] = None,
    scheme_id: Optional[str] = None,
    concept_uri: Optional[str] = None,
    include_inferencing: bool = True,
):
    if concept_id is None and scheme_id is None and concept_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        ?c dcterms:identifier ?c_id ;
            a skos:Concept ;
            skos:inScheme ?cs .
        FILTER (STR(?c_id) = "{concept_id}")
        ?cs dcterms:identifier ?cs_id ;
            a skos:ConceptScheme .
        FILTER (STR(?cs_id) = "{scheme_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{concept_uri}> as ?c)
        ?c a skos:Concept ;
            skos:inScheme ?cs .
    """
    # data which may contain inferencing
    query_in_graph = f"""
        ?c ?p1 ?o1 .
        ?cs dcterms:identifier ?cs_id;
            skos:prefLabel ?cs_label .
        OPTIONAL {{
            ?c skos:broader ?broader .
            ?broader a skos:Concept;
                dcterms:identifier ?broader_id ;
                skos:prefLabel ?broader_label .
        }}
        OPTIONAL {{
            ?c skos:narrower ?narrower .
            ?narrower a skos:Concept;
                dcterms:identifier ?narrower_id ;
                skos:prefLabel ?narrower_label .
        }}
    """

    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        CONSTRUCT {{
            ?c ?p1 ?o1 ;
                skos:broader ?broader ;
                skos:narrower ?narrower .
            ?broader dcterms:identifier ?broader_id ;
                skos:prefLabel ?broader_label .
            ?narrower dcterms:identifier ?narrower_id ;
                skos:prefLabel ?narrower_label .
            ?p1 rdfs:label ?p1Label .
            ?o1 rdfs:label ?o1Label .

            ?cs dcterms:identifier ?cs_id ;
                skos:prefLabel ?cs_label .
        }}
        WHERE {{
            {query_by_id if concept_id is not None and scheme_id is not None else query_by_uri}
            {query_by_graph(query_in_graph, "?cs", include_inferencing)}
            OPTIONAL {{
                ?p1 rdfs:label ?p1Label .
                FILTER(lang(?p1Label) = "" || lang(?p1Label) = "en")
            }}
            OPTIONAL {{
                ?o1 rdfs:label ?o1Label .
                FILTER(lang(?o1Label) = "" || lang(?o1Label) = "en")
            }}
        }}
    """
    r = await sparql_construct(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")
