# Custom Data Endpoint Configuration

Prez allows the configuration of custom endpoints.

That is, you can specify the route structure e.g.

`/catalogs/{catalogId}/products/{productId}`

And then specify which classes these endpoints deliver, and what the RDF relations between those classes are.

## Set up instructions
To set up custom endpoints:
1. Set the CONFIGURATION_MODE environment variable to "true"
2. Go to the `/configure-endpoints` page and complete the form; submit
3. Set the CUSTOM_ENDPOINTS environment variable to "true"
4. Restart Prez. You should see the dynamic endpoints being created in the logs.
5. Confirm your endpoints are working as expected.

Once working as expected:
1. Copy the "custom_endpoints.ttl" file from `prez/reference_data/data_endpoints_custom` to the remote backend (e.g. triplestore)
    > Prez will preferentially use the custom endpoints specified in the triplestore over the ones specified in the local file.
2. Set the CONFIGURATION_MODE environment variable to "false"

## Limitations
The following limitations apply at present:
- The endpoint structure must be specified in the config to match what is input through the form.
related to this:
- Only one route can be specified (though multiple class hierarchies which use that one route can be specified)
i.e. you can specify
`/catalogs/{catalogId}/products/{productId}`
but not
`/catalogs/{catalogId}/products/{productId}`
and
`/datasets/{datasetId}/items/{itemsId}
on the one prez instance.
- This limitation is only due to link generation, which looks up the (currently) single endpoint structure variable in the config file.
- This should be resolvable with a small amount of work. At link generation time, an endpoint nodeshape is in context, and endpoint nodeshapes are mapped to a route structure.

- The number of hierarchy levels within a route must be two or three (i.e. 2 or 3 levels of classes = 4-6 listing/object endpoints)
    - The lower limit of two is because prez uses the relationships between classes to identify which objects to list. A single level of hierarchy has no reference to another level. A small amount of dev work would resolve this. The endpoint nodeshapes can be specified in the case of N=1 to not look for relationships to other classes.
    - The higher limit of three is because the SHACL parsing is not completely recursive. It could be manually extended to N levels, however it would be better to write a general SHACL parsing library.
