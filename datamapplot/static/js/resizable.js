/**
 * Resizable Widget Support
 *
 * Adds a drag handle to a widget so the user can resize it. Shared by the
 * topic tree and any widget created with ``resizable=True``.
 *
 * The width and height can be applied to different elements, e.g. the outer
 * container for width and an inner scrolling area for height.
 *
 * Widgets in right hand stacks grow to the left and widgets in bottom stacks
 * grow upwards, so the handle is placed on the corner that is free to move.
 * Bottom stacks are flipped with ``scaleY(-1)``, which is accounted for when
 * positioning the handle.
 *
 * A ``widgetresize`` CustomEvent (detail: {width, height}) is dispatched on
 * the resized element whenever its size changes (by dragging, or because the
 * layout around it changed, e.g. the window was resized) so widgets that draw
 * fixed size content can redraw.
 */

/**
 * Make an element resizable via a drag handle in its bottom right corner.
 *
 * @param {HTMLElement} element  The element to resize.
 * @param {Object} [options]
 * @param {HTMLElement} [options.handleParent=element]  Element the handle is placed in.
 * @param {HTMLElement} [options.widthTarget=element]  Element that receives the width.
 * @param {HTMLElement} [options.heightTarget=element]  Element that receives the height.
 * @param {number} [options.minWidth=160]  Minimum width in pixels.
 * @param {number} [options.minHeight=80]  Minimum height in pixels.
 * @param {boolean} [options.verticalOnly]  Only allow vertical resizing. Defaults to
 *     true inside a drawer, where widget width is forced to 100%.
 * @param {string} [options.label="Resize widget"]  Accessible label for the handle.
 * @param {string} [options.handleClass]  Extra CSS class for the handle.
 * @param {function} [options.onResize]  Called with {width, height} whenever the size changes.
 * @returns {{handle: HTMLElement, reset: function, setHandleVisible: function}}
 */
