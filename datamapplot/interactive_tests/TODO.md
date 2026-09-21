# Interactive Tests Improvement Plan

## Overview
Improve Playwright test coverage for DataMapPlot interactive features while keeping CI runtime under 30 minutes.

## Phase 1: Streamline & Reduce Duplication

### 1.1 Create Shared Page Object
- [x] Create `utils/datamap-page.ts` with DataMapPage class
  - [x] `goto(htmlFile)` - Navigate to test HTML
  - [x] `waitForReady()` - Wait for loading to complete
  - [x] `zoom(delta)` - Zoom interaction
  - [x] `pan(startX, startY, endX, endY)` - Pan interaction
  - [x] `search(query)` / `clearSearch()` - Search operations
  - [x] `getCanvas()`, `getTooltip()`, `getSearchInput()`, etc. - Element accessors
  - [x] `expectCanvasScreenshot(name)` - Screenshot helper

### 1.2 Refactor Existing Tests
- [x] Update `arxiv_ml.spec.ts` path for new server root
- [x] Update `cord_canvas.spec.ts` path for new server root
- [x] Move existing tests to datasets/ directory
- [ ] Refactor to use DataMapPage (optional - existing tests work)

## Phase 2: Create Minimal Synthetic Test Fixtures

### 2.1 Dynamic Fixture Generation (via Python Tests)
- [x] Add fixture generation tests to `datamapplot/tests/test_interactive_plotting.py`
- [x] `TestMinimalFixtureGeneration` class generates minimal HTML fixtures:
  - [x] `minimal_basic.html` - ~100 points, basic labels (core navigation tests)
  - [x] `minimal_search.html` - ~200 points with searchable hover text
  - [x] `minimal_tooltip.html` - ~100 points with rich hover data
  - [x] `minimal_selection.html` - ~200 points with DisplaySample handler
  - [x] `minimal_onclick.html` - ~100 points with on_click action
  - [x] `minimal_colormap.html` - ~200 points with colormap options
  - [x] `minimal_histogram.html` - ~300 points with date histogram
  - [x] `minimal_topictree.html` - ~300 points with topic tree enabled
- [x] Fixtures output to `tests/html/` directory (same as other interactive tests)
- [x] Fixtures regenerated on every CI run (always up-to-date with rendering code)

### 2.2 HTTP Server Configuration  
- [x] Server serves from `tests/html/` directory
- [x] Playwright tests use simple filenames (e.g., `minimal_tooltip.html`)

## Phase 3: New Feature Tests (Priority Order)

