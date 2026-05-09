---
name: frontend-architect
description: Establish the frontend design system before any UI feature work. Surveys existing pages and components, commits to a bold aesthetic direction (drawing on /frontend-design thinking), chooses a CSS framework, defines design tokens, and produces docs/design/frontend-system.md as the spec all subsequent /feature agents implement against. Stops for human review before implementation.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Skill, TodoWrite
---

# Frontend Architect

Establishes the frontend design system for the project. This skill runs **once** before UI feature work begins. Its output — `docs/design/frontend-system.md` — becomes the mandatory design reference for every subsequent UI feature, the same way ADRs and LLDs govern backend decisions.

**Model:** Use Opus for this skill. When launching sub-agents, pass `model: "opus"`.

**Usage:**

- `/frontend-architect` — surveys the codebase and produces the design system spec

## Process

### Step 1: Survey the existing frontend

Read all of the following to understand what already exists:

1. Root layout / app shell (e.g. `src/app/layout.tsx` for Next.js, `src/App.tsx` for Vite/React)
2. Authenticated layout wrapper if the app has auth
3. All page/route components under the pages directory
4. All shared components (e.g. `src/components/**/*`)
5. `package.json` — check for any existing CSS/UI framework dependencies
6. Any `.css` files under `src/`
7. Framework config files (e.g. `tailwind.config.*`, `postcss.config.*`, `vite.config.*`)
8. `docs/design/` — check if any frontend design decisions already exist
9. `docs/adr/` — check for relevant ADRs (e.g., CSS framework choices)

The exact paths depend on the project's framework — read `CLAUDE.md` and `kb/conventions.md` for the project's conventions. Do not assume Next.js App Router.

Summarise what you find:
- How many pages exist and what they do
- What components exist
- What CSS/styling approach (if any) is currently in use
- What is visually missing (layout, typography, colour, spacing)

### Step 2: Commit to an aesthetic direction

Draw on the `/frontend-design` approach: **do not default to generic "AI slop"**.

Consider the product context:
- **Audience:** engineering teams and engineering managers
- **Purpose:** measure and surface team knowledge through structured assessments
- **Tone options:** refined/utilitarian (think Linear, Vercel), editorial/data-forward (think Grafana, Retool), minimal/focused (think Notion, Linear)

Choose a **specific, intentional aesthetic** and justify it. Document:

- **Aesthetic direction:** one sentence describing the visual character (e.g., "refined dark-mode utility tool — think Linear meets a developer dashboard")
- **Why it fits:** one sentence on why this suits the product and audience
- **What makes it memorable:** one distinctive design choice (e.g., subtle grid lines, a strong typographic hierarchy, a specific accent colour)

**Avoid:** purple gradients, Inter + white backgrounds, generic SaaS blue, cookie-cutter Tailwind defaults.

### Step 3: Choose the CSS/component approach

Evaluate options appropriate to the project's framework (read `CLAUDE.md` and `package.json` to identify it):

| Concern | Common options (by framework) |
|---------|------------------------------|
| CSS framework | Tailwind CSS, CSS Modules, styled-components, Panda CSS, Vanilla Extract |
| Component primitives | shadcn/ui, Radix bare, Headless UI, Ark UI, framework-native |
| Icons | lucide-react, heroicons, phosphor (or framework equivalents) |
| Fonts | `next/font`, `@fontsource`, local fonts, Google Fonts CDN |

Base your recommendation on the project's framework, not on a generic default. Record the final choices and the rationale. If you make a non-obvious technology choice, document why as an ADR using `/create-adr`.

### Step 4: Define design tokens

Commit to specific values. Do not use vague descriptions — every token must be an exact CSS variable value or Tailwind config entry.

#### Colour palette

Choose 5–7 colours. Name them semantically:

```css
--color-background:    /* page background */
--color-surface:       /* card / panel background */
--color-surface-raised: /* elevated surface (dropdown, modal) */
--color-border:        /* subtle dividers */
--color-text-primary:  /* headings, labels */
--color-text-secondary: /* supporting text, captions */
--color-accent:        /* CTAs, active states, links */
--color-destructive:   /* errors, delete actions */
```

Pick light mode, dark mode, or both — document the choice and reason.

#### Typography

Choose two fonts with rationale:

```
Display font: [name] — [why: character, associations, contrast with body]
Body font:    [name] — [why: readability, pairing, availability]
```

Define the type scale (map to Tailwind `fontSize` config or CSS variables):

| Token | Size | Weight | Use |
|-------|------|--------|-----|
| `text-heading-xl` | e.g. 2rem | 700 | Page titles |
| `text-heading-lg` | | | Section headings |
| `text-heading-md` | | | Card titles |
| `text-body` | | | Body copy |
| `text-label` | | | Form labels, table headers |
| `text-caption` | | | Metadata, timestamps |

#### Spacing & layout

