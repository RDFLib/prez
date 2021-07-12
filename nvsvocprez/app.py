import logging
from typing import Optional, AnyStr, Literal
from pathlib import Path
import fastapi
import uvicorn
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response, PlainTextResponse, JSONResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from pyldapi.renderer import RDF_MEDIATYPES
from pyldapi.data import RDF_FILE_EXTS
from profiles import void, nvs, skos, dd, vocpub, dcat, puv, sdo
from utils import sparql_query, sparql_construct, cache_return, cache_clear, get_accepts
from pyldapi import Renderer, ContainerRenderer, DisplayProperty
from config import SYSTEM_URI, PORT
from rdflib import Graph, URIRef
from rdflib import Literal as RdfLiteral, Namespace
from rdflib.namespace import DC, DCTERMS, ORG, OWL, RDF, RDFS, SKOS, VOID


api_home_dir = Path(__file__).parent
api = fastapi.FastAPI()
templates = Jinja2Templates(str(api_home_dir / "view" / "templates"))
api.mount("/static", StaticFiles(directory=str(api_home_dir / "view" / "static")), name="static")
logging.basicConfig(level=logging.DEBUG)
acc_dep_map = {
    "accepted": '?c <http://www.w3.org/2002/07/owl#deprecated> "false" .',
    "deprecated": '?c <http://www.w3.org/2002/07/owl#deprecated> "true" .',
    None: ""
}


@api.get("/")
def index(request: Request):
    dcat_file = api_home_dir / "dcat.ttl"
    sdo_file = api_home_dir / "sdo.ttl"

    class DatasetRenderer(Renderer):
        def __init__(self):
            self.instance_uri = str(request.base_url)
            self.label = "NERC Vocabulary Server Content"
            self.comment = "The NVS gives access to standardised and hierarchically-organized vocabularies. It is " \
                           "managed by the British Oceanographic Data Centre at the National Oceanography Centre " \
                           "(NOC) in Liverpool and Southampton, and receives funding from the Natural Environment " \
                           "Research Council (NERC) in the United Kingdom. Major technical developments have also " \
                           "been funded by European Union's projects notably the Open Service Network for Marine " \
                           "Environmental Data (NETMAR) programme, and the SeaDataNet and SeaDataCloud projects."
            super().__init__(
                request,
                self.instance_uri,
                {"dcat": dcat, "sdo": sdo},
                "dcat",
            )

        def render(self):
            if self.profile == "dcat":
                if self.mediatype == "text/html":
                    return templates.TemplateResponse("index.html", {"request": request})
                else:  # all other formats are RDF
                    if self.mediatype == "text/turtle":
                        return Response(
                            open(dcat_file).read().replace("xxx", self.instance_uri),
                            headers={"Content-Type": "text/turtle"}
                        )
                    else:
                        g = Graph().parse(
                            data=open(dcat_file).read().replace("xxx", self.instance_uri),
                            format="turtle"
                        )
                        return Response(
                            content=g.serialize(format=self.mediatype),
                            headers={"Content-Type": self.mediatype}
                        )
            elif self.profile == "sdo":
                if self.mediatype == "text/turtle":
                    return Response(
                        open(sdo_file).read().replace("xxx", self.instance_uri),
                        headers={"Content-Type": "text/turtle"}
                    )
                else:
                    g = Graph().parse(
                        data=open(sdo_file).read().replace("xxx", self.instance_uri),
                        format="turtle"
                    )
                    return Response(
                        content=g.serialize(format=self.mediatype),
                        headers={"Content-Type": self.mediatype}
                    )

            alt = super().render()
            if alt is not None:
                return alt

    return DatasetRenderer().render()


