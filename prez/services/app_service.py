import logging
import time

import httpx
from rdflib import Namespace
from rdflib.namespace import SKOS, DCTERMS, XSD

from prez.cache import counts_graph
from prez.services.sparql_queries import startup_count_objects
from prez.services.sparql_utils import sparql_construct

ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")

log = logging.getLogger(__name__)


async def get_object(uri: str):
    q = f"""
        PREFIX dcterms: <{DCTERMS}>
        PREFIX skos: <{SKOS}>
        PREFIX xsd: <{XSD}>
        SELECT ?type ?id ?cs_id
        WHERE {{
            <{uri}> a ?type ;
                dcterms:identifier ?id .
            FILTER(DATATYPE(?id) = prez:slug)
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
            log.info(
                f"Checking {prez} SPARQL endpoint {settings.sparql_creds[prez]['endpoint']} is online"
            )
            username = settings.sparql_creds[prez].get("username")
            password = settings.sparql_creds[prez].get("password")
            if username or password:
                auth = {"username": username, "password": password}
            else:
                auth = None
            while not connected_to_prez_flavour:
                try:
                    response = httpx.get(
                        settings.sparql_creds[prez]["endpoint"],
                        auth=auth,
                        params={"query": "ASK {}"},
                    )
                    response.raise_for_status()
                    if response.status_code == 200:
                        log.info(f"Successfully connected to {prez} SPARQL endpoint")
                        connected_to_prez_flavour = True
                except httpx.HTTPError as exc:
                    log.error(f"HTTP Exception for {exc.request.url} - {exc}")
                    log.error(
                        f"Failed to connect to {prez} endpoint {settings.sparql_creds[prez]}"
                    )
                    log.info("retrying in 3 seconds...")
                    time.sleep(3)
    else:
        raise ValueError(
            'No Prezs enabled - set one or more Prez SPARQL endpoint environment variables: ("SPACEPREZ_SPARQL_ENDPOINT",'
            '"VOCPREZ_SPARQL_ENDPOINT", and "CATPREZ_SPARQL_ENDPOINT")'
        )


async def count_objects(settings):
    query = startup_count_objects()
    for prez in settings.enabled_prezs:
        results = await sparql_construct(query, prez)
        if results[0]:
            counts_graph.__add__(results[1])
