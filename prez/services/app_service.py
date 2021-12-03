from rdflib.namespace import DCTERMS, SKOS

from config import *
from services.sparql_utils import *


async def get_object(uri: str):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        SELECT ?type ?id ?cs_id
        WHERE {{
            <{uri}> a ?type ;
                dcterms:identifier ?id .
            
            OPTIONAL {{
                <{uri}> skos:inScheme|skos:topConceptOf ?cs .
                ?cs dcterms:identifier ?cs_id .
            }}
        }}
    """
    r = await sparql_query(q)
    if r[0]:
        return r[1]
    else:
        raise Exception(f"SPARQL query error code {r[1]}: {r[2]}")

