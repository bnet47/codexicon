# Interface hardening reference

Load this reference for production flows, forms, onboarding, accounts, checkout, scheduling, permissions, or release hardening.

## State matrix

List each user action and the reachable states before declaring the flow complete:

| Concern | Verify |
|---|---|
| Entry | first visit, returning user, deep link, expired link |
| Data | loading, partial, empty, stale, unavailable, permission denied |
| Action | idle, hover, focus, pending, disabled, success, failure, retry |
| Validation | required, invalid format, conflicting values, server rejection |
| Session | signed out, expired, concurrent change, lost connectivity |
| Recovery | preserve input, explain consequence, retry, cancel, safe exit |

Only include states the feature can reach, but do not omit reachable failure paths.

## Accessibility and input

- Use semantic elements and programmatic names; placeholders are not labels.
- Preserve logical heading and focus order.
- Make every action keyboard operable with a visible focus indicator.
- Announce asynchronous status and validation at the appropriate time.
- Keep targets usable for touch and spacing tolerant of motor error.
- Verify contrast for text, icons, focus, controls, disabled states, and charts.
- Support zoom, text resizing, forced colors where relevant, and reduced motion.
- Do not encode meaning through color, position, hover, or motion alone.

## Responsive and content stress

- Test narrow mobile, wide mobile, tablet or compact desktop, and a wide viewport selected for the product.
- Test long names, translated copy growth, large numbers, missing images, many items, one item, and no items.
- Prevent clipped menus, dialogs, tooltips, tables, sticky elements, and long headings.
- Prefer content-driven breakpoints and component-level adaptation over device labels.
- Keep critical actions reachable when the virtual keyboard, browser chrome, or safe area reduces space.

## Performance and resilience

- Avoid blocking the primary task on decorative assets, fonts, animation, or analytics.
- Reserve image and media dimensions to prevent layout shifts.
- Lazy-load only content that can safely arrive later.
- Keep a usable visible default when scripts, transitions, or observers fail.
- Preserve user input across recoverable failures.
- Make destructive actions and irreversible consequences explicit.

## Release evidence

Capture the viewports, flows, inputs, and assistive checks exercised. Record concrete gaps rather than claiming broad compatibility from a single happy-path screenshot.
