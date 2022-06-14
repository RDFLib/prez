from typing import Dict, List, Optional


class SpacePrezFeatureList(object):
    def __init__(
        self,
        sparql_response: List,
        dataset: Optional[Dict] = None,  # {"id": "", "title": ""}
        collection: Optional[Dict] = None,  # {"id": "", "title": ""}
    ) -> None:
        self.dataset = dataset
        self.collection = collection
        self.members = []
        for result in sparql_response:
            d = {
                "id": result["d_id"]["value"],
                "title": result["d_label"]["value"],
            }
            coll = {
                "id": result["coll_id"]["value"],
                "title": result["coll_label"]["value"],
            }
            self.members.append(
                {
                    "uri": result["f"]["value"],
                    "title": result["label"]["value"]
                    if result.get("label")
                    else f"Feature {result['id']['value']}",
                    "id": result["id"]["value"],
                    "desc": result["desc"].get("value") if result.get("desc") else None,
                    "link": f"/dataset/{d['id']}/collections/{coll['id']}/items/{result['id']['value']}",
                    "members": None,
                    "dataset": d,
                    "collection": coll,
                }
            )
        self.members.sort(key=lambda m: m["title"])

    def get_feature_flat_list(self):
        feature_list = []
        for mem in self.members:
            feature_list.append(
                {
                    "uri": mem["uri"],
                    "prefLabel": mem["title"],
                }
            )
        return sorted(feature_list, key=lambda c: c["prefLabel"])
