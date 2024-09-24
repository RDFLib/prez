from fastapi import Depends

from prez.config import settings
from prez.dependencies import get_system_repo
from prez.models.ogc_features import QueryableProperty, Queryables
from prez.reference_data.prez_ns import PREZ, OGCFEAT
from prez.repositories import Repo


def generate_queryables_json(item_graph, annotations_graph, url, endpoint_uri):
    queryable_props = {}
    for queryable in item_graph.subjects():
        queryable_props[str(queryable)] = QueryableProperty(
            title=annotations_graph.value(queryable, PREZ.label),
            description=annotations_graph.value(queryable, PREZ.description),
        )
    if endpoint_uri == OGCFEAT["queryables-global"]:
        title = "Global Queryables"
        description = (
            "Global queryable properties for all collections in the OGC Features API."
        )
    else:
        title = "Local Queryables"
        description = (
            "Local queryable properties for the collection in the OGC Features API."
        )
    queryable_params = {
        "$id": f"{settings.system_uri}{url.path}",
        "title": title,
        "description": description,
        "properties": queryable_props,
    }
    return Queryables(**queryable_params)
