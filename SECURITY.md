# Security policy

## Supported versions

Codexicon is a project template. Security fixes are applied to the latest template release; projects created from an earlier release must review and port relevant fixes because generated projects are not updated automatically.

## Report a vulnerability

Use GitHub's **private vulnerability reporting** flow under the repository's Security tab. The **Report a vulnerability** action sends the report privately to the Codexicon maintainer. Do not open a public issue, discussion, or pull request containing exploit details, credentials, private data, or unredacted scanner output.

If GitHub's private reporting flow is unavailable, contact [@bnet47](https://github.com/bnet47) through a private contact method published on that profile. A project created from Codexicon must replace this reporting route during `$init` with its own accountable owner and private channel before public or production use.

Include the affected version, impact, reproduction conditions, and the smallest safe evidence. Never include live credentials; revoke or rotate an exposed credential immediately through its provider.

## Expected handling

The maintainer will acknowledge receipt through the same private channel, validate impact, coordinate remediation and disclosure, and publish guidance for affected template versions. No response-time guarantee is offered. Consuming projects must define their own policy and accountable owner during initialization.
