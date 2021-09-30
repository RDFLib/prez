from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
import uvicorn

from connegp import Connegp, Profile, RDF_MEDIATYPES

app = FastAPI()

dcat = Profile(
    uri="https://www.w3.org/TR/vocab-dcat/",
    id="dcat",
    label="DCAT",
    comment="Dataset Catalogue Vocabulary (DCAT) is a W3C-authored RDF vocabulary designed to "
    "facilitate interoperability between data catalogs "
    "published on the Web.",
    mediatypes=["text/html"] + RDF_MEDIATYPES,
    default_mediatype="text/html",
    languages=["en"],
    default_language="en",
)

skos = Profile(
    uri="https://www.w3.org/TR/skos-reference/",
    id="skos",
    label="SKOS",
    comment="Simple Knowledge Organization System (SKOS) is a W3C-authored, common data model for sharing "
    "and linking knowledge organization systems "
    "via the Web.",
    mediatypes=RDF_MEDIATYPES,
    default_mediatype="text/turtle",
    languages=["en"],
    default_language="en",
)


@app.get("/")
async def root(request: Request):
    # insert new headers & create new request object for testing
    extra_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Profile": "<https://www.w3.org/TR/skos-reference/>;q=1.0,<https://www.w3.org/TR/vocab-dcat/>;q=0.8",
        "Link": '<https://www.w3.org/TR/skos-reference/>; rel="profile"',
    }
    headers_new = MutableHeaders(request.headers)
    headers_new.update(extra_headers)
    new_scope = {
        "headers": headers_new._list,
        "type": request.scope["type"],
        "query_string": request.scope["query_string"],
    }
    new_request = Request(new_scope, request._receive, send=request._send)
    c = Connegp(new_request, {"dcat": dcat, "skos": skos}, "dcat")
    print(f"Profile: {c.profile}, mediatype: {c.mediatype}")
    return {"message": "Hello World"}


if __name__ == "__main__":
    uvicorn.run(app, port=8001, host="127.0.0.1")
