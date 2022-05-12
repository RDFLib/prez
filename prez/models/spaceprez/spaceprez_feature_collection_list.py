from typing import List


class SpacePrezFeatureCollectionList(object):
    def __init__(self, sparql_response: List) -> None:
        self.dataset = {"id": None, "title": None}
        self.members = []
        for result in sparql_response:
            if self.dataset["id"] is None:
                self.dataset["id"] = result["d_id"]["value"]
            if self.dataset["title"] is None:
                self.dataset["title"] = result["d_label"]["value"]
            self.members.append(
                {
                    "uri": result["coll"]["value"],
                    "title": result["label"]["value"],
                    "id": result["id"]["value"],
                    "desc": result["desc"].get("value") if result.get("desc") else None,
                    "link": f"/dataset/{self.dataset['id']}/collections/{result.get('id').get('value')}",
                    "members": f"/dataset/{self.dataset['id']}/collections/{result.get('id').get('value')}/items",
                }
            )
        self.members.sort(key=lambda m: m["title"])

    def get_feature_collection_flat_list(self):
        feature_collection_list = []
        for mem in self.members:
            feature_collection_list.append(
                {
                    "uri": mem["uri"],
                    "prefLabel": mem["title"],
                }
            )
        return sorted(feature_collection_list, key=lambda c: c["prefLabel"])
