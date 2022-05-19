from typing import List


class VocPrezCollectionList(object):
    def __init__(self, sparql_response: List) -> None:
        self.members = []
        for result in sparql_response:
            self.members.append(
                {
                    "uri": result["coll"]["value"],
                    "title": result["label"]["value"],
                    "id": result["id"]["value"],
                    "desc": result["desc"].get("value") if result.get("desc") else None,
                    "link": f"/collection/{result['id']['value']}",
                    "members": None,
                }
            )
        self.members.sort(key=lambda m: m["title"])

    def get_collection_flat_list(self):
        collection_list = []
        for mem in self.members:
            collection_list.append(
                {
                    "uri": mem["uri"],
                    "prefLabel": mem["title"],
                }
            )
        return sorted(collection_list, key=lambda c: c["prefLabel"])
