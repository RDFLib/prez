import logging
from typing import Literal
import httpx
import config
import pickle
from pathlib import Path
api_home_dir = Path(__file__).parent
collections_pickle = Path(api_home_dir / "cache" / "collections.pickle")
conceptschemes_pickle = Path(api_home_dir / "cache" / "conceptschemes.pickle")


class TriplestoreError(Exception):
    pass


def sparql_query(query: str):
    r = httpx.post(
        config.SPARQL_ENDPOINT,
        data=query,
        headers={"Content-Type": "application/sparql-query"},
        auth=(config.SPARQL_USERNAME, config.SPARQL_PASSWORD)
    )
    if 200 <= r.status_code < 300:
        return True, r.json()["results"]["bindings"]
    else:
        return False, r.status_code, r.text


def cache_clear():
    logging.debug("cleared cache")
    if collections_pickle.is_file():
        collections_pickle.unlink()


def cache_fill(collections_or_conceptschemes_or_both: Literal["collections", "conceptschemes", "both"]):
    logging.debug(f"filled cache {collections_or_conceptschemes_or_both}")
    if collections_or_conceptschemes_or_both in ["collections", "both"]:
        q = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dcterms: <http://purl.org/dc/terms/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT *
            WHERE {
                ?uri a skos:Collection .
                BIND (STRAFTER(STRBEFORE(STR(?uri), "/current/"), "/collection/") AS ?id)
                OPTIONAL { ?uri skos:prefLabel ?prefLabel .
                    FILTER(lang(?prefLabel) = "en" || lang(?prefLabel) = "") 
                }
                OPTIONAL { ?uri dcterms:created ?created }
                OPTIONAL { ?uri dcterms:issued ?issued }
                OPTIONAL { 
                    ?uri dcterms:date ?m .
                    BIND (SUBSTR(?m, 0, 11) AS ?modified)
                }
                OPTIONAL { ?uri dcterms:creator ?creator }
                OPTIONAL { ?uri dcterms:publisher ?publisher }
                OPTIONAL { ?uri dcterms:conformsTo ?conforms_to }
                OPTIONAL { ?uri owl:versionInfo ?versionInfo }
                OPTIONAL { ?uri dcterms:description ?description .
                    FILTER(lang(?description) = "en" || lang(?description) = "") 
                }
                # NVS special properties                 
                OPTIONAL {
                    ?uri <http://www.isotc211.org/schemas/grg/RE_RegisterManager> ?registermanager .
                    ?uri <http://www.isotc211.org/schemas/grg/RE_RegisterOwner> ?registerowner .
                }            
                OPTIONAL { ?uri rdfs:seeAlso ?seeAlso }
            }
            ORDER BY ?prefLabel
            """

        collections_json = sparql_query(q)
        if collections_json[0]:  # i.e. we got no error
            with open(collections_pickle, "wb") as cache_file:
                pickle.dump(collections_json[1], cache_file)
        else:
            raise TriplestoreError(
                f"The call to fill the Collections index cache failed. Status Code: {collections_json[1]} , "
                f"Error: {collections_json[2]}"
            )


def cache_return(collections_or_conceptschemes: Literal["collections", "conceptschemes"]) -> dict:
    if collections_or_conceptschemes == "collections":
        if collections_pickle.is_file():
            with open(collections_pickle, "rb") as cache_file:
                return pickle.load(cache_file)
        else:
            cache_fill(collections_or_conceptschemes_or_both="collections")
            with open(collections_pickle, "rb") as cache_file:
                return pickle.load(cache_file)
