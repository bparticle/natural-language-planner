# Harden Dashboard — Design Spec

**Date:** 2026-03-18
**Scope:** Full harden pass on `templates/dashboard/` (index.html, styles.css, app.js)
**Approach:** Single organized commit, changes grouped by concern within each file

---

## Background

A comprehensive audit of the NL Planner dashboard identified zero ARIA attributes across all interactive elements, no focus management in the modal, no `prefers-reduced-motion` support, missing text overflow guards, no error states for API failures, no debounce on search, and weak empty states. This spec covers all of those findings in a single hardening pass.

---

## Section 1 — ARIA & Semantics

### index.html changes

**Header buttons:**
- `#btn-theme` → add `aria-label="Toggle dark mode"` and `aria-pressed="false"` (JS updates this on toggle). Do NOT add `aria-disabled` as a static attribute — it is only set dynamically.
- `#btn-refresh` → add `aria-label="Refresh data"`. Do NOT add `aria-disabled` as a static attribute — it is only set dynamically when a fetch is in flight.

**Search:**
- `.search-box` div → add `role="search"`
- `#search-input` → add `aria-label="Search tasks"`. Do NOT add `aria-controls` — the search drives a full view panel, not a combobox, so `aria-controls` would create a misleading ARIA relationship without the required combobox pattern.
- Add a visually-hidden `<span id="search-status" role="status" aria-live="polite" aria-atomic="true"></span>` inside `#view-search` for result-count announcements (e.g., "3 results for 'deploy'", "No results").

**Navigation tabs:**
- `.view-tabs` nav → add `role="tablist"` and `aria-label="Dashboard views"`
- Each tab button (class `.tab`) → add `role="tab"`, `id="tab-{view-name}"`, `aria-controls="view-{view-name}"`
- Set `aria-selected` initial values concretely in HTML: the focus tab (active on load) gets `aria-selected="true"`, all other tabs get `aria-selected="false"`
- Each view div → add `role="tabpanel"`, `aria-labelledby="tab-{view-name}"`, `tabindex="0"`

**Stats bar:**
- `#stats-bar` → add `aria-label="Task statistics"`
- Do NOT add `aria-live` to the entire `#stats-bar` container — it re-renders wholesale and would announce all content on every update. Instead, add a separate visually-hidden `<span id="stats-status" role="status" aria-live="polite" aria-atomic="true"></span>` immediately after `#stats-bar`. JS sets its text to a brief summary after each data load (e.g., "Stats updated: 12 tasks, 3 overdue").

**Today section:**
- `#today-list` → add `aria-live="polite"` is acceptable here because the today section re-renders only when today tasks genuinely change (pinned/unpinned), not on every filter or tab switch. Keep `aria-live="polite"`.

**Attention/overdue banner:**
- The banner already exists as a static element `#attention-banner` in `index.html`. Add `role="status"` and `aria-live="polite"` to the existing element. Do NOT create a new element — JS currently shows/hides it via `style.display`.

**Modal:**
- `#modal-overlay` → add `role="dialog"`, `aria-modal="true"`, `aria-labelledby="modal-title"`
- `.modal-close` button → add `aria-label="Close task detail"`

### app.js changes

**Tab switching:** On each tab click, set `aria-selected="true"` on the clicked tab and `aria-selected="false"` on all others.

**`toggleTheme()`:** Toggle `aria-pressed` on `#btn-theme` — set to `"true"` when dark mode is active, `"false"` when light.

**`handleSearch()`:** After rendering results, set `#search-status` text content to e.g. `"3 results for 'deploy'"` or `"No results for 'foo'"`.

**`loadAll()` start/end:** Set `aria-disabled="true"` + `disabled = true` on `#btn-refresh` when fetch begins; remove both on completion (success or error). This replaces/supplements the existing `spinning` class — see Section 5.

**After data renders:** Set `#stats-status` text to a brief summary e.g. `"Stats updated"`.

