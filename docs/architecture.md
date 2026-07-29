# Architecture

I wanted the architecture to follow the way I explain a Datary run: capture first, interpret
second, and publish evidence only after the recording is complete.

The CLI delegates to isolated modules for format detection and parsing, session recording and
loading, metrics, quality analysis, comparison, replay, plotting, reports, conversion, and
generators. Input flows line-by-line into `raw.log` and the selected parser. A staging directory is
renamed into place only after critical artifacts and hashes are complete.

Oh! This boundary matters: there is no service, central database, or network layer hiding behind
the command. Sessions are ordinary local files, and core recording remains usable without the
optional plotting dependency.
