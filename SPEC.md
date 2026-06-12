# BYOLSP Implementation Spec

Build Your Own LSP

## 1. Product Definition

BYOLSP is a small command-line application that makes ast-grep rules easy to reuse across repositories, easy to install into a repository, and easy to expose to AI coding agents.

BYOLSP does not scan source code itself. BYOLSP does not implement a language server. BYOLSP manages files and configuration so that the normal ast-grep CLI and the normal ast-grep LSP work without wrappers.

The v1 product has three responsibilities:

1. Create and maintain the ast-grep project configuration needed for custom diagnostics.
2. Manage three rule scopes: project, local personal, and global personal.
3. Install AI-agent instructions and hook entrypoints that run ast-grep and render rule-specific feedback.

The core rule engine is ast-grep. The editor integration is ast-grep LSP. The human CLI integration is ast-grep scan. BYOLSP exists to make those integrations trivial to set up and keep consistent.

## 2. Non-Negotiable Design Constraints

These constraints define v1. An implementation that violates these constraints is not v1 BYOLSP.

1. ast-grep must remain the only scanner.
2. ast-grep LSP must remain the editor integration.
3. BYOLSP must not wrap ast-grep LSP in v1.
4. BYOLSP must not introduce a second rule language in v1.
5. BYOLSP must not require users to know that ast-grep is an implementation detail when authoring through the BYOLSP CLI, but it must store real ast-grep YAML rules on disk.
6. BYOLSP must not use symlinks for rules in v1.
7. BYOLSP must not implement packs in v1.
8. BYOLSP must not require a daemon.
9. BYOLSP must not mutate source files except BYOLSP config, ast-grep config, AI integration files, and rule files that the command explicitly owns.
10. BYOLSP must preserve existing user content in `sgconfig.yml`.
11. BYOLSP must fail loudly before producing duplicate ast-grep rule IDs.
12. BYOLSP must be usable through `uvx byolsp`.

## 3. Implementation Language

Implement BYOLSP in Python 3.11+.

Python is the correct v1 choice because BYOLSP is not a hot-path parser. The hot path remains ast-grep, which is already fast. BYOLSP mainly performs filesystem operations, YAML edits, validation, subprocess calls, and hook rendering.

The project must be packaged as a normal Python CLI:

```toml
[project]
name = "byolsp"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "platformdirs>=4.3",
  "ruamel.yaml>=0.18",
]

[project.scripts]
byolsp = "byolsp.cli:main"
```

Use `argparse` for the CLI. Do not add a heavy CLI framework in v1. Use plain text output by default. Use JSON output only behind explicit `--json` flags.

Use `ruamel.yaml` for YAML so comments and ordering in existing `sgconfig.yml` are preserved as much as practical. Do not use ad hoc regex replacement for YAML mutation.

## 4. External Dependency Contract

BYOLSP requires ast-grep to be installed separately.

The CLI must resolve the ast-grep executable in this order:

1. `$BYOLSP_AST_GREP`, if set.
2. `ast-grep` on `PATH`.
3. `sg` on `PATH`.

If no executable is found, commands that require ast-grep must exit nonzero with this message shape:

```text
ast-grep is required but was not found.

Install it, then rerun this command:
  brew install ast-grep

Other install options:
  https://ast-grep.github.io/guide/quick-start.html
```

Do not auto-install ast-grep.

The implementation should support ast-grep 0.43.0 or newer. `byolsp doctor` must print the detected version.

## 5. Repository Layout

After `byolsp init`, a repository must contain this structure:

```text
repo/
  sgconfig.yml
  .byolsp/
    config.yml
    local.yml
    state.json
    rules/
      project/
        .gitkeep
      personal/
        local/
          .gitkeep
        global/
          .gitkeep
    agents/
      README.md
```

Tracked files:

```text
sgconfig.yml
.byolsp/config.yml
.byolsp/rules/project/.gitkeep
.byolsp/rules/personal/local/.gitkeep
.byolsp/rules/personal/global/.gitkeep
.byolsp/agents/README.md
```

Ignored local files:

```text
.byolsp/local.yml
.byolsp/state.json
.byolsp/cache/
.byolsp/rules/personal/local/*.yml
.byolsp/rules/personal/local/*.yaml
.byolsp/rules/personal/global/*.yml
.byolsp/rules/personal/global/*.yaml
```

Project rule files under `.byolsp/rules/project/` are shared with the team and should be committed.

Local personal rule files under `.byolsp/rules/personal/local/` are private to the current repository and current user.

Global personal rule files under `.byolsp/rules/personal/global/` are generated copies of canonical global rules from the user's BYOLSP home directory.

## 6. Global Layout

BYOLSP must use the platform config directory by default. On macOS this should resolve to:

```text
~/.config/byolsp/
```

The global directory must contain:

```text
~/.config/byolsp/
  config.yml
  repos.yml
  rules/
    python/
      no-python-cast.yml
```

Canonical global rules live under `~/.config/byolsp/rules/`.

The global rules directory may be nested by language or topic. BYOLSP must recursively discover `.yml` and `.yaml` files below it.

## 7. ast-grep Config Contract

BYOLSP must make the repository's `sgconfig.yml` include these rule directories:

```yaml
ruleDirs:
  - .byolsp/rules/project
  - .byolsp/rules/personal/local
  - .byolsp/rules/personal/global
```

If `sgconfig.yml` does not exist, `byolsp init` must create it.

If `sgconfig.yml` exists, `byolsp init` must preserve all existing keys and append only missing `ruleDirs` entries.

