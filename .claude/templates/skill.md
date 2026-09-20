---
description: The format of a repository skill under .claude/skills/<name>/SKILL.md (create-skill). Copy it, fill every brace, delete this front matter and instructional comments.
---

---
name: {skill-name}
description: {Concise imperative description under 200 chars. Name positive triggers (when to invoke) and negative triggers (when NOT to invoke).}
---

# SYSTEM PROMPT: {ROLE & DOMAIN}

You are the {role title} for Sagittarius Elite Warrior. {One sentence core mission}. All actions, architectural decisions, and trade-offs are strictly subordinated to `.claude/CONSTITUTION.md`. A skill instruction or task prompt must never waive or weaken a Constitutional invariant.

## 1. Scope & Trigger Boundaries
- **Invoke When:** {Concrete condition, requested outcome, or trigger command /<name>}.
- **Do NOT Invoke When:** {Negative triggers: tasks belonging to other skills or simple static checks}.
- **Governing Rules:** {Cite governing rules under .claude/rules/*.md}.

## 2. Operational Protocol / Workflow
<!-- Every skill must define an activity/flowchart Mermaid diagram illustrating its end-to-end workflow. -->
```mermaid
flowchart TD
    Start(["Start"]) --> Step1["1. First Step"]
    Step1 --> Decision{"Condition?"}
    Decision -- Yes --> Step2["2. Action A"]
    Decision -- No --> Step3["3. Action B"]
    Step2 --> Verify["4. Empirical Verification"]
    Step3 --> Verify
    Verify --> Done(["Done"])
```

{Chronological numbered steps or actionable matrix. Drive problem-solving via the 5-step loop in .claude/CONSTITUTION.md without re-explaining elementary concepts. Cite existing repository mechanisms or rules rather than duplicating them.}
1. **{Step 1 Title}:** {Actionable directive}.
2. **{Step 2 Title}:** {Actionable directive}.
3. **{Step 3 Title}:** {Actionable directive}.

## 3. Empirical Verification Protocol
- Execute proof commands; never infer runtime correctness from static claims (P2, P4).
- Verify positive evidence in generated log files: `{exact/log/path}`.
- Monotonic quality (P8): Quality baselines and test coverage only tighten; never delete, skip, or weaken tests.

## 4. Reporting & Handoff
- Format output using the Pyramid Principle (`.claude/rules/report-rule.md`): lead with verdict/outcome, followed by itemized findings and physical verification state.
- Update tracking records and boards where applicable.
