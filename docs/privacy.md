# Privacy

I wanted a useful session to be shareable without quietly publishing the shape of someone’s
laptop. Working-directory paths are therefore `<redacted>` by default; enable `--include-path`
only when that provenance is genuinely useful.

Environment variables are never copied into sessions, and Datary has no telemetry or background
network calls. Oh! The raw data can still contain secrets because Datary preserves what it
receives. Check file permissions and review or redact a session before sharing it.