If `ruleDirs` exists as a scalar or invalid type, `byolsp init` must fail with a clear error instead of guessing:

```text
Cannot update sgconfig.yml: expected ruleDirs to be a list.
Edit sgconfig.yml manually or rerun with --replace-sgconfig.
```

`--replace-sgconfig` may overwrite `sgconfig.yml`, but it must first create a timestamped backup:

```text
sgconfig.yml.byolsp-backup-YYYYMMDD-HHMMSS
```

BYOLSP must not require users to invoke ast-grep through BYOLSP. After init, these commands must work directly:

```bash
ast-grep scan
ast-grep lsp
```

If the user uses `sg` as the binary name, these must also work directly:

```bash
sg scan
sg lsp
```

## 8. Git Ignore Contract

`byolsp init` must offer two ignore modes:

1. Project `.gitignore` mode.
2. Local `.git/info/exclude` mode.

Project `.gitignore` mode is the default for repositories where the team should know that BYOLSP has local generated state.

Local `.git/info/exclude` mode is for users experimenting privately without changing shared ignore policy.

The ignored patterns must be:

```gitignore
# BYOLSP local state
.byolsp/local.yml
.byolsp/state.json
.byolsp/cache/

# BYOLSP personal rules
.byolsp/rules/personal/local/*.yml
.byolsp/rules/personal/local/*.yaml
.byolsp/rules/personal/global/*.yml
.byolsp/rules/personal/global/*.yaml
!.byolsp/rules/personal/local/.gitkeep
!.byolsp/rules/personal/global/.gitkeep
```

BYOLSP must not rely on `assume-unchanged` or `skip-worktree`. Those Git features are not an ignore policy for tracked files.

## 9. Config File Schemas

All BYOLSP config files must contain a top-level `version: 1`.

### 9.1 Repository Config

Path:

```text
.byolsp/config.yml
```

Schema:

```yaml
version: 1
project:
  name: null
paths:
  sgconfig: sgconfig.yml
  project_rules: .byolsp/rules/project
  personal_local_rules: .byolsp/rules/personal/local
  personal_global_rules: .byolsp/rules/personal/global
ai:
  agents: []
```

Fields:

`project.name` is optional display metadata.

`paths.sgconfig` is the ast-grep config path relative to repo root.

`paths.project_rules` is the shared team rule directory.

`paths.personal_local_rules` is the current user's private per-repo rule directory.

`paths.personal_global_rules` is the generated copy directory for enabled global rules.

`ai.agents` records AI integrations installed by `byolsp init` or `byolsp hook install`.

### 9.2 Repository Local Config

Path:

```text
.byolsp/local.yml
```

Schema:

```yaml
version: 1
global:
  excluded_rule_ids: []
sync:
  auto_sync_on_init: true
```

Fields:

`global.excluded_rule_ids` disables specific canonical global rules for this repository only.

Disabling a global rule must remove its generated copy from `.byolsp/rules/personal/global/` on the next sync.

`sync.auto_sync_on_init` controls whether init should run sync immediately after creating files. Default is true.

### 9.3 Repository State

Path:

```text
.byolsp/state.json
```

Schema:

```json
{
  "version": 1,
  "global_rule_copies": {
    "no-python-cast": {
      "source": "/Users/example/.config/byolsp/rules/python/no-python-cast.yml",
      "destination": ".byolsp/rules/personal/global/python/no-python-cast.yml",
      "source_sha256": "abc123",
      "copied_at": "2026-06-12T14:30:00Z"
    }
  },
  "registered_repo": true
}
```

State is generated. Users should not edit it.

BYOLSP must tolerate missing state by rebuilding it from disk where possible.

### 9.4 Global Config

Path:

```text
~/.config/byolsp/config.yml
```

Schema:

```yaml
version: 1
paths:
  rules: rules
  repos: repos.yml
ast_grep:
  command: auto
sync:
  sync_registered_repos_on_global_change: true
```

Fields:

`paths.rules` is relative to the global config directory unless absolute.

`paths.repos` is relative to the global config directory unless absolute.

`ast_grep.command` may be `auto`, `ast-grep`, `sg`, or an absolute path.

`sync.sync_registered_repos_on_global_change` controls whether `byolsp add --scope global` and `byolsp edit --scope global` attempt to sync all registered repos.

### 9.5 Global Repo Registry

Path:

```text
~/.config/byolsp/repos.yml
```

Schema:

```yaml
version: 1
repos:
  - root: /Users/example/projects/my-repo
    enabled: true
    last_sync: null
```

Every `byolsp init` must register the current repository unless `--no-register` is passed.

`byolsp sync --all` must sync every enabled repo in this registry.

## 10. Rule File Format

BYOLSP rule files are valid ast-grep YAML files with optional BYOLSP metadata.

Example:

```yaml
id: no-python-cast
language: Python
severity: warning
message: Avoid typing.cast in Python code.
rule:
  pattern: cast($TYPE, $VALUE)
metadata:
  byolsp:
    rationale: >
      casting hides type model problems and can make invalid assumptions
      invisible to both reviewers and type checkers.
    agent_prompt: >
      Do not use typing.cast here. Fix the type by narrowing, changing the
      signature, introducing a protocol, or restructuring the value flow. If
      the cast is genuinely necessary, leave a concise comment explaining the
      invariant that the type checker cannot see.
    allow_with_comment: true
    tags:
      - python
      - typing
```

Required ast-grep fields:

```yaml
id: string
language: string
rule: object
message: string
```

Recommended ast-grep fields:

```yaml
severity: warning
```

