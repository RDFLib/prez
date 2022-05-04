from typing import List


class SpacePrezFeatureList(object):
    def __init__(self, sparql_response: List) -> None:
        self.dataset = {"id": None, "title": None}
        self.collection = {"id": None, "title": None}
        self.members = []
        for result in sparql_response:
            if self.dataset["id"] is None:
                self.dataset["id"] = result["d_id"]["value"]
            if self.dataset["title"] is None:
                self.dataset["title"] = result["d_label"]["value"]
            if self.collection["id"] is None:
                self.collection["id"] = result["coll_id"]["value"]
            if self.collection["title"] is None:
                self.collection["title"] = result["coll_label"]["value"]
            self.members.append(
                {
                    "uri": result["f"]["value"],
                    "title": result["label"]["value"]
                    if result.get("label")
                    else f"Feature {result['id']['value']}",
                    "id": result["id"]["value"],
                    "desc": result["desc"].get("value") if result.get("desc") else None,
                    "link": f"/dataset/{self.dataset['id']}/collections/{self.collection['id']}/items/{result['id']['value']}",
                    "members": None,
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
