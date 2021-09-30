class DisplayProperty:
    def __init__(
            self,
            predicate_uri: str,
            predicate_label: str,
            object_value: str,
            object_label: str = None,
            object_notation: str = None
    ):
        self.predicate_html = f'<a href="{predicate_uri}">{predicate_label}</a>'
        if predicate_uri == "http://purl.org/pav/hasCurrentVersion":
            self.object_html = f'<td colspan="2"><a href="{object_value}">{object_value}</a></td>'
        elif object_notation is not None:
            # this is a related Concept, so it will have an object_label
            related_col_uri = object_value.split("/current/")[0] + "/current/"
            related_col_systemUri = "/collection/" + related_col_uri.split("/collection/")[1]
            related_col_id = related_col_systemUri.replace("/collection/", "").replace("/current/", "")
            related_systemUri = "/collection/" + object_value.split("/collection/")[1]
            related_id = object_value.split("/current/")[1].rstrip("/")
            self.object_html = f'<td><code><a href="{related_col_systemUri}">{related_col_id}</a>:<a href="{related_systemUri}">{related_id}</a></code></td><td>{object_label}</td>'
        elif object_label is not None:  # URI with label
            self.object_html = f'<td colspan="2"><a href="{object_value}">{object_label}</a></td>'
        elif object_value.startswith("http"):  # URI, no label
            self.object_html = f'<td colspan="2"><a href="{object_value}">{object_value}</a></td>'
        else:  # literal
            self.object_html = f'<td colspan="2">{object_value}</td>'