Optional BYOLSP metadata:

```yaml
metadata:
  byolsp:
    rationale: string
    agent_prompt: string
    allow_with_comment: boolean
    docs_url: string
    tags: [string]
```

The `metadata.byolsp.agent_prompt` value is used by AI hooks. If absent, BYOLSP must fall back to `message`.

BYOLSP must not invent a separate compiled rule format in v1.

## 11. Rule ID Contract

Rule IDs must be unique across all directories visible to ast-grep:

```text
.byolsp/rules/project
.byolsp/rules/personal/local
.byolsp/rules/personal/global
```

Canonical global source rules must also have unique IDs within:

```text
~/.config/byolsp/rules
```

Recommended ID pattern:

```text
[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*
```

Examples:

```text
no-python-cast
python.no-cast
react.no-default-export
```

BYOLSP must warn when a rule ID does not match the recommended pattern, but it should not reject the rule if ast-grep accepts it.

BYOLSP must reject duplicate IDs before invoking ast-grep.

## 12. Rule Scope Semantics

There are exactly three v1 rule scopes.

### 12.1 Project Rules

Path:

```text
.byolsp/rules/project/
```

Project rules are shared with the repository.

Use project rules for team policy:

```text
No missing type hints in this Python package.
No direct database access from handlers.
No generated one-line function wrappers without a documented reason.
```

Project rules override global rules by rule ID. Override means that sync must not copy a global rule into `.byolsp/rules/personal/global/` if a project rule with the same ID exists.

### 12.2 Local Personal Rules

Path:

```text
.byolsp/rules/personal/local/
```

Local personal rules apply only to the current user and current repository.

Use local personal rules for experiments, personal workflow preferences, or temporary diagnostics that should not be committed.

Local personal rules override global rules by rule ID. Override means that sync must not copy a global rule into `.byolsp/rules/personal/global/` if a local personal rule with the same ID exists.

### 12.3 Global Personal Rules

Canonical source:

```text
~/.config/byolsp/rules/
```

Generated repository copy:

```text
.byolsp/rules/personal/global/
```

Global personal rules are reusable rules the user wants in many repositories.

The repository copy is generated. Users should edit canonical global rules through:

```bash
byolsp edit --scope global RULE_ID
```

or by editing files under:

```text
~/.config/byolsp/rules/
```

After manual global edits, users must run:

```bash
byolsp sync --all
```

Commands that edit global rules should run sync automatically.

## 13. Sync Algorithm

`byolsp sync` is the key mechanism that makes copied global rules behave like shared rules without symlinks.

Input:

1. Repository root.
2. Repository config.
3. Repository local config.
4. Repository state.
5. Canonical global rules directory.

Output:

1. `.byolsp/rules/personal/global/` contains the enabled canonical global rules that do not conflict with project or local personal rules.
2. `.byolsp/state.json` records generated copies.
3. ast-grep sees no duplicate rule IDs from BYOLSP-managed directories.

Algorithm:

```text
1. Resolve repo root.
2. Load .byolsp/config.yml.
3. Load or create .byolsp/local.yml.
4. Load or create .byolsp/state.json.
5. Discover project rules recursively.
6. Discover local personal rules recursively.
7. Discover canonical global rules recursively.
8. Parse each rule enough to read id, language, message, and metadata.
9. Fail if project rules contain duplicate IDs.
10. Fail if local personal rules contain duplicate IDs.
11. Fail if canonical global rules contain duplicate IDs.
12. Build blocked_global_ids:
    a. IDs from project rules.
    b. IDs from local personal rules.
    c. IDs from .byolsp/local.yml global.excluded_rule_ids.
13. For each canonical global rule:
    a. If its ID is blocked, do not copy it.
    b. Otherwise copy it to .byolsp/rules/personal/global/ preserving relative path below global rules root.
14. Remove stale managed global copies that no longer correspond to enabled canonical global rules.
15. Refuse to delete unmanaged YAML files found in .byolsp/rules/personal/global/ unless --force is passed.
16. Write .byolsp/state.json.
17. Validate the resulting combined rule set has unique IDs.
18. Optionally run ast-grep scan --max-results 1 as a smoke test when --check is passed.
```

Generated global copy paths must preserve the relative path below the global rules root.

Example:

```text
~/.config/byolsp/rules/python/no-python-cast.yml
```

copies to:

```text
.byolsp/rules/personal/global/python/no-python-cast.yml
```

Do not flatten paths. Flattening creates avoidable filename conflicts.

## 14. Duplicate and Conflict Behavior

Conflict means two rule files have the same `id`.

BYOLSP must treat conflicts differently depending on where they occur.

Duplicate IDs inside project rules:

```text
Error. User must fix.
```

Duplicate IDs inside local personal rules:

```text
Error. User must fix.
```

Duplicate IDs inside canonical global rules:

```text
Error. User must fix.
```

Project rule ID matches canonical global rule ID:

```text
Not an error. Project rule wins. Sync skips the global copy.
```

Local personal rule ID matches canonical global rule ID:

```text
Not an error. Local personal rule wins. Sync skips the global copy.
```

Project rule ID matches local personal rule ID:

```text
Error by default. ast-grep would see both.
```

If the user wants a local variation of a project rule, they must use a different ID.

## 15. CLI Specification

The executable is:

```bash
byolsp
```

Every command must support:

```bash
byolsp --version
byolsp --help
byolsp COMMAND --help
```

Commands that operate on a repository must accept:

```bash
--repo PATH
```

If `--repo` is omitted, BYOLSP must search upward from the current working directory for either:

