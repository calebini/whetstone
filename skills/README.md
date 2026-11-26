# Whetstone agent skills

`whetstone-runner/` is the repository-owned portable skill, adapted from the
previous separately installed skill. It includes mode routing and supporting
references. The [operator guide](../docs/OPERATOR_GUIDE.md) owns the shared human
and agent explanations; the skill tells an agent which guidance to consult.

[Whetstone Release](whetstone-release/SKILL.md) is the maintainer checklist for release preparation, qualification, deployment, rollback and reconciliation of installed agent skills.

## Use and installation

An agent can read either skill’s `SKILL.md` directly from this checkout when
explicitly directed to it. For automatic discovery, install the **whole folder**
(including `references/` and `agents/`) into the skill location supported by your
agent host. In Codex, a typical personal location is
`${CODEX_HOME:-$HOME/.codex}/skills/<skill-name>`. Follow the host's discovery
or reload procedure; repository presence alone does not guarantee loading.

Before replacing an existing installation, inspect it for local changes and
preserve those separately. Do not maintain two independently edited canonical
copies. Use this repository folder as the source for later updates; an optional
symlink is suitable only when your host permits it and you intend skill updates
to follow that checkout. An installed copy needs access to matching Whetstone
documentation; its references identify repository-relative document names.

Keep machine installation paths, provider credentials, personal model/budget
preferences and runtime channel mappings outside the portable skill. Installing
this skill does not install Whetstone, move a stable runtime pin, change client
permissions or authorize model calls. A newer skill must still inspect the
selected runtime before advertising a capability.

## Maintenance

Update operator guidance and skill routing together. Validate skill frontmatter,
reference paths and representative job-selection scenarios. Do not copy release
qualification claims from old checkpoint notes into current instructions. This
folder is distributed in the repository; inclusion in an installable Python
package is not claimed by the current packaging configuration.
