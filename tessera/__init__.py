"""TESSERA reference core.

A dependency-free implementation of the parts of the specification that are
defined precisely enough to be implemented and tested:

    canonical.py  the versioned canonical schema and its validation
    ledger.py     the append-only, hash-chained event ledger
    metrics.py    every score in the product, defined once
    routing.py    federated and workforce routing, with weight versions
    conflict.py   cross-system conflict resolution, with a recorded rule

What this is not: the mesh, the connectors, the web application, the mobile
client or the workforce runtime. Those are specified and not built. See
docs/20-reference-core.md for the exact boundary.

Run the demonstration:

    python3 -m tessera.cli demo

Run the tests:

    python3 -m unittest discover -s tests -v
"""

__version__ = "0.1.0"
SCHEMA_VERSION = "1.0.0"
