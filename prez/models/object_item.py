from typing import Optional, FrozenSet, Tuple
from typing import Set

from pydantic import BaseModel, root_validator
from rdflib import URIRef, PROF

from prez.cache import endpoints_graph_cache
from prez.models.model_exceptions import ClassNotFoundException
from prez.reference_data.prez_ns import PREZ, ONT
from prez.services.curie_functions import get_uri_for_curie_id
from prez.services.model_methods import get_classes


class ObjectItem(BaseModel):
    uri: Optional[URIRef] = None
    classes: Optional[FrozenSet[URIRef]] = frozenset([PROF.Profile])
    selected_class: Optional[URIRef] = None
    profile: Optional[URIRef] = None
    top_level_listing: Optional[bool] = False

    def __hash__(self):
        return hash(self.uri)
