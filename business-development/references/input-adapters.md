# Input adapters (update mode)

`--update <source>` ingests an existing service document and maps it onto the 10 modules.
Pick the adapter by source type:

| Source | Adapter | Notes |
|--------|---------|-------|
| Uploaded file (already in context) | Use the provided content directly | e.g. an exported HTML/Markdown/PDF the user attached |
| Local file path | `Read` | Any readable text/markdown/HTML file on disk |
| Notion page URL | Notion MCP `notion-fetch` | Load via ToolSearch (`select:mcp__…notion-fetch`) first; the server id is the connected Notion MCP |
| Web URL | `WebFetch` | Public pages; extract the readable content |
| Google Docs URL | — | Not natively fetchable — ask the user to export to Markdown/PDF or share a file path |

## Mapping a source onto the modules

1. Fetch the source with the right adapter.
2. Segment it by heading and match each section to the closest of the 10 modules
   (`references/template-structure.md`).
3. For each module, mark sections **present**, **thin** (needs more detail), or **outdated**.
4. Carry forward good existing content; only interview for the gaps.
5. Preserve any client-specific facts already in the source; never overwrite them with
   profile defaults.

## Large or multiple sources

For a large document (or several), read it into a temporary file first and summarise it
module-by-module before assembling, to keep the working context focused. (A dedicated
`service-document-analyst` agent is a planned v2 enhancement; for now this is done inline.)
