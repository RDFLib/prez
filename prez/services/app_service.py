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
    ENABLED_PREZS = settings.enabled_prezs.split("|")
    if len(ENABLED_PREZS) > 0:
        for prez in ENABLED_PREZS:
            connected_to_prez_flavour = False
            while not connected_to_prez_flavour:
                try:
                    print(f"Trying endpoint {settings.sparql_creds[prez]['endpoint']}")
                    username = settings.sparql_creds[prez].get("username")
                    password = settings.sparql_creds[prez].get("password")
                    if username or password:
                        auth = {"username": username, "password": password}
                    else:
                        auth = None
                    response = httpx.head(
                        settings.sparql_creds[prez]["endpoint"], auth=auth
                    )
                    response.raise_for_status()
                    if response.reason_phrase == "OK":
                        print(
                            f"Successfully connected to {prez} endpoint {settings.sparql_creds[prez]['endpoint']}"
                        )

                        # Check whether there are any remote profiles, and if so, cache them.
                        # If there will be remote profiles but they haven't yet been loaded to fuseki, they will be not be
                        # cached at startup, but will be cached after any endpoint using profiles is called.
                        # query_for_profiles = """PREFIX prof: <http://www.w3.org/ns/dx/prof/>
                        #                         DESCRIBE ?profile { ?profile a prof:Profile } LIMIT 1"""
                        # query_success, profiles_g = await sparql_construct(
                        #     query_for_profiles, prez
                        # )
                        # if query_success and len(profiles_g) > 0:
                        #     print(
                        #         f"Profiles found in data store for {prez}, caching them"
                        #     )
                        #     if prez == "CatPrez":
                        #         get_general_profiles(DCAT.Dataset)
                        #         get_general_profiles(DCAT.Resource)
                        #     if prez == "SpacePrez":
                        #         get_general_profiles(DCAT.Dataset)
                        #         get_general_profiles(GEO.FeatureCollection)
                        #         get_general_profiles(GEO.Feature)
                        #     if prez == "VocPrez":
                        #         pass
                        # else:
                        #     print(
                        #         f"No profiles found in data store for {prez}, continuing with startup"
                        #     )
                        connected_to_prez_flavour = True
                    else:
                        raise httpx.HTTPError
                        # are there any non "OK" responses that would *not* raise for status?
                except httpx.HTTPError as exc:
                    print(f"HTTP Exception for {exc.request.url} - {exc}")
                    print(f"Failed to connect to {prez} endpoint {sparql_creds[prez]}")
                    print("retrying in 3 seconds...")
                    time.sleep(3)
    else:
        raise ValueError(
            'No Prezs enabled - set "ENABLED_PREZS" environment variable to a list of enabled Prezs'
        )
