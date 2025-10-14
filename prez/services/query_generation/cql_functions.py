from sparql_grammar_pydantic import (
    IRI,
    GroupGraphPatternSub,
    TriplesBlock,
    TriplesSameSubjectPath,
    Var,
    VarOrTerm,
    GraphTerm,
)
from rdflib import Namespace
from rdflib.namespace import SOSA, RDF, SDO, PROV

TERN = Namespace("https://w3id.org/tern/ontologies/tern/")

from prez.services.query_generation.grammar_helpers import (
    convert_value_to_rdf_term,
    create_values_constraint,
    create_tssp_alt_or_alt_inverse,
    create_tssp_sequence,
    create_union_gpnt_from_tssps,
)

REGISTERED_CQL_FUNCTIONS = [
    "FOIObservationFilterDirect",
    "FOIObservationFilterSequence",
    "hasObservation",
    "hasAttribute",
    "hasAdditional",
    "qualifiedAttribution",
]


def handle_custom_functions(
    operator,
    args,
    existing_ggps: GroupGraphPatternSub | None = None,
    suffix: str = "",
):
    ggps = existing_ggps if existing_ggps is not None else GroupGraphPatternSub()
    focus_node_vot = VarOrTerm(varorterm=Var(value="focus_node"))
    if operator in [
        "FOIObservationFilterDirect",
        "FOIObservationFilterSequence",
        "hasObservation",
    ]:
        obj = VarOrTerm(varorterm=Var(value=f"observation{suffix}"))
        foi_to_obs_tssp = create_tssp_alt_or_alt_inverse(
            subject=focus_node_vot,
            first_pred=IRI(value=str(SOSA.isFeatureOfInterestOf)),
            second_pred=IRI(value=str(SOSA.hasFeatureOfInterest)),
            obj=obj,
            inverse_second_prop=True,
        )
        if operator in ["FOIObservationFilterDirect", "FOIObservationFilterSequence"]:
            filter_1_object = convert_value_to_rdf_term(args[1])
            obs_filter_1 = TriplesSameSubjectPath.from_spo(
                subject=obj.varorterm,
                predicate=IRI(value=args[0]),
                object=filter_1_object,
            )
            filter_2_object = convert_value_to_rdf_term(args[3])
            obs_filter_2 = None
            if operator == "FOIObservationFilterDirect":
                obs_filter_2 = TriplesSameSubjectPath.from_spo(
                    subject=obj.varorterm,
                    predicate=IRI(value=args[2]),
                    object=filter_2_object,
                )
            elif operator == "FOIObservationFilterSequence":
                obs_filter_2 = create_tssp_sequence(
                    subject=obj,
                    pred_1=IRI(value=args[2]),
                    pred_2=IRI(value=args[3]),
                    obj=VarOrTerm(varorterm=GraphTerm(content=filter_2_object)),
                )
            ggps.add_pattern(
                TriplesBlock.from_tssp_list(
                    [obs_filter_2, obs_filter_1, foi_to_obs_tssp]
                )
            )
        elif (
            operator == "hasObservation"
        ):  # https://github.com/RDFLib/prez/issues/378#issuecomment-3269086241
            """
            {
                ?focus sosa:isFeatureOfInterestOf/^sosa:hasFeatureOfInterest ?obs .
                ?obs sosa:observedProperty $arg1 .
                { ?obs sosa:hasSimpleResult $arg2 }
                UNION
                { ?obs sosa:hasResult $arg2 }
                UNION
                { ?obs sosa:hasResult/rdf:value $arg2}
                VALUES $arg2 { "val1" }
                VALUES $arg1 { <https://example.org/vocab/prop1> }
            }"""
            obs_prop_var = Var(value=f"obs_prop{suffix}")
            result_var = Var(value=f"result{suffix}")
            obs_filter_1 = TriplesSameSubjectPath.from_spo(
                subject=obj.varorterm,  # ?observation
                predicate=IRI(value=str(SOSA.observedProperty)),
                object=obs_prop_var,  # ?obs_prop
            )
            arg_1_values_gpnt = create_values_constraint(
                obs_prop_var, args[0]
            )  # args[0] is array for ?obs_prop
            arg_2_values_gpnt = create_values_constraint(
                result_var, args[1]
            )  # args[1] is array for ?result
            tssp_1 = TriplesSameSubjectPath.from_spo(
                subject=obj.varorterm,
                predicate=IRI(value=str(SOSA.hasSimpleResult)),
                object=result_var,
            )
            tssp_2 = TriplesSameSubjectPath.from_spo(
                subject=obj.varorterm,
                predicate=IRI(value=str(SOSA.hasResult)),
                object=result_var,
            )
            tssp_3 = create_tssp_sequence(
                subject=obj,
                pred_1=IRI(value=str(SOSA.hasResult)),
                pred_2=IRI(value=str(RDF.value)),
                obj=VarOrTerm(varorterm=result_var),
            )
            union_gpnt = create_union_gpnt_from_tssps([tssp_1, tssp_2, tssp_3])
            ggps.add_pattern(
                TriplesBlock.from_tssp_list([obs_filter_1, foi_to_obs_tssp])
            )
            ggps.add_pattern(union_gpnt)
            ggps.add_pattern(arg_1_values_gpnt)
            ggps.add_pattern(arg_2_values_gpnt)
    elif operator in ["hasAttribute"]:
        """
        {
            ?focus tern:hasAttribute ?attr .
            ?attr tern:attribute $arg1 .
            { ?attr tern:hasSimpleValue $arg2 }
            UNION
            { ?attr tern:hasValue $arg2 }
            UNION
            { ?attr tern:hasValue/rdf:value $arg2}
            VALUES $arg2 { "val1" }
            VALUES $arg1 { <https://example.org/vocab/attr1> }
        }
        """
        attr_bn_var = Var(value=f"attr_bn_var{suffix}")
        attr_name_var = Var(value=f"attr_name_var{suffix}")
        result_var = Var(value=f"result{suffix}")
        focus_to_attr_tssp = TriplesSameSubjectPath.from_spo(
            subject=focus_node_vot.varorterm,
            predicate=IRI(value=str(TERN.hasAttribute)),
            object=attr_bn_var,
        )
        attr_bn_to_attr_var_tssp = TriplesSameSubjectPath.from_spo(
            subject=attr_bn_var,
            predicate=IRI(value=str(TERN.attribute)),
            object=attr_name_var,
        )
        tssp_1 = TriplesSameSubjectPath.from_spo(
            subject=attr_bn_var,
            predicate=IRI(value=str(TERN.hasSimpleValue)),
            object=result_var,
        )
        tssp_2 = TriplesSameSubjectPath.from_spo(
            subject=attr_bn_var,
            predicate=IRI(value=str(TERN.hasValue)),
            object=result_var,
        )
        tssp_3 = create_tssp_sequence(
            subject=VarOrTerm(varorterm=attr_bn_var),
            pred_1=IRI(value=str(TERN.hasValue)),
            pred_2=IRI(value=str(RDF.value)),
            obj=VarOrTerm(varorterm=result_var),
        )
        union_gpnt = create_union_gpnt_from_tssps([tssp_1, tssp_2, tssp_3])
        arg_1_values_gpnt = create_values_constraint(attr_name_var, args[0])
        arg_2_values_gpnt = create_values_constraint(result_var, args[1])
        ggps.add_pattern(
            TriplesBlock.from_tssp_list([attr_bn_to_attr_var_tssp, focus_to_attr_tssp])
        )
        ggps.add_pattern(union_gpnt)
        ggps.add_pattern(arg_1_values_gpnt)
        ggps.add_pattern(arg_2_values_gpnt)
    elif operator in ["hasAdditional"]:
        """
        {
            ?focus schema:additionalProperty ?aprop .
            ?aprop schema:propertyID|schema:name $arg1 .
            { ?aprop schema:value $arg2 }
            UNION
            { ?aprop schema:value/rdf:value $arg2 }
            UNION
            { ?aprop rdf:value $arg2}
            VALUES $arg2 { "val1" }
            VALUES $arg1 { "attr1" }
        }
        """
        aprop_bn_var = Var(value=f"aprop_bn_var{suffix}")
        aprop_name_or_id_var = Var(value=f"aprop_name_or_id_var{suffix}")
        value_var = Var(value=f"value{suffix}")
        focus_to_aprop_tssp = TriplesSameSubjectPath.from_spo(
            subject=focus_node_vot.varorterm,
            predicate=IRI(value=str(SDO.additionalProperty)),
            object=aprop_bn_var,
        )
        aprop_name_or_id_tssp = create_tssp_alt_or_alt_inverse(
            subject=focus_node_vot,
            first_pred=IRI(value=str(SDO.propertyID)),
            second_pred=IRI(value=str(SDO.name)),
            obj=VarOrTerm(varorterm=aprop_name_or_id_var),
        )
        tssp_1 = TriplesSameSubjectPath.from_spo(
            subject=aprop_bn_var, predicate=IRI(value=str(SDO.value)), object=value_var
        )
        tssp_2 = TriplesSameSubjectPath.from_spo(
            subject=aprop_bn_var, predicate=IRI(value=str(RDF.value)), object=value_var
        )
        tssp_3 = create_tssp_sequence(
            subject=VarOrTerm(varorterm=aprop_bn_var),
            pred_1=IRI(value=str(SDO.value)),
            pred_2=IRI(value=str(RDF.value)),
            obj=VarOrTerm(varorterm=value_var),
        )
        union_gpnt = create_union_gpnt_from_tssps([tssp_1, tssp_2, tssp_3])
        arg_1_values_gpnt = create_values_constraint(aprop_name_or_id_var, args[0])
        arg_2_values_gpnt = create_values_constraint(value_var, args[1])
        ggps.add_pattern(
            TriplesBlock.from_tssp_list([aprop_name_or_id_tssp, focus_to_aprop_tssp])
        )
        ggps.add_pattern(union_gpnt)
        ggps.add_pattern(arg_1_values_gpnt)
        ggps.add_pattern(arg_2_values_gpnt)
    elif operator in ["qualifiedAttribution"]:
        """
        allows filtering on the prov qualified pattern where a known agent has a particular role
        {
            ?focus prov:qualifiedAttribution ?qa_1 .
            ?qa_1 prov:hadRole $arg1 .
            ?qa_1 prov:agent $arg2 .
            VALUES $arg1 { <https://example.org/vocab/role/contributor> }
            VALUES $arg2 { <https://example.org/vocab/org/org2> }
        }
        """
        qa_bn_var = Var(value=f"qa_bn_var{suffix}")
        role_var = Var(value=f"role_var{suffix}")
        agent_var = Var(value=f"agent_var{suffix}")

        focus_to_qa_tssp = TriplesSameSubjectPath.from_spo(
            subject=focus_node_vot.varorterm,
            predicate=IRI(value=str(PROV.qualifiedAttribution)),
            object=qa_bn_var,
        )
        qa_to_role_tssp = TriplesSameSubjectPath.from_spo(
            subject=qa_bn_var,
            predicate=IRI(value=str(PROV.hadRole)),
            object=role_var,
        )
        qa_to_agent_tssp = TriplesSameSubjectPath.from_spo(
            subject=qa_bn_var,
            predicate=IRI(value=str(PROV.agent)),
            object=agent_var,
        )

        role_values_gpnt = create_values_constraint(
            role_var, args[0]
        )  # args[0] is array for roles
        agent_values_gpnt = create_values_constraint(
            agent_var, args[1]
        )  # args[1] is array for agents

        ggps.add_pattern(
            TriplesBlock.from_tssp_list(
                [qa_to_agent_tssp, qa_to_role_tssp, focus_to_qa_tssp]
            )
        )
        ggps.add_pattern(role_values_gpnt)
        ggps.add_pattern(agent_values_gpnt)
