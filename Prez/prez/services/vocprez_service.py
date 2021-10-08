from rdflib.namespace import RDFS, DCAT

from config import *
from services.sparql_utils import *


# get dataset


async def get_datasets():
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


# get schemes

# get scheme

# get collections

# get collection

# get concepts

# get concept
