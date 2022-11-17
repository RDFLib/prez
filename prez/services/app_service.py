import time

import httpx

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


async def healthcheck_sparql_endpoints(settings):
    ENABLED_PREZS = settings.enabled_prezs
    if len(ENABLED_PREZS) > 0:
        for prez in ENABLED_PREZS:
            connected_to_prez_flavour = False
            print(f"Trying endpoint {settings.sparql_creds[prez]['endpoint']}")
            username = settings.sparql_creds[prez].get("username")
            password = settings.sparql_creds[prez].get("password")
            if username or password:
                auth = {"username": username, "password": password}
            else:
                auth = None
            while not connected_to_prez_flavour:
                try:
                    response = httpx.head(
                        settings.sparql_creds[prez]["endpoint"], auth=auth
                    )
                    response.raise_for_status()
                    if response.reason_phrase == "OK":
                        print(
                            f"Successfully connected to {prez} endpoint {settings.sparql_creds[prez]['endpoint']}"
                        )
                        connected_to_prez_flavour = True
                except httpx.HTTPError:
                    try:
                        response = httpx.get(
                            settings.sparql_creds[prez]["endpoint"],
                            auth=auth,
                            params={"query": "ASK {}"},
                        )
                        response.raise_for_status()
                        if response.status_code == 200:
                            print(
                                f"Successfully connected to {prez} endpoint {settings.sparql_creds[prez]['endpoint']}"
                            )
                            connected_to_prez_flavour = True
                    except httpx.HTTPError as exc:
                        print(f"HTTP Exception for {exc.request.url} - {exc}")
                        print(
                            f"Failed to connect to {prez} endpoint {settings.sparql_creds[prez]}"
                        )
                        print("retrying in 3 seconds...")
                        time.sleep(3)
    else:
        raise ValueError(
            'No Prezs enabled - set one or more Prez SPARQL endpoint environment variables: ("SPACEPREZ_SPARQL_ENDPOINT",'
            '"VOCPREZ_SPARQL_ENDPOINT", and "CATPREZ_SPARQL_ENDPOINT")'
        )
