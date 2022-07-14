from prez.services.sparql_utils import *


async def get_object(uri: str):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        PREFIX xsd: <{XSD}>
        SELECT ?type ?id ?cs_id
        WHERE {{
            <{uri}> a ?type ;
                dcterms:identifier ?id .
            FILTER(DATATYPE(?id) = xsd:token)
            OPTIONAL {{
                <{uri}> skos:inScheme|skos:topConceptOf ?cs .
                ?cs dcterms:identifier ?cs_id .
            }}
        }}
    """
    r = await sparql_query_multiple(q)
    if len(r[1]) > 0 and not ALLOW_PARTIAL_RESULTS:
        error_list = [
            f"Error code {e['code']} in {e['prez']}: {e['message']}\n" for e in r[1]
        ]
        raise Exception(f"SPARQL query error:\n{[e for e in error_list]}")
    else:
        return r[0]