@api.get("/collection/")
def collections(request: Request):
    class CollectionsRenderer(ContainerRenderer):
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
                            "profile_token": self.profile,
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
                        "container_mem.html",
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
                    g.add((container, RDFS.label, RdfLiteral(self.label)))
                    for c in collections:
                        g.add((container, RDFS.member, URIRef(c["uri"])))
                        g.add((URIRef(c["uri"]), RDFS.label, RdfLiteral(c["label"])))
                    return Response(
                        g.serialize(format=self.mediatype),
                        media_type=self.mediatype
                    )
            elif self.profile == "contanno":
                if self.mediatype == "text/html":
                    return templates.TemplateResponse(
                        "container_contanno.html",
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
                    g.add((container, RDFS.label, RdfLiteral(self.label)))
                    c = "This object is a container that contains a number of members. See other profiles of this " \
                        "object to see those members."
                    c += self.comment
                    g.add((container, RDFS.comment, RdfLiteral(c)))
                    return Response(
                        g.serialize(format=self.mediatype),
                        media_type=self.mediatype
                    )

            alt = super().render()
            if alt is not None:
                return alt

    return CollectionsRenderer().render()


@api.get("/scheme/")
def conceptschemes(request: Request):
    class ConceptSchemeRenderer(ContainerRenderer):
        def __init__(self):
            self.instance_uri = str(request.url).split("?")[0]
            self.label = "NVS Thesauri"
            self.comment = "SKOS concept schemes managed by the NERC Vocabulary Server. A concept scheme can be " \
                           "viewed as an aggregation of one or more SKOS concepts. Semantic relationships (links) " \
                           "between those concepts may also be viewed as part of a concept scheme. A concept scheme " \
                           "is therefore useful for containing the concepts registered in multiple concept " \
                           "collections that relate to each other as a single semantic unit, such as a thesaurus."
            super().__init__(
                request,
                str(request.url).split("?")[0],
                {"nvs": nvs},
                "nvs",
            )

        def render(self):
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
                            "uri": self.instance_uri,
                            "label": self.label,
                            "comment": self.comment,
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
                                dc:date ?m ;
                                dc:publisher ?publisher ;
                                dc:title ?title ;
                                owl:versionInfo ?version ;
                            .
                            BIND (STRDT(REPLACE(STRBEFORE(?m, "."), " ", "T"), xsd:dateTime) AS ?modified)

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
            elif self.profile == "mem":
                collections = []
                for c in cache_return(collections_or_conceptschemes="conceptschemes"):
                    collections.append({
                        "uri": c["uri"]["value"],
                        "systemUri": c["systemUri"]["value"],
                        "label": c["prefLabel"]["value"]}
                    )

                if self.mediatype == "text/html":
                    return templates.TemplateResponse(
                        "container_mem.html",
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
                    g.add((container, RDFS.label, RdfLiteral(self.label)))
                    for c in collections:
                        g.add((container, RDFS.member, URIRef(c["uri"])))
                        g.add((URIRef(c["uri"]), RDFS.label, RdfLiteral(c["label"])))
                    return Response(
                        g.serialize(format=self.mediatype),
                        media_type=self.mediatype
                    )
            elif self.profile == "contanno":
                if self.mediatype == "text/html":
                    return templates.TemplateResponse(
                        "container_contanno.html",
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
                    g.add((container, RDFS.label, RdfLiteral(self.label)))
                    c = "This object is a container that contains a number of members. See other profiles of this " \
                        "object to see those members."
                    c += self.comment
                    g.add((container, RDFS.comment, RdfLiteral(c)))
                    return Response(
                        g.serialize(format=self.mediatype),
                        media_type=self.mediatype
                    )
            alt = super().render()
            if alt is not None:
                return alt

    return ConceptSchemeRenderer().render()


@api.get("/collection/{collection_id}")
@api.get("/collection/{collection_id}/")
def collection_no_current(request: Request, collection_id):
    return RedirectResponse(url=f"/collection/{collection_id}/current/")


@api.get("/collection/{collection_id}/current/")
@api.get("/collection/{collection_id}/current/{acc_dep_or_concept}")
@api.get("/collection/{collection_id}/current/{acc_dep_or_concept}/")
def collection(
        request: Request,
        collection_id,
        acc_dep_or_concept: str = None
):
    if acc_dep_or_concept not in ["accepted", "deprecated", None]:
        # this is a call for a Concept
        return concept(request)

    class CollectionRenderer(Renderer):
        def __init__(self):
            self.instance_uri = f"http://vocab.nerc.ac.uk/collection/{collection_id}/current/"

            super().__init__(
                request,
                self.instance_uri,
                {
                    "nvs": nvs,
                    "skos": skos,
                    "vocpub": vocpub,
                    "dd": dd
                },
                "nvs",
            )

        def _get_collection(self):
            for collection in cache_return(collections_or_conceptschemes="collections"):
                if collection["id"]["value"] == collection_id:
                    return collection

        def _get_concepts(self):
            q = """
                PREFIX dcterms: <http://purl.org/dc/terms/>
                PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                SELECT DISTINCT ?c ?systemUri ?id ?pl ?def ?date ?dep
                WHERE {
                        <xxx> skos:member ?c .
                        BIND (STRBEFORE(STRAFTER(STR(?c), "/current/"), "/") AS ?id)
                        BIND (STRAFTER(STR(?c), ".uk") AS ?systemUri)

                        acc_dep
                        OPTIONAL {
                            ?c <http://www.w3.org/2002/07/owl#deprecated> ?dep .
                        }
                        ?c skos:prefLabel ?pl ;
                             skos:definition ?def ;
                             dcterms:date ?date .

                        FILTER(lang(?pl) = "en" || lang(?pl) = "") 
                        FILTER(lang(?def) = "en" || lang(?def) = "")
                }
                ORDER BY ?pl
                """.replace("xxx", self.instance_uri).replace("acc_dep", acc_dep_map.get(acc_dep_or_concept))

            sparql_result = sparql_query(q)
            if sparql_result[0]:
                return [
                    {
                        "uri": concept["c"]["value"],
                        "id": concept["id"]["value"],
                        "systemUri": concept["systemUri"]["value"],
                        "prefLabel": concept["pl"]["value"].replace("_", " "),
                        "definition": concept["def"]["value"].replace("_", "_ "),
                        "date": concept["date"]["value"][0:10],
                        "deprecated": True if concept.get("dep") and concept["dep"]["value"] == "true" else False
                    }
                    for concept in sparql_result[1]
                ]
            else:
                return False

        def render(self):
            if self.profile == "nvs":
                if self.mediatype == "text/html":
                    collection = self._get_collection()
                    collection["concepts"] = self._get_concepts()

                    if not collection["concepts"]:
                        return templates.TemplateResponse(
                            "error.html",
                            {
                                "request": request,
                                "title": "DB Error",
                                "status": "500",
                                "message": "There was an error with accessing the Triplestore",
                            }
                        )

                    return templates.TemplateResponse(
                        "collection.html",
                        {
                            "request": request,
                            "uri": self.instance_uri,
                            "collection": collection,
                            "profile_token": self.profile,
                        }
                    )
                elif self.mediatype in RDF_MEDIATYPES:
                    q = """
                        PREFIX dc: <http://purl.org/dc/terms/>
                        PREFIX dce: <http://purl.org/dc/elements/1.1/>
                        PREFIX grg: <http://www.isotc211.org/schemas/grg/>
                        PREFIX owl: <http://www.w3.org/2002/07/owl#>
                        PREFIX pav: <http://purl.org/pav/>
                        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                        PREFIX void: <http://rdfs.org/ns/void#>
                        
                        CONSTRUCT {
                          <xxx> ?p ?o .                           
                          <xxx> skos:member ?m .                        
                          ?m ?p2 ?o2 .              
                        }
                        WHERE {
                          {
                            <xxx> ?p ?o .                          
                            MINUS { <xxx> skos:member ?o . }
                          }
                          
                          {
                            <xxx> skos:member ?m .
                            ?m a skos:Concept .
                        
                            ?m ?p2 ?o2 .
                        
                            FILTER ( ?p2 != skos:broaderTransitive )
                            FILTER ( ?p2 != skos:narrowerTransitive )
                          }
                        }
                        """.replace("xxx", self.instance_uri)
                    r = sparql_construct(q, self.mediatype)
                    if r[0]:
                        return Response(r[1], headers={"Content-Type": self.mediatype})
                    else:
                        return PlainTextResponse(
                            "There was an error obtaining the Collections RDF from the Triplestore",
                            status_code=500
                        )
            elif self.profile == "dd":
                q = """
                    PREFIX dcterms: <http://purl.org/dc/terms/>
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    SELECT DISTINCT ?c ?pl
                    WHERE {
                        <xxx> skos:member ?c .
                        ?c skos:prefLabel ?pl .
                    }
                    ORDER BY ?pl                
                    """.replace("xxx", self.instance_uri)
                r = sparql_query(q)
                return JSONResponse([
                    {"uri": x["c"]["value"], "prefLabel": x["pl"]["value"]}
                    for x in r[1]
                ])
            elif self.profile == "skos":
                q = """
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>                    
                    CONSTRUCT {
                        <xxx> 
                            a skos:Collection ;
                            skos:prefLabel ?prefLabel ;
                            skos:definition ?description ;
                            skos:member ?c .
                        ?c skos:prefLabel ?c_pl .
                    }
                    WHERE {
                        <xxx> 
                            a skos:Collection ;
                            skos:prefLabel ?prefLabel ;
                            <http://purl.org/dc/terms/description> ?description ;
                            skos:member ?c .
                        ?c skos:prefLabel ?c_pl .
                    }
                    ORDER BY ?prefLabel
                    """.replace("xxx", self.instance_uri)
                r = sparql_construct(q, self.mediatype)
                if r[0]:
                    return Response(r[1], headers={"Content-Type": self.mediatype})
                else:
                    return PlainTextResponse(
                        "There was an error obtaining the Collections RDF from the Triplestore",
                        status_code=500
                    )
            elif self.profile == "vocpub":
                q = """
                    PREFIX dcterms: <http://purl.org/dc/terms/>
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    CONSTRUCT {
                        <xxx>
                            a skos:Collection ;
                            skos:prefLabel ?prefLabel ;
                            skos:definition ?description ;
                            dcterms:creator ?creator ;
                            dcterms:publisher ?publisher ;   
                            dcterms:provenance "Made by NERC and maintained within the NERC Vocabulary Server" ;                            
                            skos:member ?c .
                            
                        ?c skos:prefLabel ?c_pl .
                    }
                    WHERE {
                        <xxx>
                            a skos:Collection ;
                            skos:prefLabel ?prefLabel ;
                            dcterms:description ?description ;
                            dcterms:creator ?creator ;
                            dcterms:publisher ?publisher ;   
                            skos:member ?c .
  
                        ?c skos:prefLabel ?c_pl .
                    }
                    """.replace("xxx", self.instance_uri)

                r = sparql_construct(q, self.mediatype)
                if r[0]:
                    return Response(r[1], headers={"Content-Type": self.mediatype})
                else:
                    return PlainTextResponse(
                        "There was an error obtaining the Collections RDF from the Triplestore",
                        status_code=500
                    )

            alt = super().render()
            if alt is not None:
                return alt

    return CollectionRenderer().render()


@api.get("/scheme/{scheme_id}")
@api.get("/scheme/{scheme_id}/")
def scheme_no_current(request: Request, scheme_id):
    return RedirectResponse(url=f"/scheme/{scheme_id}/current/")


@api.get("/scheme/{scheme_id}/current/")
@api.get("/scheme/{scheme_id}/current/{acc_dep}")
@api.get("/scheme/{scheme_id}/current/{acc_dep}/")
def scheme(
        request: Request,
        scheme_id,
        acc_dep: Literal["accepted", "deprecated", None] = None
):
    class SchemeRenderer(Renderer):
        def __init__(self):
            self.instance_uri = f"http://vocab.nerc.ac.uk/scheme/{scheme_id}/current/"

            super().__init__(
                request,
                self.instance_uri,
                {
                    "nvs": nvs,
                    "skos": skos,
                    "vocpub": vocpub,
                    "dd": dd
                },
                "nvs",
            )

        def _get_scheme(self):
            for scheme in cache_return(collections_or_conceptschemes="conceptschemes"):
                if scheme["id"]["value"] == scheme_id:
                    return scheme

        def _get_concept_hierarchy(self):
            def make_hierarchical_dicts(data):
                children_parents = []
                labels = {}

                for d in data:
                    child = d["c"]["value"]
                    parent = d["broader"]["value"] if d.get("broader") is not None else None
                    children_parents.append((child, parent))
                    labels[child] = d["pl"]["value"].replace("<", "&lt;")

                children_parents.sort(key=lambda x: x[0])
                has_parent = set()
                all_items = {}
                for child, parent in children_parents:
                    if parent not in all_items:
                        all_items[parent] = {}
                    if child not in all_items:
                        all_items[child] = {}
                    all_items[parent][child] = all_items[child]
                    has_parent.add(child)

                hierarchy = {}
                for key, value in all_items.items():
                    if key not in has_parent:
                        hierarchy[key] = value
                return hierarchy, labels

            def make_nested_ul(hierarchy, labels):
                html = ""
                for k, v in hierarchy.items():
                    if v:
                        html += f'<li><span class="caret"><a href="{k.replace("http://vocab.nerc.ac.uk", "")}">{labels[k]}</a></span>' if k is not None else "None"
                        html += '<ul class="nested">'
                        html += make_nested_ul(v, labels)
                        html += "</ul>"
                    else:
                        html += f'<li><a href="{k.replace("http://vocab.nerc.ac.uk", "")}">{labels[k]}</a>' if k is not None else "None"
                    html += "</li>"
                return html

            q = """
                PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                SELECT DISTINCT ?c ?pl ?broader
                WHERE {
                  { 
                    ?c skos:inScheme <xxx>  .
                  }
                  UNION
                  { ?c skos:topConceptOf <xxx>  . }
                  UNION
                  { <xxx>  skos:hasTopConcept ?c . }
                
                  ?c skos:prefLabel ?pl .
                  BIND (STRAFTER(STR(?c), ".uk") AS ?systemUri)
                  
                  acc_dep
                  OPTIONAL { 
                    ?c skos:broader ?broader .
                    { ?broader skos:inScheme <xxx>  . }
                    UNION
                    { ?broader skos:topConceptOf <xxx>  . }
                    UNION
                    { <xxx>  skos:hasTopConcept ?broader . }
                  }
                  FILTER(lang(?pl) = "en" || lang(?pl) = "")                                    
                }
                ORDER BY ?pl
                """.replace("xxx", self.instance_uri).replace("acc_dep", acc_dep_map.get(acc_dep))
            try:
                r = sparql_query(q)

                if not r[0]:
                    return None
                else:
                    hier = make_hierarchical_dicts(r[1])
                    hier[1][None] = None
                    return "<ul class=\"concept-hierarchy\">" + make_nested_ul(hier[0], hier[1])[23:-5]
            except RecursionError as e:
                logging.warning("Encountered a recursion limit error for {}".format(self.vocab_uri))
                # make a flat list of concepts
                q = """
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    SELECT DISTINCT ?c ?pl
                    WHERE {{
                        ?c skos:inScheme <{vocab_uri}> .              
                        ?c skos:prefLabel ?pl .
                        FILTER(lang(?pl) = "{language}" || lang(?pl) = "") 
                    }}
                    ORDER BY ?pl
                    """.format(vocab_uri=self.instance_uri, language=self.language)

                concepts = [
                    (concept["systemUri"]["value"], concept["pl"]["value"])
                    for concept in sparql_query(q)
                ]

                concepts_html = "<br />".join(["<a href=\"{}\">{}</a>".format(c[0], c[1]) for c in concepts])
                return """<p><strong><em>This concept hierarchy cannot be displayed</em></strong><p>
                            <p>The flat list of all this Scheme's Concepts is:</p>
                            <p>{}</p>
                        """.format(concepts_html)

        def render(self):
            if self.profile == "nvs":
                if self.mediatype == "text/html":
                    scheme = self._get_scheme()
                    scheme["concept_hierarchy"] = self._get_concept_hierarchy()

                    if not scheme["concept_hierarchy"]:
                        return templates.TemplateResponse(
                            "error.html",
                            {
                                "request": request,
                                "title": "DB Error",
                                "status": "500",
                                "message": "There was an error with accessing the Triplestore",
                            }
                        )

                    return templates.TemplateResponse(
                        "scheme.html",
                        {
                            "request": request,
                            "uri": self.instance_uri,
                            "scheme": scheme,
                            "profile_token": "nvs",
                        }
                    )
                elif self.mediatype in RDF_MEDIATYPES:
                    q = """
                        PREFIX dc: <http://purl.org/dc/terms/>
                        PREFIX dce: <http://purl.org/dc/elements/1.1/>
                        PREFIX grg: <http://www.isotc211.org/schemas/grg/>
                        PREFIX owl: <http://www.w3.org/2002/07/owl#>
                        PREFIX pav: <http://purl.org/pav/>
                        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                        PREFIX void: <http://rdfs.org/ns/void#>

                        CONSTRUCT {
                          <xxx> ?p ?o .                           
                          <xxx> skos:member ?m .                        
                          ?m ?p2 ?o2 .              
                        }
                        WHERE {
                          {
                            <xxx> ?p ?o .                          
                            MINUS { <xxx> skos:member ?o . }
                          }

                          {
                            <xxx> skos:member ?m .
                            ?m a skos:Concept .

                            ?m ?p2 ?o2 .

                            FILTER ( ?p2 != skos:broaderTransitive )
                            FILTER ( ?p2 != skos:narrowerTransitive )
                          }
                        }
                        """.replace("xxx", self.instance_uri)
                    r = sparql_construct(q, self.mediatype)
                    if r[0]:
                        return Response(r[1], headers={"Content-Type": self.mediatype})
                    else:
                        return PlainTextResponse(
                            "There was an error obtaining the Collections RDF from the Triplestore",
                            status_code=500
                        )
            elif self.profile == "dd":
                q = """
                    PREFIX dcterms: <http://purl.org/dc/terms/>
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    SELECT DISTINCT ?c ?pl ?b
                    WHERE {
                        ?c skos:inScheme <xxx> ;
                           skos:prefLabel ?pl .

                        OPTIONAL {
                            ?b skos:inScheme <xxx> .
                            ?c skos:broader ?b .
                        }
                        
                        FILTER(lang(?pl) = "en" || lang(?pl) = "")
                    }
                    ORDER BY ?pl                
                    """.replace("xxx", self.instance_uri)
                r = sparql_query(q)
                return JSONResponse([
                    {"uri": x["c"]["value"], "prefLabel": x["pl"]["value"], "broader": x["b"]["value"]}
                    if x.get("b") is not None
                    else {"uri": x["c"]["value"], "prefLabel": x["pl"]["value"]}
                    for x in r[1]
                ])
            elif self.profile == "skos":
                q = """
                    PREFIX dcterms: <http://purl.org/dc/terms/>
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    CONSTRUCT {
                        <xxx>
                          a skos:ConceptScheme ;
                          skos:prefLabel ?pl ;
                          skos:defintion ?def ;  
                          skos:hasTopConcept ?tc ;
                        .
                        ?c a skos:Concept ;
                           skos:prefLabel ?c_pl ;
                           skos:defintion ?c_def ; 
                           skos:broader ?broader ;
                           skos:inScheme <xxx> ;
                        .
                        
                        ?tc skos:topConceptOf <xxx> .  
                        ?broader skos:narrower ?c .                        
                    }
                    WHERE {
                        <xxx>
                          skos:prefLabel ?pl ;
                          dcterms:description ?def ;  
                          skos:hasTopConcept ?tc ;
                        .
                    
                        { ?c skos:inScheme <xxx> }
                        UNION
                        { ?c skos:topConceptOf <xxx> }
                        UNION
                        { <xxx>  skos:hasTopConcept ?c }
                    
                        ?c 
                            skos:prefLabel ?c_pl ;
                            skos:definition ?c_def ;
                        .
                    
                        BIND (STRAFTER(STR(?c), ".uk") AS ?systemUri)
                        
                        OPTIONAL { 
                            ?c skos:broader ?broader .
                            { ?broader skos:inScheme <xxx>  . }
                            UNION
                            { ?broader skos:topConceptOf <xxx>  . }
                            UNION
                            { <xxx>  skos:hasTopConcept ?broader . }
                        }
                        FILTER(lang(?pl) = "en" || lang(?pl) = "")
                        FILTER(lang(?def) = "en" || lang(?def) = "")
                        FILTER(lang(?c_pl) = "en" || lang(?c_pl) = "")
                        FILTER(lang(?c_def) = "en" || lang(?c_def) = "")
                    }
                    ORDER BY ?pl
                    """.replace("xxx", self.instance_uri)
                r = sparql_construct(q, self.mediatype)
                if r[0]:
                    return Response(r[1], headers={"Content-Type": self.mediatype})
                else:
                    return PlainTextResponse(
                        "There was an error obtaining the Collections RDF from the Triplestore",
                        status_code=500
                    )
            elif self.profile == "vocpub":
                q = """
                    PREFIX dcterms: <http://purl.org/dc/terms/>
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
                    CONSTRUCT {
                        <xxx>
                          a skos:ConceptScheme ;
                          skos:prefLabel ?pl ;
                          skos:defintion ?def ;  
                          skos:hasTopConcept ?tc ;
                          dcterms:creator ?creator ;
                          dcterms:publisher ?publisher ;
                          dcterms:modified ?modified ;
                          dcterms:provenance "Made by NERC and maintained within the NERC Vocabulary Server" ; 
                        .                        
                        
                        ?c a skos:Concept ;
                           skos:prefLabel ?c_pl ;
                           skos:defintion ?c_def ; 
                           skos:broader ?broader ;
                           skos:inScheme <xxx> ;
                        .

                        ?tc skos:topConceptOf <xxx> .  
                        ?broader skos:narrower ?c .                        
                    }
                    WHERE {
                        <xxx>
                          skos:prefLabel ?pl ;
                          dcterms:description ?def ;  
                          skos:hasTopConcept ?tc ;
                          dcterms:publisher ?publisher ;
                          dcterms:date ?m ;                                                    
                        .
                        BIND (STRDT(REPLACE(STRBEFORE(?m, "."), " ", "T"), xsd:dateTime) AS ?modified)
                        
                        { ?c skos:inScheme <xxx> }
                        UNION
                        { ?c skos:topConceptOf <xxx> }
                        UNION
                        { <xxx>  skos:hasTopConcept ?c }

                        ?c 
                            skos:prefLabel ?c_pl ;
                            skos:definition ?c_def ;
                        .

                        BIND (STRAFTER(STR(?c), ".uk") AS ?systemUri)

                        OPTIONAL { 
                            ?c skos:broader ?broader .
                            { ?broader skos:inScheme <xxx>  . }
                            UNION
                            { ?broader skos:topConceptOf <xxx>  . }
                            UNION
                            { <xxx>  skos:hasTopConcept ?broader . }
                        }
                        FILTER(lang(?pl) = "en" || lang(?pl) = "")
                        FILTER(lang(?def) = "en" || lang(?def) = "")
                        FILTER(lang(?c_pl) = "en" || lang(?c_pl) = "")
                        FILTER(lang(?c_def) = "en" || lang(?c_def) = "")
                    }
                    ORDER BY ?pl
                    """.replace("xxx", self.instance_uri)

                r = sparql_construct(q, self.mediatype)
                if r[0]:
                    return Response(r[1], headers={"Content-Type": self.mediatype})
                else:
                    return PlainTextResponse(
                        "There was an error obtaining the Collections RDF from the Triplestore",
                        status_code=500
                    )

            alt = super().render()
            if alt is not None:
                return alt

    return SchemeRenderer().render()


@api.get("/standard_name/")
@api.get("/standard_name/{acc_dep_or_concept}")
@api.get("/standard_name/{acc_dep_or_concept}/")
def standard_name(request: Request, acc_dep_or_concept: str = None):
    if acc_dep_or_concept not in ["accepted", "deprecated", None]:
        # this is a call for a Standard Name Concept
        return standard_name_concept(request, acc_dep_or_concept)

    class CollectionRenderer(Renderer):
        def __init__(self):
            self.instance_uri = f"http://vocab.nerc.ac.uk/collection/P07/current/"

            super().__init__(
                request,
                self.instance_uri,
                {
                    "nvs": nvs,
                    "skos": skos,
                    "vocpub": vocpub,
                    "dd": dd
                },
                "nvs",
            )

        def _get_collection(self):
            for collection in cache_return(collections_or_conceptschemes="collections"):
                if collection["id"]["value"] == "P07":
                    return collection

        def _get_concepts(self):
            q = """
                PREFIX dcterms: <http://purl.org/dc/terms/>
                PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                SELECT DISTINCT ?c ?id ?pl ?def ?date ?dep
                WHERE {
                        <xxx> skos:member ?x .
                        ?x    						
                            skos:prefLabel ?pl ;
                            skos:definition ?def ;
                            dcterms:date ?date ;
                        .
                        BIND (?pl AS ?id)
                        BIND (CONCAT("/standard_name/", ?pl, "/") AS ?c)

                        acc_dep
                        OPTIONAL {
                            ?x <http://www.w3.org/2002/07/owl#deprecated> ?dep .
                        }

                        FILTER(lang(?pl) = "en" || lang(?pl) = "") 
                        FILTER(lang(?def) = "en" || lang(?def) = "")
                }
                ORDER BY ?pl
                """.replace("xxx", self.instance_uri)\
                .replace("acc_dep", acc_dep_map.get(acc_dep_or_concept).replace("?c", "?x"))

            sparql_result = sparql_query(q)
            if sparql_result[0]:
                return [
                    {
                        "systemUri": concept["c"]["value"],
                        "id": concept["id"]["value"],
                        "prefLabel": concept["pl"]["value"].replace("_", " "),
                        "definition": concept["def"]["value"].replace("_", "_ "),
                        "date": concept["date"]["value"][0:10],
                        "deprecated": True if concept.get("dep") and concept["dep"]["value"] == "true" else False
                    }
                    for concept in sparql_result[1]
                ]
            else:
                return False

        def render(self):
            if self.profile == "nvs":
                if self.mediatype == "text/html":
                    collection = self._get_collection()
                    collection["concepts"] = self._get_concepts()

                    if not collection["concepts"]:
                        return templates.TemplateResponse(
                            "error.html",
                            {
                                "request": request,
                                "title": "DB Error",
                                "status": "500",
                                "message": "There was an error with accessing the Triplestore",
                            }
                        )

                    self.instance_uri = "http://vocab.nerc.ac.uk/standard_name/"

                    return templates.TemplateResponse(
                        "collection.html",
                        {
                            "request": request,
                            "uri": self.instance_uri,
                            "collection": collection,
                            "profile_token": "nvs",
                        }
                    )
                elif self.mediatype in RDF_MEDIATYPES:
                    q = """
                        PREFIX dc: <http://purl.org/dc/terms/>
                        PREFIX dce: <http://purl.org/dc/elements/1.1/>
                        PREFIX grg: <http://www.isotc211.org/schemas/grg/>
                        PREFIX owl: <http://www.w3.org/2002/07/owl#>
                        PREFIX pav: <http://purl.org/pav/>
                        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                        PREFIX void: <http://rdfs.org/ns/void#>

                        CONSTRUCT {
                          <http://vocab.nerc.ac.uk/standard_name/> ?p ?o .                           
                          <http://vocab.nerc.ac.uk/standard_name/> skos:member ?m .                        
                          ?m ?p2 ?o2 .              
                        }
                        WHERE {
                          {
                            <xxx> ?p ?o .                          
                            MINUS { <xxx> skos:member ?o . }
                          }

                          {
                            <xxx> skos:member ?mx .
                            ?mx a skos:Concept ;
                                skos:prefLabel ?pl ;
                            .

                            ?mx ?p2 ?o2 .

                            FILTER ( ?p2 != skos:broaderTransitive )
                            FILTER ( ?p2 != skos:narrowerTransitive )
                          }
                          
                          BIND (CONCAT("http://vocab.nerc.ac.uk/standard_name/", ?pl, "/") AS ?m)
                        }
                        """.replace("xxx", self.instance_uri)
                    r = sparql_construct(q, self.mediatype)
                    if r[0]:
                        return Response(r[1], headers={"Content-Type": self.mediatype})
                    else:
                        return PlainTextResponse(
                            "There was an error obtaining the Collections RDF from the Triplestore",
                            status_code=500
                        )
            elif self.profile == "dd":
                q = """
                    PREFIX dcterms: <http://purl.org/dc/terms/>
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    SELECT DISTINCT ?c ?pl ?b
                    WHERE {
                        <xxx> skos:member ?xc .
                        ?xc skos:prefLabel ?xpl .
                        
                        BIND (CONCAT("http://vocab.nerc.ac.uk/standard_name/", ?xpl, "/") AS ?c)
                        BIND (REPLACE(?xpl, "_", " ") AS ?pl)
                    }
                    ORDER BY ?pl                
                    """.replace("xxx", self.instance_uri)
                r = sparql_query(q)
                return JSONResponse([
                    {"uri": x["c"]["value"], "prefLabel": x["pl"]["value"]}
                    for x in r[1]
                ])
            elif self.profile == "skos":
                q = """
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>                    
                    CONSTRUCT {
                        <http://vocab.nerc.ac.uk/standard_name/> 
                            a skos:Collection ;
                            skos:prefLabel ?prefLabel ;
                            skos:definition ?description ;
                            skos:member ?c .
                        ?c skos:prefLabel ?c_pl .
                    }
                    WHERE {
                        <xxx> 
                            a skos:Collection ;
                            skos:prefLabel ?prefLabel ;
                            <http://purl.org/dc/terms/description> ?description ;
                            skos:member ?xc .
                        ?xc skos:prefLabel ?xc_pl .
                        
                        BIND (CONCAT("http://vocab.nerc.ac.uk/standard_name/", ?xc_pl, "/") AS ?c)
                        BIND (REPLACE(?xc_pl, "_", " ") AS ?c_pl)                        
                    }
                    ORDER BY ?prefLabel
                    """.replace("xxx", self.instance_uri)
                r = sparql_construct(q, self.mediatype)
                if r[0]:
                    return Response(r[1], headers={"Content-Type": self.mediatype})
                else:
                    return PlainTextResponse(
                        "There was an error obtaining the Collections RDF from the Triplestore",
                        status_code=500
                    )
            elif self.profile == "vocpub":
                q = """
                    PREFIX dcterms: <http://purl.org/dc/terms/>
                    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                    PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
                    CONSTRUCT {
                        <http://vocab.nerc.ac.uk/standard_name/> 
                            a skos:Collection ;
                            skos:prefLabel ?prefLabel ;
                            skos:definition ?description ;
                            dcterms:modified ?modified ;
                            dcterms:creator ?creator ;
                            dcterms:publisher ?publisher ;   
                            dcterms:provenance "Made by NERC and maintained within the NERC Vocabulary Server" ;                            
                            skos:member ?c .
                        ?c skos:prefLabel ?c_pl .
                    }
                    WHERE {
                        <xxx> 
                            a skos:Collection ;
                            skos:prefLabel ?prefLabel ;                            
                            dcterms:description ?description ;
                            dcterms:date ?date ;
                            dcterms:creator ?creator ;
                            dcterms:publisher ?publisher ;                             
                            skos:member ?xc .
                        ?xc skos:prefLabel ?xc_pl .
                        
                        BIND (CONCAT("http://vocab.nerc.ac.uk/standard_name/", ?xc_pl, "/") AS ?c)
                        BIND (REPLACE(?xc_pl, "_", " ") AS ?c_pl)
                        BIND (STRDT(REPLACE(STRBEFORE(?date, "."), " ", "T"), xsd:dateTime) AS ?modified)
                    }
                    ORDER BY ?xc                    
                    """.replace("xxx", self.instance_uri)

                r = sparql_construct(q, self.mediatype)
                if r[0]:
                    return Response(r[1], headers={"Content-Type": self.mediatype})
                else:
                    return PlainTextResponse(
                        "There was an error obtaining the Collections RDF from the Triplestore",
                        status_code=500
                    )

            self.instance_uri = "http://vocab.nerc.ac.uk/standard_name/"
            alt = super().render()
            if alt is not None:
                return alt

    return CollectionRenderer().render()


def standard_name_concept(request: Request, standard_name_concept_id: str):
    c = ConceptRenderer(request)
    return c.render()


class ConceptRenderer(Renderer):
    def __init__(self, request):
        self.request = request
        if "collection" in str(request.url):
            self.instance_uri = "http://vocab.nerc.ac.uk/collection/" + \
                                str(request.url).split("/collection/")[1].split("?")[0]
        elif "standard_name" in str(request.url):
            self.instance_uri = "http://vocab.nerc.ac.uk/standard_name/" + \
                                str(request.url).split("/standard_name/")[1].split("?")[0]

        concept_profiles = {
            "nvs": nvs,
            "skos": skos,
            "vocpub": vocpub,
            "sdo": sdo,
        }

        def _is_collection_puv():
            collection_uri = self.instance_uri.split("/current/")[0] + "/current/"
            for collection in cache_return(collections_or_conceptschemes="collections"):
                if collection["uri"]["value"] == collection_uri:
                    if collection.get("conforms_to") and collection["conforms_to"][
                        "value"] == "https://w3id.org/env/puv":
                        return True
            return False

        if _is_collection_puv():
            concept_profiles["puv"] = puv

        super().__init__(
            request,
            self.instance_uri,
            concept_profiles,
            "nvs"
        )

    def _render_nvs_or_puv_html(self):
        q = """
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT DISTINCT ?p ?o ?o_label ?o_notation ?collection_uri ?collection_systemUri ?collection_label
            WHERE {
              BIND (<xxx> AS ?concept)
              ?concept ?p ?o .
            
              FILTER(!isLiteral(?o) || lang(?o) = "en" || lang(?o) = "")
            
              OPTIONAL {
                ?o skos:prefLabel ?o_label ;
                   skos:notation ?o_notation .
                FILTER(!isLiteral(?o_label) || lang(?o_label) = "en" || lang(?o_label) = "")
              }
            
              BIND(
                IF(
                  CONTAINS(STR(?concept), "standard_name"), 
                    <http://vocab.nerc.ac.uk/standard_name/>,
                    IRI(CONCAT(STRBEFORE(STR(?concept), "/current/"), "/current/"))
                )
                AS ?collection_uri
              )
              BIND (REPLACE(STR(?collection_uri), "http://vocab.nerc.ac.uk", "") AS ?collection_systemUri)
              OPTIONAL {?collection_uri skos:prefLabel ?x }
              BIND (COALESCE(?x, "Climate and Forecast Standard Names") AS ?collection_label)
            }         
            """.replace("xxx", self.instance_uri)
        r = sparql_query(q)
        if not r[0]:
            return PlainTextResponse(
                "There was an error obtaining the Concept RDF from the Triplestore",
                status_code=500
            )

        PAV = Namespace("http://purl.org/pav/")
        PUV = Namespace("https://w3id.org/env/puv#")
        STATUS = Namespace("http://www.opengis.net/def/metamodel/ogc-na/")

        props = {
            str(PUV.analyticalMethod): {"label": "analytical method", "group": "puv"},
            str(PUV.biologicalObject): {"label": "biological object of interest", "group": "puv"},
            str(PUV.chemicalObject): {"label": "chemical object of interest", "group": "puv"},
            str(PUV.dataProcessing): {"label": "data processing method", "group": "puv"},
            str(PUV.isComposedOf): {"label": "is composed of", "group": "puv"},
            str(PUV.matrix): {"label": "matrix", "group": "puv"},
            str(PUV.matrixRelationship): {"label": "measurement-matrix relationship", "group": "puv"},
            str(PUV.method): {"label": "method", "group": "puv"},
            str(PUV.objectOfInterest): {"label": "object of interest", "group": "puv"},
            str(PUV.physicalObject): {"label": "physical object of interest", "group": "puv"},
            str(PUV.property): {"label": "property", "group": "puv"},
            str(PUV.samplePreparation): {"label": "sample-preparation method", "group": "puv"},
            str(PUV.statistic): {"label": "statistic", "group": "puv"},
            str(PUV.uom): {"label": "unit-of-measurement", "group": "puv"},

            str(DCTERMS.contributor): {"label": "Contributor", "group": "agent"},
            str(DCTERMS.creator): {"label": "Creator", "group": "agent"},
            str(DCTERMS.publisher): {"label": "Publisher", "group": "agent"},

            str(SKOS.notation): {"label": "Identifier", "group": "annotation"},
            # str(DCTERMS.identifier): {"label": "Identifier", "group": "annotation"},
            str(STATUS.status): {"label": "Status", "group": "annotation"},
            str(SKOS.altLabel): {"label": "Alternative Label", "group": "annotation"},
            str(SKOS.note): {"label": "Note", "group": "annotation"},
            str(SKOS.scopeNote): {"label": "Scope Note", "group": "annotation"},
            str(SKOS.historyNote): {"label": "History Note", "group": "annotation"},
            str(SKOS.notation): {"label": "Identifier", "group": "annotation"},

            str(OWL.sameAs): {"label": "Same As", "group": "related"},
            str(SKOS.broader): {"label": "Broader", "group": "related"},
            str(SKOS.related): {"label": "Related", "group": "related"},
            str(SKOS.narrower): {"label": "Narrower", "group": "related"},
            str(SKOS.exactMatch): {"label": "Exact Match", "group": "related"},
            str(SKOS.broadMatch): {"label": "Broad Match", "group": "related"},
            str(SKOS.closeMatch): {"label": "Close Match", "group": "related"},
            str(SKOS.narrowMatch): {"label": "Narrow Match", "group": "related"},

            str(PAV.hasCurrentVersion): {"label": "Has Current Version", "group": "provenance"},
            str(PAV.version): {"label": "Version", "group": "provenance"},
            str(OWL.deprecated): {"label": "Deprecated", "group": "provenance"},
            str(PAV.previousVersion): {"label": "Previous Version", "group": "provenance"},
            str(DCTERMS.isVersionOf): {"label": "Is Version Of", "group": "provenance"},
            str(PAV.authoredOn): {"label": "Authored On", "group": "provenance"},

            str(DC.identifier): {"group": "ignore"},
            str(DCTERMS.identifier): {"group": "ignore"},
            str(VOID.inDataset): {"group": "ignore"},
            str(RDF.type): {"group": "ignore"},
            str(OWL.versionInfo): {"group": "ignore"},
            str(PAV.authoredOn): {"group": "ignore"},
        }

        context = {
            "request": self.request,
            "deprecated": False,
            "prefLabel": None,
            "uri": self.instance_uri,
            "collection_systemUri": None,
            "collection_label": None,
            "definition": None,
            "date": None,
            "altLabels": [],
            "puv": [],
            "annotation": [],
            "agent": [],
            "related": [],
            "provenance": [],
            "other": [],
            "profile_token": self.profile,
        }

        static_puv_params = [
            {
                'p': {
                    'type': 'uri',
                    'value': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
                },
                'o': {
                    'type': 'uri',
                    'value': 'https://w3id.org/env/puv#Parameter'
                },
                'o_label': {
                    'type': 'literal',
                    'value': 'Parameter',
                    'xml:lang': 'en'
                },
                "collection_uri": {"type": "uri", "value": "http://vocab.nerc.ac.uk/collection/P01/current/"},
                "collection_systemUri": {"type": "literal", "value": "/collection/P01/current/SAGEMSFM/"},
                "collection_label": {"type": "literal", "value": "BODC Parameter Usage Vocabulary"},
            },
            {
                'p': {
                    'type': 'uri',
                    'value': 'https://w3id.org/env/puv#biologicalObject'
                },
                'o': {
                    'type': 'uri',
                    'value': 'http://vocab.nerc.ac.uk/collection/S25/current/BE006569/'
                },
                'o_label': {
                    'type': 'literal',
                    'value': 'Mytilus galloprovincialis (ITIS: 79456: WoRMS 140481) [Subcomponent: flesh]',
                    'xml:lang': 'en'
                },
                'o_notation': {
                    'type': 'literal',
                    'value': 'SDN:S25:BE006569'
                },
                "collection_uri": {"type": "uri", "value": "http://vocab.nerc.ac.uk/collection/P01/current/"},
                "collection_systemUri": {"type": "literal", "value": "/collection/P01/current/SAGEMSFM/"},
                "collection_label": {"type": "literal", "value": "BODC Parameter Usage Vocabulary"},
            },
            {
                'p': {
                    'type': 'uri',
                    'value': 'https://w3id.org/env/puv#chemicalObject'
                },
                'o': {
                    'type': 'uri',
                    'value': 'http://vocab.nerc.ac.uk/collection/S27/current/CS003687/'
                },
                'o_label': {
                    'type': 'literal',
                    'value': '1,2,3,7,8-pentachlorodibenzofuran',
                    'xml:lang': 'en'
                },
                'o_notation': {
                    'type': 'literal',
                    'value': 'SDN:S27:CS003687'
                },
                "collection_uri": {"type": "uri", "value": "http://vocab.nerc.ac.uk/collection/P01/current/"},
                "collection_systemUri": {"type": "literal", "value": "/collection/P01/current/SAGEMSFM/"},
                "collection_label": {"type": "literal", "value": "BODC Parameter Usage Vocabulary"},
            },
            {
                'p': {
                    'type': 'uri',
                    'value': 'https://w3id.org/env/puv#matrix'
                },
                'o': {
                    'type': 'uri',
                    'value': 'http://vocab.nerc.ac.uk/collection/S26/current/MAT01963/'
                },
                'o_label': {
                    'type': 'literal',
                    'value': 'biota',
                    'xml:lang': 'en'
                },
                'o_notation': {
                    'type': 'literal',
                    'value': 'SDN:S26:MAT01963'
                },
                "collection_uri": {"type": "uri", "value": "http://vocab.nerc.ac.uk/collection/P01/current/"},
                "collection_systemUri": {"type": "literal", "value": "/collection/P01/current/SAGEMSFM/"},
                "collection_label": {"type": "literal", "value": "BODC Parameter Usage Vocabulary"},
            },
            {
                'p': {
                    'type': 'uri',
                    'value': 'https://w3id.org/env/puv#matrixRelationship'
                },
                'o': {
                    'type': 'uri',
                    'value': 'http://vocab.nerc.ac.uk/collection/S02/current/S041/'
                },
                'o_label': {
                    'type': 'literal',
                    'value': 'per unit dry weight of',
                    'xml:lang': 'en'
                },
                'o_notation': {
                    'type': 'literal',
                    'value': 'SDN:S02:S041'
                },
                "collection_uri": {"type": "uri", "value": "http://vocab.nerc.ac.uk/collection/P01/current/"},
                "collection_systemUri": {"type": "literal", "value": "/collection/P01/current/SAGEMSFM/"},
                "collection_label": {"type": "literal", "value": "BODC Parameter Usage Vocabulary"},
            },
            {
                'p': {
                    'type': 'uri',
                    'value': 'https://w3id.org/env/puv#property'
                },
                'o': {
                    'type': 'uri',
                    'value': 'http://vocab.nerc.ac.uk/collection/S06/current/S0600045/'
                },
                'o_label': {
                    'type': 'literal',
                    'value': 'Concentration',
                    'xml:lang': 'en'
                },
                'o_notation': {
                    'type': 'literal',
                    'value': 'SDN:S06:S0600045'
                },
                "collection_uri": {"type": "uri", "value": "http://vocab.nerc.ac.uk/collection/P01/current/"},
                "collection_systemUri": {"type": "literal", "value": "/collection/P01/current/SAGEMSFM/"},
                "collection_label": {"type": "literal", "value": "BODC Parameter Usage Vocabulary"},
            },
            {
                'p': {
                    'type': 'uri',
                    'value': 'https://w3id.org/env/puv#property'
                },
                'o': {
                    'type': 'uri',
                    'value': 'http://vocab.nerc.ac.uk/collection/S06/current/S0600082/'
                },
                'o_label': {
                    'type': 'literal',
                    'value': 'Temperature',
                    'xml:lang': 'en'
                },
                'o_notation': {
                    'type': 'literal',
                    'value': 'SDN:S06:S0600082'
                },
                "collection_uri": {"type": "uri", "value": "http://vocab.nerc.ac.uk/collection/P01/current/"},
                "collection_systemUri": {"type": "literal", "value": "/collection/P01/current/SAGEMSFM/"},
                "collection_label": {"type": "literal", "value": "BODC Parameter Usage Vocabulary"},
            },
            {
                'p': {
                    'type': 'uri',
                    'value': 'https://w3id.org/env/puv#property'
                },
                'o': {
                    'type': 'uri',
                    'value': 'http://vocab.nerc.ac.uk/collection/S06/current/S06000160/'
                },
                'o_label': {
                    'type': 'literal',
                    'value': 'Temperature (IPTS-68)',
                    'xml:lang': 'en'
                },
                'o_notation': {
                    'type': 'literal',
                    'value': 'SDN:S06:S06000160'
                },
                "collection_uri": {"type": "uri", "value": "http://vocab.nerc.ac.uk/collection/P01/current/"},
                "collection_systemUri": {"type": "literal", "value": "/collection/P01/current/SAGEMSFM/"},
                "collection_label": {"type": "literal", "value": "BODC Parameter Usage Vocabulary"},
            },
            {
                'p': {
                    'type': 'uri',
                    'value': 'https://w3id.org/env/puv#uom'
                },
                'o': {
                    'type': 'uri',
                    'value': 'http://vocab.nerc.ac.uk/collection/P06/current/UUKG/'
                },
                'o_label': {
                    'type': 'literal',
                    'value': 'Micrograms per kilogram',
                    'xml:lang': 'en'
                },
                'o_notation': {
                    'type': 'literal',
                    'value': 'SDN:P06:UUKG'
                },
                "collection_uri": {"type": "uri", "value": "http://vocab.nerc.ac.uk/collection/P01/current/"},
                "collection_systemUri": {"type": "literal", "value": "/collection/P01/current/SAGEMSFM/"},
                "collection_label": {"type": "literal", "value": "BODC Parameter Usage Vocabulary"},
            }
        ]
        r[1].extend(static_puv_params)

        def make_predicate_label_from_uri(uri):
            return uri.split("#")[-1].split("/")[-1]

        for x in r[1]:
            p = x["p"]["value"]
            o = x["o"]["value"]
            o_label = x["o_label"]["value"] if x.get("o_label") is not None else None
            o_notation = x["o_notation"]["value"] if x.get("o_notation") is not None else None
            context["collection_systemUri"] = x["collection_systemUri"]["value"]
            context["collection_label"] = x["collection_label"]["value"]
            if p == str(OWL.deprecated):
                if o == "true":
                    context["deprecated"] = True
            elif p == str(SKOS.prefLabel):
                context["prefLabel"] = o
            elif p == str(SKOS.altLabel):
                context["altLabels"].append(o)
            elif p == str(SKOS.definition):
                context["definition"] = o
            elif p == str(DCTERMS.date):
                context["date"] = o.replace(" ", "T").rstrip(".0")
            elif p in props.keys():
                if props[p]["group"] != "ignore":
                    context[props[p]["group"]].append(DisplayProperty(p, props[p]["label"], o, o_label, o_notation))
            else:
                context["other"].append(DisplayProperty(p, make_predicate_label_from_uri(p), o, o_label))

        def clean_prop_list_labels(prop_list):
            last_pred_html = None
            for x in prop_list:
                this_predicate_html = x.predicate_html
                if this_predicate_html == last_pred_html:
                    x.predicate_html = ""
                last_pred_html = this_predicate_html

        context["altLabels"].sort()
        context["puv"].sort(key=lambda x: x.predicate_html)
        clean_prop_list_labels(context["puv"])
        context["agent"].sort(key=lambda x: x.predicate_html)
        clean_prop_list_labels(context["agent"])
        context["annotation"].sort(key=lambda x: x.predicate_html)
        clean_prop_list_labels(context["annotation"])
        context["related"].sort(key=lambda x: x.predicate_html)
        clean_prop_list_labels(context["related"])
        context["provenance"].sort(key=lambda x: x.predicate_html)
        clean_prop_list_labels(context["provenance"])
        context["other"].sort(key=lambda x: x.predicate_html)
        clean_prop_list_labels(context["other"])
        return templates.TemplateResponse("concept.html", context=context)

    def _render_nvs_rdf(self):
        q = """
            PREFIX dc: <http://purl.org/dc/terms/>
            PREFIX dce: <http://purl.org/dc/elements/1.1/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX pav: <http://purl.org/pav/>
            PREFIX prov: <https://www.w3.org/ns/prov#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX void: <http://rdfs.org/ns/void#>

            CONSTRUCT {
              <xxx> ?p ?o .

              # remove provenance, for now
              # ?s ?p2 ?o2 .              
              # ?s rdf:subject <xxx> ;
              #   prov:has_provenance ?m .              
            }
            WHERE {
                <xxx> ?p ?o .

                # remove provenance, for now
                # OPTIONAL {
                #     ?s rdf:subject <xxx> ;
                #        prov:has_provenance ?m .
                #         
                #     # { ?s ?p2 ?o2 }
                # }

                # exclude PUV properties from NVS view
                FILTER (!STRSTARTS(STR(?p), "https://w3id.org/env/puv#"))
            }        
            """.replace("xxx", self.instance_uri)
        r = sparql_construct(q, self.mediatype)
        if r[0]:
            return Response(r[1], headers={"Content-Type": self.mediatype})
        else:
            return PlainTextResponse(
                "There was an error obtaining the Concept RDF from the Triplestore",
                status_code=500
            )

    def _render_skos_rdf(self):
        q = """
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            CONSTRUCT {
              <xxx> ?p ?o .   
              ?s ?p2 <xxx> .  
            }
            WHERE {
              <xxx> ?p ?o .
              ?s ?p2 <xxx> .

              # include only SKOS properties
              FILTER (STRSTARTS(STR(?p), "http://www.w3.org/2004/02/skos/core#"))
              FILTER (STRSTARTS(STR(?p2), "http://www.w3.org/2004/02/skos/core#"))
            }
            """.replace("xxx", self.instance_uri)
        r = sparql_construct(q, self.mediatype)
        if r[0]:
            return Response(r[1], headers={"Content-Type": self.mediatype})
        else:
            return PlainTextResponse(
                "There was an error obtaining the Concept RDF from the Triplestore",
                status_code=500
            )

    def _render_vocpub_rdf(self):
        q = """
            PREFIX dce: <http://purl.org/dc/elements/1.1/>
            PREFIX dcterms: <http://purl.org/dc/terms/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX pav: <http://purl.org/pav/>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX void: <http://rdfs.org/ns/void#>
            CONSTRUCT {
              <xxx> ?p ?o .   
              ?s ?p2 <xxx> .  
            }
            WHERE {
              <xxx> ?p ?o .
              ?s ?p2 <xxx> .

              FILTER (!STRSTARTS(STR(?p2), "http://www.w3.org/1999/02/22-rdf-syntax-ns#"))
            }
            """.replace("xxx", self.instance_uri)
        r = sparql_construct(q, self.mediatype)
        if r[0]:
            return Response(r[1], headers={"Content-Type": self.mediatype})
        else:
            return PlainTextResponse(
                "There was an error obtaining the Concept RDF from the Triplestore",
                status_code=500
            )

    def _render_sdo_rdf(self):
        q = """
            PREFIX dcterms: <http://purl.org/dc/terms/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX sdo: <https://schema.org/>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            CONSTRUCT {
              <http://vocab.nerc.ac.uk/collection/P01/current/SAGEMSFM/>
                a sdo:DefinedTerm ;
                sdo:name ?pl ;
                sdo:alternateName ?al ;
                sdo:description ?def ;
                sdo:identifier ?id ;
                sdo:dateModified ?modified ;
                sdo:version ?versionInfo ;
                sdo:inDefinedTermSet ?collection ;
                sdo:isPartOf ?scheme ;
                sdo:sameAs ?sameAs ;
              .
            }
            WHERE {
              <http://vocab.nerc.ac.uk/collection/P01/current/SAGEMSFM/> 
                skos:prefLabel ?pl ;
                skos:definition ?def ;
                dcterms:identifier ?id ;
                dcterms:date ?date ;
                owl:versionInfo ?versionInfo ;
              .

              BIND (STRDT(REPLACE(STRBEFORE(?date, "."), " ", "T"), xsd:dateTime) AS ?modified)

              ?collection skos:member <http://vocab.nerc.ac.uk/collection/P01/current/SAGEMSFM/>  .

              OPTIONAL {
                <http://vocab.nerc.ac.uk/collection/P01/current/SAGEMSFM/>
                  skos:altLabel ?al ;
                  skos:inScheme ?scheme ;
                  owl:sameAs ?sameAs ;
                .
              }
            }            
            """
        r = sparql_construct(q, self.mediatype)
        if r[0]:
            return Response(r[1], headers={"Content-Type": self.mediatype})
        else:
            return PlainTextResponse(
                "There was an error obtaining the Concept RDF from the Triplestore",
                status_code=500
            )

    def _render_puv_rdf(self):
        q = """
            PREFIX puv: <https://w3id.org/env/puv#>
            CONSTRUCT {
              <xxx> ?p ?o .
            }
            WHERE {
              <xxx> ?p ?o .

              # include only PUV properties
              FILTER (STRSTARTS(STR(?p), "https://w3id.org/env/puv#"))
            }
            """.replace("xxx", self.instance_uri)
        r = sparql_construct(q, self.mediatype)
        if r[0]:
            return Response(r[1], headers={"Content-Type": self.mediatype})
        else:
            return PlainTextResponse(
                "There was an error obtaining the Concept RDF from the Triplestore",
                status_code=500
            )

    def render(self):
        if self.profile == "nvs":
            if self.mediatype in RDF_MEDIATYPES or self.mediatype in Renderer.RDF_SERIALIZER_TYPES_MAP:
                return self._render_nvs_rdf()
            else:
                return self._render_nvs_or_puv_html()
        elif self.profile == "skos":
            return self._render_skos_rdf()
        elif self.profile == "vocpub":
            return self._render_vocpub_rdf()
        elif self.profile == "sdo":
            return self._render_sdo_rdf()
        elif self.profile == "puv":
            if self.mediatype in RDF_MEDIATYPES or self.mediatype in Renderer.RDF_SERIALIZER_TYPES_MAP:
                return self._render_puv_rdf()
            else:
                return self._render_nvs_or_puv_html()

        alt = super().render()
        if alt is not None:
            return alt


def concept(request: Request):
    return ConceptRenderer(request).render()


@api.get("/mapping/{int_ext}/{mapping_id}/")
def mapping(request: Request):
    class MappingRenderer(Renderer):
        def __init__(self):
            self.instance_uri = "http://vocab.nerc.ac.uk/mapping/" + \
                                str(request.url).split("/mapping/")[1].split("?")[0]

            super().__init__(request, self.instance_uri, {"nvs": nvs}, "nvs")

        def render(self):
            if "/I/" not in self.instance_uri and "/O/" not in self.instance_uri:
                return PlainTextResponse(
                    'All requests for Mappings must contain either "I" or "O" in the URI',
                    status_code=400
                )

            if self.profile == "nvs":
                g = self._get_mapping_rdf()
                if not g:
                    return PlainTextResponse(
                        "There was an error obtaining the Collections RDF from the Triplestore",
                        status_code=500
                    )
                if len(g) == 0:
                    return PlainTextResponse(
                        "The URI you supplied for the Mapping does not exist",
                        status_code=400
                    )

                if self.mediatype in RDF_MEDIATYPES or self.mediatype in Renderer.RDF_SERIALIZER_TYPES_MAP:
                    return self._render_nvs_rdf(g)
                else:
                    return self._render_nvs_html(g)

            # try returning alt profile
            response = super().render()
            if response is not None:
                return response

        def _get_mapping_rdf(self):
            r = sparql_construct(f"DESCRIBE <{self.instance_uri}>")
            if r[0]:
                return Graph().parse(r[1])
            else:
                return False

        def _render_nvs_rdf(self, g):
            g.bind("dc", DC)
            REG = Namespace("http://purl.org/linked-data/registry#")
            g.bind("reg", REG)
            g.bind("org", ORG)

            return self._make_rdf_response(g)

        def _render_nvs_html(self, g):
            mapping = {}
            for p, o in g.predicate_objects(subject=URIRef(self.instance_uri)):
                if str(p) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#subject":
                    mapping["subject"] = str(o)
                elif str(p) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#predicate":
                    mapping["predicate"] = str(o)
                elif str(p) == "http://www.w3.org/1999/02/22-rdf-syntax-ns#object":
                    mapping["object"] = str(o)
                elif str(p) == "http://purl.org/dc/elements/1.1/modified":
                    mapping["modified"] = str(o)
                elif str(p) == "http://purl.org/linked-data/registry#status":
                    mapping["status"] = str(o)
                elif str(p) == "http://purl.org/linked-data/registry#submitter":
                    for p2, o2 in g.predicate_objects(subject=o):
                        if str(p2) == "http://purl.org/linked-data/registry#title":
                            mapping["title"] = str(o2)
                        elif str(p2) == "http://purl.org/linked-data/registry#name":
                            mapping["name"] = str(o2)
                        elif str(p2) == "http://www.w3.org/ns/org#memberOf":
                            mapping["memberof"] = str(o2)

            context = {
                "request": request,
                "uri": self.instance_uri,
                "systemUri": self.instance_uri.replace("http://vocab.nerc.ac.uk", ""),
                "subject": mapping["subject"],
                "subjectSystemUri": mapping["subject"].replace("http://vocab.nerc.ac.uk", ""),
                "predicate": mapping["predicate"],
                "predicateSystemUri": mapping["predicate"].replace("http://vocab.nerc.ac.uk", ""),
                "object": mapping["object"],
                "objectSystemUri": mapping["object"].replace("http://vocab.nerc.ac.uk", ""),
                "modified": mapping["modified"],
                "status": mapping["status"],
                "submitter_title": mapping.get("title"),
                "submitter_name": mapping.get("name"),
                "submitter_memberof": mapping.get("memberof"),
                "profile_token": self.profile
            }

            return templates.TemplateResponse("mapping.html", context=context)

    return MappingRenderer().render()


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
def contact(request: Request):
    return templates.TemplateResponse("contact_us.html", {"request": request})


@api.get("/sparql")
def sparql(request: Request):
    # queries to /sparql with an accept header set to a SPARQL return type or an RDF type
    # are forwarded to /endpoint for a response
    # all others (i.e. with no Accept header, an Accept header HTML or for an unsupported Accept header
    # result in the SPARQL page HTML respose where the query is placed into the YasGUI UI for interactive querying
    SPARQL_RESPONSE_MEDIA_TYPES = [
        "application/sparql-results+json",
        "text/csv",
        "text/tab-separated-values",
    ]
    QUERY_RESPONSE_MEDIA_TYPES = ["text/html"] + SPARQL_RESPONSE_MEDIA_TYPES + RDF_MEDIATYPES
    accepts = get_accepts(request.headers["Accept"])
    accept = [x for x in accepts if x in QUERY_RESPONSE_MEDIA_TYPES][0]
    if accept == "text/html":
        return templates.TemplateResponse("sparql.html", {"request": request})
    else:
        return endpoint_get(request)


# the SPARQL endpoint under-the-hood
def _get_sparql_service_description(rdf_fmt="text/turtle"):
    """Return an RDF description of PROMS' read only SPARQL endpoint in a requested format
    :param rdf_fmt: 'turtle', 'n3', 'xml', 'json-ld'
    :return: string of RDF in the requested format
    """
    sd_ttl = """
        @prefix rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix sd:     <http://www.w3.org/ns/sparql-service-description#> .
        @prefix sdf:    <http://www.w3.org/ns/formats/> .
        @prefix void:   <http://rdfs.org/ns/void#> .
        @prefix xsd:    <http://www.w3.org/2001/XMLSchema#> .
        <{0}>
            a                       sd:Service ;
            sd:endpoint             <{0}> ;
            sd:supportedLanguage    sd:SPARQL11Query ; # yes, read only, sorry!
            sd:resultFormat         sdf:SPARQL_Results_JSON ;  # yes, we only deliver JSON results, sorry!
            sd:feature sd:DereferencesURIs ;
            sd:defaultDataset [
                a sd:Dataset ;
                sd:defaultGraph [
                    a sd:Graph ;
                    void:triples "100"^^xsd:integer
                ]
            ]
        .
    """.format(SYSTEM_URI + "/sparql")
    grf = Graph().parse(data=sd_ttl)
    if rdf_fmt in RDF_MEDIATYPES:
        return grf.serialize(format=rdf_fmt)
    else:
        raise ValueError(
            "Input parameter rdf_format must be one of: " + ", ".join(RDF_MEDIATYPES)
        )


def _sparql_query2(q, mimetype="application/json"):
        """ Make a SPARQL query"""
        from config import SPARQL_ENDPOINT, SPARQL_USERNAME, SPARQL_PASSWORD
        import httpx
        logging.debug("sparql_query2: {}".format(q))
        data = q

        headers = {
            "Content-Type": "application/sparql-query",
            "Accept": mimetype,
            "Accept-Encoding": "UTF-8",
        }
        if SPARQL_USERNAME is not None and SPARQL_PASSWORD is not None:
            auth = (SPARQL_USERNAME, SPARQL_PASSWORD)
        else:
            auth = None

        try:
            logging.debug(
                "endpoint={}\ndata={}\nheaders={}".format(
                    SPARQL_ENDPOINT, data, headers
                )
            )
            if auth is not None:
                r = httpx.post(
                    SPARQL_ENDPOINT, auth=auth, data=data, headers=headers, timeout=60
                )
            else:
                r = httpx.post(
                    SPARQL_ENDPOINT, data=data, headers=headers, timeout=60
                )
            return r.content.decode()
        except Exception as ex:
            raise ex


@api.post("/sparql")
@api.post("/endpoint")
def endpoint_post(request: Request, query: str = fastapi.Form(...)):
    """
    TESTS
    Form POST:
    curl -X POST -d query="PREFIX%20skos%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2Fskos%2Fcore%23%3E%0ASELECT%20* \
    %20WHERE%20%7B%3Fs%20a%20skos%3AConceptScheme%20.%7D" http://localhost:5000/endpoint
    Raw POST:
    curl -X POST -H 'Content-Type: application/sparql-query' --data-binary @query.sparql http://localhost:5000/endpoint
    using query.sparql:
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT * WHERE {?s a skos:ConceptScheme .}
    GET:
    curl http://localhost:5000/endpoint?query=PREFIX%20skos%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2Fskos%2Fcore \
    %23%3E%0ASELECT%20*%20WHERE%20%7B%3Fs%20a%20skos%3AConceptScheme%20.%7D
    GET CONSTRUCT:
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        CONSTRUCT {?s a rdf:Resource}
        WHERE {?s a skos:ConceptScheme}
    curl -H 'Accept: application/ld+json' http://localhost:5000/endpoint?query=PREFIX%20rdf%3A%20%3Chttp%3A%2F%2F \
    www.w3.org%2F1999%2F02%2F22-rdf-syntax-ns%23%3E%0APREFIX%20skos%3A%20%3Chttp%3A%2F%2Fwww.w3.org%2F2004%2F02%2F \
    skos%2Fco23%3E%0ACONSTRUCT%20%7B%3Fs%20a%20rdf%3AResource%7D%0AWHERE%20%7B%3Fs%20a%20skos%3AConceptScheme%7D
    """
    """Pass on the SPARQL query to the underlying endpoint defined in config"""
    if "application/x-www-form-urlencoded" in request.headers["content-type"]:
        """
        https://www.w3.org/TR/2013/REC-sparql11-protocol-20130321/#query-via-post-urlencoded
        2.1.2 query via POST with URL-encoded parameters
        Protocol clients may send protocol requests via the HTTP POST method by URL encoding the parameters. When
        using this method, clients must URL percent encode all parameters and include them as parameters within the
        request body via the application/x-www-form-urlencoded media type with the name given above. Parameters must
        be separated with the ampersand (&) character. Clients may include the parameters in any order. The content
        type header of the HTTP request must be set to application/x-www-form-urlencoded.
        """

        if query is None or len(query) < 5:
            return PlainTextResponse(
                "Your POST request to the SPARQL endpoint must contain a 'query' parameter if form posting is used.",
                status_code=400
            )
    elif "application/sparql-query" in request.headers["content-type"]:
        """
        https://www.w3.org/TR/2013/REC-sparql11-protocol-20130321/#query-via-post-direct
        2.1.3 query via POST directly
        Protocol clients may send protocol requests via the HTTP POST method by including the query directly and
        unencoded as the HTTP request message body. When using this approach, clients must include the SPARQL query
        string, unencoded, and nothing else as the message body of the request. Clients must set the content type
        header of the HTTP request to application/sparql-query. Clients may include the optional default-graph-uri
        and named-graph-uri parameters as HTTP query string parameters in the request URI. Note that UTF-8 is the
        only valid charset here.
        """
        query = request.query_params.get("data")  # get the raw request
        if query is None:
            return PlainTextResponse(
                "Your POST request to this SPARQL endpoint must contain the query in plain text in the "
                "POST body if the Content-Type 'application/sparql-query' is used.",
                status_code=400
            )
    else:
        return PlainTextResponse(
            "Your POST request to this SPARQL endpoint must either the 'application/x-www-form-urlencoded' or"
            "'application/sparql-query' ContentType.",
            status_code=400
        )

    try:
        if "CONSTRUCT" in query:
            format_mimetype = "text/turtle"
            return Response(
                _sparql_query2(query, request.headers["Accept"]),
                media_type=format_mimetype
            )
        else:
            return Response(
                _sparql_query2(query, request.headers["Accept"]),
            )
    except ValueError as e:
        return PlainTextResponse(
            "Input error for query {}.\n\nError message: {}".format(query, str(e)),
            status_code=400
        )
    except ConnectionError as e:
        return PlainTextResponse(str(e), status_code=500)


@api.get("/endpoint")
def endpoint_get(request: Request):
        if request.query_params.get("query") is not None:
            # SPARQL GET request
            """
            https://www.w3.org/TR/2013/REC-sparql11-protocol-20130321/#query-via-get
            2.1.1 query via GET
            Protocol clients may send protocol requests via the HTTP GET method. When using the GET method, clients must
            URL percent encode all parameters and include them as query parameter strings with the names given above.
            HTTP query string parameters must be separated with the ampersand (&) character. Clients may include the
            query string parameters in any order.
            The HTTP request MUST NOT include a message body.
            """
            query = request.query_params.get("query")
            accepts = get_accepts(request.headers["Accept"])
            if "CONSTRUCT" in query or "DESCRIBE" in query:
                accept = [x for x in accepts if x in RDF_MEDIATYPES][0]
                if accept is None:
                    return PlainTextResponse(
                        "Accept header must include at least on RDF Media Type:" + ", ".join(RDF_MEDIATYPES) + ".",
                        status_code=400,
                    )
                return Response(
                    _sparql_query2(query, mimetype=request.headers["Accept"]),
                    media_type=accept,
                    headers={
                        "Content-Disposition":
                            f'attachment; filename=query_result.{RDF_FILE_EXTS[accept]}'
                    },
                )
            else:
                return Response(_sparql_query2(query), media_type="application/sparql-results+json")
        else:
            # SPARQL Service Description
            """
            https://www.w3.org/TR/sparql11-service-description/#accessing
            SPARQL services made available via the SPARQL Protocol should return a service description document at the
            service endpoint when dereferenced using the HTTP GET operation without any query parameter strings
            provided. This service description must be made available in an RDF serialization, may be embedded in
            (X)HTML by way of RDFa, and should use content negotiation if available in other RDF representations.
            """

            accepts = get_accepts(request.headers["Accept"])
            print(accepts)
            if accepts[0] in ['application/sparql-results+json', 'text/html']:
                # show the SPARQL query form
                return RedirectResponse(url="/sparql")
            else:
                accept = [x for x in accepts if x in RDF_MEDIATYPES][0]
                if accept is None:
                    return PlainTextResponse(
                        "Accept header must include at least on RDF Media Type:" + ", ".join(RDF_MEDIATYPES) + ".",
                        status_code=400,
                    )
                return Response(
                    _get_sparql_service_description(accept),
                    media_type=accept
                )


@api.get("/cache-clear")
def cache_clr(request: Request):
    cache_clear()
    return PlainTextResponse("Cache cleared")


if __name__ == "__main__":
    uvicorn.run(api, port=PORT, host=SYSTEM_URI)
