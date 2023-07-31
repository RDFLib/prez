from fastapi import APIRouter, Request, HTTPException, status, Query
from starlette.responses import PlainTextResponse

from prez.models import SpatialItem, VocabItem, CatalogItem

router = APIRouter(tags=["Object"])


@router.get("/count", summary="Get object's statement count")
def count_route(
    curie: str,
    inbound: str = Query(
        None,
        examples={
            "skos:inScheme": {
                "summary": "skos:inScheme",
                "value": "http://www.w3.org/2004/02/skos/core#inScheme",
            },
            "skos:topConceptOf": {
                "summary": "skos:topConceptOf",
                "value": "http://www.w3.org/2004/02/skos/core#topConceptOf",
            },
        },
    ),
    outbound: str = Query(
        None,
        examples={
            "skos:inScheme": {
                "summary": "skos:hasTopConcept",
                "value": "http://www.w3.org/2004/02/skos/core#hasTopConcept",
            },
        },
    ),
):
    """Get an Object's statements count based on the inbound or outbound predicate"""
    if inbound is None and outbound is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "At least 'inbound' or 'outbound' is supplied a valid IRI.",
        )

    return f"{curie} {inbound} {outbound}"


@router.get("/object", summary="Object")
async def object(
    request: Request,
):
    from prez.config import settings

    uri = request.query_params.get("uri")
    if not uri:
        return PlainTextResponse(
            "An object uri must be provided as a query string argument (?uri=<object_uri>)"
        )

    prez_items = {
        "SpacePrez": SpatialItem,
        "VocPrez": VocabItem,
        "CatPrez": CatalogItem,
    }

    returned_items = {}
    for prez in prez_items.keys():
        try:
            item = prez_items[prez](uri=uri, url_path="/object")
            returned_items[prez] = item
        except (
            Exception
        ):  # will get exception if URI does not exist with classes in prez flavour's SPARQL endpoint
            pass
    if len(returned_items) == 0:
        return PlainTextResponse(
            f"No object found for the provided URI in enabled prez flavours: {', '.join(settings.enabled_prezs)}"
        )
    elif len(returned_items):
        prez = list(returned_items.keys())[0]
        if prez == "SpacePrez":
            from prez.routers.spaceprez import item_endpoint

            return await item_endpoint(request, returned_items[prez])
        elif prez == "VocPrez":
            from prez.routers.vocprez import item_endpoint

            return await item_endpoint(request, returned_items[prez])
        elif prez == "CatPrez":
            from prez.routers.catprez import item_endpoint

            return await item_endpoint(request, returned_items[prez])
