# SPEC-000 — the template (copy this file, do not edit it)

- **Status:** 🔵 specified, not built
- **Actor:** who is doing this — trader, operator, developer. Not "the user" if a narrower word fits.
- **Origin:** what asked for this — a `US-xx` from `Tasks/UserStory_Propose.md`, a `PRO-xxx`, a
  `BOT-xxx`, or "measured from the code" when the spec was written after the fact.
- **Surfaces:** the screens and commands this use case is reachable from.

## 1. Trigger

The one sentence that starts it, in the actor's words. *"I want to see this symbol's chart and
it has no data yet."*

## 2. Preconditions

What must already be true. Each line is checkable — not "the app is set up" but
"`secrets.local.json` holds a Futures Testnet key pair".

## 3. Main flow

Numbered, one action or one system response per line. The actor's steps and the system's
answers interleave, so a reader can follow it with the app open.

1. The actor …
2. The app …

## 4. What must be true afterwards

The observable result, in terms the actor can check. Not "the repository was written to" but
"re-opening the screen shows the new candles without another sync".

## 5. When it goes wrong

| What goes wrong | What the actor sees | Why it is this and not a crash |
| :--- | :--- | :--- |

Every row is a **named** outcome, not an exception the actor has to interpret. A flow with no
failure rows is almost always an unfinished spec: the network, the credentials and the empty
store are the three that apply to nearly everything here.

## 6. What this use case does NOT promise

The line a reader would otherwise assume. This section is what keeps the app from being read as
more capable than it is (`domain-truth-rule.md`).

## 7. Ports and modules it exercises

Which published contracts carry it (`modules/<id>/contracts/`), so a change to one of them can
find the use cases it affects. Names, not paths — a rename is a rename.

## 8. Proven by

| Evidence | Where | Tier |
| :--- | :--- | :--- |

Every path here must exist: the guard checks it. A step only a person can verify is written as
**the user runs it**, with what they must see — those are the steps a green gate cannot cover,
and naming them is how they stop being forgotten.
