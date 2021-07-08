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
from model.profiles import void
from utils import sparql_query, cache_return, cache_clear, cache_fill

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


@api.get("/collections")
def collections(request: Request):
    collections = cache_return(collections_or_conceptschemes="collections")

    if request.query_params.get("filter"):
        def concat_vocab_fields(vocab):
            return f"{vocab['id']['value']}" \
                   f"{vocab['prefLabel']['value']}" \
                   f"{vocab['description']['value']}"
        collections = [x for x in collections if request.query_params.get("filter") in concat_vocab_fields(x)]

    return templates.TemplateResponse(
        "collections.html",
        {
            "request": request,
            "collections": collections,
            "profile_token": "nvs",
        }
    )


@api.get("/conceptschemes")
def conceptschemes(request: Request):
    conceptschemes = cache_return(collections_or_conceptschemes="conceptschemes")
    import pprint
    pprint.pprint(conceptschemes)

    if request.query_params.get("filter"):
        def concat_vocab_fields(vocab):
            return f"{vocab['id']['value']}" \
                   f"{vocab['prefLabel']['value']}" \
                   f"{vocab['description']['value']}"
        conceptschemes = [x for x in conceptschemes if request.query_params.get("filter") in concat_vocab_fields(x)]

    return templates.TemplateResponse(
        "conceptschemes.html",
        {
            "request": request,
            "conceptschemes": conceptschemes,
            "profile_token": "nvs",
        }
    )


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

    from pyldapi.renderer import Renderer

    class WkRenderer(Renderer):
        def __init__(self):
            super().__init__(
                request,
                "http://vocab.nerc.ac.uk/.well_known/void",
                {"void": void},
                "void",
                MEDIATYPE_NAMES=RDF_MEDIATYPES,
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
    uvicorn.run(api, port=5000, host="127.0.0.1")
