import json
from pathlib import Path

from rdflib import Graph, Namespace, RDF, Literal, RDFS, SH, URIRef, BNode
from rdflib.collection import Collection

from prez.reference_data.prez_ns import ONT



EX = Namespace("http://example.org/")
TEMP = Namespace("http://temporary/")


def add_endpoint(g, endpoint_type, name, api_path, shapes_name, i):
    hl = (i + 2) // 2
    endpoint_uri = EX[f"{name}-{endpoint_type}"]
    title_cased = f"{name.title()} {endpoint_type.title()}"

    g.add((endpoint_uri, RDF.type, ONT[f"{endpoint_type.title()}Endpoint"]))
    g.add((endpoint_uri, RDFS.label, Literal(title_cased)))
    g.add((endpoint_uri, ONT.apiPath, Literal(api_path)))
    g.add((endpoint_uri, TEMP.relevantShapes, Literal(hl)))


def create_endpoint_metadata(data, g):
    for route in data['routes']:
        fullApiPath = route["fullApiPath"]
        components = fullApiPath.split("/")[1:]

        for i in range(len(components)):
            name = components[i] if i % 2 == 0 else components[i - 1]
            api_path = f"/{'/'.join(components[:i + 1])}"
            shapes_name = name.title()

            if i % 2 == 0:
                add_endpoint(g, "listing", name, api_path, shapes_name, i)
            else:
                add_endpoint(g, "object", name, api_path, shapes_name, i)

def process_relations(data):
    for route in data['routes']:
        levels = {}
        for hier_rel in route["hierarchiesRelations"]:
            hierarchy_dict = {h["hierarchyLevel"]: h for h in hier_rel["hierarchy"]}
            for relation in hier_rel["relations"]:
                rel_key = tuple(sorted(relation.items()))  # Sort items before creating tuple
                level_from = relation["levelFrom"]
                level_to = relation["levelTo"]
                klass_from = hierarchy_dict[level_from]
                klass_to = hierarchy_dict[level_to]
                klass_from_key = tuple(sorted(klass_from.items()))  # Sort items before creating tuple
                klass_to_key = tuple(sorted(klass_to.items()))  # Sort items before creating tuple

                if rel_key in levels:
                    levels[rel_key]["klasses_from"].add(klass_from_key)
                    levels[rel_key]["klasses_to"].add(klass_to_key)
                else:
                    levels[rel_key] = {
                        "klasses_from": {klass_from_key},
                        "klasses_to": {klass_to_key}
                    }
    return levels


def process_levels(levels: dict, g: Graph):
    unique_suffix = 1
    shape_names = set()
    for i, (k, v) in enumerate(levels.items()):
        proposed_shape_uri = EX[f"shape-{k[2][1]}"]
        if proposed_shape_uri not in shape_names:
            shape_names.add(proposed_shape_uri)
            shape_uri = proposed_shape_uri
        else:
            shape_uri = EX[f"shape-{k[2][1]}-{unique_suffix}"]
            unique_suffix += 1
        g.add((shape_uri, RDF.type, SH.NodeShape))
        g.add((shape_uri, ONT.hierarchyLevel, Literal(k[2][1])))  # hierarchyLevel = levelTo
        klasses_to = []
        klasses_from = []
        for tup in v["klasses_to"]:
            klasses_to.append(URIRef(tup[2][1]))
        for klass in klasses_to:
            g.add((shape_uri, SH.targetClass, klass))
        for tup in v["klasses_from"]:
            klasses_from.append(URIRef(tup[2][1]))
        prop_bn = BNode()
        g.add((shape_uri, SH.property, prop_bn))
        if k[1][1] > k[2][1]:  # levelFrom > levelTo - top level endpoint only
            klass_bns = []
            or_bn = BNode()
            g.add((prop_bn, SH["or"], or_bn))
            for klass in klasses_from:
                klass_bn = BNode()
                g.add((klass_bn, SH["class"], klass))
                klass_bns.append(klass_bn)
            Collection(g, or_bn, klass_bns)
            g.add((prop_bn, SH["path"], URIRef(k[3][1])))
        elif k[1][1] < k[2][1]:  # levelFrom < levelTo
            if k[0][1] == "outbound":
                path_bn = BNode()
                g.add((prop_bn, SH.path, path_bn))
                g.add((path_bn, SH.inversePath, URIRef(k[3][1])))  # relation
            else:
                g.add((prop_bn, SH.path, URIRef(k[3][1])))
            g.add((prop_bn, SH["class"], klasses_from[0]))  # klass_from
        for tup in v["klasses_to"]:
            if tup[1][1] > 2:  # hierarchy level > 2
                klass_to_match = klasses_from[0]
                for rel, klass_info in levels.items():
                    for n in klass_info["klasses_to"]:
                        if klass_to_match == URIRef(n[2][1]):
                            second_rel = rel
                            second_klass = klass_info
                            break
                second_prop_bn = BNode()
                second_path_bn = BNode()
                g.add((shape_uri, SH.property, second_prop_bn))
                g.add((second_prop_bn, SH.path, second_path_bn))
                list_comps = []
                if k[0][1] == "outbound":
                    inverse_bn = BNode()
                    g.add((inverse_bn, SH.inversePath, URIRef(k[3][1])))  # relation
                    list_comps.append(inverse_bn)
                else:
                    list_comps.append(URIRef(k[3][1]))
                if second_rel[0][1] == "outbound":
                    inverse_bn = BNode()
                    g.add((inverse_bn, SH.inversePath, URIRef(second_rel[3][1])))  # relation
                    list_comps.append(inverse_bn)
                else:
                    list_comps.append(URIRef(second_rel[3][1]))
                Collection(g, second_path_bn, list_comps)
                for tup in second_klass["klasses_from"]:
                    g.add((second_prop_bn, SH["class"], URIRef(tup[2][1])))



def read_json(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
        for route in data['routes']:
            for hr in route["hierarchiesRelations"]:
                for relation in hr["relations"]:
                    if relation["levelFrom"] == 1 and relation["levelTo"] == 2:
                        inverted_relation = {
                            "levelFrom": 2,
                            "levelTo": 1,
                            "rdfPredicate": relation["rdfPredicate"],
                            "direction": "inbound" if relation["direction"] == "outbound" else "outbound"
                        }
                        hr["relations"].append(inverted_relation)
        return data


def link_endpoints_shapes(endpoints_g, shapes_g, links_g):
    for s, p, o in shapes_g.triples((None, ONT.hierarchyLevel, None)):
        for s2, p2, o2 in endpoints_g.triples((None, TEMP.relevantShapes, None)):
            if o == o2:
                links_g.add((s2, ONT.relevantShapes, s))
                endpoints_g.remove((s2, TEMP.relevantShapes, o2))


if __name__ == "__main__":
    file_path = Path(__file__).parent.parent.parent / "test_data" / "custom_endpoints.json"
    data = read_json(file_path)
    g = Graph()
    create_endpoint_metadata(data, g)
    levels = process_relations(data)
    g2 = Graph()
    results = process_levels(levels, g2)
    g3 = Graph()
    link_endpoints_shapes(g, g2, g3)
    complete = g + g2 + g3
    complete.bind("ont", ONT)
    complete.bind("ex", EX)
    file_path = Path(__file__).parent.parent / "reference_data" / "endpoints" / "data_endpoints_custom" / "custom_endpoints.ttl"
    complete.serialize(destination=file_path, format="turtle")
