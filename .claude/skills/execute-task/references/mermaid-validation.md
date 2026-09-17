# Validate Mermaid before showing it

Use this for every Mermaid diagram in a user report, including each epic Kanban refresh. Use the official [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli) to parse and render the exact draft to SVG. This is a reporting check, not a replacement for the application's CI gate.

## Tool and setup

The verified invocation uses `@mermaid-js/mermaid-cli@11.17.0` through `npm exec`; Node/npm and a Puppeteer-compatible browser are required. The package runs from npm's cache. Do not create an application package manifest or add a runtime dependency for reporting.

On first use, npm downloads the CLI and Puppeteer's browser. If a compatible Chrome is already installed, set `PUPPETEER_SKIP_DOWNLOAD=true` for that setup command and pass a temporary Puppeteer JSON config with its verified `executablePath` through `--puppeteerConfigFile`. Check that path exists; do not hard-code another machine's browser path or disable its sandbox as a routine workaround. Follow `install-rule.md` for environment setup failures.

## Draft, check, show

1. Write the exact diagram body to a UTF-8 `.mmd` file in a unique temporary directory, without the Markdown fence. Include the final labels and translated text now. Keep its SVG and logs outside tracked source files.
2. Render using the command below. Use a fresh output path for this attempt so an old SVG cannot masquerade as success. Capture the command, CLI version, exit code, input SHA-256 and output path.
3. Require **exit code 0 and a newly generated, non-empty SVG**. A syntax error means fix the `.mmd` and rerun. Installation, browser or process failures mean validation could not run; they are not PASS and not necessarily syntax errors.
4. Read back the validated file and use that exact content inside the displayed `mermaid` fence. Do not retype, translate or adjust it after checking. Any content change requires another run; unchanged content may reuse its recorded successful check.
5. A successful render validates this CLI/browser combination, not the chat client's Mermaid version. If chat rendering is unsupported, provide the validated SVG when deliverable or a table with the same state. If validation cannot run, explain the concrete blocker and show the table only; do not present an unchecked Mermaid block as the required diagram.

Run from the repository root, replacing the paths with the actual absolute temporary paths:

```text
npm exec --yes --package=@mermaid-js/mermaid-cli@11.17.0 -- mmdc --input "<draft.mmd>" --output "<fresh-output.svg>"
```

On Windows PowerShell use `npm.cmd` and inspect `$LASTEXITCODE`; on POSIX shells use `npm` and inspect `$?`. Do not infer success from the presence of a prior file or a line of console text.

PowerShell checks after the command, with `$mermaidSource` and `$mermaidOutput` set to those paths:

```powershell
if ($LASTEXITCODE -ne 0) { throw 'Mermaid validation failed; read the captured error.' }
if (!(Test-Path -LiteralPath $mermaidOutput) -or (Get-Item -LiteralPath $mermaidOutput).Length -eq 0) {
    throw 'Mermaid produced no SVG.'
}
Get-FileHash -LiteralPath $mermaidSource -Algorithm SHA256
Get-Content -LiteralPath $mermaidSource -Raw -Encoding utf8
```

Do not place unchecked drafts in a rendered Mermaid fence while debugging in chat. A text description of the parser error is enough. Before adopting a new CLI version, rerun a valid Kanban, a deliberately broken Kanban and a valid non-Kanban diagram; the broken example must exit nonzero. Visual clarity and correct task state still require inspection after syntax succeeds.
