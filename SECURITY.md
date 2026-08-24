# Security policy

## Supported versions

Codexicon never updates consuming repositories automatically. Security fixes are applied to the latest template release. An adopted repository can inspect a trusted local release with `python scripts/codexicon.py update --source SOURCE` and explicitly apply baseline-unchanged harness files; conflicts and project-owned files still require deliberate review. Repositories without an adoption lock must review and port relevant fixes manually.

## Report a vulnerability

Use GitHub's **private vulnerability reporting** flow under the repository's Security tab. The **Report a vulnerability** action sends the report privately to the Codexicon maintainer. Do not open a public issue, discussion, or pull request containing exploit details, credentials, private data, or unredacted scanner output.

If GitHub does not offer the private reporting action, do not disclose vulnerability details publicly. Open a non-sensitive issue asking the maintainer to establish a private channel, without including exploit details or confidential evidence. A project created from Codexicon must replace this reporting route during `$init` with its own accountable owner and private channel before public or production use.

Include the affected version, impact, reproduction conditions, and the smallest safe evidence. Never include live credentials; revoke or rotate an exposed credential immediately through its provider.

## Expected handling

The maintainer will acknowledge receipt through the same private channel, validate impact, coordinate remediation and disclosure, and publish guidance for affected template versions. No response-time guarantee is offered. Consuming projects must define their own policy and accountable owner during initialization.
