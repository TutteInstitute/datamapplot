
// Touch "tap-to-inspect": touch devices have no hover, so tapping a point
// shows its hover content in a bottom-sheet card; tapping empty space (or
// the close button) dismisses it. Only pointerType === 'touch' events are
// diverted into the card flow — mouse and pen behavior is unchanged. When
// an on_click action is configured it is exposed as an explicit button in
// the card rather than firing on the tap itself, so the point can be
// inspected before navigating away.
class TapToInspectManager {
    constructor(datamap, config = {}) {
        this.config = {
            // (info) => string | {html|text, style?, className?} | Promise | null
            // Defaults to the datamap's own tooltip function.
            contentProvider: null,
            // Optional (info) => same shape, rendered while a Promise resolves.
            loadingContent: null,
            // False when the dynamic tooltip owns the hover path.
            useHoverPath: true,
            actionLabel: 'Open',
            selfCloseGuardMs: 400,
            dragThresholdPx: 10,
            ...config // Override defaults with user-provided config
        };

        this.datamap = datamap;
        this.card = null;
        this.contentElement = null;
        this.actionButton = null;
        this.lastPointerType = 'mouse';
        this.isDrag = false;
        this.lastOpenTime = 0;
        this._dragStart = null;
        this._currentInfo = null;
        this._currentEvent = null;
        this._showToken = 0;

        // Hook consumed by DataMap.addMetaData for hover-tooltip wrapping
        // and user-on_click suppression.
        datamap._tapInspect = this;

        this._bindPointerTracking();
        this._bindDeckHandlers();
        this._bindDocumentDismiss();
    }

    // mjolnir.js events carry pointerType directly; fall back to the source
    // browser event for anything that doesn't.
    _pointerType(event) {
        return (
            event?.pointerType ??
            event?.srcEvent?.pointerType ??
            (event?.srcEvent?.type?.startsWith('touch') ? 'touch' : 'mouse')
        );
    }

    // Capture-phase listeners run before deck.gl's own canvas handlers, so
    // lastPointerType and isDrag are always current when deck callbacks fire.
    _bindPointerTracking() {
        const container = this.datamap.container;
        const threshold = this.config.dragThresholdPx * this.config.dragThresholdPx;
        this._onPointerDown = (e) => {
            this.lastPointerType = e.pointerType || 'mouse';
            this._dragStart = { x: e.clientX, y: e.clientY };
            this.isDrag = false;
        };
        this._onPointerMove = (e) => {
            this.lastPointerType = e.pointerType || 'mouse';
            if (!this._dragStart) return;
            const dx = e.clientX - this._dragStart.x;
            const dy = e.clientY - this._dragStart.y;
            if (dx * dx + dy * dy > threshold) {
                this.isDrag = true;
            }
        };
        this._onPointerUp = () => {
            this._dragStart = null;
        };
        container.addEventListener('pointerdown', this._onPointerDown, { capture: true, passive: true });
        container.addEventListener('pointermove', this._onPointerMove, { capture: true, passive: true });
        container.addEventListener('pointerup', this._onPointerUp, { capture: true, passive: true });
    }

    _bindDeckHandlers() {
        if (this.config.useHoverPath) {
            // A tap synthesizes a pointermove, so hover fires on taps that
            // deck.gl's click recognizer sometimes misses.
            this.datamap.onHover('tapToInspect', this._handleHover.bind(this));
        }
        this.datamap.onClick('tapToInspect', this._handleClick.bind(this));
    }

    _bindDocumentDismiss() {
        this._onDocumentClick = (e) => {
            if (!this.card || !this.card.classList.contains('visible')) return;
            if (this.card.contains(e.target)) return;
            // The tap that opened the card also bubbles a click to the
            // document; ignore clicks inside the guard window.
            if (Date.now() - this.lastOpenTime < this.config.selfCloseGuardMs) return;
            this.hide();
        };
        document.addEventListener('click', this._onDocumentClick);
    }

    // Wraps the deck.gl getTooltip function so hover tooltips stay
    // mouse/pen-only and a tap doesn't flash the tooltip under the card.
    wrapTooltip(tooltipFunction) {
        return (info) => (this.lastPointerType === 'touch' ? null : tooltipFunction(info));
    }

    shouldSuppressUserClick(info, event) {
        return this._pointerType(event) === 'touch';
    }

    _handleHover(info, event) {
        if (this._pointerType(event) !== 'touch') return;
        if (this.isDrag) return;
        if (info && info.picked) {
            this.show(info, event);
        }
    }

    _handleClick(info, event) {
        if (this._pointerType(event) !== 'touch') return;
        if (info && info.picked) {
            this.show(info, event);
        } else {
            this.hide();
        }
    }

    // Mirrors the addMetaData hover_text gate so the card shows exactly
    // what the hover tooltip would.
    _defaultContent(info) {
        const datamap = this.datamap;
        if (
            datamap.metaData &&
            datamap.metaData.hasOwnProperty('hover_text') &&
            typeof datamap.tooltipFunction === 'function'
        ) {
            return datamap.tooltipFunction(info);
        }
        return null;
    }

