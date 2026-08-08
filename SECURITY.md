# Security

Datary treats input and session content as untrusted inert data. It does not evaluate expressions,
execute input files, deserialize Python objects, invoke shells from records, expand spreadsheet
formulas, or perform background network requests.

## Defences

- conservative format detection and explicit ambiguity errors;
- line, JSON-buffer, field, manifest, and source-file safety limits;
- duplicate-key and non-finite JSON rejection;
- staging plus recoverable atomic session overwrite;
- traversal and symlink checks at session and generated-output trust boundaries;
- atomic critical metadata and report writes;
- spreadsheet-formula neutralization in CSV convenience output;
- terminal-control and Markdown/HTML escaping;
- SHA-256 coverage of the manifest and all evidentiary files;
- structural parsing and record-count checks during integrity verification.

Checksums detect corruption; they do not authenticate an author against an attacker who can
rewrite the complete session. Use external signatures and trusted storage when authenticity is
required.

## Reporting a vulnerability

Report security problems privately through
[GitHub Security Advisories](https://github.com/devkyato/Datary/security/advisories/new)
or the repository owner's private contact. Do not attach confidential recordings. A minimal
deterministic synthetic reproducer, affected version, operating system, and expected boundary are
enough to begin investigation.

Users remain responsible for filesystem permissions, trusted installation sources, producer
program safety, and privacy review before sharing sessions.
