# Security policy

## Supported version

Security fixes target the latest 0.1.x release until a newer minor release replaces it.

## Reporting

Use GitHub’s private vulnerability reporting feature for the public repository. Do not open a public issue with an exploit, credential, sensitive fixture, or personal data. No password or token is ever required by PhaseProbe maintainers in chat.

Include the affected version, operating system, minimal reproduction, impact, and suggested remediation if known. Ali will acknowledge a valid report through GitHub and coordinate disclosure after a fix is available.

## Security boundary

PhaseProbe executes installed Python adapter code with the user’s permissions. Configuration files are data, but an adapter is code and must be reviewed before installation. Generated tests use a fixed template and sanitized names; replay fixtures are integrity checked before execution. HTML reports contain escaped data and no script or external resource.

Review downstream fixtures before committing because model parameters and state may be sensitive. PhaseProbe has no telemetry and performs no runtime network calls.