```
Page max-width:   e.g. 1280px
Content padding:  e.g. 24px (mobile), 48px (desktop)
Section gap:      e.g. 32px
Card padding:     e.g. 20px
```

#### Border radius & shadow

```
Radius-sm:  e.g. 4px  — inputs, badges
Radius-md:  e.g. 8px  — cards, panels
Radius-lg:  e.g. 12px — modals, dialogs
Shadow-sm:  e.g. 0 1px 3px rgba(0,0,0,0.1)
Shadow-md:  e.g. 0 4px 16px rgba(0,0,0,0.15)
```

### Step 5: Define the layout shell

Describe the page structure all authenticated pages will share:

```
AuthenticatedLayout
  ├── NavBar (top, full-width)
  │   ├── Logo / app name
  │   ├── Primary nav links
  │   ├── OrgSwitcher
  │   └── User menu (username, sign-out)
  └── <main> (centred, max-width, horizontal padding)
      └── page content
```

Specify:
- NavBar height, background, border
- Whether a sidebar is needed (probably not for MVP)
- Page header pattern (title + optional subtitle + optional actions)
- Whether pages use a card container or full-bleed layout

### Step 6: Define shared component patterns

For each component that multiple pages will need, specify the expected visual pattern:

| Component | Description |
|-----------|-------------|
| `PageHeader` | Page title + optional subtitle + optional right-side action button |
| `Card` | Surface container with padding and border |
| `Button` variants | Primary, secondary, destructive, ghost — with size variants |
| `Badge` | Status pill for assessment states (pending, ready, etc.) |
| `EmptyState` | Centred illustration area + message + optional CTA |
| `LoadingState` | Skeleton or spinner pattern |
| `FormField` | Label + input + error message layout |

These are **patterns**, not full implementations — enough for `/feature` agents to know what to produce.

### Step 7: Produce docs/design/frontend-system.md

Write the design system document combining all decisions from Steps 1–6.

Structure:

```markdown
# Frontend Design System

## Document Control
[version, date, status]

## Aesthetic Direction
[one paragraph: what it looks like, why, what's memorable]

## Technology Choices
[CSS framework, component library, icons, fonts — with rationale]

## Colour Tokens
[CSS variable definitions + palette rationale]

## Typography
[font choices, type scale table]

## Spacing & Layout
[tokens, page shell diagram]

## Component Patterns
[table of shared components with visual description]

## Bootstrap Tasks
[ordered list of what must be done before any feature uses this system]
```

The **Bootstrap Tasks** section is critical — it lists the one-time setup work that must happen before any feature can use the design system. Tasks vary by framework; derive them from the choices in Step 3. Example for a Tailwind/Next.js setup:

1. Install dependencies (CSS framework, component library, icons, fonts)
2. Create global stylesheet with CSS variables and framework base
3. Create framework config with extended design tokens
4. Update root layout to import global styles and set font variables
5. Update authenticated shell layout with the layout shell styles

The exact file paths depend on the project's framework — use `CLAUDE.md` and `kb/conventions.md` for the correct paths.

Each bootstrap task should become a GitHub issue.

### Step 8: Create bootstrap GitHub issues

For each bootstrap task in Step 7, create an issue using the shared script (handles dedup automatically):

```bash
BODY=$(cat <<'EOF'
## Design reference
docs/design/frontend-system.md

## What
[description of the bootstrap task]

## Acceptance criteria
- [ ] [criterion]
EOF
)
RESULT=$(${CLAUDE_PLUGIN_ROOT}/bin/gh-create-issue.sh \
  --title "<task title>" \
  --body "$BODY" \
  --labels "area:frontend,kind:task" \
  --add-to-board)
# RESULT is "created:<number>" or "exists:<number>"
```

### Step 9: Commit the design system doc

```bash
git add docs/design/frontend-system.md
git commit -m "docs: frontend design system spec — aesthetic direction, tokens, layout shell"
```

### Step 10: Report and stop

Present a summary:

- Aesthetic direction chosen (one sentence)
- CSS/component approach
- Key token decisions (background, accent, fonts)
- Bootstrap issues created (numbers + titles)
- Next step: human reviews `docs/design/frontend-system.md`, approves, then bootstrap issues run through `/feature`

**Stop here.** Do not implement. The user reviews the spec before any code is written.

## Guidelines

- **Do not implement.** This skill produces a design spec and bootstrap issues only — no production code, no `globals.css`, no `tailwind.config.ts`.
- **Be specific.** Every token must be an exact value. "A neutral dark palette" is not a token. `--color-background: #0f1117` is.
- **Be bold.** Generic defaults (Inter, white background, blue accent) are explicitly forbidden. The design must have a point of view.
- **Respect existing structure.** Work with the project's existing framework and layout hierarchy, not against it.
- **British English** in all documentation.
- **One ADR if a non-obvious technology choice is made.** Document the rationale.
- **The spec is a contract.** Once approved, `/feature` agents must not deviate from the tokens, fonts, or component patterns without updating the spec first.