### 3.1 Tooltips (Highest Priority)
- [x] Create `tests/features/tooltip.spec.ts`
- [x] Test: Tooltip appears on point hover
- [x] Test: Tooltip contains expected hover text
- [x] Test: Tooltip disappears when moving away
- [x] Test: Tooltip positioning (doesn't overflow viewport)
- [ ] Test: Custom tooltip HTML template rendering (deferred - needs custom fixture)

### 3.2 Selection Handlers
- [x] Create `tests/features/selection.spec.ts`
- [x] Test: Lasso selection activates on modifier key + drag
- [x] Test: Selection container appears after selection
- [x] Test: Selected points are highlighted
- [x] Test: Resample button works
- [x] Test: Clear selection works
- [ ] Test: Selection count is accurate (deferred - needs implementation detail check)

### 3.3 On-Click Actions
- [x] Create `tests/features/onclick.spec.ts`
- [x] Test: Click on point triggers action
- [x] Test: Action receives correct point data
- [x] Test: Custom JavaScript executes

### 3.4 Colormaps
- [x] Create `tests/features/colormap.spec.ts`
- [x] Test: Colormap selector is visible
- [x] Test: Changing colormap updates point colors
- [x] Test: Colormap legend updates

### 3.5 Topic Tree
- [x] Create `tests/features/topictree.spec.ts`
- [x] Test: Topic tree panel is visible
- [x] Test: Expanding/collapsing nodes works
- [x] Test: Clicking topic highlights related points
- [x] Test: Topic tree navigation updates view

### 3.6 Histograms (Lowest Priority)
- [x] Create `tests/features/histogram.spec.ts`
- [x] Test: Histogram is rendered
- [x] Test: Brush selection works
- [x] Test: Points filter based on selection
- [x] Test: Clear filter works

## Phase 4: Test Organization

### 4.1 Reorganize Directory Structure
- [x] Create `tests/core/` directory
- [x] Create `tests/features/` directory
- [x] Create `tests/datasets/` directory
- [x] Move/refactor existing tests into new structure

### 4.2 Implement Test Tagging
- [x] Add `@fast` tag to tests using minimal fixtures
- [x] Add `@slow` tag to full dataset visual regression tests
- [ ] Add feature-specific tags (`@tooltip`, `@selection`, etc.) - optional

## Phase 5: CI Configuration Updates

### 5.1 Update Azure Pipelines
- [x] Configure PR builds to run `--grep-invert @slow` (excludes slow tests)
- [x] Configure main/nightly builds to run all tests
- [x] Split Playwright step for Unix/Windows compatibility
- [ ] Verify runtime stays under 30 minutes (needs CI run)
- [ ] Generate baseline snapshots for new tests (happens automatically)

## Remaining Work / Next Steps

1. **Run tests locally or in CI to generate baseline snapshots**
   - The new tests will fail initially because they don't have baseline screenshots
   - Run: `npx playwright test --update-snapshots` to generate baselines

2. **Verify test structure works**
   - Run: `npx playwright test --list` to verify all tests are discovered
   - Run: `npx playwright test --grep @fast` to run only fast tests

3. **Fine-tune tests based on actual HTML structure**
   - Some selectors in tests may need adjustment based on actual DOM structure
   - Tooltip, selection, histogram selectors may vary

4. **Optional: Add more granular feature tags**
   - `@tooltip`, `@selection`, `@histogram` etc. for running specific feature tests

## Target Directory Structure
```
datamapplot/
├── tests/
│   ├── html/                   # Generated by Python tests
│   │   ├── minimal_basic.html      ✅ Dynamic
│   │   ├── minimal_search.html     ✅ Dynamic
│   │   ├── minimal_tooltip.html    ✅ Dynamic
│   │   ├── minimal_selection.html  ✅ Dynamic
│   │   ├── minimal_onclick.html    ✅ Dynamic
│   │   ├── minimal_colormap.html   ✅ Dynamic
│   │   ├── minimal_histogram.html  ✅ Dynamic
│   │   └── minimal_topictree.html  ✅ Dynamic
│   └── test_interactive_plotting.py  # Generates minimal fixtures
├── interactive_tests/
│   ├── playwright.config.ts        ✅ Updated
│   ├── package.json
│   ├── TODO.md (this file)
│   ├── utils/
│   │   ├── canvas.ts               ✅ Existing
│   │   └── datamap-page.ts         ✅ NEW
│   └── tests/
│       ├── core/
│       │   ├── navigation.spec.ts  ✅ NEW
│       │   └── search.spec.ts      ✅ NEW
│       ├── features/
│       │   ├── tooltip.spec.ts     ✅ NEW
│       │   ├── selection.spec.ts   ✅ NEW
│       │   ├── onclick.spec.ts     ✅ NEW
│       │   ├── colormap.spec.ts    ✅ NEW
│       │   ├── topictree.spec.ts   ✅ NEW
│       │   └── histogram.spec.ts   ✅ NEW
│       └── datasets/
│           ├── arxiv_ml.spec.ts    ✅ Moved
│           └── cord_canvas.spec.ts ✅ Moved
```

## Estimated Runtime Budget
| Category | Tests | Time | When |
|----------|-------|------|------|
| Core Navigation (minimal) | 4 | 2 min | Always |
| Search (minimal) | 3 | 1 min | Always |
| Tooltips | 5 | 1 min | Always |
| Selection | 6 | 1.5 min | Always |
| On-Click | 3 | 1 min | Always |
| Colormaps | 3 | 1 min | Always |
| Topic Tree | 4 | 1.5 min | Always |
| Histograms | 4 | 1.5 min | Always |
| **Fast Total** | **32** | **~10 min** | **PR** |
| ArXiv ML Visual Regression | 4 | 5 min | Nightly |
| CORD19 Visual Regression | 4 | 8 min | Nightly |
| **Slow Total** | **8** | **~13 min** | **Nightly** |
| **Grand Total** | **40** | **~23 min** | **Nightly** |

## Implementation Order
1. Phase 1.1: Create datamap-page.ts page object
2. Phase 2.1: Create fixture generation script + minimal_basic.html
3. Phase 3.1: Implement tooltip tests (highest priority)
4. Phase 1.2: Refactor existing tests to use new infrastructure
5. Phase 2.1 (cont): Generate remaining minimal fixtures
6. Phase 3.2-3.6: Implement remaining feature tests in priority order
7. Phase 4: Reorganize directory structure
8. Phase 5: Update CI configuration

## Notes
- Windows compatibility: Handle if easy, otherwise focus on Linux coverage
- Snapshots: Keep per-browser/per-OS granularity for now
- Static fixtures: Commit to repo, document regeneration process
