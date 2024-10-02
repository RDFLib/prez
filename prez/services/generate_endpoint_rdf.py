import json
from pathlib import Path

from rdflib import Graph, Namespace, RDF, Literal, RDFS, SH, URIRef, BNode
from rdflib.collection import Collection

from prez.reference_data.prez_ns import ONT

EX = Namespace("http://example.org/")
TEMP = Namespace("http://temporary/")


def add_endpoint(g, endpoint_type, name, api_path, i, route_num):
    hl = (i + 2) // 2
    endpoint_uri = EX[f"{name}-{endpoint_type}"]
    title_cased = f"{name.title()} {endpoint_type.title()}"

    g.add((endpoint_uri, RDF.type, ONT[f"{endpoint_type.title()}Endpoint"]))
    g.add((endpoint_uri, RDF.type, ONT.DynamicEndpoint))
    g.add((endpoint_uri, RDFS.label, Literal(title_cased)))
    g.add((endpoint_uri, ONT.apiPath, Literal(api_path)))
    g.add((endpoint_uri, TEMP.route_num, Literal(route_num)))
    g.add((endpoint_uri, TEMP.hierarchy_level, Literal(hl)))


def create_endpoint_metadata(data, g):
    for route_num, route in enumerate(data['routes']):
        fullApiPath = route["fullApiPath"]
        components = fullApiPath.split("/")[1:]

        for i in range(len(components)):
            name = components[i] if i % 2 == 0 else components[i - 1]
            api_path = f"/{'/'.join(components[:i + 1])}"
            shapes_name = name.title()

            if i % 2 == 0:
                add_endpoint(g, "listing", name, api_path, i, route_num)
            else:
                add_endpoint(g, "object", name, api_path, i, route_num)


def process_relations(data):
    levels_list = []
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
        levels_list.append(levels)
    return levels_list


def process_levels(levels: dict, g: Graph, route_num: int, shape_names: set):
    unique_suffix = 1
    for i, (k, v) in enumerate(levels.items()):
        proposed_shape_uri = EX[f"shape-R{route_num}-HL{k[2][1]}"]
        if proposed_shape_uri not in shape_names:
            shape_uri = proposed_shape_uri
            shape_names.add(shape_uri)
        else:
            shape_uri = EX[f"shape-R{route_num}-HL{k[2][1]}-{unique_suffix}"]
            shape_names.add(shape_uri)
            unique_suffix += 1
        g.add((shape_uri, RDF.type, SH.NodeShape))
        g.add((shape_uri, TEMP.route_num, Literal(route_num)))
        g.add((shape_uri, TEMP.hierarchy_level, Literal(k[2][1])))
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
            if k[0][1] == "outbound":
                path_bn = BNode()
                g.add((prop_bn, SH.path, path_bn))
                g.add((path_bn, SH.inversePath, URIRef(k[3][1])))  # relation
            else:
                g.add((prop_bn, SH.path, URIRef(k[3][1])))
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


def add_inverse_for_top_level(data):
    """
    the RDF relation between the first and second endpoints is reused in reverse so endpoints can be defined based on
    their relation to each other rather than needing to say put the class of objects at the top level in some arbitrary
    collection
    """
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
    for s_s in shapes_g.subjects(predicate=RDF.type, object=SH.NodeShape):
        s_route_num = shapes_g.value(s_s, TEMP.route_num)
        s_hl = shapes_g.value(s_s, TEMP.hierarchy_level)
        for ep_s, _, _ in endpoints_g.triples_choices((None, RDF.type, [ONT.ListingEndpoint, ONT.ObjectEndpoint])):
            ep_route_num = endpoints_g.value(ep_s, TEMP.route_num)
            ep_hl = endpoints_g.value(ep_s, TEMP.hierarchy_level)
            if (s_route_num == ep_route_num) and (s_hl == ep_hl):
                links_g.add((ep_s, ONT.relevantShapes, s_s))
                # endpoints_g.remove((ep_s, TEMP.relevantShapes, o2))


def cleanup_temp_preds(g):
    for s, p, o in g.triples((None, TEMP.route_num, None)):
        g.remove((s, p, o))
    for s, p, o in g.triples((None, TEMP.hierarchy_level, None)):
        g.remove((s, p, o))


def create_endpoint_rdf(endpoint_json: dict):
    data = add_inverse_for_top_level(endpoint_json)
    g = Graph()
    create_endpoint_metadata(data, g)
    levels_list = process_relations(data)
    shape_names = set()
    for route_num, levels in enumerate(levels_list):
        g2 = Graph()
        process_levels(levels, g2, route_num, shape_names)
        g3 = Graph()
        link_endpoints_shapes(g, g2, g3)
        g += g2
        g += g3
    cleanup_temp_preds(g)
    g.bind("ont", ONT)
    g.bind("ex", EX)
    file_path = Path(
        __file__).parent.parent / "reference_data" / "endpoints" / "data_endpoints_custom" / "custom_endpoints.ttl"
    g.serialize(destination=file_path, format="turtle")
