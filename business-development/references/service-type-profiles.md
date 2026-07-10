# Service-type profiles

Each service type has a YAML profile in
`skills/service-outline/templates/service-types/<type>.yaml`, validated by
`schemas/service-type-profile.schema.json`. A profile does two things:

1. **Switches the conditional addenda** via `include_addenda`.
2. **Seeds defaults** (tools, deliverables, timeline, pricing model, metrics, risks) so the
   interview starts from a realistic draft rather than a blank page.

Profile values are always **starting points** — the interview confirms and overrides them.

## `include_addenda` values

| Value | Meaning |
|-------|---------|
| `true` | Include the addendum by default. |
| `false` | Exclude it by default. |
| `"interview"` | Decide during the interview (ask the trigger question). |

## Per-type summary

| Profile | Module 8 (Tech/Sec) | Module 9 (AI) | Default timeline |
|---------|---------------------|---------------|------------------|
| `consulting` | interview | no | Audit 1-2 wk / strategy 2-4 wk |
| `ai-engineering` | yes | **yes** | Prototype 2-6 wk / system 6-16+ wk |
| `software-development` | yes | interview | 6-16+ wk |
| `web-design` | yes | no | 4-10 wk |
| `ai-ppc-optimisation` | interview | **yes** | Sprint 2-4 wk / ongoing |
| `branding` | no | no | 3-8 wk |
| `generic` | interview | interview | inferred |

## Adding a new service type

1. Copy `generic.yaml` to `<new-type>.yaml`.
2. Set `service_type`, `display_name`, `category`, `engagement_type`.
3. Set `include_addenda` and seed the defaults.
4. Validate against the schema.

If `--type` is missing or unrecognised, the skill falls back to `generic.yaml` and infers
everything from the interview.