```text
.byolsp/config.yml
sgconfig.yml
.git/
```

Repo discovery rules:

1. Prefer nearest `.byolsp/config.yml`.
2. Else prefer nearest `.git/`.
3. Else use current working directory.

### 15.1 init

Command:

```bash
byolsp init [--repo PATH] [--agents AGENTS] [--ignore-mode project|local] [--non-interactive] [--no-register] [--replace-sgconfig]
```

Purpose:

Initialize BYOLSP in a repository.

Behavior:

1. Create global BYOLSP directory if missing.
2. Create global config if missing.
3. Create global repo registry if missing.
4. Create repository `.byolsp/` directories.
5. Create `.byolsp/config.yml` if missing.
6. Create `.byolsp/local.yml` if missing.
7. Create `.byolsp/state.json` if missing.
8. Create `.gitkeep` files in empty rule directories.
9. Update or create `sgconfig.yml`.
10. Update `.gitignore` or `.git/info/exclude`.
11. Install requested AI agent files or instructions.
12. Register repo globally unless `--no-register`.
13. Run `byolsp sync`.
14. Run `byolsp doctor --quick`.

Interactive behavior:

If `--non-interactive` is not provided, ask:

```text
Which AI integrations should BYOLSP install?
  [ ] generic
  [ ] claude-code
  [ ] codex
  [ ] copilot

Where should local BYOLSP ignore rules be written?
  [x] project .gitignore
  [ ] local .git/info/exclude
```

The prompt can be implemented as plain numbered choices. Do not require a terminal UI library.

`--agents` format:

```text
generic,claude-code,codex,copilot
```

Idempotency:

Running `byolsp init` multiple times must be safe. It must not duplicate YAML list entries, duplicate `.gitignore` blocks, or overwrite user-edited config without an explicit flag.

### 15.2 sync

Command:

```bash
byolsp sync [--repo PATH] [--all] [--check] [--force]
```

Purpose:

Copy enabled canonical global rules into the repository generated global copy directory.

Behavior:

`byolsp sync` syncs the current repository.

`byolsp sync --all` syncs all enabled repos in `~/.config/byolsp/repos.yml`.

`--check` validates that the sync output is current without writing. It exits nonzero if changes would be made.

`--force` allows BYOLSP to remove unmanaged YAML files inside `.byolsp/rules/personal/global/`. Without `--force`, unmanaged YAML files in that directory are an error.

Output example:

```text
Synced 7 global rules into /path/to/repo
Skipped 2 global rules:
  no-python-cast: overridden by project rule
  no-one-line-wrapper: excluded in .byolsp/local.yml
```

### 15.3 doctor

Command:

```bash
byolsp doctor [--repo PATH] [--quick] [--json]
```

Purpose:

Validate installation health.

Checks:

1. ast-grep executable can be resolved.
2. ast-grep version can be read.
3. Repository config exists.
4. Local config exists or can be created.
5. `sgconfig.yml` exists.
6. Required `ruleDirs` are present.
7. Rule directories exist.
8. Rule YAML parses.
9. Required ast-grep rule fields exist.
10. Rule IDs are unique after sync rules are considered.
11. Generated global copies match state.
12. Registered repo path exists.
13. AI hook files exist for configured agents.

`--quick` may skip expensive recursive validation but must still check ast-grep, sgconfig, and directories.

JSON output schema:

```json
{
  "ok": true,
  "checks": [
    {
      "id": "ast_grep_found",
      "ok": true,
      "message": "ast-grep 0.43.0"
    }
  ]
}
```

### 15.4 add

Command:

```bash
byolsp add --scope project|local|global [--language LANGUAGE] [--id RULE_ID] [--from FILE] [--edit] [--repo PATH]
```

Purpose:

Create a new rule in the selected scope.

Modes:

`--from FILE` copies an existing ast-grep YAML rule into the selected scope.

`--edit` opens a generated template in `$EDITOR`.

If neither `--from` nor `--edit` is provided, BYOLSP must print a template path and ask the user to rerun with `--edit` or `--from`.

Template:

```yaml
id: REPLACE_ME
language: Python
severity: warning
message: REPLACE_ME
rule:
  pattern: REPLACE_ME
metadata:
  byolsp:
    rationale: REPLACE_ME
    agent_prompt: REPLACE_ME
    allow_with_comment: false
    tags: []
```

Validation:

1. YAML parses.
2. Required ast-grep fields exist.
3. Rule ID does not conflict illegally.
4. `ast-grep scan --rule RULE_FILE --max-results 1` succeeds syntactically where practical.

Post-action:

Project scope:

```text
write rule -> sync current repo -> doctor --quick
```

Local scope:

```text
write rule -> sync current repo -> doctor --quick
```

Global scope:

```text
write canonical global rule -> sync current repo -> optionally sync all registered repos -> doctor --quick
```

### 15.5 edit

Command:

```bash
byolsp edit RULE_ID [--scope project|local|global|auto] [--repo PATH]
```

Purpose:

Open an existing rule in `$EDITOR`.

Scope resolution:

If `--scope auto`, resolve in this order:

1. Project rule.
2. Local personal rule.
3. Canonical global rule.

Do not open generated global copies for editing. If the resolved file would be under `.byolsp/rules/personal/global/`, map it back to the canonical global source using state.

Post-action:

1. Validate edited rule.
2. Run sync.
3. Run doctor quick.

### 15.6 promote

Command:

```bash
byolsp promote RULE_ID --from local|global --to project [--repo PATH] [--replace]
```

Purpose:

