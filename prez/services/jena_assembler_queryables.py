import logging

from rdflib import DCTERMS, RDF, SH, XSD, BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection

from prez.reference_data.prez_ns import ONT

log = logging.getLogger(__name__)

FUSEKI = Namespace("http://jena.apache.org/fuseki#")
GEOSPARQL = Namespace("http://jena.apache.org/geosparql#")
TEXT = Namespace("http://jena.apache.org/text#")
IDX = Namespace("urn:jena:lucene:index#")
CQL = Namespace("http://www.opengis.net/doc/IS/cql2/1.0/")


class JenaAssemblerTransformError(ValueError):
    pass


FIELD_TYPE_TO_DATATYPE = {
    IDX.KeywordField: XSD.string,
    IDX.TextField: XSD.string,
    IDX.IntField: XSD.integer,
    IDX.LongField: XSD.long,
    IDX.DoubleField: XSD.double,
}

FIELD_TYPE_TO_LABEL = {
    IDX.KeywordField: "keyword",
    IDX.TextField: "text",
    IDX.IntField: "int",
    IDX.LongField: "long",
    IDX.DoubleField: "double",
    IDX.LatLonField: "latlon",
}

UNSUPPORTED_FIELD_TYPES = {IDX.LatLonField}


def transform_jena_assembler_to_queryables(assembler_graph: Graph) -> Graph:
    service_node = _find_single_fuseki_service(assembler_graph)
    dataset_node = assembler_graph.value(service_node, FUSEKI.dataset)
    if dataset_node is None:
        raise JenaAssemblerTransformError(
            "The assembler's fuseki:Service is missing fuseki:dataset."
        )

    text_dataset = _resolve_text_dataset(assembler_graph, dataset_node, seen=set())
    index_nodes = _resolve_text_indexes(assembler_graph, text_dataset)
    if not index_nodes:
        raise JenaAssemblerTransformError(
            "The assembler's text dataset is missing required text:indexes."
        )

    shape_nodes: list[URIRef | BNode] = []
    for index_node in index_nodes:
        shapes_list_node = assembler_graph.value(index_node, TEXT.shapes)
        if shapes_list_node is None:
            raise JenaAssemblerTransformError(
                f"Index {index_node} is missing text:shapes."
            )
        shape_nodes.extend(list(Collection(assembler_graph, shapes_list_node)))
    if not shape_nodes:
        raise JenaAssemblerTransformError(
            "The assembler's configured indexes have no shapes in text:shapes."
        )

    output_graph = Graph()
    output_graph.bind("cql", CQL)
    output_graph.bind("dcterms", DCTERMS)
    output_graph.bind("sh", SH)
    output_graph.bind("prez", ONT)
    output_graph.bind("xsd", XSD)

    transformed_fields: set[URIRef] = set()
    for shape_node in shape_nodes:
        for field_node in assembler_graph.objects(shape_node, SH.property):
            transformed_field = _transform_field(
                assembler_graph,
                field_node,
                output_graph,
            )
            if transformed_field is not None:
                transformed_fields.add(transformed_field)

    if not transformed_fields:
        raise JenaAssemblerTransformError(
            "The assembler did not produce any supported queryable fields."
        )
    return output_graph


def _find_single_fuseki_service(graph: Graph) -> URIRef | BNode:
    services = list(graph.subjects(RDF.type, FUSEKI.Service))
    if not services:
        raise JenaAssemblerTransformError(
            "No fuseki:Service was found in the assembler."
        )
    if len(services) > 1:
        raise JenaAssemblerTransformError(
            "Multiple fuseki:Service resources were found in the assembler. "
            "Prez now assumes exactly one service per assembler file."
        )
    return services[0]


def _resolve_text_dataset(
    graph: Graph, dataset_node: URIRef | BNode, seen: set[URIRef | BNode]
) -> URIRef | BNode:
    if dataset_node in seen:
        raise JenaAssemblerTransformError(
            f"Cycle detected while resolving text dataset from {dataset_node}."
        )
    seen.add(dataset_node)

    if (dataset_node, RDF.type, TEXT.TextDataset) in graph or graph.value(
        dataset_node, TEXT["index"]
    ):
        return dataset_node

    for predicate in (GEOSPARQL.dataset,):
        nested_dataset = graph.value(dataset_node, predicate)
        if nested_dataset is not None:
            return _resolve_text_dataset(graph, nested_dataset, seen)

    raise JenaAssemblerTransformError(
        f"Could not resolve a text:TextDataset from dataset node {dataset_node}."
    )


