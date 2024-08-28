from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter(tags=["Conformance"])


class ConformanceDeclaration(BaseModel):
    conformsTo: List[str]


CONFORMANCE_CLASSES = [
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/html",
    # "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
]


@router.get("/conformance", response_model=ConformanceDeclaration, status_code=200)
async def get_conformance():
    try:
        return ConformanceDeclaration(conformsTo=CONFORMANCE_CLASSES)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
