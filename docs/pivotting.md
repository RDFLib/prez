# Pivotting data with pivot profiles

## Use Case

Prez has limited capabilities for data pivotting, which can be useful for condensing
information spread across nested blank nodes.

Take the following data:

```turtle
ex:catalog a dcat:Catalog ;
  dct:title "Demo Catalog" ;
  prov:qualifiedAssociation [
    a prov:Association ;
    prov:agent "agent 1" ;
    prov:hadRole ex:role1
  ],
  [
    a prov:Association ;
    prov:agent "agent 2" ;
    prov:hadRole ex:role2
  ],
  [
    a prov:Association ;
    prov:agent "agent 3" ;
    prov:hadRole ex:role3
  ],
  [
    a prov:Association ;
    prov:agent "agent 4" ;
    prov:hadRole ex:role3
  ]
.
```

And suppose you want to view it in the condensed format

| Item       | ex:role1  | ex:role2  | ex:role3             |
| ---------- | --------- | --------- | -------------------- |
| ex:catalog | "agent 1" | "agent 2" | "agent 3", "agent 4" |

A pivot profile tells prez to transform the data such that it is suitable for this
display.

## Quick Start

With the above data, and the below pivot profile you can achieve the desired outcome.

```turtle
@prefix altr-ext: <http://www.w3.org/ns/dx/connegp/altr-ext#> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dcterms: <http://purl.org/dc/terms/> .
@prefix prez: <https://prez.dev/> .
@prefix prof: <http://www.w3.org/ns/dx/prof/> .
@prefix profile: <https://prez.dev/profile/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix shext: <http://example.com/shacl-extension#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

profile:pivot-assoc a prof:Profile, prez:ListingProfile ;
  dcterms:identifier "pivot-assoc"^^xsd:token ;
  dcterms:title "Pivot Associations" ;
  dcterms:description "Pivot agent associations on a catalog around the role" ;
  altr-ext:constrainsClass dcat:Catalog ;
  altr-ext:hasDefaultResourceFormat "text/anot+turtle" ;
  altr-ext:hasResourceFormat "application/geo+json" ,
      "application/ld+json" ,
      "application/anot+ld+json" ,
      "application/rdf+xml" ,
      "text/anot+turtle" ,
      "text/turtle" ;
  sh:property [
    sh:path [
      shext:pivotPath [
          sh:path prov:qualifiedAssociation ;
          shext:pivotKey prov:hadRole ;
          shext:pivotValue prov:agent
      ] ;
    ] ;
  ] ;
.
```

The requirements of the pivot profile are as follows:

The profile **MUST**

- conform to all other Profile requirements,
- be a `prez:ListingProfile`,
- contain a `sh:property` with a `sh:path` that points to the `shext:pivotPath`

The `shext:pivotPath` **MUST**

- contain a `sh:path`, `shext:pivotKey`, and `shext:pivotValue`, where

  - the `sh:path` gives the path to the nested nodes on which there are values you want to pivot.
  - the `shext:pivotKey` is a path to the column headers
  - and the `shext:pivotValue` is the path to the cell values.

The `shext:pivotPath` **MAY**

  - be under a `sh:union` clause like

  ```turtle
  sh:property [
    sh:path [
      sh:union (
        rdf:type
        [ shext:pivotPath [
            sh:path (ex:path ex:to ex:node ) ;
            sh:piovotKey ex:key ;
            sh:pivotValue ex:value ;
          ]
        ]
      )
    ]
  ]
  ```

You can think of using `shext:pivotPath` in the same way as other shacl pathing
operators like `sh:inversPath`

With the above pivot profile Prez will produce queries like the following

```sparql
CONSTRUCT {
  ?focus_node a prez:FocusNode .
  ?focus_node ?key ?value .
}
WHERE {
  ?focus_node prov:qualifiedAssociation ?prof_1_node_1 .
  ?prof_1_node_1 prov:hadRole ?key .
  ?prof_1_node_1 prov:agent ?value .
}
```

Which with the example data would give back RDF like

```turtle
ex:catalog ex:role1 "agent 1" ;
ex:catalog ex:role2 "agent 2" ;
ex:catalog ex:role3 "agent 3", "agent 4" ;
.
```

As per the standard content negotiation by profile mechanisms, you can ask for prez to
use this profile with the `_profile` query parameter or `Profile` header field, and
specifying the `dcterms:identifier` of the profile.

i.e.

```
/catalogs?_profile=pivot-assoc
```