Move or copy a personal rule into shared project rules.

Behavior for `--from local`:

1. Copy local personal rule into project rules.
2. If copy succeeds and `--keep-local` is not passed, remove local personal rule.
3. Run sync.
4. Run doctor quick.

Behavior for `--from global`:

1. Copy canonical global rule into project rules.
2. Do not remove the canonical global rule.
3. Run sync.
4. Sync skips the global copy because project now owns the ID.
5. Run doctor quick.

If destination project rule already exists, fail unless `--replace` is passed.

Do not add promoted global rules to `global.excluded_rule_ids` automatically. The project rule conflict is enough to suppress the generated global copy. If the project rule is later removed, sync should allow the global rule to return.

### 15.7 exclude

Command:

```bash
byolsp exclude RULE_ID [--repo PATH]
```

Purpose:

Disable a canonical global rule in the current repository.

Behavior:

1. Add `RULE_ID` to `.byolsp/local.yml` `global.excluded_rule_ids`.
2. Run sync.
3. Remove generated global copy for that rule.

This command only affects global rules. It must not disable project rules.

### 15.8 include

Command:

```bash
byolsp include RULE_ID [--repo PATH]
```

Purpose:

Re-enable a previously excluded global rule.

Behavior:

1. Remove `RULE_ID` from `.byolsp/local.yml` `global.excluded_rule_ids`.
2. Run sync.
3. If a project or local personal rule still has the same ID, the global rule remains skipped.

### 15.9 list

Command:

```bash
byolsp list [--repo PATH] [--scope project|local|global|effective|all] [--json]
```

Purpose:

Show rules and where they come from.

Effective output must show what ast-grep will see after sync:

```text
project  python.no-missing-type-hints  .byolsp/rules/project/python/no-missing-type-hints.yml
local    python.experimental-api       .byolsp/rules/personal/local/python/experimental-api.yml
global   no-python-cast                .byolsp/rules/personal/global/python/no-python-cast.yml
```

All output must include skipped global rules:

```text
skipped  no-python-cast                overridden by project rule
skipped  no-one-line-wrapper           excluded in .byolsp/local.yml
```

### 15.10 agent-check

Command:

```bash
byolsp agent-check [--repo PATH] [--files FILE ...] [--stdin-files] [--format text|json] [--max-results N]
```

Purpose:

Run ast-grep against files changed by an AI agent and render diagnostics in a form suitable for injecting back into the agent context.

This command exists for hooks. Humans can still use `ast-grep scan` directly.

Behavior:

1. Run `byolsp sync --check`.
2. If sync is stale, run `byolsp sync` unless `--no-sync` is passed.
3. Build an ast-grep scan command:

```bash
ast-grep scan --json=compact --include-metadata --color never FILES...
```

4. Parse the JSON output.
5. For each match, render:
   - file path
   - 1-based line and column
   - rule ID
   - severity
   - message
   - `metadata.byolsp.agent_prompt` if present
   - short matched line
6. Exit 0 when there are no diagnostics.
7. Exit 2 when diagnostics exist.
8. Exit 1 for tool/config errors.

ast-grep JSON match shape currently includes:

```json
{
  "file": "path.py",
  "range": {
    "start": {
      "line": 0,
      "column": 0
    }
  },
  "ruleId": "no-python-cast",
  "severity": "warning",
  "message": "Avoid typing.cast in Python code.",
  "metadata": {
    "byolsp": {
      "agent_prompt": "Do not use typing.cast here..."
    }
  }
}
```

Rendered text example:

```text
BYOLSP found 1 issue in AI-written code.

src/model.py:42:13
Rule: no-python-cast
Severity: warning
Message: Avoid typing.cast in Python code.

Instruction:
Do not use typing.cast here. Fix the type by narrowing, changing the signature,
introducing a protocol, or restructuring the value flow. If the cast is genuinely
necessary, leave a concise comment explaining the invariant that the type checker
cannot see.
```

### 15.11 hook install

Command:

```bash
byolsp hook install --agent generic|claude-code|codex|copilot [--repo PATH]
```

Purpose:

Install agent-specific hook or instruction files.

The command must support agents even if full hook automation is not possible.

Agent support tiers:

`generic`:

Write documentation showing how to call:

```bash
byolsp agent-check --files <changed-files>
```

`claude-code`:

Install a hook configuration if the local Claude Code hook format is detected. If not detected, write instructions under `.byolsp/agents/claude-code.md`.

`codex`:

Write a Codex skill/instruction file if a supported local location is detected. Otherwise write `.byolsp/agents/codex.md` with exact command guidance.

`copilot`:

Write repository instructions compatible with Copilot custom instructions if a supported location is detected. Otherwise write `.byolsp/agents/copilot.md`.

The v1 implementation may start with instruction-file support for all agents and real post-write hooks only where the agent exposes a stable hook API.

### 15.12 hook uninstall

Command:

```bash
byolsp hook uninstall --agent generic|claude-code|codex|copilot [--repo PATH]
```

Purpose:

Remove files created by BYOLSP for an agent.

This command must not delete user-edited files unless they contain a BYOLSP-managed marker.

## 16. AI Instruction Files

BYOLSP must generate AI-facing instructions that are direct and operational.

The generic instruction file should say:

````markdown
# BYOLSP Agent Instructions

This repository uses BYOLSP to expose custom ast-grep diagnostics.

After writing or editing code, run:

```bash
byolsp agent-check --files <changed files>
```

If BYOLSP reports a diagnostic, fix it before continuing.