### Visually-hidden utility class (styles.css)

```css
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

Apply to `#search-status` and `#stats-status` spans.

---

## Section 2 — Focus Management

### Focus trap utility (app.js)

Add a `trapFocus(el)` function. Initialise the module-level variable as `let removeTrap = null;` so `closeModal()` can safely call `removeTrap?.()` even before any modal has been opened.

```js
let removeTrap = null;

function trapFocus(el) {
  const focusable = el.querySelectorAll(
    'button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  function handler(e) {
    if (e.key !== 'Tab') return;
    if (e.shiftKey) {
      if (document.activeElement === first) { e.preventDefault(); last.focus(); }
    } else {
      if (document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }

  el.addEventListener('keydown', handler);
  return () => el.removeEventListener('keydown', handler);
}
```

### openModal(id)

1. Store `document.activeElement` as `lastFocusedEl` (module-level variable, initialised to `null`)
2. Open modal (existing logic)
3. Move focus to `els.modalClose`
4. `removeTrap = trapFocus(els.modal)`

### closeModal()

1. `removeTrap?.(); removeTrap = null;`
2. Close modal (existing logic)
3. `lastFocusedEl?.focus(); lastFocusedEl = null;`

**Note on stale focus target:** After a data re-render (triggered by visibility-change while modal is closed), the previously focused card element may be removed from the DOM. `focus()` on a detached element silently fails — this is acceptable behaviour for this app. The focus simply lands on `<body>`. No additional mitigation is needed.

**Existing Escape key handler:** The existing `keydown` handler in `init()` already uses if/else to close the lightbox first, then calls `closeModal()`. This is compatible with the new focus-restore call in `closeModal()` — no change needed to the Escape handler.

### Focus rings (styles.css)

Replace the bare border-color change on `.filter-select:focus` with a visible ring:

```css
.filter-select:focus {
  border-color: var(--blue);
  box-shadow: 0 0 0 3px var(--blue-light);
  outline: none;
}
```

Add keyboard-only focus rings to tab buttons (actual class: `.tab`) and ghost buttons:

```css
.tab:focus-visible,
.btn-ghost:focus-visible {
  outline: 2px solid var(--blue);
  outline-offset: 2px;
}
```

Use `:focus-visible` (not `:focus`) to avoid showing rings on mouse clicks.

### Theme flash fix

**styles.css:** Remove `transition: background 200ms ease, color 200ms ease` from the `body` default rule. Add:

```css
body.theme-ready {
  transition: background 200ms ease, color 200ms ease;
}
```

**app.js:** The double-rAF must be added inside `initTheme()` itself — not in a `DOMContentLoaded` handler. This is because `init()` is called immediately if `document.readyState !== "loading"` (which is the common case for a script at the bottom of `<body>`), meaning `DOMContentLoaded` may never fire in this code path. Modify `initTheme()`:

```js
function initTheme() {
  const saved = localStorage.getItem("nlp-theme");
  if (saved === "dark" || (!saved && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
    els.body.classList.add("dark");
  }
  // Add transition class after first paint to prevent flash on load
  requestAnimationFrame(() => requestAnimationFrame(() => {
    document.body.classList.add('theme-ready');
  }));
}
```

The double-rAF guarantees the theme is applied and painted before the transition is enabled, eliminating the flash-then-transition on load.

---

## Section 3 — Motion & Transitions

### prefers-reduced-motion (styles.css)

Add at the bottom of `styles.css`, after all other rules:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

This single block covers all keyframe animations (spin, modal-in, modal-slide-up) and all CSS transitions, including the hardcoded `width 400ms ease` on `.progress-bar-modal .progress-bar-fill` (line ~964) which is not a `var(--transition)` reference.

### Modal progress animation (styles.css + index.html + app.js)

Replace `max-height` animation on the modal progress section with `grid-template-rows`.

