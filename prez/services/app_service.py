import logging
import time

import httpx
from rdflib import Namespace

from prez.cache import counts_graph
from prez.config import settings
from prez.services.sparql_queries import startup_count_objects
from prez.services.sparql_utils import sparql_construct

ALTREXT = Namespace("http://www.w3.org/ns/dx/conneg/altr-ext#")

log = logging.getLogger(__name__)


async def healthcheck_sparql_endpoints():
    ENABLED_PREZS = settings.enabled_prezs
    log.info(f"Enabled Prezs: {', '.join(ENABLED_PREZS)}")
    if len(ENABLED_PREZS) > 0:
        for prez in ENABLED_PREZS:
            connected_to_prez_flavour = False
            log.info(
                f"Checking {prez} SPARQL endpoint {settings.sparql_creds[prez]['endpoint']} is online"
            )
            username = settings.sparql_creds[prez].get("username")
            password = settings.sparql_creds[prez].get("password")
            if username or password:
                auth = (username, password)
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


async def count_objects():
    query = startup_count_objects()
    for prez in settings.enabled_prezs:
        results = await sparql_construct(query, prez)
        if results[0]:
            counts_graph.__add__(results[1])
