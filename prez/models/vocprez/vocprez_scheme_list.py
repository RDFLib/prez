from typing import List


class VocPrezSchemeList(object):
    def __init__(self, sparql_response: List) -> None:
        self.members = []
        for result in sparql_response:
            self.members.append(
                {
                    "uri": result["cs"]["value"],
                    "title": result["label"]["value"],
                    "id": result["id"]["value"],
                    "desc": result["desc"].get("value") if result.get("desc") else None,
                    "link": f"/vocab/{result['id']['value']}",
                    "members": None,
                }
            )
        self.members.sort(key=lambda m: m["title"])

    def get_scheme_flat_list(self):
        scheme_list = []
        for mem in self.members:
            scheme_list.append(
                {
                    "uri": mem["uri"],
                    "prefLabel": mem["title"],
                }
            )
        return sorted(scheme_list, key=lambda c: c["prefLabel"])