If a rule says an exception is allowed with a comment, only keep the violating code when the code is genuinely necessary and add a concise comment explaining why.
````

Agent-specific files may add harness-specific hook wiring, but must keep the same core instruction.

## 17. ast-grep Rule Examples Required In Docs

The repository docs must include at least these examples.

### 17.1 Python: Disallow typing.cast

```yaml
id: no-python-cast
language: Python
severity: warning
message: Avoid typing.cast in Python code.
rule:
  pattern: cast($TYPE, $VALUE)
metadata:
  byolsp:
    rationale: >
      typing.cast can hide type model problems. Prefer narrowing, better
      signatures, protocols, or clearer control flow.
    agent_prompt: >
      Do not use typing.cast here. Fix the type by narrowing, changing the
      signature, introducing a protocol, or restructuring the value flow. If
      this cast is genuinely necessary, leave a concise comment explaining the
      invariant the type checker cannot see.
    allow_with_comment: true
    tags:
      - python
      - typing
```

### 17.2 Python: Disallow One-Line Delegating Function

This rule is intentionally approximate. It catches suspicious wrappers and relies on the message to explain the exception policy.

```yaml
id: no-trivial-delegating-function
language: Python
severity: warning
message: Avoid one-line functions that only delegate to another function.
rule:
  pattern: |
    def $NAME($$$ARGS):
        return $CALLEE($$$CALL_ARGS)
metadata:
  byolsp:
    rationale: >
      A function that only routes to another function often adds call-stack
      noise without creating a useful abstraction.
    agent_prompt: >
      Do not add a one-line delegating function unless it creates a meaningful
      boundary, stable public API, semantic name, or compatibility layer. Inline
      the call or use the real function directly. If this wrapper is genuinely
      necessary, leave a concise comment explaining the boundary it protects.
    allow_with_comment: true
    tags:
      - python
      - abstraction
```

### 17.3 Python: Function Definitions Should Have Type Hints

This rule may need refinement with ast-grep constraints. The docs should label it as a starting point, not as perfect policy.

```yaml
id: python.require-return-type
language: Python
severity: warning
message: Add an explicit return type annotation.
rule:
  pattern: |
    def $NAME($$$ARGS):
        $$$BODY
constraints:
  NAME:
    regex: ".*"
metadata:
  byolsp:
    rationale: >
      Return types make function contracts visible to reviewers, editors, and
      static analysis.
    agent_prompt: >
      Add an explicit return type annotation. Prefer the most precise readable
      type. Do not use Any, object, or cast as a shortcut.
    allow_with_comment: false
    tags:
      - python
      - typing
```

The implementation does not need to ship these as enabled default rules. They are documentation examples unless the user explicitly adds them.

## 18. File Ownership and Safety

BYOLSP may create and modify:

```text
sgconfig.yml
.gitignore
.git/info/exclude
.byolsp/**
~/.config/byolsp/**
```

BYOLSP must not modify arbitrary source files.

BYOLSP must only remove files it knows it owns.

Ownership markers:

For generated markdown or hook files, include:

```text
<!-- Managed by BYOLSP. Manual edits may be overwritten. -->
```

For generated global rule copies, track ownership in `.byolsp/state.json`.

If a generated file was manually modified, commands should either:

1. Preserve it and fail with an actionable message, or
2. Overwrite only when `--force` is passed.

Prefer preserving and failing.

## 19. Module Architecture

Package layout:

```text
byolsp/
  __init__.py
  cli.py
  ast_grep.py
  config.py
  doctor.py
  errors.py
  fs.py
  hooks.py
  render.py
  rules.py
  sync.py
  yaml_io.py
tests/
  test_ast_grep.py
  test_config.py
  test_doctor.py
  test_hooks.py
  test_rules.py
  test_sync.py
```

### 19.1 cli.py

Responsibilities:

1. Parse arguments.
2. Call command handlers.
3. Convert expected BYOLSP errors into clean messages.
4. Return correct exit codes.

`main(argv: Sequence[str] | None = None) -> int`

### 19.2 ast_grep.py

Responsibilities:

1. Resolve ast-grep executable.
2. Run ast-grep subprocesses.
3. Parse ast-grep version.
4. Run JSON scans for agent-check.

Do not put BYOLSP rule indexing in this module.

### 19.3 config.py

Responsibilities:

1. Resolve global config directory.
2. Resolve repo root.
3. Load and write BYOLSP config files.
4. Register repositories.

Use typed dataclasses.

### 19.4 yaml_io.py

Responsibilities:

1. Load YAML with `ruamel.yaml`.
2. Write YAML atomically.
3. Preserve comments where possible.
4. Normalize relative paths.

### 19.5 rules.py

Responsibilities:

1. Discover rule files.
2. Parse minimal rule metadata.
3. Validate required fields.
4. Detect duplicate IDs.
5. Map generated global copies back to canonical sources.

Core dataclass:

```python
@dataclass(frozen=True)
class RuleFile:
    id: str
    language: str | None
    message: str | None
    path: Path
    scope: RuleScope
    metadata: Mapping[str, object]
    sha256: str
```

Avoid `Any`. If external YAML values are unknown, use narrow recursive JSON-like type aliases.

### 19.6 sync.py

Responsibilities:

1. Implement sync algorithm.
2. Copy canonical global rules.
3. Remove stale generated copies.
4. Update state.
5. Produce sync summary.

### 19.7 doctor.py

Responsibilities:

1. Run health checks.
2. Return structured check results.
3. Render human or JSON output.

### 19.8 hooks.py

Responsibilities:

