---
name: design-experience
description: Build distinctive production-grade app and web interfaces. Use for UI/UX, responsive states, accessibility, visual systems, redesigns, or frontend polish.
---

# Design experience

Create a coherent customer experience, not a decorated wireframe. Make every visual choice serve the product, audience, setting, and task.

## 1. Establish context

Read the approved charter or feature brief, existing interface, design system, brand assets, content, and relevant conventions. Read `agent_docs/design.md` when it exists. Do not create durable design context unless the user requests it or the approved workflow requires it.

Define before implementation:

- user, primary task, setting, and observable success;
- surface register: **brand** when design carries identity and persuasion, or **product** when design primarily serves repeated work;
- product personality, emotional tone, and anti-references;
- one memorable, context-specific design idea;
- brand, platform, accessibility, performance, content, and licensing constraints;
- required viewports, states, and interaction paths.

Write one physical-scene sentence: who uses this, where, in what conditions, and with what level of urgency or attention. Use it to choose light versus dark, density, contrast, target sizes, motion, and information hierarchy.

Set three dials explicitly: **variance** (quiet to expressive), **motion** (still to dynamic), and **density** (spacious to compact). Do not equate distinctive with loud.

## 2. Inspect before inventing

- Reuse established tokens, components, content style, and asset language when they work.
- Inspect the running product and representative project files; source code alone does not reveal the experience.
- For an existing surface, preserve product identity unless the request explicitly authorizes redesign.
- Verify current platform guidance and references when they may have changed. Never clone proprietary layouts or assets.
- Confirm fonts, icons, images, and libraries are available, performant, and licensed.

For visual-system work, new surfaces, redesigns, or polish, read [references/interface-craft.md](references/interface-craft.md). For production flows, forms, onboarding, or release hardening, also read [references/hardening.md](references/hardening.md).

## 3. Shape before styling

Define the information order, primary action, navigation model, state transitions, content requirements, and responsive behavior before choosing decorative treatments. Remove sections and controls that do not advance the task or argument.

State the direction in one sentence, then encode it consistently through typography, color, spacing, shape, imagery, motion, and information density. Use real product language. If real content is unavailable, mark neutral placeholders clearly and avoid invented proof or business facts.

Run both reflex checks:

1. Could the category alone predict the palette and layout?
2. Could the category plus a request to avoid common clichés predict the replacement aesthetic?

If either answer is yes, return to the scene, content, and product artifacts instead of swapping one fashionable template for another.

## 4. Implement the complete experience

- Preserve working behavior and build the smallest complete flow.
- Cover every reachable default, hover, focus, active, disabled, loading, empty, error, success, stale, and permission state.
- Make responsive behavior deliberate at content-driven breakpoints.
- Use semantic structure, keyboard operation, visible focus, usable targets, sufficient contrast, reduced-motion support, and helpful validation.
- Keep navigation, state, and failures observable and recoverable. Preserve deep links and browser behavior when applicable.
- Stress long text, localization growth, narrow screens, zoom, slow networks, missing data, and repeated content.
- Avoid decorative complexity that harms loading, readability, maintainability, or task completion.
- Never fabricate product data, customer quotes, logos, outcomes, social proof, or decorative dashboards.

Use an installed specialist site, browser, image, document, or presentation skill when the requested artifact needs it. Follow that skill's render-and-verify workflow.

## 5. Iterate on rendered evidence

Run the real interface and inspect it at agreed critical widths. Exercise the primary flow plus loading, empty, error, keyboard, zoom, and reduced-motion behavior.

Use two passes:

1. **Composition:** hierarchy, rhythm, typography, color, imagery, density, responsive composition, and unwanted template reflexes.
2. **Operation:** comprehension, interaction feedback, recovery, accessibility, content stress, and performance.

Fix the highest-impact gap, rerender, and recheck. Do not declare visual quality from code inspection. If rendering is unavailable, report the limitation.

## 6. Report

Summarize the design direction and dials, implemented behavior, rendered and functional verification, and residual constraints. Recommend `$review-creative` for an independent quality pass on customer-facing or high-impact work.
