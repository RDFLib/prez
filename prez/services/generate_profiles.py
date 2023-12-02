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
        PREFIX dcat: <http://www.w3.org/ns/dcat#>
        PREFIX geo: <http://www.opengis.net/ont/geosparql#>
        PREFIX prof: <http://www.w3.org/ns/dx/prof/>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

        CONSTRUCT {?s ?p ?o .
                    ?o ?p2 ?o2 .
                    ?o2 ?p3 ?o3 .
                    ?class ?cp ?co}
        WHERE {?s a prof:Profile ;
                      ?p ?o
          OPTIONAL {?o ?p2 ?o2
            FILTER(ISBLANK(?o))
            OPTIONAL {?o2 ?p3 ?o3
            FILTER(ISBLANK(?o2))}
          }
          OPTIONAL {
            ?class rdfs:subClassOf dcat:Resource ;
                ?cp ?co .
          }
          OPTIONAL {
            ?class rdfs:subClassOf geo:Feature ;
                ?cp ?co .
          }
          OPTIONAL {
            ?class rdfs:subClassOf skos:Concept ;
                ?cp ?co .
          }
        }
        """
    g, _ = await repo.send_queries([remote_profiles_query], [])
    if len(g) > 0:
        profiles_graph_cache.__iadd__(g)
        log.info(f"Remote profile(s) found and added")
    else:
        log.info("No remote profiles found")
