from functools import lru_cache
from typing import List

from sparql_grammar import (
    IRI,
    BuiltInCall,
    ConstructQuery,
    ConstructTemplate,
    ConstructTriples,
    Expression,
    Filter,
    GroupGraphPattern,
    GroupGraphPatternSub,
    InlineData,
    InlineDataFull,
    InlineDataOneVar,
    RDFLiteral,
    SolutionModifier,
    TriplesBlock,
    TriplesSameSubject,
    TriplesSameSubjectPath,
    Var,
    WhereClause,
)

from prez.config import settings
from prez.reference_data.prez_ns import PREZ


class AnnotationsConstructQuery(ConstructQuery):
    """
    Example query; all queries are of this form:

    CONSTRUCT {
      ?term ?prezAnotProp ?annotation
    }
    WHERE {
      VALUES ?term { <http://www.w3.org/ns/dx/connegp/altr-ext#hasResourceFormat> <http://purl.org/dc/terms/description>  }
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
        # VALUES ?term { ... }
        term_var = Var(value="term")
        terms_values = InlineData(InlineDataOneVar(term_var, list(terms)))

        # VALUES ( ?prop ?prezAnotProp ) { (...) (...) }
        prez_anot_var = Var(value="prezAnotProp")
        prop_var = Var(value="prop")
        props_values = InlineData(
            InlineDataFull(
                [prop_var, prez_anot_var],
                [
                    [IRI(value=prop), IRI(value=prez_prop)]
                    for prop, prez_prop in self.get_prez_annotation_tuples()
                ],
            )
        )

        # FILTER (LANG(?annotation) IN ("en", "") || isURI(?annotation))
        anot_var = Var(value="annotation")
        lang_filter = Filter(
            Expression.any_of(
                Expression.in_(
                    BuiltInCall.create("LANG", anot_var),
                    [RDFLiteral(value=settings.default_language), RDFLiteral(value="")],
                ),
                BuiltInCall.create("isURI", anot_var),
            )
        )

        construct_template = ConstructTemplate(
            ConstructTriples(
                [TriplesSameSubject.from_spo(term_var, prez_anot_var, anot_var)]
            )
        )
        where_clause = WhereClause(
            GroupGraphPattern(
                GroupGraphPatternSub(
                    [
                        terms_values,  # VALUES ?term { ... }
                        props_values,  # VALUES ( ?prop ?prezAnotProp ) { (...) (...) }
                        TriplesBlock(  # ?term ?prop ?annotation
                            [
                                TriplesSameSubjectPath.from_spo(
                                    term_var, prop_var, anot_var
                                )
                            ]
                        ),
                        lang_filter,  # FILTER (LANG(?annotation) IN ("en", "") || isURI(?annotation))
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
        value_tuples = [
            (value_prop, PREZ.value) for value_prop in settings.value_predicates
        ]
        # other is different - the ORIGINAL property is returned as the predicate; not prez:x
        other_tuples = [
            (other_prop, other_prop) for other_prop in settings.other_predicates
        ]
        all_tuples = (
            label_tuples
            + description_tuples
            + provenance_tuples
            + value_tuples
            + other_tuples
        )
        return all_tuples
