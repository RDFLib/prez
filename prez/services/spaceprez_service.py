from typing import Optional

from rdflib import Namespace
from rdflib.namespace import RDFS, DCAT, DCTERMS

from config import *
from services.sparql_utils import *

GEO = Namespace("http://www.opengis.net/ont/geosparql#")

async def list_datasets():
    q = f"""
        PREFIX dcat: <{DCAT}>
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        SELECT DISTINCT ?d ?id ?label
        WHERE {{
            ?d a dcat:Dataset ;
                dcterms:identifier ?id ;
                skos:prefLabel|dcterms:title|rdfs:label ?label .
        }}
    """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def get_dataset_construct(dataset_id: Optional[str] = None, dataset_uri: Optional[str] = None):
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
            ?p1 rdfs:label ?p1Label .
            ?o1 rdfs:label ?o1Label .
        }}
        WHERE {{
            {query_by_id if dataset_id is not None else query_by_uri}
            ?d ?p1 ?o1 .
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

async def list_collections(dataset_id: str):
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
                skos:prefLabel|dcterms:title|rdfs:label ?d_label .
            FILTER (STR(?d_id) = "{dataset_id}")
            ?coll a geo:FeatureCollection ;
                dcterms:isPartOf ?d ;
                dcterms:identifier ?id ;
                skos:prefLabel|dcterms:title|rdfs:label ?label .
        }}
    """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")