    async show(info, event) {
        const token = ++this._showToken;
        const provider = this.config.contentProvider || this._defaultContent.bind(this);
        const hasAction = typeof this.datamap.onClickFunction === 'function';
        let content = provider(info);

        if (content && typeof content.then === 'function') {
            if (this.config.loadingContent) {
                this._open(this.config.loadingContent(info), info, event, hasAction);
            }
            content = await content;
            if (token !== this._showToken) return; // superseded or dismissed
        }
        if (!content && !hasAction) return;
        this._open(content, info, event, hasAction);
    }

    _open(content, info, event, hasAction) {
        this._ensureCard();
        this._compensateViewportScale();
        this._renderContent(content);
        this._currentInfo = { index: info.index, picked: true, layer: null };
        this._currentEvent = event;
        this.actionButton.style.display = hasAction ? 'block' : 'none';
        this.card.classList.add('visible');
        this.lastOpenTime = Date.now();
    }

    _renderContent(content) {
        const el = this.contentElement;
        el.removeAttribute('style');
        el.className = 'tap-inspect-card-content';
        if (content == null) {
            el.innerHTML = '';
        } else if (typeof content === 'string') {
            el.textContent = content;
        } else {
            // deck.gl getTooltip-style object: {html|text, style?, className?}
            if (content.html != null) {
                el.innerHTML = content.html;
            } else {
                el.textContent = content.text != null ? content.text : '';
            }
            if (content.style) Object.assign(el.style, content.style);
            if (content.className) el.className += ` ${content.className}`;
        }
    }

    _ensureCard() {
        if (this.card) return;

        this.card = document.createElement('div');
        this.card.className = 'tap-inspect-card';
        this.card.setAttribute('role', 'dialog');

        const closeButton = document.createElement('button');
        closeButton.className = 'tap-inspect-close';
        closeButton.setAttribute('aria-label', 'Close');
        closeButton.innerHTML = '&times;';
        closeButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.hide();
        });

        this.contentElement = document.createElement('div');
        this.contentElement.className = 'tap-inspect-card-content';

        this.actionButton = document.createElement('button');
        this.actionButton.className = 'tap-inspect-action';
        this.actionButton.textContent = this.config.actionLabel;
        this.actionButton.style.display = 'none';
        this.actionButton.addEventListener('click', () => {
            if (typeof this.datamap.onClickFunction === 'function' && this._currentInfo) {
                this.datamap.onClickFunction(this._currentInfo, this._currentEvent);
            }
        });

        this.card.appendChild(closeButton);
        this.card.appendChild(this.contentElement);
        this.card.appendChild(this.actionButton);
        document.body.appendChild(this.card);
    }

    // Pages without a <meta name="viewport"> render through a ~980px layout
    // viewport that mobile browsers scale down, leaving the card unreadably
    // small. Scale the card's font (all card sizes are in em) to compensate.
    // Once the output ships a viewport meta this is a no-op (scale ≈ 1).
    _compensateViewportScale() {
        const scale = window.visualViewport?.scale;
        if (scale && scale < 0.9) {
            this.card.style.fontSize = `${Math.min(0.9 / scale, 3)}em`;
        } else {
            this.card.style.fontSize = '';
        }
    }

    // On touch devices the point highlight comes from the browser's
    // compatibility mousemove fired after a tap (deck.gl's event layer
    // drives hover from mouse events), and no compatibility mouseleave ever
    // follows -- so the tapped point stays highlighted when the card is
    // dismissed from a DOM control (close button, other chrome). Send the
    // "mouse moved to an empty spot" event the browser never sends: probe
    // for a screen position with nothing to pick and dispatch a synthetic
    // mousemove there, so deck runs its normal empty-hover clearing path.
    _clearPointHighlight() {
        const deckgl = this.datamap.deckgl;
        const canvas = deckgl.canvas;
        if (!canvas || typeof deckgl.pickObject !== 'function' || typeof MouseEvent !== 'function') {
            return;
        }
        const rect = canvas.getBoundingClientRect();
        const w = rect.width;
        const h = rect.height;
        const probes = [
            [3, 3], [w - 4, 3], [3, h - 4], [w - 4, h - 4],
            [w / 2, 3], [w / 2, h - 4], [3, h / 2], [w - 4, h / 2],
        ];
        for (const [x, y] of probes) {
            let picked;
            try {
                picked = deckgl.pickObject({ x: x, y: y, radius: 2 });
            } catch (e) {
                return;
            }
            if (!picked) {
                canvas.dispatchEvent(new MouseEvent('mousemove', {
                    bubbles: true,
                    clientX: rect.left + x,
                    clientY: rect.top + y,
                }));
                return;
            }
        }
    }

    hide() {
        this._showToken++; // cancel any pending async show
        if (this.card) {
            this.card.classList.remove('visible');
        }
        this._clearPointHighlight();
    }

    destroy() {
        this.datamap.offHover('tapToInspect');
        this.datamap.offClick('tapToInspect');
        const container = this.datamap.container;
        container.removeEventListener('pointerdown', this._onPointerDown, { capture: true });
        container.removeEventListener('pointermove', this._onPointerMove, { capture: true });
        container.removeEventListener('pointerup', this._onPointerUp, { capture: true });
        document.removeEventListener('click', this._onDocumentClick);
        if (this.card && this.card.parentNode) {
            this.card.parentNode.removeChild(this.card);
        }
        this.card = null;
        if (this.datamap._tapInspect === this) {
            delete this.datamap._tapInspect;
        }
    }
}
