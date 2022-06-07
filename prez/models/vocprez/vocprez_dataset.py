from typing import List, Dict

from prez.config import *
from prez.models import PrezModel


class VocPrezDataset(PrezModel):
    # class attributes for property grouping & order
    main_props = []
    hidden_props = []

    def __init__(self, graph: Graph) -> None:
        super().__init__(graph)

        self.uri = VOCPREZ_DATA_URI
        self.title = VOCPREZ_TITLE
        self.description = VOCPREZ_DESC

    # override
    def to_dict(self) -> Dict:
        return {
            "uri": self.uri,
            "title": self.title,
            "description": self.description,
        }

    # override
    def _get_properties(self) -> List[Dict]:
        props_dict = self._get_props_dict()

        # group props in order, filtering out hidden props
        properties = []
        main_props = []
        other_props = []

        for uri, prop in props_dict.items():
            if uri in VocPrezDataset.hidden_props:
                continue
            elif uri in VocPrezDataset.main_props:
                main_props.append(prop)
            else:
                other_props.append(prop)

        properties.extend(
            sorted(
                main_props,
                key=lambda p: self._sort_within_list(p, VocPrezDataset.main_props),
            )
        )
        properties.extend(other_props)

        return properties
