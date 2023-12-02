from functools import lru_cache
from typing import List

from prez.config import settings
from prez.reference_data.prez_ns import PREZ
from temp.grammar import *


class AnnotationsConstructQuery(ConstructQuery):
    """
    Example query; all queries are of this form:

    CONSTRUCT {
      ?term ?prezAnotProp ?annotation
    }
    WHERE {
      VALUES ?term { <http://www.w3.org/ns/dx/conneg/altr-ext#hasResourceFormat> <http://purl.org/dc/terms/description>  }
      VALUES (?prop ?prezAnotProp ) {(<http://www.w3.org/2004/02/skos/core#prefLabel> <https://prez.dev/label> )
        (<http://purl.org/dc/terms/title> <https://prez.dev/label> )
        (<http://www.w3.org/2000/01/rdf-schema#label> <https://prez.dev/label> )
        (<http://www.w3.org/2004/02/skos/core#definition> <https://prez.dev/description> )
        (<http://purl.org/dc/terms/description> <https://prez.dev/description> )
        (<http://purl.org/dc/terms/provenance> <https://prez.dev/provenance> )
      }?term ?prop ?annotation
      FILTER (LANG(?annotation) IN ("en", "") || isURI(?annotation))
    }
    """
    def __init__(self, terms: List[IRI]):
        # create terms VALUES clause
        # e.g. VALUES ?term { ... }
        term_var = Var(value="term")
        terms_gpnt = GraphPatternNotTriples(
            content=InlineData(
                data_block=DataBlock(
                    block=InlineDataOneVar(
                        variable=term_var,
                        datablockvalues=[DataBlockValue(value=term) for term in terms],
                    )
                )
            )
        )

        # create prez annotation to annotation properties VALUES clause
        # e.g. VALUES ( ?prop ?prezAnotProp ) { (...) (...) }

        prez_anot_var = Var(value="prezAnotProp")
        prop_var = Var(value="prop")
        all_annotation_tuples = self.get_prez_annotation_tuples()
        props_gpnt = GraphPatternNotTriples(
            content=InlineData(
                data_block=DataBlock(
                    block=InlineDataFull(
                        vars=[prop_var, prez_anot_var],
                        datablocks=[
                            [
                                DataBlockValue(value=IRI(value=prop)),
                                DataBlockValue(value=IRI(value=prez_prop)),
                            ]
                            for prop, prez_prop in all_annotation_tuples
                        ],
                    )
                )
            )
        )

        # create a language filter
        # e.g. FILTER (LANG(?annotation) IN ("en", ""))
        anot_var = Var(value="annotation")
        lang_filter_gpnt = GraphPatternNotTriples(
            content=Filter(
                constraint=Constraint(
                    content=BrackettedExpression(
                        expression=Expression.create_in_expression(
                            left_primary_expression=PrimaryExpression(
                                content=BuiltInCall.create_with_one_expr(
                                    function_name="LANG",
                                    expression=PrimaryExpression(content=anot_var),
                                )
                            ),
                            operator="IN",
                            right_primary_expressions=[
                                PrimaryExpression(
                                    content=RDFLiteral(value=settings.default_language)
                                ),
                                PrimaryExpression(content=RDFLiteral(value="")),
                            ],
                        )
                    )
                )
            )
        )
        # || isURI(?annotation)
        isuri_expr = Expression.from_primary_expression(
            primary_expression=PrimaryExpression(
                content=BuiltInCall.create_with_one_expr(
                    function_name="isURI",
                    expression=PrimaryExpression(content=anot_var),
                )
            )
        )
        lang_filter_gpnt.content.constraint.content.expression.conditional_or_expression.conditional_and_expressions.append(
            isuri_expr
        )

        # create the main query components - construct and where clauses
        construct_template = ConstructTemplate(
            construct_triples=ConstructTriples.from_tss_list(
                [
                    TriplesSameSubject.from_spo(
                        subject=term_var,
                        predicate=prez_anot_var,
                        object=anot_var,
                    )
                ]
            )
        )
        where_clause = WhereClause(
            group_graph_pattern=GroupGraphPattern(
                content=GroupGraphPatternSub(
                    graph_patterns_or_triples_blocks=[
                        terms_gpnt,  # VALUES ?term { ... }
                        props_gpnt,  # VALUES ( ?prop ?prezAnotProp ) { (...) (...) }
                        TriplesBlock.from_tssp_list(
                            [
                                TriplesSameSubjectPath.from_spo(  # ?term ?prop ?annotation
                                    subject=term_var,
                                    predicate=prop_var,
                                    object=anot_var,
                                )
                            ]
                        ),
                        lang_filter_gpnt,  # FILTER (LANG(?annotation) IN ("en", ""))
                    ]
                )
            )
        )
        super().__init__(
            construct_template=construct_template,
            where_clause=where_clause,
            solution_modifier=SolutionModifier(),
        )

    @staticmethod
    @lru_cache(maxsize=None)
    def get_prez_annotation_tuples():
        label_tuples = [
            (label_prop, PREZ.label) for label_prop in settings.label_predicates
        ]
        description_tuples = [
            (description_prop, PREZ.description)
            for description_prop in settings.description_predicates
        ]
        provenance_tuples = [
            (provenance_prop, PREZ.provenance)
            for provenance_prop in settings.provenance_predicates
        ]
        # other is different - the ORIGINAL property is returned as the predicate; not prez:x
        other_tuples = [
            (other_prop, other_prop) for other_prop in settings.other_predicates
        ]
        all_tuples = (
            label_tuples + description_tuples + provenance_tuples + other_tuples
        )
        return all_tuples
