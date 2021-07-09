import logging
from typing import Optional, AnyStr
from pathlib import Path
import fastapi
import uvicorn
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response, PlainTextResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from pyldapi.renderer import RDF_MEDIATYPES
from model.profiles import void, nvs
from utils import sparql_query, sparql_construct, cache_return, cache_clear, cache_fill, TriplestoreError
from pyldapi import Renderer, ContainerRenderer
from config import SYSTEM_URI, PORT
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, RDFS

api_home_dir = Path(__file__).parent
api = fastapi.FastAPI()
templates = Jinja2Templates(str(api_home_dir / "view" / "templates"))
api.mount("/static", StaticFiles(directory=str(api_home_dir / "view" / "static")), name="static")
logging.basicConfig(level=logging.DEBUG)


# @api.on_event("startup")
# def startup():
#     cache_clear()
#     cache_fill(collections_or_conceptschemes_or_both="both")


@api.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@api.get("/collection/")
def collections(request: Request):
    class CollectionRenderer(ContainerRenderer):
        def __init__(self):
            self.instance_uri = str(request.url).split("?")[0]
            self.label = "NVS Vocabularies"
            self.comment = "SKOS concept collections held in the NERC Vocabulary Server. A concept collection " \
                           "is useful where a group of concepts shares something in common, and it is convenient " \
                           "to group them under a common label. In the NVS, concept collections are synonymous " \
                           "with controlled vocabularies or code lists. Each collection is associated with its " \
                           "governance body. An external website link is displayed when applicable."
            super().__init__(
                request,
                self.instance_uri,
                {"nvs": nvs},
                "nvs",
            )

        def render(self):
            if self.profile == "nvs":
                if self.mediatype == "text/html":
                    collections = cache_return(collections_or_conceptschemes="collections")

                    if request.query_params.get("filter"):
                        def concat_vocab_fields(vocab):
                            return f"{vocab['id']['value']}" \
                                   f"{vocab['prefLabel']['value']}" \
                                   f"{vocab['description']['value']}"

                        collections = [x for x in collections if
                                       request.query_params.get("filter") in concat_vocab_fields(x)]

                    return templates.TemplateResponse(
                        "collections.html",
                        {
                            "request": request,
                            "uri": self.instance_uri,
                            "label": self.label,
                            "comment": self.comment,
                            "collections": collections,
                            "profile_token": "nvs",
                        }
                    )
                elif self.mediatype in RDF_MEDIATYPES:
                    q = """
                        PREFIX dc: <http://purl.org/dc/terms/>
                        PREFIX grg: <http://www.isotc211.org/schemas/grg/>
                        PREFIX owl: <http://www.w3.org/2002/07/owl#>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

                        CONSTRUCT {
                            ?cs a skos:Collection ;
                                dc:alternative ?alternative ;
                                dc:creator ?creator ;
                                dc:date ?date ;
                                dc:description ?description ;
                                dc:publisher ?publisher ;
                                dc:title ?title ;
                                rdfs:comment ?comment ;
                                owl:versionInfo ?version ;
                                skos:altLabel ?al ;
                                skos:narrower ?narrower ;
                                skos:prefLabel ?pl .

                            ?cs
                                grg:RE_RegisterManager ?registermanager ;
                                grg:RE_RegisterOwner ?registerowner .

                            ?cs rdfs:seeAlso ?seeAlso .
                        }
                        WHERE {
                            ?cs a skos:Collection ;
                                dc:alternative ?alternative ;
                                dc:creator ?creator ;
                                dc:date ?date ;
                                dc:description ?description ;
                                dc:publisher ?publisher ;
                                dc:title ?title ;
                                rdfs:comment ?comment ;
                                owl:versionInfo ?version ;
                                skos:prefLabel ?pl .

                            OPTIONAL { ?cs skos:altLabel ?al }
                            OPTIONAL { ?cs skos:narrower ?narrower }
                            OPTIONAL {
                                ?cs skos:prefLabel ?pl .
                                FILTER(lang(?pl) = "en" || lang(?pl) = "")
                            }
                            OPTIONAL {
                                ?cs grg:RE_RegisterManager ?registermanager .
                                ?cs grg:RE_RegisterManager ?registerowner .
                            }
                            OPTIONAL { ?cs rdfs:seeAlso ?seeAlso }
                        }
                        """
                    r = sparql_construct(q, self.mediatype)
                    if r[0]:
                        return Response(r[1], headers={"Content-Type": self.mediatype})
                    else:
                        return PlainTextResponse(
                            "There was an error obtaining the Collections RDF from the Triplestore",
                            status_code=500
                        )
            elif self.profile == "mem":
                collections = []
                for c in cache_return(collections_or_conceptschemes="collections"):
                    collections.append({
                        "uri": c["uri"]["value"],
                        "systemUri": c["systemUri"]["value"],
                        "label": c["prefLabel"]["value"]}
                    )

                if self.mediatype == "text/html":
                    return templates.TemplateResponse(
                        "collections_mem.html",
                        {
                            "request": request,
                            "uri": self.instance_uri,
                            "label": self.label,
                            "collections": collections,
                            "profile_token": "nvs",
                        }
                    )
                elif self.mediatype == "application/json":
                    return [{"uri": c["uri"], "label": c["prefLabel"]} for c in collections]
                else:  # all other available mediatypes are RDF
                    g = Graph()
                    container = URIRef(self.instance_uri)
                    g.add((container, RDF.type, RDF.Bag))
                    g.add((container, RDFS.label, Literal(self.label)))
                    for c in collections:
                        g.add((container, RDFS.member, URIRef(c["uri"])))
                        g.add((URIRef(c["uri"]), RDFS.label, Literal(c["label"])))
                    return Response(
                        g.serialize(format=self.mediatype),
                        media_type=self.mediatype
                    )
            elif self.profile == "contanno":
                if self.mediatype == "text/html":
                    return templates.TemplateResponse(
                        "collections_contanno.html",
                        {
                            "request": request,
                            "uri": self.instance_uri,
                            "label": self.label,
                            "comment": self.comment,
                            "profile_token": "nvs",
                        }
                    )
                else:  # all other available mediatypes are RDF
                    g = Graph()
                    container = URIRef(self.instance_uri)
                    g.add((container, RDF.type, RDF.Bag))
                    g.add((container, RDFS.label, Literal(self.label)))
                    c = "This object is a container that contains a number of members. See other profiles of this " \
                        "object to see those members."
                    c += self.comment
                    g.add((container, RDFS.comment, Literal(c)))
                    return Response(
                        g.serialize(format=self.mediatype),
                        media_type=self.mediatype
                    )

            alt = super().render()
            if alt is not None:
                return alt

    return CollectionRenderer().render()


