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
        auth=(config.SPARQL_USERNAME, config.SPARQL_PASSWORD),
        timeout=60.0
    )
    if 200 <= r.status_code < 300:
        return True, r.json()["results"]["bindings"]
    else:
        return False, r.status_code, r.text


def sparql_construct(query: str, rdf_mediatype="text/turtle"):
    r = httpx.post(
        config.SPARQL_ENDPOINT,
        data=query,
        headers={"Content-Type": "application/sparql-query", "Accept": rdf_mediatype},
        auth=(config.SPARQL_USERNAME, config.SPARQL_PASSWORD),
        timeout=60.0
    )
    if 200 <= r.status_code < 300:
        return True, r.content
    else:
        return False, r.status_code, r.text


def cache_clear():
    logging.debug("cleared cache")
    if collections_pickle.is_file():
        collections_pickle.unlink()
    if conceptschemes_pickle.is_file():
        conceptschemes_pickle.unlink()


def cache_fill(collections_or_conceptschemes_or_both: Literal["collections", "conceptschemes", "both"] = "both"):
    logging.debug(f"filled cache {collections_or_conceptschemes_or_both}")
    if collections_or_conceptschemes_or_both == "collections":
        q = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dcterms: <http://purl.org/dc/terms/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT *
            WHERE {
                ?uri a skos:Collection .
                BIND (STRAFTER(STRBEFORE(STR(?uri), "/current/"), "/collection/") AS ?id)
                BIND (STRAFTER(STR(?uri), ".uk") AS ?systemUri)
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
    elif collections_or_conceptschemes_or_both == "conceptschemes":
        q = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dcterms: <http://purl.org/dc/terms/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?uri ?id ?systemUri ?prefLabel ?modified ?creator ?publisher ?versionInfo ?description
            WHERE {
                ?uri a skos:ConceptScheme .
                BIND (STRAFTER(STRBEFORE(STR(?uri), "/current/"), "/scheme/") AS ?id)
                BIND (STRAFTER(STR(?uri), ".uk") AS ?systemUri)
                OPTIONAL { ?uri skos:prefLabel ?prefLabel .
                    FILTER(lang(?prefLabel) = "en" || lang(?prefLabel) = "") 
                }
                OPTIONAL { 
                    ?uri dcterms:date ?m .
                    BIND (SUBSTR(?m, 0, 11) AS ?modified)
                }
                OPTIONAL { ?uri dcterms:creator ?creator }
                OPTIONAL { ?uri dcterms:publisher ?publisher }
                OPTIONAL { ?uri owl:versionInfo ?versionInfo }
                OPTIONAL { ?uri dcterms:description ?description .
                    FILTER(lang(?description) = "en" || lang(?description) = "") 
                }
            }
            ORDER BY ?prefLabel
            """

        conceptschemes_json = sparql_query(q)
        if conceptschemes_json[0]:  # i.e. we got no error
            with open(conceptschemes_pickle, "wb") as cache_file:
                pickle.dump(conceptschemes_json[1], cache_file)
        else:
            raise TriplestoreError(
                f"The call to fill the Concept Schemes index cache failed. Status Code: {conceptschemes_json[1]} , "
                f"Error: {conceptschemes_json[2]}"
            )
    else:  # both
        pass


def cache_return(collections_or_conceptschemes: Literal["collections", "conceptschemes"]) -> dict:
    if collections_or_conceptschemes == "collections":
        if not collections_pickle.is_file():
            cache_fill(collections_or_conceptschemes_or_both="collections")

        with open(collections_pickle, "rb") as cache_file:
            return pickle.load(cache_file)

    elif collections_or_conceptschemes == "conceptschemes":
        if not conceptschemes_pickle.is_file():
            cache_fill(collections_or_conceptschemes_or_both="conceptschemes")

        with open(conceptschemes_pickle, "rb") as cache_file:
            return pickle.load(cache_file)

    def draw_concept_hierarchy(hierarchy):
        tab = "\t"
        previous_length = 1

        text = ""
        tracked_items = []
        for item in hierarchy:
            mult = None

            if item[0] > previous_length + 2:  # SPARQL query error on length value
                for tracked_item in tracked_items:
                    if tracked_item["name"] == item[3]:
                        mult = tracked_item["indent"] + 1

            if mult is None:
                found = False
                for tracked_item in tracked_items:
                    if tracked_item["name"] == item[3]:
                        found = True
                if not found:
                    mult = 0

            if mult is None:  # else: # everything is normal
                mult = item[0] - 1

            t = tab * mult + "* [" + item[2] + "](" + get_content_uri(item[1]) + ")\n"
            text += t
            previous_length = mult
            tracked_items.append({"name": item[1], "indent": mult})

        return markdown.markdown(text)


def render_concept_tree(html_doc):
    soup = BeautifulSoup(html_doc, "html.parser")

    # concept_hierarchy = soup.find(id='concept-hierarchy')

    uls = soup.find_all("ul")

    for i, ul in enumerate(uls):
        # Don't add HTML class nested to the first 'ul' found.
        if not i == 0:
            ul["class"] = "nested"
            if ul.parent.name == "li":
                temp = BeautifulSoup(str(ul.parent.a.extract()), "html.parser")
                ul.parent.insert(
                    0, BeautifulSoup('<span class="caret">', "html.parser")
                )
                ul.parent.span.insert(0, temp)
    return soup
