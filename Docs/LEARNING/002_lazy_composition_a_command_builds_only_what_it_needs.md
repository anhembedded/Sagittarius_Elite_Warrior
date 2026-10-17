Status: Current

# 002 — Lazy composition: a command builds only what it needs

Teaches the change of [`PRO-014`](../../Tasks/proposal/PRO-014.md) (task [`BOT-188`](../../Tasks/completed/BOT-188_a_command_loads_only_the_modules_it_needs.md)). The mechanism is `shell/module_selection.py` → `select_modules`, `shell/modules.py` → `ModuleEntry`, and `core/contracts/deferred.py` → `Deferred`.

## 1. The problem

On the owner's VPS (one small Ubuntu box) every short command spent about 3 s before the application logged its first line. `main.py bot list` took 3.7 s; composing the application, running the query and disposing it took 0.057 s of that. The Python interpreter starts in 0.033 s and `sudo` in 0.018 s, so neither was the cause. `python -X importtime` showed where the time went: **importing code**. The command that reads a file imported every bounded context, the exchange SDK (`binance`, with `dateparser`, `aiohttp`, `requests`) and `pyarrow`.

## 2. Constraints

- Every command's behaviour and output stays the same; the host (`run`) and the desktop application still get everything.
- The architecture guards stay green: no function-local imports, layers point inward, a context imports another only through its `contracts/`.
- The Engine (a separate repository) refuses a context whose declared dependencies are not registered.
- No resident process: out of scope, a later option.

## 3. Solutions considered

| Option | For | Against |
| :--- | :--- | :--- |
| Compile the checkout once (`python -m compileall`) | One command; saves about 0.6 s | The other ~3 s is not compilation, it is running the module bodies. Kept as a runbook step. |
| Make the heavy libraries lazy at their adapters only | Smallest per-file change | Saves the SDK (about 0.4 s) and nothing of the contexts' own 400+ modules. |
| Stop importing SDK exception classes to map exit codes | One file | It was one of seven places that import the SDK. |
| **A command declares the contexts it needs; the composition root builds those and their suppliers; the adapters that import the SDK are named by path** | Measurable cut for every read command; a new command is one JSON line | The saving is bounded by the suppliers a context drags in. |
| A resident process answering read commands over a socket | Near-zero latency per command | A second long-lived thing to secure and supervise. Out of scope. |

## 4. The choice and why

Two cuts, because the cost had two kinds. **Which contexts a run registers** is a property of the command, so it is declared where the command is (`cli_commands.json`, the same place that already says whether a command is read-only), not computed from the code. **Which libraries a context imports** is a property of the adapter, so the class that imports the SDK is named by `Deferred("package.module:Class")` and imported on the first call that needs it. The absent declaration means "everything": the safe direction, and exactly what every command had before.

## 5. How it is implemented

```text
main.py bot list
  -> command_needed_modules(commands, args)      -> {"bots"}            (cli_commands.json)
  -> create_app(..., needed_modules={"bots"})
       select_modules(MODULES, {"bots"})         -> market_data, trading, bots   (+ suppliers, list order)
       register_modules(app, entries)            -> entry() imports <module>.module only now
```

`ModuleEntry("bots", "BotsModule")` names the class by path, so reading the list imports nothing. Inside the contexts, the trading venue assembly, the websocket service, the Parquet writer and the writable half of the bots' boot are reached the same way, each at the call that needs it.

## 6. Risks and failure modes

- **A path string escapes the type checker.** `tests/unit/architecture/test_every_deferred_literal_resolves.py` resolves every literal in `src/`.
- **A command declares too few contexts.** It fails at the first resolve, in a process nobody ran. `tests/integration/presentation/test_a_read_command_imports_only_what_it_needs_process.py` runs the declared sets for real.
- **The static "headless imports no Qt" guard stops seeing the contexts.** It now follows `Deferred` and `ModuleEntry` strings (it stops at a `ui` package).

## 7. Limits

A context drags in its suppliers (`bots` needs `trading` and `market_data`), and the Engine's health query imports the SQL toolkit for every run. What is left after this change is the cost of registering three contexts and of the Engine, about 55% of what a `bot list` paid in the container (1.8x faster, not the 2x hoped for). Going lower means a read path that does not register the suppliers at all, or a resident process.

## 8. Names to know

Lazy loading, lazy initialization, composition root, dependency closure (a transitive-dependency selection), import-time side effects, `python -X importtime`, the *Main* component (Martin).

## 9. Interview questions

1. *Where does the start-up time of a Python CLI go, and how do you find out?* Mostly imports; `python -X importtime` gives per-module cumulative and self time, and the first importer pays for a shared library.
2. *Why not make every import lazy inside functions?* It hides dependencies from tools and tests, moves failures to run time and breaks "all imports at the top"; a named lazy reference in one place keeps a guard able to check it.
3. *Why declare the contexts per command instead of detecting them?* Detection needs the code imported, which is the cost; a declaration is checked by a test and is the safe default when absent.
4. *Why must dependencies come along?* The framework refuses a registered component whose declared dependency is missing, and a component reads its supplier's ports.
5. *When is a resident process better?* When start-up cost cannot go below the interpreter and library floor and the command rate is high.

## 10. Read more

- Python documentation, `-X importtime`, and `importlib.import_module`.
- Robert C. Martin, *Clean Architecture*, the *Main* component.
