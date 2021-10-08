from fastapi import APIRouter, Request

from renderers import VocPrezDatasetRenderer
from services.vocprez_service import *
from models import VocPrezDataset

router = APIRouter(prefix="/vocprez")


@router.get("/")
async def dataset(request: Request):
    dataset_response = await get_datasets()
    # group by dataset URI (assume 1 dataset for now)
    dataset = VocPrezDataset(dataset_response)
    dataset_renderer = VocPrezDatasetRenderer(
        request,
        str(request.url.remove_query_params(keys=request.query_params.keys())),
        dataset,
    )
    return dataset_renderer.render()