**index.html:** Restructure `#modal-progress` to use the grid animation pattern. The actual existing markup (lines 208–216) includes a `.modal-progress-header` with `#modal-progress-pct`. Preserve all existing children:

```html
<!-- Before (actual markup) -->
<div class="modal-progress" id="modal-progress" style="display:none">
  <div class="modal-progress-header">
    <span class="modal-progress-label">Progress</span>
    <span class="modal-progress-pct" id="modal-progress-pct"></span>
  </div>
  <div class="progress-bar progress-bar-modal">
    <div class="progress-bar-fill" id="modal-progress-fill"></div>
  </div>
</div>

<!-- After -->
<div class="modal-progress-wrapper" id="modal-progress">
  <div class="modal-progress-inner">
    <div class="modal-progress-header">
      <span class="modal-progress-label">Progress</span>
      <span class="modal-progress-pct" id="modal-progress-pct"></span>
    </div>
    <div class="progress-bar progress-bar-modal">
      <div class="progress-bar-fill" id="modal-progress-fill"></div>
    </div>
  </div>
</div>
```

`id="modal-progress"` stays on the outermost element so `els.modalProgress` (and `els.modalProgressPct`, `els.modalProgressFill`) in `app.js` still work — they reference descendant elements by their own IDs, not by position.

**styles.css:** Replace the existing `.modal-progress` rules with:

```css
.modal-progress-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 250ms ease;
}
.modal-progress-wrapper.open {
  grid-template-rows: 1fr;
}
.modal-progress-inner {
  overflow: hidden;
  padding-bottom: 0;
  transition: padding-bottom 250ms ease;
}
.modal-progress-wrapper.open .modal-progress-inner {
  padding-bottom: 12px;
}
```

**app.js:** Replace all instances of `els.modalProgress.style.display = 'none'` with `els.modalProgress.classList.remove('open')`, and `els.modalProgress.style.display = ''` (or `block`) with `els.modalProgress.classList.add('open')`. Remove the `style="display:none"` from the HTML too, since the CSS `grid-template-rows: 0fr` hides it by default.

---

## Section 4 — Text Overflow

### styles.css additions

Verify each selector against the actual HTML before applying. Confirmed class names from the codebase:

**Focus card titles** — class is `.focus-card-title` (clamp to 2 lines, with flex shrink guard):
```css
.focus-card-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-width: 0; /* flex shrink guard — allows shrinking below content size */
}
```

**Kanban task card titles** — class is `.task-card-title` (clamp to 2 lines, with flex shrink guard):
```css
.task-card-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-width: 0; /* flex shrink guard */
}
```

**Modal title** — class is `.modal-title` (allow wrapping, prevent overflow):
```css
.modal-title {
  overflow-wrap: break-word;
  word-break: break-word;
}
```

**Project card titles** — actual class is `.project-card-title` (NOT `.project-card-name`):
```css
.project-card-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
```

**Flex shrink guards** — `min-width: 0` inlined into the relevant CSS blocks above:
- `.focus-card-title` — included in the block above
- `.task-card-title` — include `min-width: 0` in the clamp block below
- `.project-card-title` — include `min-width: 0` in the ellipsis block below (`.project-card-header` does not exist in the codebase; `.task-card-body` has no CSS rules and is a plain block, so the guard belongs on the title directly)

Note: `.today-item-title` already has `min-width: 0` in the existing CSS — no change needed there.

---

## Section 5 — Error & Loading States

### Error banner (index.html)

Add after line 86 (`</section>` closing `.top-bar`), before `<nav class="view-tabs">`, hidden by default:

```html
<div id="error-banner" role="alert" hidden>
  <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
    <line x1="12" y1="16" x2="12.01" y2="16"/>
  </svg>
  <span id="error-message">Could not reach the planner server.</span>
  <button id="btn-retry" class="btn btn-ghost">Retry</button>
</div>
```

