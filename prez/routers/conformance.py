from fastapi import APIRouter, HTTPException

from prez.models.ogc_features import CONFORMANCE_CLASSES, ConformanceDeclaration

router = APIRouter(tags=["Conformance"])


@router.get("/conformance", response_model=ConformanceDeclaration, status_code=200)
async def get_conformance():
    try:
        return ConformanceDeclaration(conformsTo=CONFORMANCE_CLASSES)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
