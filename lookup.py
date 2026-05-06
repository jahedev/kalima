#!/usr/bin/env python3
import sys
from DictionaryServices import DCSCopyTextDefinition

def lookup(term: str):
    result = DCSCopyTextDefinition(None, term, (0, len(term)))
    return result

if __name__ == "__main__":
    term = " ".join(sys.argv[1:]).strip()
    if not term:
        print("Usage: python lookup.py <word>")
        sys.exit(1)

    definition = lookup(term)
    if definition:
        print(definition)
    else:
        print("No definition found.")