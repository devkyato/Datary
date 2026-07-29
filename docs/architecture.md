# Architecture

The CLI delegates to isolated modules for format detection/parsing, session recording/loading,
metrics, quality analysis, comparison, replay, plotting, reports, conversion, and generators.
Input flows line-by-line into `raw.log` and parsers. A staging directory is atomically renamed only
after critical artifacts and hashes are complete. There is no service, database, or network layer.