1. Install agent instruction files.
2. Uninstall BYOLSP-managed agent files.
3. Detect supported agent config locations.

### 19.9 render.py

Responsibilities:

1. Render agent diagnostics.
2. Render command summaries.
3. Keep text deterministic for tests.

## 20. Error Model

Define one base expected exception:

```python
class ByolspError(Exception):
    exit_code: int = 1
```

Expected errors should not print tracebacks by default.

Unexpected errors may print tracebacks when:

```bash
BYOLSP_DEBUG=1
```

Common expected errors:

```python
class AstGrepNotFound(ByolspError): ...
class ConfigError(ByolspError): ...
class DuplicateRuleId(ByolspError): ...
class RuleValidationError(ByolspError): ...
class UnsafeOverwrite(ByolspError): ...
class RepoNotInitialized(ByolspError): ...
```

Exit codes:

```text
0 success
1 configuration/tool/runtime error
2 diagnostics found by agent-check
3 sync check failed because changes are needed
```

## 21. Atomic Writes

All generated file writes must be atomic:

1. Write to a temporary file in the same directory.
2. Flush and close.
3. Rename into place.

This applies to:

```text
.byolsp/config.yml
.byolsp/local.yml
.byolsp/state.json
~/.config/byolsp/config.yml
~/.config/byolsp/repos.yml
generated hook files
generated global rule copies
```

## 22. Path Handling

Store repository config paths as POSIX-style relative paths.

Use absolute paths only in the global repo registry.

Do not resolve symlinks for repo root identity unless necessary. If a repo is registered through two different textual paths that resolve to the same directory, `doctor` should warn.

## 23. Command Details for ast-grep Invocation

For agent-check:

```bash
ast-grep scan --json=compact --include-metadata --color never --max-results N FILES...
```

If `--max-results` is omitted, do not pass it.

For single-rule validation:

```bash
ast-grep scan --rule RULE_FILE --max-results 1 --color never REPO_ROOT
```

If validation should avoid scanning the entire repo, use a tiny temporary fixture only when the rule language is known and a fixture can be generated safely. Otherwise validate YAML shape and let `doctor` run full validation later.

Do not use `ast-grep scan --off` as part of the normal integration. `--off` works for CLI scans but does not solve LSP behavior.

## 24. Why v1 Uses Copies Instead of Symlinks

ast-grep follows a rule directory if the `ruleDirs` entry itself is a symlink. However, symlinked rule files inside a real rule directory and symlinked child directories inside a real rule directory are not loaded as normal rules. `ruleDirs` also does not accept globbed directories like `.byolsp/packs/*`.

Because v1 needs plain ast-grep LSP and plain ast-grep scan to work with normal `sgconfig.yml`, BYOLSP must use copied generated global rules instead of nested symlinks.

The cost is duplication. The benefit is compatibility.

This must be documented in the repository README.

## 25. AI Hook Behavior

BYOLSP v1 must treat AI integrations as adapters over the same command:

```bash
byolsp agent-check --files <changed files>
```

Each adapter must answer:

1. Where can instructions be installed?
2. Is there a real post-write hook API?
3. How can changed files be passed to `byolsp agent-check`?
4. How is output injected back to the agent?

If an agent does not expose a stable post-write hook API, BYOLSP must still install instructions that tell the agent to run `byolsp agent-check`.

Do not block v1 on perfect hook support for every agent.

## 26. Agent-Check Rendering Requirements

Agent output must be concise, directive, and specific.

Bad output:

```text
warning no-python-cast
```

Good output:

```text
BYOLSP found an issue in AI-written code.

src/types.py:18:12
Rule: no-python-cast
Message: Avoid typing.cast in Python code.

Instruction:
Do not use typing.cast here. Fix the type by narrowing, changing the signature,
introducing a protocol, or restructuring the value flow. If this cast is
genuinely necessary, leave a concise comment explaining the invariant the type
checker cannot see.
```

Multiple diagnostics must be grouped by file, then sorted by line, then by rule ID.

Limit output by default:

```text
max diagnostics rendered: 20
```

If more exist, print:

```text
...and 12 more diagnostics. Run ast-grep scan for the full list.
```

## 27. Security Requirements

BYOLSP must not execute code from rule files.

BYOLSP must not treat YAML values as shell fragments.

Subprocess calls must pass argv lists, not shell strings.

Generated hook commands must quote paths safely.

When opening `$EDITOR`, split only with `shlex.split` and default to:

```text
vi
```

Do not send rule contents or source code to external services.

## 28. Tests

Use pytest.

The minimum test suite must cover:

### 28.1 Config Tests

1. `init` creates expected files in an empty temp repo.
2. `init` preserves existing `sgconfig.yml` keys.
3. `init` appends missing ruleDirs only once.
4. `init` fails on invalid `ruleDirs` type.
5. `.gitignore` block is idempotent.
6. `.git/info/exclude` mode is idempotent.

### 28.2 Rule Tests

1. Rule discovery is recursive.
2. YAML parse errors include file path.
3. Missing `id` is rejected.
4. Missing `rule` is rejected.
5. Duplicate project rule IDs fail.
6. Duplicate global rule IDs fail.
7. Project/global same ID is allowed during sync and project wins.
8. Local/global same ID is allowed during sync and local wins.
9. Project/local same ID fails.

### 28.3 Sync Tests

1. Global rule is copied into personal global directory.
2. Updated global rule overwrites generated copy.
3. Removed global rule removes generated copy.
4. Excluded global rule is not copied.
5. Promoted global rule suppresses generated copy.
6. Unmanaged YAML file in generated global directory causes error.
7. `--force` removes unmanaged generated-global YAML file.
8. State file is updated deterministically.
9. `sync --check` exits with code 3 when stale.

