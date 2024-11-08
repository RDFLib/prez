import logging
from pathlib import Path

from rdflib import Graph

from prez.cache import profiles_graph_cache

log = logging.getLogger(__name__)


async def create_profiles_graph(repo) -> Graph:
    if (
        len(profiles_graph_cache) > 0
    ):  # pytest imports app.py multiple times, so this is needed. Not sure why cache is
        # not cleared between calls
        return
    for f in (Path(__file__).parent.parent / "reference_data/profiles").glob("*.ttl"):
        profiles_graph_cache.parse(f)
    log.info("Prez default profiles loaded")
    remote_profiles_query = """
        PREFIX prof: <http://www.w3.org/ns/dx/prof/>
        PREFIX prez: <https://prez.dev/>

        DESCRIBE ?prof {
            VALUES ?prof_class { prez:ListingProfile prez:ObjectProfile prez:IndexProfile }
            ?prof a ?prof_class
        }
        """
    g, _ = await repo.send_queries([remote_profiles_query], [])
    if len(g) > 0:
        profiles_graph_cache.__iadd__(g)
        log.info("Remote profile(s) found and added")
    else:
        log.info("No remote profiles found")
