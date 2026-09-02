---
name: Environment Rule
description: Setting up the environment is the agent's job — the boundary between installing something already declared (do it) and adding a new dependency (ask first).
trigger: always_on
---

# ENVIRONMENT & DEPENDENCY RULES

---

## 1. Setting up the environment is the agent's job

Reporting *"cannot verify — X is missing"* **without trying to install X** is
stopping one command early, not hitting a wall.

Missing tooling, a missing system library, or a dependency the project
**already declares** but this environment hasn't installed yet — that is
something to **install**, not a reason to skip the verification gate:

- **System packages** the app's stack needs to boot (graphics libraries, fonts,
  D-Bus when running a GUI headless). Don't trust a copied list — let the actual
  error (`cannot open shared object file`) name the missing library.
- **A runtime/shell** the gate script needs.
- **An internal library / sibling repository** the project depends on.
- **Any package already pinned in a manifest** that this environment simply
  hasn't installed — install **the pinned version**.

---

## 2. The boundary: installing ≠ adding a dependency

This is **not** permission to add a new dependency to the project.

> **The single test: does the install change a manifest file committed to the
> repository?**
>
> - **Yes** → it's a design decision. **Ask first.**
> - **No** (it only changes what exists on disk in this environment) →
>   **install it and move on.**

---

## 3. Only report "cannot verify" once the install itself failed

And failed for a reason **outside your control**: no network, a registry/proxy
blocking the package, or missing credentials/access to a private repository you
were never given.

Say plainly **which install failed and why**, rather than routing around the gap
by skipping the verification gate.

---

## 4. Runtime version: run CI **on** the floor, don't merely declare it

If the project declares a minimum version, create the environment and **run CI
on exactly that version** — even when a newer one also works.

> **Why:** a developer on a newer version can use syntax only that version has,
> watch every test pass locally, and leave the "supported from version N" claim
> **silently false** — breaking only for whoever installs on the floor. This is
> the same shape as a real bug where a published package **could not be
> imported** while its own CI reported green.

If running CI on the floor isn't possible, add **a guard test** that reads the
floor from the manifest and **re-parses every first-party module at that
version**. It catches syntax, but **not** standard-library APIs that only exist
in newer versions — running CI on the floor covers both.

Raising the floor must be a **deliberate** act: change the manifest, and the
guard follows automatically.

---

## 5. When an API "doesn't exist", the FIRST question is "is the installed build current?"

Before concluding the app references it wrongly:

> **Real evidence:** three errors of the form `AttributeError: type object 'X'
> has no attribute 'Y'` and `TypeError: __init__() got an unexpected keyword
> argument` were **all misdiagnosed** as "the app uses a non-existent API". All
> three APIs **really existed** in the library's repository. The installed build
> was simply older — **and both builds reported the same version number**, so
> checking the version told you nothing.

Check by **real signature**, not by a version string:

```bash
<python> -c "import inspect; from <pkg> import <Thing>; print(inspect.signature(<Thing>.__init__))"
```

And check the install **source**, not just the version — an outdated build often
comes from a stale local checkout (`file:///...`) rather than from the registry:

```bash
<pip> list | grep <pkg>
```
