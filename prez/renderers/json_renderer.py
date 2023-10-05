from itertools import chain

from rdflib import Graph, URIRef, RDF, SH, Literal
from rdflib.term import Node

from prez.cache import profiles_graph_cache
from prez.reference_data.prez_ns import ALTREXT


class NotFoundError(Exception):
    ...


def _get_resource_iri(graph: Graph, profile_graph: Graph, profile: URIRef) -> Node:
    target_classes = profile_graph.objects(profile, ALTREXT.constrainsClass)
    for target_class in target_classes:
        iri = graph.value(predicate=RDF.type, object=target_class)
        if iri is not None:
            return iri

    raise NotFoundError(
        f"No resource IRI found based on the constrained classes defined in {profile}."
    )


def _get_child_to_focus_predicates(
    profile_graph: Graph, profile: URIRef, target_class: Node
) -> list[Node]:
    node_shapes = profile_graph.objects(profile, ALTREXT.hasNodeShape)
    child_to_focus_predicates = []
    for node_shape in node_shapes:
        shape_target_class = profile_graph.value(node_shape, SH.targetClass)
        if shape_target_class == target_class:
            child_to_focus_predicate_iris = list(
                profile_graph.objects(node_shape, ALTREXT.childToFocus)
            )

            if child_to_focus_predicate_iris:
                child_to_focus_predicates += child_to_focus_predicate_iris

    return child_to_focus_predicates


def _get_focus_to_parent_predicates(
    profile_graph: Graph, profile: URIRef, target_class: Node
) -> list[Node]:
    node_shapes = profile_graph.objects(profile, ALTREXT.hasNodeShape)
    focus_to_parent = []
    for node_shape in node_shapes:
        shape_target_class = profile_graph.value(node_shape, SH.targetClass)
        if shape_target_class == target_class:
            focus_to_parent_predicate_iris = list(
                profile_graph.objects(node_shape, ALTREXT.focusToParent)
            )

            if focus_to_parent_predicate_iris:
                focus_to_parent += focus_to_parent_predicate_iris

    return focus_to_parent


def _get_focus_to_child_predicates(
    profile_graph: Graph, profile: URIRef, target_class: Node
) -> list[Node]:
    node_shapes = profile_graph.objects(profile, ALTREXT.hasNodeShape)
    focus_to_child = []
    for node_shape in node_shapes:
        shape_target_class = profile_graph.value(node_shape, SH.targetClass)
        if shape_target_class == target_class:
            focus_to_child_predicate_iris = list(
                profile_graph.objects(node_shape, ALTREXT.focusToChild)
            )

            if focus_to_child_predicate_iris:
                focus_to_child += focus_to_child_predicate_iris

    return focus_to_child


def _get_label_predicates(profile_graph: Graph, profile: URIRef) -> list[Node]:
    return list(profile_graph.objects(profile, ALTREXT.hasLabelPredicate))


def _get_label(graph: Graph, iri: Node, predicates: list[Node]) -> Literal | None:
    result = list(
        chain.from_iterable([graph.objects(iri, prop) for prop in predicates])
    )

    for value in result:
        return value

    return None


def _get_relative_predicates(
    profile_graph: Graph, profile: URIRef, target_class: Node
) -> list[Node]:
    node_shapes = profile_graph.objects(profile, ALTREXT.hasNodeShape)
    relative_predicates = []
    for node_shape in node_shapes:
        shape_target_class = profile_graph.value(node_shape, SH.targetClass)
        if shape_target_class == target_class:
            relative_predicate_iris = list(
                profile_graph.objects(node_shape, ALTREXT.relativeProperties)
            )
            if relative_predicate_iris:
                relative_predicates += relative_predicate_iris

    if not relative_predicates:
        raise NotFoundError(
            f"No relative predicates found for class {target_class} in profile {profile}.",
        )

    return relative_predicates


def _get_child_iris(
    graph: Graph,
    iri: Node,
    child_to_focus_predicates: list[Node],
    parent_to_focus_predicates: list[Node],
    focus_to_child_predicates: list[Node],
) -> list[Node]:
    children = []
    for predicate in child_to_focus_predicates:
        child_iris = list(graph.subjects(predicate, iri))
        if child_iris:
            children += child_iris

    for predicate in parent_to_focus_predicates:
        child_iris = list(graph.objects(iri, predicate))
        if child_iris:
            children += child_iris

    for predicate in focus_to_child_predicates:
        child_iris = list(graph.objects(iri, predicate))
        if child_iris:
            children += child_iris

    return children


def create_graph_item(
    iri: str, predicates: list[Node], graph: Graph, context: dict
) -> tuple[dict, dict]:
    item = {"iri": iri}
    for predicate in predicates:
        values = list(graph.objects(URIRef(iri), predicate))
        predicate_localname = str(predicate).split("#")[-1].split("/")[-1]
        item[str(predicate_localname)] = str(values[0]) if values else None
        context[predicate_localname] = str(predicate)

    return item, context


async def render_json_dropdown(
    graph: Graph,
    profile: URIRef,
    selected_class: URIRef,
) -> dict:
    # TODO: This currently doesn't take literals with different lang tags into consideration.
    #       E.g., labels always just return the first value found.
    #       Will need to consider lang tags for literal values of relative predicates, etc.
    profile_graph = profiles_graph_cache.cbd(profile)

    iri = _get_resource_iri(graph, profile_graph, profile)

    child_to_focus_predicates = _get_child_to_focus_predicates(
        profile_graph, profile, selected_class
    )

    focus_to_parent_predicates = _get_focus_to_parent_predicates(
        profile_graph, profile, selected_class
    )

    focus_to_child_predicates = _get_focus_to_child_predicates(
        profile_graph, profile, selected_class
    )

    items = []
    context = {
        "iri": "@id",
    }

    if (
        not child_to_focus_predicates
        and not focus_to_parent_predicates
        and not focus_to_child_predicates
    ):
        # This is a listing view, e.g. /v/vocab.
        node_shape = profile_graph.value(
            predicate=SH.targetClass, object=selected_class
        )
        container_class = profile_graph.value(node_shape, ALTREXT.containerClass)
        if container_class is None:
            raise NotFoundError(
                f"No container class found for resource {iri} in profile {profile}."
            )

        for resource in graph.subjects(RDF.type, container_class):
            relative_predicates = _get_relative_predicates(
                profile_graph, profile, selected_class
            )
            relative_predicates += _get_label_predicates(profile_graph, profile)
            item, context = create_graph_item(
                str(resource), relative_predicates, graph, context
            )
            items.append(item)
    else:
        relative_predicates = _get_relative_predicates(
            profile_graph, profile, selected_class
        )
        relative_predicates += _get_label_predicates(profile_graph, profile)

        child_iris = _get_child_iris(
            graph,
            iri,
            child_to_focus_predicates,
            focus_to_parent_predicates,
            focus_to_child_predicates,
        )
        for child_iri in child_iris:
            item, context = create_graph_item(
                str(child_iri), relative_predicates, graph, context
            )
            items.append(item)

    return {"@context": context, "@graph": sorted(items, key=lambda x: x["iri"])}
