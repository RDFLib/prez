import json
from pathlib import Path

responses_json = Path(__file__).parent / "rdf_response_examples.json"
responses = json.loads(responses_json.read_text())
cql_json_examples_dir = Path(__file__).parent.parent / "examples/cql"
cql_examples = {
    file.stem: {"summary": file.stem, "value": json.loads(file.read_text())}
    for file in cql_json_examples_dir.glob("*.json")
}


def create_path_param(name: str, description: str, example: str):
    return {
        "in": "path",
        "name": name,
        "required": True,
        "schema": {
            "type": "string",
            "example": example,
        },
        "description": description,
    }


ogc_extended_path_parameters = {
    "collection-listing": [
        create_path_param("catalogId", "Curie of the Catalog ID.", "bblck-ctlg:bblocks")
    ],
    "item-listing": [
        create_path_param(
            "catalogId", "Curie of the Catalog ID.", "bblck-ctlg:bblocks"
        ),
        create_path_param(
            "recordsCollectionId", "Curie of the Collection ID.", "bblck-vcbs:api"
        ),
    ],
    "top-concepts": [
        create_path_param("parent_curie", "Parent CURIE.", "exm:SchemingConceptScheme")
    ],
    "narrowers": [
        create_path_param("parent_curie", "Parent CURIE.", "exm:TopLevelConcept")
    ],
    "profile-object": [
        create_path_param("profile_curie", "Profile CURIE.", "prez:OGCItemProfile")
    ],
    "catalog-object": [
        create_path_param("catalogId", "Catalog ID.", "bblck-ctlg:bblocks")
    ],
    "collection-object": [
        create_path_param("catalogId", "Catalog ID.", "bblck-ctlg:bblocks"),
        create_path_param("recordsCollectionId", "Collection ID.", "bblck-vcbs:api"),
    ],
    "item-object": [
        create_path_param("catalogId", "Catalog ID.", "bblck-ctlg:bblocks"),
        create_path_param("recordsCollectionId", "Collection ID.", "bblck-vcbs:api"),
        create_path_param("itemId", "Item ID.", "bblcks:ogc.unstable.sosa"),
    ],
}
ogc_extended_openapi_extras = {
    name: {"parameters": params} for name, params in ogc_extended_path_parameters.items()
}

ogc_features_path_parameters = {
    "feature-collection": [
        create_path_param("collectionId", "Collection ID.", "syn:68a782a8-d7fe-4b3e-8377-c76c9cc245cc")
    ],
    "feature": [
        create_path_param("collectionId", "Collection ID.", "syn:68a782a8-d7fe-4b3e-8377-c76c9cc245cc"),
        create_path_param("featureId", "Feature ID.", "ns3:2c8e292e-6eff-4a36-ad27-54fed2c1b422"),
    ],
}
ogc_features_openapi_extras = {
    name: {"parameters": params} for name, params in ogc_features_path_parameters.items()
}