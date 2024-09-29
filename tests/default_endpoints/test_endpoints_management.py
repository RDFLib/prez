from rdflib import Graph

from prez.reference_data.prez_ns import PREZ


def test_annotation_predicates(client):
    r = client.get(f"/")
    response_graph = Graph().parse(data=r.text)
    labelList = list(
        response_graph.objects(
            subject=PREZ["AnnotationPropertyList"], predicate=PREZ.labelList
        )
    )
    assert len(labelList) == 1
    descriptionList = list(
        response_graph.objects(
            subject=PREZ["AnnotationPropertyList"], predicate=PREZ.descriptionList
        )
    )
    assert len(descriptionList) == 1
    provList = list(
        response_graph.objects(
            subject=PREZ["AnnotationPropertyList"], predicate=PREZ.provenanceList
        )
    )
    assert len(provList) == 1
