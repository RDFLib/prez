from typing import List, Dict

class VocPrezSchemeList(object):
    def __init__(self, sparql_response: List) -> None:
        self.members = []
        for result in sparql_response:
            self.members.append({
                "uri": result["cs"]["value"],
                "title": result["label"]["value"],
                "id": result["id"]["value"]
            })
        self.members.sort(key=lambda m: m["title"])