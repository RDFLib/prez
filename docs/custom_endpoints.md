# Custom Data Endpoint Configuration

Prez allows the configuration of custom endpoints.

That is, you can specify the route structure e.g.

`/catalogs/{catalogId}/products/{productId}`

And then specify which classes these endpoints deliver, and what the RDF relations between those classes are.

## Examples

For a fully worked example of a custom endpoint definition see the [examples](./examples/custom_endpoints) and
of course the [default endpoint definitions](../prez/reference_data/endpoints/data_endpoints_default/default_endpoints.ttl)

## Creating custom endpoint definitions


Firstly, refer to the examples above, to get an idea of what an endpoint definition file
looks like. In particular [this one](./examples/custom_endpoints/example_4_levels.trig)

The definitions are just RDF so can be stored in any RDF serialisation format.
They can be written by hand, and there is also a UI to create them via a form.

The form is sufficient for the simple case, but for more advanced definitions you may
prefer to write them by hand.

To access the form:

1. Set the `CONFIGURATION_MODE` environment variable to "true"
2. Start Prez
3. Go to the `/configure-endpoints` page and complete the form
4. Save your work
5. turn off CONFIGURATION_MODE

Once you have a custom endpoint definition file refer to the next section to see how to
tell Prez to use it.

## using Custom Endpoint definitions

Custom endpoints are defined in RDF. Prez detects them in a specific location in the codebase (useful for development, where the Prez git repo has been cloned), or can retrieve them from a remote repository (useful for production, or when using the docker image). To set up Prez to read custom endpoints using the first method, where the Prez repo has been cloned:

1. Set the `CUSTOM_ENDPOINTS` environment variable to "true"
2. Copy your endpoint definition file to `prez/reference_data/endpoints/custom_endpoints/`
3. Start / restart Prez. You should see the dynamic endpoints being created in the logs.

To set up Prez to read custom endpoints from a repository (typically a SPARQL endpoint, but can also be Pyoxigraph reading from a local directory):

1. Set the `CUSTOM_ENDPOINTS` environment variable to "true"
2. upload your endpoint definition file to the triplestore into the `<https://prez.dev/SystemGraph>` named graph. The endpoints must be of type `https://prez.dev/ont/OGCFeaturesEndpoint` or `ont:DynamicEndpoint`, AND also a `https://prez.dev/ont/ListingEndpoint` or `https://prez.dev/ont/ObjectEndpoint`.
3. Start / restart Prez. You should see the dynamic endpoints being created in the logs.

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
