from pathlib import Path

from pyshacl import validate
import httpx

from config import *


def main():
    # get the validator
    r = httpx.get("https://w3id.org/profile/vocpub/validator", follow_redirects=True)

    assert r.status_code == 200

    # for all vocabs...
    warning_vocabs = {}  # format {vocab_filename: warning_msg}
    invalid_vocabs = {}  # format {vocab_filename: error_msg}
    vocabs_dir = Path(__file__).parent.parent / "vocabularies"
    for f in vocabs_dir.glob("**/*"):
        # ...validate each file
        if f.name.endswith(".ttl"):
            try:
                v = validate(str(f), shacl_graph=r.text, shacl_graph_format="ttl")
                if not v[0]:
                    if "Severity: sh:Violation" in v[2]:
                        invalid_vocabs[f.name] = v[2]
                    elif "Severity: sh:Warning" in v[2]:
                        warning_vocabs[f.name] = v[2]

            # syntax errors crash the validate() function
            except Exception as e:
                invalid_vocabs[f.name] = e

    # check to see if we have any invalid vocabs
    if len(warning_vocabs.keys()) > 0 and SHOW_WARNINGS:
        print("Warning Vocabs:\n")
        for vocab, warning in warning_vocabs.items():
            print(f"- {vocab}:")
            print(warning)
            print("-----")

    # check to see if we have any invalid vocabs
    if len(invalid_vocabs.keys()) > 0:
        print("Invalid Vocabs:\n")
        for vocab, error in invalid_vocabs.items():
            print(f"- {vocab}:")
            print(error)
            print("-----")

    if WARNINGS_INVALID:
        assert len(warning_vocabs.keys()) == 0, "Warning vocabs: {}".format(
            ", ".join([str(x) for x in warning_vocabs.keys()])
        )
    assert len(invalid_vocabs.keys()) == 0, "Invalid vocabs: {}".format(
        ", ".join([str(x) for x in invalid_vocabs.keys()])
    )


if __name__ == "__main__":
    main()
