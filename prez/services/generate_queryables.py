from pyoxigraph import Store as OxiStore, NamedNode as OxiNamedNode

from prez.config import settings
from prez.models.ogc_features import QueryableProperty, Queryables
from prez.reference_data.prez_ns import OGCFEAT, PREZ


def generate_queryables_json(
    item_store: OxiStore, annotations_store: OxiStore, url, endpoint_uri
):
    queryable_props = {}

    # Get all unique subjects from the item store
    subjects = set()
    for quad in item_store.quads_for_pattern(subject=None, predicate=None, object=None):
        subjects.add(quad[0])

    for queryable in subjects:
        # Get title from annotations store
        title_quad = next(
            annotations_store.quads_for_pattern(
                subject=queryable, predicate=OxiNamedNode(PREZ.label), object=None
            ),
            None,
        )
        title = title_quad[2].value if title_quad else None

        # Get description from annotations store
        description_quad = next(
            annotations_store.quads_for_pattern(
                subject=queryable, predicate=OxiNamedNode(PREZ.description), object=None
            ),
            None,
        )
        description = description_quad[2].value if description_quad else None

        queryable_props[str(queryable.value)] = QueryableProperty(
            title=title,
            description=description,
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
