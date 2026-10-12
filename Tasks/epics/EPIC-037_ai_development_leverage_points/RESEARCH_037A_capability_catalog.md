# Research for EPIC-037A — how an agent learns a shared mechanism exists at the moment it decides

Recorded 2026-10-12 for [`EPIC-037A`](incomplete/EPIC-037A_capability_catalog.md). Sources were read or searched on that date; a claim a source does not state is marked *(inferred)*. Question: what delivers "this mechanism already exists" to an AI session at the moment it chooses what to write, and keeps that statement true as the code changes?

## 1. Delivering project knowledge just in time

| Source | What it does | We take | We reject, and why |
| :--- | :--- | :--- | :--- |
| [Claude Code memory and rules](https://code.claude.com/docs/en/memory) | `.claude/rules/*.md` with `paths:` front matter load "when Claude uses the Read, Write, or Edit tool on a matching file"; rules without `paths:` load at launch. `paths` is the only field read; globs support braces. | The loader itself. The catalog is one path-scoped rule, so it costs nothing in a session that touches no matching file. No new loader. | The docs say rules are "context, not enforced configuration": the catalog informs, so the guards (§2) carry enforcement. |
| Cursor rules (`.cursor/rules/*.mdc`): [overview of the four types](https://morphllm.com/cursor-mdc-rules), [forum](https://forum.cursor.com/t/my-take-on-cursor-rules/67535) | Type is inferred from front matter: always-apply, auto-attached by `globs`, agent-requested by `description`, manual (`@rule`). Guides advise keeping always-apply rules short because every token loads in every request. | Confirms the two-tier split we already use (always vs by glob); confirms short always-loaded text. | Agent-requested rules (the model decides from a description whether to pull the rule): the failure we are fixing is exactly an agent that does not know to ask. |
| [AGENTS.md](https://www.tembo.io/blog/agents-md), [monorepo guide](https://www.mintlify.com/agentsmd/agents.md/guides/monorepos) | A plain Markdown file for agents; the spec says the file nearest the edited file wins, so a package can carry its own. Tools differ on precedence (secondary sources). | Idea of the guidance sitting next to the code it describes: the marker lives in the module that provides the mechanism. | A per-directory `AGENTS.md` under `src/support/*`: Claude Code does not read it as an on-demand rule, so it would add a second loader. |
| [llms.txt](https://llmstxt.org/) (Howard, 2024-09-03) | A Markdown index at a site root: name, summary, links to detail. A proposal; no major provider has confirmed consuming it (secondary source, early 2026). | The row shape: one line per item, a pointer, the detail left at the target. | Treating it as a standard that agents already read: unproven, and ours is for the repository's own sessions. |
| [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) (Anthropic, 2025-09-29) | Context is finite; find "the smallest set of high-signal tokens". Agents keep "lightweight identifiers" (paths, names) and load the data just in time; folder structure and naming signal relevance. | The design principle: the catalog holds identifiers (symbol, path, one user), not explanations; the detail stays in the module docstring a session opens next. | Preloading the HLD: the epic analysis (§3 of the analysis file) shows more preloaded text feeds loop R1. |
| [Model Context Protocol resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources) | Resources are addressed by URI and "application-driven": the host decides how they enter context (picker, search, automatic). | The addressing idea: a row is a stable identifier an agent can resolve. | Building an MCP server for a table of ~30 rows: a process to run and secure, against a file the existing loader already delivers. Revisit if the catalog outgrows one file. |
| [Aider repo map](https://aider.chat/docs/repomap.html) | Tree-sitter extracts definitions; references rank symbols (PageRank, secondary source); the map is fitted to a token budget and sent up front. | Confirms that a compact symbol map beats raw files for choosing what to touch. | Ranking by reference count: the symbol most worth reusing (a new picker) is the least referenced, and a count says nothing of *need*. Also an up-front map is the preload we avoid. |

**Finding.** Every tool delivers by *scope* (path or description) and holds *identifiers*, not prose. Only path scope is deterministic, because the trigger is an act the agent cannot skip: opening a file. That is why the catalog is path-scoped.

## 2. Keeping a catalog true to the code

| Source | What it does | We take | We reject, and why |
| :--- | :--- | :--- | :--- |
| [Backstage descriptor format](https://backstage.io/docs/features/software-catalog/descriptor-format) | `catalog-info.yaml` lives in each repository; `Component` needs `type`, `lifecycle` (`experimental`/`production`/`deprecated`), `owner`; `dependsOn`/`consumesApis` are relations. | A `Status` field with a deprecated state; a row naming the thing's real consumers. | A separate YAML per package: the source states no sync mechanism *(the page does not say)*, and a file apart from the module is the drift we want to avoid. `owner` is meaningless in a one-team repository. |
| Docstring conventions: [Napoleon](https://sphinix-doc.readthedocs.io/en/latest/extensions/napoleon.html), [pydoctor Google/NumPy](https://pydoctor.readthedocs.io/en/stable/docformat/google-numpy.html) | Google style: `Args:` heading, indented entries. NumPy: underlined headings. Sphinx: reST field lists (`:param x:`). | Google's shape for a labelled block: a heading line then indented `Key: value` lines. It reads well in a source file and cannot collide with prose because the heading is fixed. | reST fields (`:capability:`): ugly in source, and nothing here renders Sphinx. NumPy underlines: two extra lines per block. |
| [griffe](https://mkdocstrings.github.io/griffe/) | Builds objects by parsing source into an AST rather than importing; parses Google, NumPy and Sphinx docstrings (aggregator pages; official docs returned 404 on fetch). | The mechanism: read docstrings with `ast`, never import, so the generator needs no Qt and runs in any job. | The dependency: stdlib `ast.get_docstring` is enough, and `pyproject.toml`/requirements are the owner's to change. |
| [import-linter](https://import-linter.readthedocs.io/) contract types (forbidden, independence, layers) | Contracts declared in config, checked in CI against the real import graph. | The idea that a declaration is only as good as the check that runs it: our `User:` line is verified by an AST import check, not trusted. Pairs with `EPIC-037C`'s "only one" guards. | Adding the tool: a dependency, and the repository already has 59 AST guards in this style. |
| `__all__` (Python language reference) | A module's declared public names. | The `Use:` symbols must be defined in, or re-exported by, the marked module: the same test `__all__` implies. | Deriving rows from `__all__` alone: it lists what is public, not what is *worth reusing for which need*; `ui_kit` exports dozens. |

**Finding.** A catalog stays true when (a) it is generated from declarations next to the code, (b) every claim in a declaration is checked against the tree (symbol defined, user imports it), and (c) a completeness check fails when something exists with no declaration. Backstage and import-linter show (b) and (c) are separable from the file format.

## 3. Walking skeleton

- Alistair Cockburn, *Crystal Clear* (2004) and his site: a tiny implementation of the system that performs a small end-to-end function, linking the main architectural components; it need not use the final architecture and is meant to evolve, unlike a throwaway spike ([summary of the definition](https://henricodolfing.com/2018/04/start-your-project-with-walking-skeleton.html)).
- Freeman and Pryce, *Growing Object-Oriented Software, Guided by Tests* (2009): "the thinnest possible slice of real functionality that we can automatically build, deploy, and test end-to-end" (quoted by [a secondary summary](https://learnagilepractices.substack.com/p/first-steps-in-code-the-significance)); the earliest tests drive the first slice.
- Gojko Adzic, [put it on crutches](https://gojko.net/2014/06/09/forget-the-walking-skeleton-put-it-on-crutches/): a skeleton is judged by what it lets you learn, not by being complete.

**We take** the definition literally for this task: commit A touches every part of the mechanism (marker, generator, rule file with `paths:`, completeness guard with a shrink-only baseline, Reuse section, rubric row, navigation rows) with three real entries, so the cheap question "does the whole chain run?" is answered before the expensive one ("are all packages marked?"). **We reject** a throwaway prototype: the skeleton's files are the final files.

## 4. Other approaches to "the agent does not know it exists"

| Approach | Verdict |
| :--- | :--- |
| Code search (grep for the word) | Already available and it failed in `BUG-155`: the developer-facing word was "symbol picker", the session searched for what it was building. The catalog's `Also:` synonyms target this gap. |
| A reviewer finding duplicates after the fact | The current loop (analysis §3, B1). It acts after the cost is paid. The Reuse section moves the same question to the moment of design. |
| "Only one" guards | Complementary, not an alternative: `EPIC-037C` makes a second copy red. They need this catalog to know what the canonical mechanism is. |

## 5. What the research changed in the plan

1. **Marker form:** Google-style labelled block in the module docstring (§2), not a decorator, constant or sidecar file.
2. **Verification:** claims are checked by AST (griffe's lesson, import-linter's lesson), not trusted.
3. **Size:** identifiers only (Anthropic, llms.txt); synonyms are the one addition, because the failure was a vocabulary miss.
4. **No agent-decided loading** (Cursor "agent requested"): path scope only.
5. **Skeleton before fill** as defined by Cockburn and GOOS.
