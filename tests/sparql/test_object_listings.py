from rdflib.namespace import PROV

from prez.sparql.objects_listings import generate_sequence_construct


def test_generate_sequence_construct() -> None:
    sequence_construct, sequence_construct_where = generate_sequence_construct(
        [
            [PROV.qualifiedDerivation, PROV.hadRole],
            [PROV.qualifiedDerivation, PROV.entity],
        ],
        "?top_level_item",
    )

    expected_sequence_construct = """\t?top_level_item <http://www.w3.org/ns/prov#qualifiedDerivation> ?seq_o1_0 .
\t?seq_o1_0 <http://www.w3.org/ns/prov#hadRole> ?seq_o2_0 .\t?top_level_item <http://www.w3.org/ns/prov#qualifiedDerivation> ?seq_o1_1 .
\t?seq_o1_1 <http://www.w3.org/ns/prov#entity> ?seq_o2_1 ."""

    assert sequence_construct == expected_sequence_construct

    expected_sequence_construct_where = """\
OPTIONAL {
\t?top_level_item <http://www.w3.org/ns/prov#qualifiedDerivation> ?seq_o1_0 .
\t?seq_o1_0 <http://www.w3.org/ns/prov#hadRole> ?seq_o2_0 .
}
OPTIONAL {
\t?top_level_item <http://www.w3.org/ns/prov#qualifiedDerivation> ?seq_o1_1 .
\t?seq_o1_1 <http://www.w3.org/ns/prov#entity> ?seq_o2_1 .
}
"""

    assert sequence_construct_where == expected_sequence_construct_where
