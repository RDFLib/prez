from typing import Optional

from rdflib.namespace import RDFS, DCAT, DCTERMS

from config import *
from services.sparql_utils import *


async def count_datasets():
    q = f"""
        PREFIX dcat: <{DCAT}>
        SELECT (COUNT(?d) as ?count) 
        WHERE {{
            ?d a dcat:Dataset .
        }}
    """
    r = await sparql_query(q, "SpacePrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def list_datasets(page: int, per_page: int):
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        SELECT DISTINCT ?d ?id ?label
        WHERE {{
            ?d a dcat:Dataset ;
                dcterms:identifier ?id ;
                dcterms:title ?label .
            FILTER(lang(?label) = "" || lang(?label) = "en")
        }} LIMIT {per_page} OFFSET {(page - 1) * per_page}
    """
    r = await sparql_query(q, "SpacePrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def get_dataset_construct(
    dataset_id: Optional[str] = None, dataset_uri: Optional[str] = None
):
    if dataset_id is None and dataset_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        ?d dcterms:identifier ?id ;
            a dcat:Dataset .
        FILTER (STR(?id) = "{dataset_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{dataset_uri}> as ?d)
        ?d a dcat:Dataset .
    """

    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        CONSTRUCT {{
            ?d ?p1 ?o1 .

            ?o1 ?p2 ?o2 .

            ?p1 rdfs:label ?p1Label .
            ?o1 rdfs:label ?o1Label .
            
            ?p2 rdfs:label ?p2Label .
        }}
        WHERE {{
            {query_by_id if dataset_id is not None else query_by_uri}
            ?d ?p1 ?o1 .
            OPTIONAL {{
                ?o1 ?p2 ?o2 .
                FILTER(ISBLANK(?o1))

                OPTIONAL {{
                    ?p2 rdfs:label ?p2Label .
                    FILTER(lang(?p2Label) = "" || lang(?p2Label) = "en")
                }}
                OPTIONAL {{
                    ?o2 rdfs:label ?o2Label .
                    FILTER(lang(?o2Label) = "" || lang(?o2Label) = "en")
                }}
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
    r = await sparql_construct(q, "SpacePrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def count_collections(dataset_id: str):
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        PREFIX rdfs: <{RDFS}>
        SELECT (COUNT(?coll) as ?count) 
        WHERE {{
            ?d dcterms:identifier ?d_id ;
                a dcat:Dataset ;
                rdfs:member ?coll .
            FILTER (STR(?d_id) = "{dataset_id}")
            ?coll a geo:FeatureCollection .
        }}
    """
    r = await sparql_query(q, "SpacePrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def list_collections(dataset_id: str, page: int, per_page: int):
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        SELECT DISTINCT *
        WHERE {{
            ?d dcterms:identifier ?d_id ;
                a dcat:Dataset ;
                dcterms:title ?d_label ;
                rdfs:member ?coll .
            FILTER(lang(?d_label) = "" || lang(?d_label) = "en")
            FILTER (STR(?d_id) = "{dataset_id}")
            ?coll a geo:FeatureCollection ;
                dcterms:identifier ?id ;
                dcterms:title ?label .
            FILTER(lang(?label) = "" || lang(?label) = "en")
        }} LIMIT {per_page} OFFSET {(page - 1) * per_page}
    """
    r = await sparql_query(q, "SpacePrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def get_collection_construct_1(
    dataset_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    collection_uri: Optional[str] = None,
):
    if collection_id is None and collection_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        FILTER (STR(?d_id) = "{dataset_id}")
        ?coll a geo:FeatureCollection ;
            dcterms:identifier ?id .
        ?d a dcat:Dataset ;
            rdfs:member ?fc ;
            dcterms:identifier ?d_id .
        FILTER (STR(?id) = "{collection_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{collection_uri}> as ?coll)
        ?coll a geo:FeatureCollection .
    """

    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        CONSTRUCT {{
            ?coll ?p1 ?o1 .
            ?o1 ?p2 ?o2 .

            ?p1 rdfs:label ?p1Label .
            ?o1 rdfs:label ?o1Label .

            ?p2 rdfs:label ?p2Label .

            ?d a dcat:Dataset ;
                dcterms:identifier ?d_id ;
                dcterms:title ?d_label ;
                rdfs:member ?coll .
        }}
        WHERE {{
            {query_by_id if collection_id is not None else query_by_uri}
            ?coll ?p1 ?o1 .
            
            FILTER(!STRENDS(STR(?p1), "member"))

            OPTIONAL {{
                ?o1 ?p2 ?o2 .
                FILTER(ISBLANK(?o1))

                OPTIONAL {{
                    ?p2 rdfs:label ?p2Label .
                    FILTER(lang(?p2Label) = "" || lang(?p2Label) = "en")
                }}
                OPTIONAL {{
                    ?o2 rdfs:label ?o2Label .
                    FILTER(lang(?o2Label) = "" || lang(?o2Label) = "en")
                }}
            }}
            ?d a dcat:Dataset ;
                rdfs:member ?fc ;
                dcterms:identifier ?d_id ;
                dcterms:title ?d_label .
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
    r = await sparql_construct(q, "SpacePrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def get_collection_construct_2(
    dataset_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    collection_uri: Optional[str] = None,
):
    if collection_id is None and collection_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        FILTER (STR(?d_id) = "{dataset_id}")
        ?coll a geo:FeatureCollection ;
            dcterms:identifier ?id .
        ?d a dcat:Dataset ;
            dcterms:identifier ?d_id ;
            rdfs:member ?fc .
        FILTER (STR(?id) = "{collection_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{collection_uri}> as ?coll)
        ?coll a geo:FeatureCollection .
    """

    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        CONSTRUCT {{
            ?coll rdfs:member ?mem .
        }}
        WHERE {{
            {query_by_id if collection_id is not None else query_by_uri}
            ?coll rdfs:member ?mem .
        }} LIMIT 20
    """
    r = await sparql_construct(q, "SpacePrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def count_features(dataset_id: str, collection_id: str):
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        PREFIX rdfs: <{RDFS}>
        
        SELECT (COUNT(?f) as ?count) 
        WHERE {{
            ?d dcterms:identifier ?d_id ;
                a dcat:Dataset ;
                rdfs:member ?coll .
            FILTER (STR(?d_id) = "{dataset_id}")
            ?coll dcterms:identifier ?coll_id ;
                a geo:FeatureCollection ;
                rdfs:member ?f .
            FILTER (STR(?coll_id) = "{collection_id}")
            ?f a geo:Feature .
        }}
    """
    r = await sparql_query(q, "SpacePrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def list_features(dataset_id: str, collection_id: str, page: int, per_page: int):
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        SELECT DISTINCT *
        WHERE {{
            ?d dcterms:identifier ?d_id ;
                a dcat:Dataset ;
                dcterms:title ?d_label ;
                rdfs:member ?coll .
            FILTER(lang(?d_label) = "" || lang(?d_label) = "en")
            FILTER (STR(?d_id) = "{dataset_id}")
            ?coll a geo:FeatureCollection ;
                dcterms:identifier ?coll_id ;
                dcterms:title ?coll_label ;
                rdfs:member ?f .
            FILTER(lang(?coll_label) = "" || lang(?coll_label) = "en")
            FILTER (STR(?coll_id) = "{collection_id}")
            ?f a geo:Feature ;
                dcterms:identifier ?id .
                
            OPTIONAL {{
                ?f dcterms:title ?label .
                FILTER(lang(?label) = "" || lang(?label) = "en")
            }}
        }} LIMIT {per_page} OFFSET {(page - 1) * per_page}
    """
    r = await sparql_query(q, "SpacePrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")


async def get_feature_construct(
    dataset_id: Optional[str] = None,
    collection_id: Optional[str] = None,
    feature_id: Optional[str] = None,
    feature_uri: Optional[str] = None,
):
    if feature_id is None and feature_uri is None:
        raise ValueError("Either an ID or a URI must be provided for a SPARQL query")

    # when querying by ID via regular URL path
    query_by_id = f"""
        FILTER (STR(?d_id) = "{dataset_id}")
        ?d rdfs:member ?coll .
        ?coll a geo:FeatureCollection ;
            dcterms:identifier ?coll_id ;
            rdfs:member ?f .
        FILTER (STR(?coll_id) = "{collection_id}")
        ?f a geo:Feature ;
            dcterms:identifier ?id .
        FILTER (STR(?id) = "{feature_id}")
    """
    # when querying by URI via /object?uri=...
    query_by_uri = f"""
        BIND (<{feature_uri}> as ?f)
        ?f a geo:Feature .
    """

    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX geo: <{GEO}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        
        CONSTRUCT {{
            ?f ?p1 ?o1 ;
                dcterms:title ?title .
            ?o1 ?p2 ?o2 .
            
            ?p1 rdfs:label ?p1Label .
            ?o1 rdfs:label ?o1Label .

            ?p2 rdfs:label ?p2Label .
            ?o2 rdfs:label ?o2Label .

            dcterms:title rdfs:label "Title" .

            ?coll a geo:FeatureCollection ;
                dcterms:identifier ?coll_id ;
                dcterms:title ?coll_label ;
                rdfs:member ?f .
            
            ?d a dcat:Dataset ;
                dcterms:identifier ?d_id ;
                dcterms:title ?d_label .
        }}
        WHERE {{
            {query_by_id if feature_id is not None else query_by_uri}
            {{?coll rdfs:member ?f .}}
            {{?f ?p1 ?o1 . }}
            OPTIONAL {{
                ?o1 ?p2 ?o2 .
                FILTER(ISBLANK(?o1))

                OPTIONAL {{
                    ?p2 rdfs:label ?p2Label .
                    FILTER(lang(?p2Label) = "" || lang(?p2Label) = "en")
                }}
                OPTIONAL {{
                    ?o2 rdfs:label ?o2Label .
                    FILTER(lang(?o2Label) = "" || lang(?o2Label) = "en")
                }}
            }}
            OPTIONAL {{
                ?f dcterms:title ?label .
            }}
            BIND(COALESCE(?label, CONCAT("Feature ", ?id)) AS ?title)
            ?coll a geo:FeatureCollection ;
                dcterms:identifier ?coll_id ;
                dcterms:title ?coll_label .
            ?d a dcat:Dataset ;
                dcterms:identifier ?d_id ;
                dcterms:title ?d_label .
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
    r = await sparql_construct(q, "SpacePrez")
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]['code']}: {r[1]['message']}")
