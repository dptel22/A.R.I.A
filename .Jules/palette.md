## 2025-05-18 - Modal Accessibility & Form Helper Micro-UX

**Learning:** Modal dialogs in enterprise web apps often lack key WAI-ARIA attributes (`role="dialog"`, `aria-modal="true"`, `aria-labelledby`, explicit close button labels) and explicit form label linkages (`id`/`htmlFor`). Additionally, static example helper text (like sample coordinates) can be transformed into interactive one-click inputs to significantly streamline workflow without cluttering the UI.

**Action:** Whenever building or modifying modals:
1. Always attach `role="dialog"`, `aria-modal="true"`, and `aria-labelledby` referencing the dialog title.
2. Ensure icon-only buttons (like `X` close buttons) have explicit `aria-label`s and clear focus-visible outlines.
3. Link form input `<label>`s using matching `htmlFor` and `id` attributes.
4. Convert passive example text (e.g. sample inputs, example coordinates) into accessible `<button type="button">` elements that pre-fill form fields on click.
