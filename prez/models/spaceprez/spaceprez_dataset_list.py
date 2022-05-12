from typing import List


class SpacePrezDatasetList(object):
    def __init__(self, sparql_response: List) -> None:
        self.members = []
        for result in sparql_response:
            self.members.append(
                {
                    "uri": result["d"]["value"],
                    "title": result["label"]["value"],
                    "id": result["id"]["value"],
                    "desc": result["desc"].get("value") if result.get("desc") else None,
                    "link": f"/dataset/{result['id']['value']}",
                    "members": f"/dataset/{result['id']['value']}/collections",
                }
            )
        self.members.sort(key=lambda m: m["title"])

    def get_dataset_flat_list(self):
        dataset_list = []
        for mem in self.members:
            dataset_list.append(
                {
                    "uri": mem["uri"],
                    "prefLabel": mem["title"],
                }
            )
        return sorted(dataset_list, key=lambda c: c["prefLabel"])
