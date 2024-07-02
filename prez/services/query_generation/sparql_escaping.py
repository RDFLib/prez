def escape_for_lucene_and_sparql(query):
    chars_to_escape = r'\+-!(){}[]^"~*?:/'
    return "".join(r"\\" + char if char in chars_to_escape else char for char in query)
