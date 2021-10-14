from rdflib.namespace import RDFS, DCAT, DCTERMS

from config import *
from services.sparql_utils import *


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


async def get_scheme(scheme_id: str):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        SELECT *
        WHERE {{
            ?cs dcterms:identifier '{scheme_id}'@en ;
                a skos:ConceptScheme ;
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
            ?collection dcterms:identifier '{collection_id}'@en ;
                a skos:Collection ;
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


# get concept
async def get_concept(scheme_id: str, concept_id: str):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX rdfs: <{RDFS}>
        PREFIX skos: <{SKOS}>
        SELECT *
        WHERE {{
            ?c dcterms:identifier '{concept_id}'@en ;
                a skos:Concept ;
                skos:inScheme ?cs ;
                ?p1 ?o1 .
            BIND ('{scheme_id}'@en as ?cs_id)
            ?cs dcterms:identifier '{scheme_id}'@en ;
                skos:prefLabel ?csLabel .
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
            ?collection dcterms:identifier '{collection_id}'@en ;
                a skos:Collection ;
                skos:member ?c .
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


async def get_concept_hierarchy(scheme_id: str):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        SELECT DISTINCT ?c ?label ?id ?narrower ?broader
        WHERE {{
            ?cs dcterms:identifier '{scheme_id}'@en ;
                a skos:ConceptScheme .
            
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
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def get_broader_concepts(concept_id: str):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        SELECT DISTINCT ?broader ?id ?cs_id ?label
        WHERE {{
            ?c dcterms:identifier '{concept_id}'@en ;
                a skos:Concept .
            {{
                ?c skos:broader ?broader .
            }}
            UNION
            {{
                ?broader skos:narrower ?c .
            }}
            ?broader a skos:Concept ;
                dcterms:identifier ?id ;
                skos:prefLabel ?label ;
                skos:inScheme|skos:topConceptOf ?cs .
            ?cs dcterms:identifier ?cs_id .
        }}
    """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")


async def get_narrower_concepts(concept_id: str):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        SELECT DISTINCT ?narrower ?id ?cs_id ?label
        WHERE {{
            ?c dcterms:identifier '{concept_id}'@en ;
                a skos:Concept .
            {{
                ?c skos:narrower ?narrower .
            }}
            UNION
            {{
                ?narrower skos:broader ?c .
            }}
            ?narrower a skos:Concept ;
                dcterms:identifier ?id ;
                skos:prefLabel ?label ;
                skos:inScheme|skos:topConceptOf ?cs .
            ?cs dcterms:identifier ?cs_id .
        }}
    """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")
