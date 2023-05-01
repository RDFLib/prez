from fastapi import APIRouter, Request
from starlette.responses import PlainTextResponse

from prez.models import SpatialItem, VocabItem, CatalogItem

router = APIRouter(tags=["Object"])


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
    for prez in settings.enabled_prezs:
        try:
            item = prez_items[prez](uri=uri, url_path="/object")
            returned_items[prez] = item
        except Exception:  # will get exception if URI does not exist with classes in prez flavour's SPARQL endpoint
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
        # TODO reimplement class based logic to select the most relevant .. endpoint?
    # elif len(returned_items) > 1:
    #     lower_keys = [k.lower() for k in returned_items.keys()]
    #     links = "\n".join(
    #         ["/" + lower_key[0] + "/object?uri=" + uri for lower_key in lower_keys]
    #     )
    #     return PlainTextResponse(f"Object found in multiple prez flavours:\n{links}")
