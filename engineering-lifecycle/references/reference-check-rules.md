# Reference Check Rules

What `scripts/references.py` checks, what it deliberately does not, and why each
exclusion earns its place.

## Why there are two standards

An audit of this repository found `ai-utilities/skills/audit-resolver` routing findings
to four plugins and two agents that are not in this marketplace, and telling the reader
to install them from a marketplace that is not this one. Nothing had ever compared a
name written in prose against the set of names that exist.

The obvious fix - check every reference in every document - was measured before it was
built, over 197 markdown files:

| Approach | References | Unresolved | Genuinely dead | Precision |
| --- | ---: | ---: | ---: | ---: |
| Every path-shaped token | 385 | 278 | ~8 | 3% |
| Bare basenames dropped | - | 52 | ~8 | 15% |
| Anchored to a real top-level directory | - | 5 | 5 | 100% |
| Closed-namespace tokens | 20 | 17 | 17 | 100% |

Two standards follow from that. Closed-namespace misses **block**. Path misses
**warn**. Shipping both at error strength would have buried the real findings under
278 false ones, and `anti-slop-register.md` already records what happens then: a
checker that guesses produces noise, and noise gets ignored.

## Blocking rules

Every namespace is rebuilt from the filesystem on each run, so the checker cannot
become the stale document it exists to catch.

| Rule | Fires when |
| --- | --- |
| `namespaced-plugin-ref` | A backticked token shaped `namespace/plugin:name`. Claude Code has no such addressing form, so the shape alone is the finding. |
| `unknown-plugin` | A backticked `plugin:name`, or a `/plugin:command` in prose, whose left side is not a plugin this marketplace ships. |
| `unknown-plugin-member` | The plugin exists, but ships no skill, agent or command by that name. |
| `unknown-command` | The plugin exists, but ships no command by that name. |
| `unknown-wiki-link` | A wiki-style double-bracket link naming no skill, agent or command. |
| `unknown-marketplace` | An `@name` on a line that installs a plugin, naming a marketplace that is not this one. |
| `missing-plugin-file` | A `${CLAUDE_PLUGIN_ROOT}/...` path that does not exist under the plugin owning the document. |

## Advisory rule

| Rule | Fires when |
| --- | --- |
| `unresolved-path` | A path-shaped token, rooted in a directory this repository actually has, that resolves neither relative to the document, nor to its plugin, nor to the repository root, nor by suffix against tracked files. |

Paths inside a backticked command are extracted word by word, because
<!-- ref-check: ignore-next reason="names the dead reference this rule was built to catch" -->
`python tests/scripts/test_smoke.py` names a script exactly as much as a bare path
does - and that is the form two of the dead verifier references were written in.

## Exclusions

Each removes a class measured as a false positive on this repository. The count is
how many it removed here.

| Exclusion | Reason | Removed |
| --- | --- | ---: |
| Bare basenames with no separator | Names a file in the repository the document is *about*, or one generated at runtime. Measured 49 of 49 false. | 49 |
| First segment is not a top-level directory of this repo or of the owning plugin | A path rooted in a directory this repository does not have cannot be describing this repository. This single rule removed 63 of 66 warnings without losing a real one. | 63 |
| First segment is a workspace artifact directory | Names an output under `.project/`, not a file in the repository. | - |
| Anything under `examples/` or `templates/` - **path class only** | Illustrative paths are the entire point of an example. The closed-namespace class is still enforced there, which is how a fictional route in a template was caught. | 12 |
| `CHANGELOG.md` - **path class only** | A changelog describes the state of the world when it was written. A script deleted last year was real at the time. | 40 |
| Fenced code blocks - **path class only** | A command in a fenced block is usually a template for the reader's repository. | - |
| A token containing a metavariable marker | A template, not a claim. Markers: angle brackets, `*`, `|`, `{{`, `${`, `YYYY`, `HHMMSS`, `...` | 5 |
| `_unreleased/`, `.project/`, `node_modules/` and the usual caches | Not this marketplace's documentation, or generated. | - |
| Left side in `TOOL_PERMISSION_PREFIXES` | A tool-permission token, not a plugin reference. This is what keeps a backticked `git` plus a subcommand from reading as a plugin. | 3 |
| Token in `PLACEHOLDER_TOKENS` | A documented metavariable. | - |

## Suppressing a single reference

Two tiers, and both require a stated reason. A bare ignore is indistinguishable from
an oversight six months later, so the pragma without `reason=` is itself a lint error.

Inline, suppressing the rest of the line:

```markdown
See the upstream package `some-org/some-tool`. <!-- ref-check: external reason="npm package, not a repo path" -->
```

On the following line:

```markdown
<!-- ref-check: ignore-next reason="illustrates the broken form on purpose" -->
```

For a whole class, `.reference-allowlist.json` at the repository root - deliberately
**not** under `.project/`, which is gitignored and would silence the checker on one
machine and nowhere else:

```json
{
  "tokens": ["@some-marketplace"],
  "prefixes": ["vendor/"],
  "reasons": { "@some-marketplace": "referenced in migration notes for users coming from it" }
}
```

## Claim checking

`claim_check` handles one further form: a count next to `plugins`, `skills`, `agents`
or `commands`, compared against the set it counts. It is restricted to README files,
and scoped to the owning plugin when the README belongs to one - a plugin README
counting its own skills is correct, and comparing it against the marketplace total is
the false positive that makes a cardinality check useless.

Behavioural claims are out of scope, permanently. "This is fast", "the hook fires
before Y", "this handles X gracefully" have no enumerable other side. Verifying them
means running the thing, which is what an audit is for.

## Where it runs

| Surface | Scope | Blocks |
| --- | --- | --- |
| `PostToolUse` on an edited markdown file | Both classes, silent when clean | No |
| `pre-commit` | Closed-namespace only | Yes |
| `scripts/validate-repo.py`, and therefore CI | Whole repo, closed-namespace only | Yes |
