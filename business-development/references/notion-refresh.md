# Refreshing bundled templates from Notion

The 10 module templates are **bundled** in the plugin so normal operation is fast and
offline. Notion is where they were authored. `--refresh` re-pulls the latest from Notion and
rewrites the bundled files — a **confirmation-gated, mutating** action.

## Module → Notion page id

| Module file | Notion page id |
|-------------|----------------|
| `01-service-overview.md` | `39966f0b815580f3a7e3ef9c460850cd` |
| `02-customer-fit-and-qualification.md` | `39966f0b815580aa8c9df986b8457698` |
| `03-scope-and-deliverables.md` | `39966f0b81558063ba7af068bc7ed2dc` |
| `04-delivery-plan.md` | `39966f0b8155808f97eac953f67ef405` |
| `05-roles-responsibilities-and-client-inputs.md` | `39966f0b815580e3b99ac3b67712bc18` |
| `06-success-measurement-and-reporting.md` | `39966f0b81558042996bef5068e337e1` |
| `07-risks-dependencies-and-constraints.md` | `39966f0b815580dfb195fca0e34f2330` |
| `08-technical-security-and-compliance-addendum.md` | `39966f0b815580dca280c1d90f320149` |
| `09-ai-service-addendum.md` | `39966f0b81558079a954fb0f9890f661` |
| `10-support-warranty-and-handover.md` | `39966f0b8155809bbd4bce5e50e91b67` |
| `internal-service-brief.template.md` | `39966f0b815580bc8830c65fda090458` |

Container ("Services") page: `39966f0b815580e9834bcd0ea930f6cf`.

## Refresh steps

1. Load the Notion MCP tool via ToolSearch (`select:mcp__…notion-fetch`).
2. For each module, `notion-fetch` its page id and convert the content to the module
   template format (H2 title, H3 subsections, `[bracketed]` placeholders, tables preserved).
3. **Show the user a diff** against the current bundled file and confirm before overwriting.
4. After refresh, keep the ids above in sync if pages are renamed or moved.

Normal (non-`--refresh`) runs never touch Notion — they read the bundled files only.
