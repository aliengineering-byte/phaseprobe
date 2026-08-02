# Security policy

## Supported version

Security fixes target the latest 0.2.x release until a newer minor release replaces it.

## Reporting

Use GitHub's private vulnerability reporting feature for the public repository. Do not open a
public issue with an exploit, credential, sensitive fixture, or personal data. No password or token
is ever required by PhaseProbe maintainers in chat.

Include the affected version, operating system, minimal reproduction, impact, and suggested
remediation if known. Ali will acknowledge a valid report through GitHub and coordinate disclosure
after a fix is available.

## Security boundary

PhaseProbe executes installed Python adapter code with the user's permissions. A schema-v2
`adapter.module` must be an absolute dotted module name and `adapter.factory` a Python identifier;
path separators, relative imports, calls, and punctuation are rejected. Parsing and validation do
not import the module. Running, replaying, or generating a test does import it and call the factory,
so the selected code must be trusted. This validation is not a sandbox.

Generated tests use a fixed template and sanitized names; user strings are never inserted into
executable source. Replay fixtures are SHA-256 integrity checked before execution, including when
their numerical policy is tolerance-based. Callable source is not serialized. HTML reports contain
escaped data and no script or external resource.

Review downstream fixtures before committing because model parameters and state may be sensitive.
PhaseProbe has no telemetry and performs no runtime network calls.