### 28.4 CLI Tests

1. `--help` works.
2. Unknown command exits nonzero.
3. Expected errors do not print tracebacks.
4. `BYOLSP_DEBUG=1` prints tracebacks for unexpected errors.
5. `--repo` works outside the repo.

### 28.5 ast-grep Tests

1. Executable resolution respects `$BYOLSP_AST_GREP`.
2. Executable resolution falls back to `ast-grep`.
3. Executable resolution falls back to `sg`.
4. Missing ast-grep produces actionable error.
5. agent-check parses compact JSON.
6. agent-check includes metadata prompt when present.
7. agent-check falls back to message when metadata prompt is absent.

### 28.6 Hook Tests

1. Generic agent instructions are installed.
2. Hook install is idempotent.
3. Hook uninstall removes only BYOLSP-managed files.
4. User-edited hook files are not deleted without force.

## 29. Type Checking and Linting

Use:

```bash
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv run pytest
```

All public functions must have type hints.

Avoid `Any`.

Avoid `typing.cast`.

Use narrow type guards for YAML values.

## 30. Documentation Requirements

The repository must include:

```text
README.md
docs/rules.md
docs/ai-agents.md
docs/sync-model.md
```

README must explain:

1. BYOLSP means Build Your Own LSP.
2. ast-grep is the rule engine.
3. BYOLSP does not replace ast-grep LSP.
4. `uvx byolsp init` is the recommended start.
5. `ast-grep scan` and `ast-grep lsp` continue to be the primary integrations.

`docs/rules.md` must explain:

1. Rule scopes.
2. Rule metadata.
3. How to add project rules.
4. How to add local personal rules.
5. How to add global personal rules.
6. How promotion works.
7. How exclusions work.

`docs/ai-agents.md` must explain:

1. Generic command integration.
2. Claude Code status.
3. Codex status.
4. Copilot status.
5. How `agent-check` formats output.

`docs/sync-model.md` must explain:

1. Why copies are used instead of symlinks.
2. How sync avoids duplicate ast-grep rule IDs.
3. What happens when global rules change.
4. What happens when a global rule is promoted.
5. What happens when a global rule is excluded.

## 31. README Quickstart

README quickstart must include:

```bash
uvx byolsp init
```

Then:

```bash
ast-grep scan
```

Then:

```bash
ast-grep lsp
```

Then adding a global rule:

```bash
byolsp add --scope global --edit
```

Then syncing:

```bash
byolsp sync --all
```

Then AI check:

```bash
byolsp agent-check --files src/example.py
```

## 32. Acceptance Criteria

The v1 implementation is acceptable when all of these are true:

1. `uvx byolsp --help` works.
2. `uvx byolsp init` creates the repository layout.
3. Existing `sgconfig.yml` content is preserved.
4. ast-grep sees project rules after init.
5. ast-grep LSP can run directly with the generated config.
6. A canonical global rule can be added.
7. `byolsp sync` copies the canonical global rule into a repo.
8. `ast-grep scan` sees the synced global rule.
9. A project rule with the same ID suppresses the generated global copy.
10. A local personal rule with the same ID suppresses the generated global copy.
11. `byolsp exclude RULE_ID` suppresses the generated global copy.
12. `byolsp include RULE_ID` restores it when no project/local conflict exists.
13. `byolsp promote RULE_ID --from global --to project` creates a project rule and avoids duplicate IDs.
14. `byolsp agent-check` runs ast-grep JSON scan and renders `metadata.byolsp.agent_prompt`.
15. `byolsp doctor` reports actionable diagnostics.
16. The test suite passes.
17. The docs explain that BYOLSP means Build Your Own LSP.

## 33. Explicitly Deferred

Do not build these in v1:

1. Rule packs.
2. Symlink-based sync.
3. LSP wrapper.
4. Custom LSP server.
5. Remote rule registries.
6. Rule publishing.
7. Automatic ast-grep installation.
8. Non-ast-grep rule engines.
9. GUI.
10. Background daemon.

## 34. Upstream ast-grep Follow-Up

After v1, consider opening an ast-grep issue requesting one or more of:

1. `ruleDirs` glob support.
2. Loading symlinked files inside rule directories.
3. Loading symlinked child directories inside rule directories.
4. A config-level rule disable mechanism by ID that works for LSP.
5. Global and project config merge semantics.

If ast-grep gains these capabilities, BYOLSP can simplify sync and possibly revisit symlinks or packs.

## 35. Implementation Order

Build in this order:

1. Package skeleton and CLI help.
2. Path/config loading.
3. `init` with repository layout and sgconfig editing.
4. Rule discovery and validation.
5. `sync`.
6. `doctor`.
7. `list`.
8. `exclude` and `include`.
9. `add` and `edit`.
10. `promote`.
11. `agent-check`.
12. Hook instruction installation.
13. Docs.
14. Full tests and type checks.

Do not start with hooks. Hooks depend on the rule and sync model.

Do not start with an LSP. ast-grep already provides the LSP.

## 36. Core Principle

BYOLSP should make custom diagnostics feel native everywhere by arranging plain files so ast-grep already knows what to do.

The winning experience is:

```bash
uvx byolsp init
byolsp add --scope global --edit
ast-grep scan
ast-grep lsp
```

No wrapper. No daemon. No custom editor protocol. Just durable rule files, predictable sync, and sharp AI feedback.