@api.get("/scheme/")
def conceptschemes(request: Request):
    class ConceptSchemeRenderer(Renderer):
        def __init__(self):
            super().__init__(
                request,
                str(request.url).split("?")[0],
                {"nvs": nvs},
                "nvs",
            )

        def render(self):
            alt = super().render()
            if alt is not None:
                return alt
            if self.profile == "nvs":
                if self.mediatype == "text/html":
                    conceptschemes = cache_return(collections_or_conceptschemes="conceptschemes")

                    if request.query_params.get("filter"):
                        def concat_vocab_fields(vocab):
                            return f"{vocab['id']['value']}" \
                                   f"{vocab['prefLabel']['value']}" \
                                   f"{vocab['description']['value']}"

                        conceptschemes = [x for x in conceptschemes if
                                       request.query_params.get("filter") in concat_vocab_fields(x)]

                    return templates.TemplateResponse(
                        "conceptschemes.html",
                        {
                            "request": request,
                            "conceptschemes": conceptschemes,
                            "profile_token": "nvs",
                        }
                    )
                elif self.mediatype in RDF_MEDIATYPES:
                    q = """
                        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                        PREFIX dc: <http://purl.org/dc/terms/>
                        PREFIX owl: <http://www.w3.org/2002/07/owl#>
                        CONSTRUCT {
                            ?cs a skos:ConceptScheme ;
                                dc:alternative ?alt ;
                                dc:creator ?creator ;
                                dc:date ?modified ;
                                dc:publisher ?publisher ;
                                dc:title ?title ;
                                owl:versionInfo ?version ;
                                skos:hasTopConcept ?tc ;
                                skos:altLabel ?al ;
                                dc:description ?description ;
                                skos:prefLabel ?pl .
                        }
                        WHERE {
                            ?cs a skos:ConceptScheme ;
                                dc:alternative ?alt ;
                                dc:creator ?creator ;
                                dc:date ?modified ;
                                dc:publisher ?publisher ;
                                dc:title ?title ;
                                owl:versionInfo ?version ;

                            OPTIONAL {?cs skos:hasTopConcept ?tc .}
                            OPTIONAL { ?cs skos:altLabel ?al . }
                            {
                                ?cs dc:description ?description .
                                FILTER(lang(?description) = "en" || lang(?description) = "")
                            }
                            {
                                ?cs skos:prefLabel ?pl .
                                FILTER(lang(?title) = "en" || lang(?pl) = "")
                            }
                        }
                        """
                    r = sparql_construct(q, self.mediatype)
                    if r[0]:
                        return Response(r[1], headers={"Content-Type": self.mediatype})
                    else:
                        return PlainTextResponse(
                            "There was an error obtaining the Collections RDF from the Triplestore",
                            status_code=500
                        )

    return ConceptSchemeRenderer().render()


@api.get("/about")
def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


@api.get("/.well_known/")
def well_known(request: Request):
    return RedirectResponse(url="/.well_known/void")


@api.get("/.well_known/void")
def well_known_void(
        request: Request,
        _profile: Optional[AnyStr] = None,
        _mediatype: Optional[AnyStr] = "text/turtle"):

    void_file = api_home_dir / "void.ttl"

    class WkRenderer(Renderer):
        def __init__(self):
            super().__init__(
                request,
                "http://vocab.nerc.ac.uk/.well_known/void",
                {"void": void},
                "void",
            )

        def render(self):
            if self.mediatype == "text/turtle":
                return Response(open(void_file).read(), headers={"Content-Type": "text/turtle"})
            else:
                from rdflib import Graph
                logging.debug(f"media type: {self.mediatype}")
                g = Graph().parse(void_file, format="turtle")
                logging.debug(len(g))
                return Response(
                    content=g.serialize(format=self.mediatype),
                    headers={"Content-Type": self.mediatype}
                )

    return WkRenderer().render()


@api.get("/contact")
@api.get("/contact-us")
def about(request: Request):
    return templates.TemplateResponse("contact_us.html", {"request": request})


@api.get("/cache-clear")
def about(request: Request):
    cache_clear()
    return PlainTextResponse("Cache cleared")


if __name__ == "__main__":
    uvicorn.run(api, port=PORT, host=SYSTEM_URI)