def _resolve_text_indexes(
    graph: Graph, text_dataset: URIRef | BNode
) -> list[URIRef | BNode]:
    direct_index = graph.value(text_dataset, TEXT["index"])
    indexes_list = graph.value(text_dataset, TEXT.indexes)
    if direct_index is not None and indexes_list is not None:
        raise JenaAssemblerTransformError(
            "Assembler text dataset must not define both text:index and text:indexes."
        )

    if indexes_list is not None:
        if (indexes_list, RDF.first, None) in graph:
            return list(Collection(graph, indexes_list))
        return [indexes_list]

    if direct_index is not None:
        return [direct_index]

    if indexes_list is None:
        return []
    return []


def _transform_field(
    assembler_graph: Graph, field_node: URIRef | BNode, output_graph: Graph
) -> URIRef | None:
    # Support new occurrence model: blank node with idx:field -> canonical field resource.
    # sh:path lives on the occurrence; all other metadata lives on the canonical resource.
    canonical_ref = assembler_graph.value(field_node, IDX.field)
    if canonical_ref is not None:
        meta_node = canonical_ref
        path_node = assembler_graph.value(field_node, SH.path)
    else:
        meta_node = field_node
        path_node = assembler_graph.value(field_node, SH.path)

    field_name = assembler_graph.value(meta_node, IDX.fieldName)
    if field_name is None:
        raise JenaAssemblerTransformError(
            f"Field {field_node} is missing required idx:fieldName."
        )
    if path_node is None:
        raise JenaAssemblerTransformError(
            f"Field {field_node} is missing required sh:path."
        )

    field_type = assembler_graph.value(meta_node, IDX.fieldType) or IDX.TextField
    if field_type in UNSUPPORTED_FIELD_TYPES:
        log.warning(
            "Skipping unsupported Lucene field type %s for %s", field_type, field_node
        )
        return None

    datatype = FIELD_TYPE_TO_DATATYPE.get(field_type)
    if datatype is None:
        log.warning(
            "Skipping unmapped Lucene field type %s for %s", field_type, field_node
        )
        return None

    field_uri = _field_identity(meta_node, str(field_name))
    if (field_uri, RDF.type, CQL.Queryable) in output_graph:
        return field_uri

    output_graph.add((field_uri, RDF.type, CQL.Queryable))
    output_graph.add((field_uri, RDF.type, SH.PropertyShape))
    output_graph.add((field_uri, DCTERMS.identifier, Literal(str(field_uri))))
    output_graph.add((field_uri, SH.name, Literal(str(field_name))))
    output_graph.add(
        (
            field_uri,
            SH.description,
            Literal(f"Lucene indexed field {field_name}"),
        )
    )
    output_graph.add((field_uri, SH.datatype, datatype))
    output_graph.add((field_uri, SH.path, path_node))
    output_graph.add(
        (field_uri, ONT.luceneFieldType, Literal(FIELD_TYPE_TO_LABEL[field_type]))
    )
    output_graph.add(
        (
            field_uri,
            ONT.stored,
            Literal(_field_bool(assembler_graph, meta_node, IDX.stored, True)),
        )
    )
    output_graph.add(
        (
            field_uri,
            ONT.indexed,
            Literal(_field_bool(assembler_graph, meta_node, IDX.indexed, True)),
        )
    )
    output_graph.add(
        (
            field_uri,
            ONT.facetable,
            Literal(_field_bool(assembler_graph, meta_node, IDX.facetable, False)),
        )
    )
    output_graph.add(
        (
            field_uri,
            ONT.sortable,
            Literal(_field_bool(assembler_graph, meta_node, IDX.sortable, False)),
        )
    )
    output_graph.add(
        (
            field_uri,
            ONT.multiValued,
            Literal(_field_bool(assembler_graph, meta_node, IDX.multiValued, False)),
        )
    )
    output_graph.add(
        (
            field_uri,
            ONT.defaultSearch,
            Literal(_field_bool(assembler_graph, meta_node, IDX.defaultSearch, False)),
        )
    )
    return field_uri


def _field_identity(field_node: URIRef | BNode, field_name: str) -> URIRef:
    if isinstance(field_node, URIRef):
        return field_node
    return URIRef(f"urn:jena:lucene:field#{field_name}")


def _literal_truthy(value) -> bool:
    if value is None:
        return False
    if isinstance(value, Literal):
        python_value = value.toPython()
        if isinstance(python_value, bool):
            return python_value
        return str(python_value).lower() in {"true", "1"}
    return str(value).lower() in {"true", "1"}


def _field_bool(
    assembler_graph: Graph,
    field_node: URIRef | BNode,
    predicate: URIRef,
    default: bool,
) -> bool:
    value = assembler_graph.value(field_node, predicate)
    if value is None:
        return default
    return _literal_truthy(value)
