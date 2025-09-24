"""
OGC Features Functions data module.

This module provides the functions list for the /functions endpoint,
based on the actual CQL functions implemented in cql_functions.py.
"""

from prez.models.ogc_features import (
    Function,
    FunctionArgument,
    FunctionArgumentType,
    FunctionsResponse,
)

from prez.services.query_generation.cql_functions import REGISTERED_CQL_FUNCTIONS


def get_ogc_functions_response() -> FunctionsResponse:
    """
    Get the functions response for the OGC Features /functions endpoint.

    Returns FunctionsResponse with the actual implemented CQL functions.
    """
    functions = []

    # Define function metadata based on actual implementations
    function_metadata = {
        "FOIObservationFilterDirect": {
            "description": "Filter observations related to a Feature of Interest by specifying two direct "
            "property values on an observation.",
            "arguments": [
                FunctionArgument(
                    title="Property one predicate",
                    description="IRI of the first observation property to filter on",
                    type=[FunctionArgumentType.STRING],
                ),
                FunctionArgument(
                    title="Property one value",
                    description="Filter value for the first observation property",
                    type=[FunctionArgumentType.STRING, FunctionArgumentType.NUMBER],
                ),
                FunctionArgument(
                    title="Property two predicate",
                    description="IRI of the second observation property to filter on",
                    type=[FunctionArgumentType.STRING],
                ),
                FunctionArgument(
                    title="Property two value",
                    description="Filter value for the second observation property",
                    type=[FunctionArgumentType.STRING, FunctionArgumentType.NUMBER],
                ),
            ],
            "returns": [FunctionArgumentType.BOOLEAN],
        },
        "FOIObservationFilterSequence": {
            "description": "Filter observations related to a Feature of Interest by specifying one direct"
            " property value and one sequence path property value.",
            "arguments": [
                FunctionArgument(
                    title="Property one predicate",
                    description="IRI of the first observation property to filter on",
                    type=[FunctionArgumentType.STRING],
                ),
                FunctionArgument(
                    title="Property one value",
                    description="Filter value for the first observation property",
                    type=[FunctionArgumentType.STRING, FunctionArgumentType.NUMBER],
                ),
                FunctionArgument(
                    title="Sequence path first predicate",
                    description="First IRI in the sequence path of the second observation property chain"
                    " to filter on",
                    type=[FunctionArgumentType.STRING],
                ),
                FunctionArgument(
                    title="Sequence path second predicate",
                    description="Second IRI in the sequence path of the second observation property chain"
                    " to filter on",
                    type=[FunctionArgumentType.STRING],
                ),
                FunctionArgument(
                    title="Property two value",
                    description="Filter value for the second observation property chain",
                    type=[FunctionArgumentType.STRING, FunctionArgumentType.NUMBER],
                ),
            ],
            "returns": [FunctionArgumentType.BOOLEAN],
        },
        "hasObservation": {
            "description": "Filter focus nodes by sosa observed properties (sosa:observedProperty) and their "
            "corresponding values (union of sosa:hasSimpleResult, sosa:hasResult, and "
            "sosa:hasResult/rdf:value).",
            "arguments": [
                FunctionArgument(
                    title="Observed Property IRIs",
                    description="Array of observed property IRIs (passed as CQL arrayLiteral)",
                    type=[FunctionArgumentType.ARRAY],
                ),
                FunctionArgument(
                    title="Results",
                    description="Array of observation result values (passed as CQL arrayLiteral)",
                    type=[FunctionArgumentType.ARRAY],
                ),
            ],
            "returns": [FunctionArgumentType.BOOLEAN],
        },
        "hasAttribute": {
            "description": "Filter focus nodes by tern attributes (tern:attribute) and their corresponding "
            "values (union of tern:hasSimpleValue, tern:hasValue, and tern:hasValue/rdf:value).",
            "arguments": [
                FunctionArgument(
                    title="Attribute Names",
                    description="Array of attribute name IRIs (passed as CQL arrayLiteral)",
                    type=[FunctionArgumentType.ARRAY],
                ),
                FunctionArgument(
                    title="Attribute Values",
                    description="Array of attribute values (passed as CQL arrayLiteral)",
                    type=[FunctionArgumentType.ARRAY],
                ),
            ],
            "returns": [FunctionArgumentType.BOOLEAN],
        },
        "hasAdditional": {
            "description": "Filter on the names/values of a schema:additionalProperty of an object.",
            "arguments": [
                FunctionArgument(
                    title="PropertyIds or Names",
                    description="Array of schema:propertyID or schema:name values (passed as CQL arrayLiteral)",
                    type=[FunctionArgumentType.ARRAY],
                ),
                FunctionArgument(
                    title="Attribute Values",
                    description="Array of any of schema:value, rdf:value, or schema:value/rdf:value values "
                    "(passed as CQL arrayLiteral)",
                    type=[FunctionArgumentType.ARRAY],
                ),
            ],
            "returns": [FunctionArgumentType.BOOLEAN],
        },
    }

    # Create Function objects for each registered CQL function
    for func_name in REGISTERED_CQL_FUNCTIONS:
        metadata = function_metadata.get(func_name)
        if metadata:
            functions.append(
                Function(
                    name=func_name,
                    description=metadata["description"],
                    arguments=metadata["arguments"],
                    returns=metadata["returns"],
                )
            )

    return FunctionsResponse(functions=functions)