function makeResizable(element, options = {}) {
    const VIEWPORT_MARGIN = 16;
    const KEY_STEP = 20;

    const handleParent = options.handleParent || element;
    const widthTarget = options.widthTarget || element;
    const heightTarget = options.heightTarget || element;
    const minWidth = options.minWidth ?? 160;
    const minHeight = options.minHeight ?? 80;
    const verticalOnly = options.verticalOnly ?? Boolean(element.closest('.drawer-container'));
    const onResize = options.onResize;

    // Which edges stay fixed while the widget grows, based on its stack.
    const stack = element.closest('.stack, .drawer-container');
    const inStack = (...names) => Boolean(stack) && names.some(n => stack.classList.contains(n));
    const anchorRight = inStack('top-right', 'bottom-right');
    const anchorBottom = inStack('bottom-left', 'bottom-right', 'drawer-bottom');
    const dirX = anchorRight ? -1 : 1;
    const dirY = anchorBottom ? -1 : 1;

    // Remember the original inline sizing so it can be restored on reset.
    const targets = verticalOnly ? [heightTarget] : [...new Set([widthTarget, heightTarget])];
    const initialStyles = targets.map(target => ({
        target,
        width: target.style.width,
        height: target.style.height,
        maxWidth: target.style.maxWidth,
        maxHeight: target.style.maxHeight,
    }));

    if (getComputedStyle(handleParent).position === 'static') {
        handleParent.style.position = 'relative';
    }
    // Content must scroll once the box is smaller than it.
    if (getComputedStyle(heightTarget).overflowY === 'visible') {
        heightTarget.style.overflow = 'auto';
    }

    const handle = document.createElement('div');
    handle.classList.add('widget-resize-handle');
    if (options.handleClass) {
        handle.classList.add(options.handleClass);
    }
    if (verticalOnly) {
        handle.classList.add('vertical-only');
    }
    // Place the handle on the free corner. In a vertically flipped element the
    // visual top is the DOM bottom, so the DOM position is inverted to match.
    if (anchorBottom !== isFlippedVertically(handleParent)) {
        handle.classList.add('dom-top');
    }
    if (anchorRight) {
        handle.classList.add('dom-left');
    }
    if (!verticalOnly) {
        // The cursor is not transformed, so pick it from the visual corner.
        handle.style.cursor = anchorRight !== anchorBottom ? 'nesw-resize' : 'nwse-resize';
    }
    handle.setAttribute('role', 'separator');
    handle.setAttribute('aria-label', options.label || 'Resize widget');
    handle.setAttribute('tabindex', '0');
    handle.setAttribute('title', 'Drag to resize, double-click to reset');
    handleParent.appendChild(handle);

    // If the handle sits inside the element that scrolls, keep it pinned to
    // the visible corner rather than scrolling away with the content.
    if (handleParent === heightTarget) {
        handleParent.addEventListener('scroll', () => {
            handle.style.transform =
                `translate(${handleParent.scrollLeft}px, ${handleParent.scrollTop}px)`;
        });
    }

    // Height that can actually be seen: when the handle's parent clips its
    // content (e.g. a squashed stack item), part of heightTarget may be hidden,
    // and measuring from the full height would leave a dead zone when dragging.
    const visibleHeight = () => {
        const rect = heightTarget.getBoundingClientRect();
        if (handleParent === heightTarget || getComputedStyle(handleParent).overflowY === 'visible') {
            return rect.height;
        }
        const clip = handleParent.getBoundingClientRect();
        return Math.max(0, Math.min(rect.bottom, clip.bottom) - Math.max(rect.top, clip.top));
    };

    const currentSize = () => ({
        width: widthTarget.getBoundingClientRect().width,
        height: visibleHeight(),
    });

    // Size before the user first resized; the minimums never force a widget
    // larger than this, so a small widget does not jump when the drag starts.
    let naturalSize = null;

    // Notify on any size change, not just drags: stacks cap their height
    // (e.g. 50vh), so resizing the window can squash a resized widget.
    // Track every observed box, since the stack can squash the outer container
    // while the inner element keeps the height the user chose.
    const layoutKey = () => targets.map(target => {
        const rect = target.getBoundingClientRect();
        return `${rect.width}x${rect.height}`;
    }).join(',');
    let lastKey = layoutKey();
    const observer = new ResizeObserver(() => {
        const size = currentSize();
        if (size.width === 0 && size.height === 0) return;  // hidden
        const key = layoutKey();
        if (key === lastKey) return;
        lastKey = key;
        element.dispatchEvent(new CustomEvent('widgetresize', { detail: size }));
        if (onResize) onResize(size);
    });
    targets.forEach(target => observer.observe(target));

    // Room left before the stack reaches its max-height. Beyond that the stack
    // squashes items that clip their content (flex items only shrink below
    // their content size when overflow is not visible); others just overflow.
    let stackItem = element;
    while (stack && stackItem.parentElement && stackItem.parentElement !== stack) {
        stackItem = stackItem.parentElement;
    }
    const stackRoom = () => {
        if (!stack || !stack.classList.contains('stack')) return Infinity;
        if (getComputedStyle(stackItem).overflowY === 'visible') return Infinity;
        const stackMax = parseFloat(getComputedStyle(stack).maxHeight);
        if (Number.isNaN(stackMax)) return Infinity;
        return Math.max(0, stackMax - stack.getBoundingClientRect().height);
    };

    // `base` is the size before this change; never clamp below it so a widget
    // that already extends past the viewport limit does not jump smaller.
    const clampedSize = (width, height, base) => {
        const widthRect = widthTarget.getBoundingClientRect();
        const heightRect = heightTarget.getBoundingClientRect();
        const lowerWidth = Math.min(minWidth, naturalSize.width);
        const lowerHeight = Math.min(minHeight, naturalSize.height);
        const maxWidth = Math.max(
            lowerWidth,
            base.width,
            (anchorRight ? widthRect.right : window.innerWidth - widthRect.left) - VIEWPORT_MARGIN
        );
        const maxHeight = Math.max(
            lowerHeight,
            base.height,
            Math.min(
                (anchorBottom ? heightRect.bottom : window.innerHeight - heightRect.top) - VIEWPORT_MARGIN,
                visibleHeight() + stackRoom()
            )
        );
        return {
            width: Math.min(Math.max(width, lowerWidth), maxWidth),
            height: Math.min(Math.max(height, lowerHeight), maxHeight),
        };
    };

    const applySize = (width, height, base) => {
        if (!naturalSize) naturalSize = base;
        const size = clampedSize(width, height, base);
        // Inline or stylesheet max-width/max-height caps would otherwise block growth.
        // Sizes are measured as border boxes; convert for content-box elements.
        if (!verticalOnly) {
            widthTarget.style.maxWidth = 'none';
            widthTarget.style.width = `${size.width - boxExtra(widthTarget, 'x')}px`;
        }
        heightTarget.style.maxHeight = 'none';
        heightTarget.style.height = `${size.height - boxExtra(heightTarget, 'y')}px`;
        fitWithinGrid();
    };

    // The stacks sit in a two column `1fr` grid, which widens a column to fit
    // its widest widget and pushes the other side off screen. Give back any
    // overflow from the width the user chose.
    const grid = stack && stack.classList.contains('stack') ? stack.parentElement : null;
    const fitWithinGrid = () => {
        if (!grid || verticalOnly || !widthTarget.style.width) return;
        const overflow = grid.scrollWidth - grid.clientWidth;
        if (overflow <= 0) return;
        const width = parseFloat(widthTarget.style.width);
        widthTarget.style.width = `${Math.max(minWidth - boxExtra(widthTarget, 'x'), width - overflow)}px`;
    };
    window.addEventListener('resize', fitWithinGrid);

    const reset = () => {
        initialStyles.forEach(({ target, width, height, maxWidth, maxHeight }) => {
            target.style.width = width;
            target.style.height = height;
            target.style.maxWidth = maxWidth;
            target.style.maxHeight = maxHeight;
        });
        naturalSize = null;
    };

    let startX = 0;
    let startY = 0;
    let startSize = null;

    handle.addEventListener('pointerdown', (event) => {
        // Keep the drag away from deck.gl, which would otherwise pan the map.
        event.preventDefault();
        event.stopPropagation();
        startX = event.clientX;
        startY = event.clientY;
        startSize = currentSize();
        element.classList.add('widget-resizing');
        handle.setPointerCapture(event.pointerId);
    });

    handle.addEventListener('pointermove', (event) => {
        if (!handle.hasPointerCapture(event.pointerId)) return;
        event.preventDefault();
        event.stopPropagation();
        applySize(
            startSize.width + dirX * (event.clientX - startX),
            startSize.height + dirY * (event.clientY - startY),
            startSize
        );
    });

    const endDrag = (event) => {
        if (!handle.hasPointerCapture(event.pointerId)) return;
        handle.releasePointerCapture(event.pointerId);
        element.classList.remove('widget-resizing');
    };
    handle.addEventListener('pointerup', endDrag);
    handle.addEventListener('pointercancel', endDrag);

    // Stop clicks reaching widgets that act on them (e.g. the minimap recentres).
    handle.addEventListener('click', (event) => event.stopPropagation());

    handle.addEventListener('dblclick', (event) => {
        event.preventDefault();
        event.stopPropagation();
        reset();
    });

    handle.addEventListener('keydown', (event) => {
        const deltas = {
            ArrowLeft: [-KEY_STEP, 0],
            ArrowRight: [KEY_STEP, 0],
            ArrowUp: [0, -KEY_STEP],
            ArrowDown: [0, KEY_STEP],
        };
        const delta = deltas[event.key];
        if (!delta) return;
        event.preventDefault();
        event.stopPropagation();
        const size = currentSize();
        applySize(size.width + dirX * delta[0], size.height + dirY * delta[1], size);
    });

    return {
        handle,
        reset,
        setHandleVisible(visible) {
            handle.classList.toggle('hidden', !visible);
        },
    };
}

/**
 * Whether an element is drawn vertically flipped by its own or its ancestors'
 * transforms (the bottom stacks use ``scaleY(-1)``).
 * @param {HTMLElement} element
 * @returns {boolean}
 */
function isFlippedVertically(element) {
    let flipped = false;
    for (let el = element; el && el !== document.documentElement; el = el.parentElement) {
        const transform = getComputedStyle(el).transform;
        if (transform && transform !== 'none' && new DOMMatrix(transform).d < 0) {
            flipped = !flipped;
        }
    }
    return flipped;
}

/**
 * Padding plus border along one axis for content-box elements, i.e. the
 * difference between the border box size and the CSS width/height.
 * @param {HTMLElement} element
 * @param {'x'|'y'} axis
 * @returns {number}
 */
function boxExtra(element, axis) {
    const style = getComputedStyle(element);
    if (style.boxSizing === 'border-box') return 0;
    const sides = axis === 'x' ? ['Left', 'Right'] : ['Top', 'Bottom'];
    return sides.reduce(
        (total, side) => total
            + (parseFloat(style[`padding${side}`]) || 0)
            + (parseFloat(style[`border${side}Width`]) || 0),
        0
    );
}