`role="alert"` causes screen readers to announce it immediately when it appears (equivalent to `aria-live="assertive"`). No separate `aria-live` is needed.

### Error banner styles (styles.css)

```css
#error-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 24px;
  background: var(--red-light);
  color: var(--red);
  border-bottom: 1px solid var(--red);
  font-size: 0.88rem;
}
#error-banner[hidden] { display: none; }
```

Dark mode: `--red-light` is `rgba(239,68,68,.15)` and `--red` is `#ef4444` — contrast is adequate on dark backgrounds. No dark-mode override needed.

### app.js changes

**Module-level state additions:**
```js
let isLoading = false;
let isInitialLoad = true;
let lastFocusedEl = null;
```

**`loadAll()` refactor:**

The existing `loadAll()` already has a `spinning` class animation on `#btn-refresh`. Preserve the spin animation and add the disabled/aria-disabled guard:

```js
async function loadAll() {
  if (isLoading) return;
  isLoading = true;
  els.btnRefresh.disabled = true;
  els.btnRefresh.setAttribute('aria-disabled', 'true');
  els.btnRefresh.classList.add('spinning'); // preserve existing animation

  try {
    // ... existing fetch logic unchanged ...
    hideError();
    isInitialLoad = false;
  } catch (err) {
    showError('Could not reach the planner server.');
  } finally {
    isLoading = false;
    els.btnRefresh.disabled = false;
    els.btnRefresh.setAttribute('aria-disabled', 'false');
    els.btnRefresh.classList.remove('spinning');
  }
}
```

**Error helpers:**
```js
function showError(msg) {
  els.errorMessage.textContent = msg;
  els.errorBanner.hidden = false;
}

function hideError() {
  els.errorBanner.hidden = true;
}
```

**`#btn-retry` listener (in `init()`):**
```js
els.btnRetry.addEventListener('click', () => {
  hideError();
  loadAll();
});
```

**Add to `els` cache:**
```js
modal: $('#task-modal'),          // needed by trapFocus and openModal
errorBanner: $('#error-banner'),
errorMessage: $('#error-message'),
btnRetry: $('#btn-retry'),
statsStatus: $('#stats-status'),
searchStatus: $('#search-status'),
```

**Loading state:**

When `isInitialLoad` is `true` and `allTasks` is empty, the main content area shows:

```html
<div class="loading-state">Loading…</div>
```

```css
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 64px 24px;
  color: var(--text-muted);
  font-size: 0.9rem;
}
```

Each view-render function (`renderFocusView`, `renderBoard`, etc.) checks `if (isInitialLoad && allTasks.length === 0)` at the top and returns the loading markup early. `isInitialLoad` is set to `false` after the first successful `loadAll()` completes (inside the `try` block).

---

## Section 6 — Debounce & Interaction Guards

### Debounce utility (app.js)

Add near the top of `app.js`, before `init()`:

```js
function debounce(fn, ms) {
  let timer;
  return function(...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), ms);
  };
}
```

### Search debounce

**Important:** `handleSearch` already implements a correct internal pattern: it calls `hideSearch()` immediately for empty queries, then debounces only the API call via `searchDebounce = setTimeout(...)`. Wrapping the whole function in `debounce()` would delay the `hideSearch()` path by 300ms — creating a visible lag when the user clears the search box.

The correct approach is to replace the ad-hoc `let searchDebounce` + `clearTimeout`/`setTimeout` inside `handleSearch` with the `debounce` utility extracted as a named function:

```js
// Remove: let searchDebounce = null; (module-level variable)

// Add a debounced API caller:
const debouncedSearchApi = debounce(async (query) => {
  const results = await api(`/api/search?q=${encodeURIComponent(query)}`);
  showSearch(results || []);
}, 300);

// Rewrite handleSearch to use it:
function handleSearch() {
  const query = els.searchInput.value.trim();
  if (!query) {
    hideSearch();
    return;
  }
  debouncedSearchApi(query);
}
```

