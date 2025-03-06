# Custom Endpoints

Prez allows the configuration of custom endpoints.

That is, you can specify the route structure e.g.

`/catalogs/{catalogId}/products/{productId}`

And then specify which classes these endpoints deliver, and what the RDF relations between those classes are.

## Examples

For example custom endpoint definitions see the [examples](./examples/custom_endpoints) and
of the [defaults](../prez/reference_data/endpoints/data_endpoints_default/default_endpoints.ttl).

## Creating custom endpoints

Firstly, refer to the examples above, to get an idea of what an endpoint definition file
looks like. In particular [this one](./examples/custom_endpoints/example_4_levels.trig)

The definitions are just RDF so can be stored in any RDF serialization format.
They can be written by hand, and there is also a UI to create them via a form.

The form is sufficient for the simple case, but for more advanced definitions you may
prefer to write them by hand.

To access the form:

1. Set the `CONFIGURATION_MODE` environment variable to "true"
2. Start Prez
3. Go to the `/configure-endpoints` page and complete the form
4. Save your work
5. turn off CONFIGURATION_MODE

Once you have your endpoint definitions refer to the next section on how to use it.

## Using Custom Endpoints

To set up custom endpoints:

1. Set the `CUSTOM_ENDPOINTS` environment variable to "true"
2. Update the `ENDPOINT_STRUCTURE` environment variable to reflect the apiPaths you have
   specified.

   > For example, if you have defined the following apiPath
   >
   > `/books/{bookId}/chapters/{chapterId}/paragraphs/{paragraphId}/sentences/{sentenceId}`
   >
   > then you would need to set
   >
   > ENDPOINT_STRUCTURE='["books", "chapters", "paragraphs", "sentences"]'
   >
   > The default configuration is
   >
   > `/catalogs/{catalogId}/collections/{collectionId}/items/{itemId}`
   >
   > with
   >
   > ENDPOINT_STRUCTURE='["catalogs", "collections", "items"]'

3. - **If you cannot add data to the SPARQL_ENDPOINT:**

     Copy the endpoint definition file to `prez/reference_data/endpoints/custom_endpoints/myDefinitionFile.ttl`

   - **If you can:**

     Add your endpoint definitions to the triplestore under the `<https://prez.dev/SystemGraph>` named graph.

4. Start / restart Prez. You should see the custom endpoints being created in the logs.

## Limitations

The following limitations apply at present:

- Only one route can be specified

  i.e. you can specify

  `/catalogs/{catalogId}/products/{productId}`

  but not

  `/catalogs/{catalogId}/products/{productId}` and
  `/datasets/{datasetId}/items/{itemsId}`

- The number of hierarchy levels within a route must be two or three

  - The lower limit of two is because prez uses the relationships between classes
    to identify which objects to list. A single level of hierarchy has no reference
    to another level. A small amount of dev work would resolve this.
    The endpoint nodeshapes can be specified in the case of N=1 to not look for
    relationships to other classes.

  - The higher limit of three is because the SHACL parsing is not completely recursive.
    It could be manually extended to N levels, however it would be better to write
    a general SHACL parsing library.
