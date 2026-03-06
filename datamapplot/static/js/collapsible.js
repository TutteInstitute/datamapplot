/**
 * Collapsible Widget System
 *
 * Provides collapse/expand behaviour for widgets whose template wrapper
 * carries the `.collapsible-wrapper` class.
 *
 * DOM structure expected (produced by content_layout.html.jinja2):
 *
 *   <div class="collapsible-wrapper" data-widget-id="...">
 *     <div class="collapsible-header container-box">
 *       <span class="collapse-chevron">&#10095;</span>
 *       <span class="collapsible-title">Widget Title</span>
 *     </div>
 *     <div class="collapsible-content">
 *       <!-- widget.html output -->
 *     </div>
 *     <button class="collapse-overlay-btn" aria-label="Collapse widget">
 *       <span class="collapse-chevron">&#10095;</span>
 *     </button>
 *   </div>
 */

(function () {
    'use strict';

    var STORAGE_KEY = 'datamapplot-collapsed-widgets';
    var ANIMATION_DURATION = 250; // ms – matches TopicTree timing

    /**
     * Load persisted collapsed state from localStorage.
     * @returns {Object} Map of widgetId -> true for collapsed widgets.
     */
    function loadCollapsedState() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (_) {
            return {};
        }
    }

    /**
     * Persist collapsed state to localStorage.
     * @param {Object} state Map of widgetId -> true for collapsed widgets.
     */
    function saveCollapsedState(state) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch (_) {
            // Silently ignore storage quota errors
        }
    }

    /**
     * Collapse a widget with animation.
     * @param {HTMLElement} wrapper  The .collapsible-wrapper element.
     * @param {HTMLElement} content  The .collapsible-content element.
     * @param {boolean} animate     Whether to animate the transition.
     */
    function collapseWidget(wrapper, content, animate) {
        if (animate && content.offsetHeight > 0) {
            var startHeight = content.offsetHeight;
            content.animate(
                [
                    { height: startHeight + 'px', opacity: 1 },
                    { height: '0px', opacity: 0 },
                ],
                { duration: ANIMATION_DURATION, easing: 'ease-in-out' }
            ).onfinish = function () {
                wrapper.classList.add('collapsed');
            };
        } else {
            wrapper.classList.add('collapsed');
        }
    }

    /**
     * Expand a widget with animation.
     * @param {HTMLElement} wrapper  The .collapsible-wrapper element.
     * @param {HTMLElement} content  The .collapsible-content element.
     * @param {boolean} animate     Whether to animate the transition.
     */
    function expandWidget(wrapper, content, animate) {
        // Remove collapsed so content is in the DOM for measurement
        wrapper.classList.remove('collapsed');

        if (animate) {
            var targetHeight = content.scrollHeight;
            content.animate(
                [
                    { height: '0px', opacity: 0 },
                    { height: targetHeight + 'px', opacity: 1 },
                ],
                { duration: ANIMATION_DURATION, easing: 'ease-in-out' }
            );
        }
    }

    /**
     * Toggle collapsed state for a widget.
     * @param {HTMLElement} wrapper The .collapsible-wrapper element.
     */
    function toggleWidget(wrapper) {
        var content = wrapper.querySelector('.collapsible-content');
        if (!content) return;

        var isCollapsed = wrapper.classList.contains('collapsed');
        var widgetId = wrapper.dataset.widgetId;
        var state = loadCollapsedState();

        if (isCollapsed) {
            expandWidget(wrapper, content, true);
            delete state[widgetId];
        } else {
            collapseWidget(wrapper, content, true);
            state[widgetId] = true;
        }

        saveCollapsedState(state);
    }

    /**
     * Initialise all collapsible wrappers in the document.
     * Safe to call multiple times – already-initialised wrappers are skipped.
     */
    function initCollapsible() {
        var wrappers = document.querySelectorAll('.collapsible-wrapper');
        var savedState = loadCollapsedState();

        wrappers.forEach(function (wrapper) {
            if (wrapper.dataset.collapsibleInit) return; // already set up
            wrapper.dataset.collapsibleInit = 'true';

            var overlayBtn = wrapper.querySelector('.collapse-overlay-btn');
            var header = wrapper.querySelector('.collapsible-header');
            var content = wrapper.querySelector('.collapsible-content');
            var widgetId = wrapper.dataset.widgetId;

            if (!content) return;

            // Attach click handlers
            if (overlayBtn) {
                overlayBtn.addEventListener('click', function (e) {
                    e.stopPropagation();
                    toggleWidget(wrapper);
                });
            }

            if (header) {
                header.addEventListener('click', function (e) {
                    e.stopPropagation();
                    toggleWidget(wrapper);
                });
            }

            // Restore persisted collapsed state (no animation on load)
            if (widgetId && savedState[widgetId]) {
                collapseWidget(wrapper, content, false);
            }
        });
    }

    // Expose globally so it can be called after dynamic widget insertion
    window.initCollapsible = initCollapsible;

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCollapsible);
    } else {
        initCollapsible();
    }
})();