The event listener registration stays the same — no wrapping needed:
```js
els.searchInput.addEventListener('input', handleSearch);
```

Keep the existing `keydown` Enter handler as-is — it calls `handleSearch()` directly and fires immediately.

### isLoading guard

Covered in Section 5. The `isLoading` flag at the top of `loadAll()` also gates visibility-change and interval-triggered calls from racing.

### Kanban column overflow fix (styles.css)

The actual task list class inside kanban columns is `.column-body` (not `.kanban-column-tasks`).

```css
/* Remove overflow: hidden from the column wrapper */
.kanban-column {
  /* remove: overflow: hidden */
  overflow: visible; /* or simply remove the property */
}

/* Move scrolling to the task list */
.column-body {
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}
```

`.kanban-column` already uses `display: flex; flex-direction: column` so `.column-body` will correctly fill available height.

---

## Section 7 — Empty States

### Kanban empty columns (app.js)

When a kanban column renders zero task cards, append inside `.column-body`:

```html
<div class="empty-column">No tasks here</div>
```

```css
.empty-column {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.85rem;
  padding: 32px 0;
}
```

### Search empty state (app.js)

When `handleSearch` returns zero results, set the content of `#view-search`:

```html
<div class="empty-state">
  <p>No tasks match "<strong id="empty-search-query"></strong>"</p>
</div>
```

Also update `#search-status` (visually hidden): `"No results for '${query}'"`.

### Filter empty state (app.js)

When active filters produce zero tasks in any view, render:

```html
<div class="empty-state">
  <p>No tasks match the current filters.</p>
  <button class="btn btn-ghost js-clear-filters">Clear filters</button>
</div>
```

**Wiring:** Because the app is inside an IIFE and `clearAllFilters()` is not on the global scope, attach the click handler immediately after injecting the empty state HTML:

```js
// Inside the render function, after setting innerHTML:
const clearBtn = container.querySelector('.js-clear-filters');
if (clearBtn) clearBtn.addEventListener('click', clearAllFilters);
```

### Shared empty state styles

```css
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 24px;
  color: var(--text-muted);
  font-size: 0.9rem;
  text-align: center;
}
```

---

## Lightbox (out of scope, noted)

The lightbox (`#lightbox-overlay`) has the same missing focus trap and ARIA issues as the modal. This is out of scope for this pass but should be addressed in a follow-up harden pass.

---

## Files Changed

| File | Nature of changes |
|------|-------------------|
| `templates/dashboard/index.html` | ARIA attributes on buttons/tabs/modal/search; error banner; `#stats-status` and `#search-status` spans; tabpanel roles; `#attention-banner` ARIA; modal-progress wrapper restructure |
| `templates/dashboard/styles.css` | `.sr-only` utility; focus rings (`.filter-select`, `.tab`, `.btn-ghost`); `prefers-reduced-motion` block; `grid-template-rows` animation; text overflow guards; error banner and loading/empty state styles; `body.theme-ready` theme flash fix |
| `templates/dashboard/app.js` | `trapFocus()`, `debounce()`; `isLoading`, `isInitialLoad`, `lastFocusedEl`, `removeTrap` state; `showError()`/`hideError()`; `aria-selected` management; `aria-pressed` toggle; `#btn-retry` handler; focus save/restore; double-rAF in `initTheme()`; `#search-status` and `#stats-status` updates; `debouncedSearchApi` extraction (replaces `searchDebounce` variable); `.js-clear-filters` wiring; `loadAll()` guard + spinner reconciliation |

---

## Out of Scope

- Virtual scrolling / pagination for archive (separate `/optimize` task)
- Loading skeleton screens (separate `/delight` task)
- Font or color palette changes (separate `/normalize` task)
- RTL language support (no i18n requirement identified for this project)
- Lightbox focus trap and ARIA (follow-up `/harden` pass)
