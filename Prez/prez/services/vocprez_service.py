from typing import Optional

from rdflib.namespace import RDFS, DCAT, DCTERMS

from config import *
from services.sparql_utils import *


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
        ?cs a skos:ConceptScheme ;
            dcterms:identifier ?cs_id ;
            skos:prefLabel ?cs_label .
        OPTIONAL {{
            ?c skos:broader ?broader .
            ?broader a skos:Concept ;
                skos:prefLabel ?broader_label ;
                dcterms:identifier ?broader_id ;
                skos:inScheme ?broader_cs .
            ?broader_cs a skos:ConceptScheme ;
                dcterms:identifier ?cs_broader_id .
        }}
        OPTIONAL {{
            ?c skos:narrower ?narrower .
            ?narrower a skos:Concept ;
                skos:prefLabel ?narrower_label ;
                dcterms:identifier ?narrower_id ;
                skos:inScheme ?narrower_cs .
            ?narrower_cs a skos:ConceptScheme ;
                dcterms:identifier ?cs_narrower_id .
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
            ?broader a skos:Concept ;
                skos:prefLabel ?broader_label ;
                dcterms:identifier ?broader_id ;
                skos:inScheme ?broader_cs .
            ?broader_cs a skos:ConceptScheme ;
                dcterms:identifier ?cs_broader_id .
            ?narrower a skos:Concept ;
                skos:prefLabel ?narrower_label ;
                dcterms:identifier ?narrower_id ;
                skos:inScheme ?narrower_cs .
            ?narrower_cs a skos:ConceptScheme ;
                dcterms:identifier ?cs_narrower_id .
            ?p1 rdfs:label ?p1Label .
            ?o1 rdfs:label ?o1Label .

            ?cs a skos:ConceptScheme ;
                dcterms:identifier ?cs_id ;
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


async def get_dataset_construct():
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX rdfs: <{RDFS}>
        CONSTRUCT {{
            ?dataset ?p1 ?o1 .
            ?p1 rdfs:label ?p1Label .
            ?o1 rdfs:label ?o1Label .
        }}
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
    r = await sparql_construct(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def get_collection_construct(
    collection_id: Optional[str] = None,
    collection_uri: Optional[str] = None,
    include_inferencing: bool = True,
):
    if collection_id is None and collection_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        ?coll dcterms:identifier ?coll_id ;
            a skos:Collection .
        FILTER (STR(?coll_id) = "{collection_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{collection_uri}> as ?coll)
        ?coll a skos:Collection .
    """
    # data which may contain inferencing
    query_in_graph = f"""
        ?coll skos:member ?c ;
            ?p1 ?o1 .
        ?c skos:inScheme ?cs ;
            a skos:Concept ;
            ?p2 ?o2 .
        ?cs ?p3 ?o3 .
    """

    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        CONSTRUCT {{
            ?coll ?p1 ?o1 .
            ?p1 rdfs:label ?p1Label .
            ?o1 rdfs:label ?o1Label .

            ?c ?p2 ?o2 .
            ?p2 rdfs:label ?p2Label .
            ?o2 rdfs:label ?o2Label .

            ?cs ?p3 ?o3 .
            ?p3 rdfs:label ?p3Label .
            ?o3 rdfs:label ?o3Label .
        }}
        WHERE {{
            {query_by_id if collection_id is not None else query_by_uri}
            {query_in_graph}
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
            OPTIONAL {{
                ?p3 rdfs:label ?p3Label .
                FILTER(lang(?p3Label) = "" || lang(?p3Label) = "en")
            }}
            OPTIONAL {{
                ?o3 rdfs:label ?o3Label .
                FILTER(lang(?o3Label) = "" || lang(?o3Label) = "en")
            }}
        }}
    """
    r = await sparql_construct(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")
