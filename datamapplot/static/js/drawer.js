/**
 * DrawerManager - Manages slide-out drawer panels for widgets
 * 
 * Handles opening/closing of left and right drawers with smooth animations
 * and content push effects.
 */
class DrawerManager {
    /**
     * Create a new DrawerManager instance
     * 
     * @param {Object} options - Configuration options
     * @param {boolean} options.leftEnabled - Whether left drawer is enabled
     * @param {boolean} options.rightEnabled - Whether right drawer is enabled
     * @param {boolean} options.persistState - Whether to save drawer state to localStorage
     * @param {number} options.drawerWidth - Width of drawer in pixels (default: 400)
     */
    constructor(options = {}) {
        this.options = {
            leftEnabled: options.leftEnabled || false,
            rightEnabled: options.rightEnabled || false,
            persistState: options.persistState !== undefined ? options.persistState : true,
            drawerWidth: options.drawerWidth || 400,
        };

        this.state = {
            leftOpen: false,
            rightOpen: false,
        };

        this.elements = {
            leftDrawer: null,
            rightDrawer: null,
            leftHandle: null,
            rightHandle: null,
            contentWrapper: null,
        };

        this.init();
    }

    /**
     * Initialize the drawer manager
     */
    init() {
        // Get DOM elements
        this.elements.leftDrawer = document.querySelector('.drawer-container.drawer-left');
        this.elements.rightDrawer = document.querySelector('.drawer-container.drawer-right');
        this.elements.leftHandle = document.querySelector('.drawer-handle.left');
        this.elements.rightHandle = document.querySelector('.drawer-handle.right');
        this.elements.contentWrapper = document.querySelector('.content-wrapper');

        // Setup event listeners
        this.setupEventListeners();

        // Restore state from localStorage if enabled
        if (this.options.persistState) {
            this.restoreState();
        }

        // Setup keyboard shortcuts
        this.setupKeyboardShortcuts();
    }

    /**
     * Setup event listeners for drawer handles
     */
    setupEventListeners() {
        if (this.options.leftEnabled && this.elements.leftHandle) {
            this.elements.leftHandle.addEventListener('click', () => {
                this.toggleDrawer('left');
            });
        }

        if (this.options.rightEnabled && this.elements.rightHandle) {
            this.elements.rightHandle.addEventListener('click', () => {
                this.toggleDrawer('right');
            });
        }
    }

    /**
     * Setup keyboard shortcuts for drawer control
     */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Escape key closes all drawers
            if (e.key === 'Escape') {
                if (this.state.leftOpen || this.state.rightOpen) {
                    this.closeAll();
                    e.preventDefault();
                }
            }

            // Ctrl/Cmd + [ toggles left drawer
            if ((e.ctrlKey || e.metaKey) && e.key === '[') {
                if (this.options.leftEnabled) {
                    this.toggleDrawer('left');
                    e.preventDefault();
                }
            }

            // Ctrl/Cmd + ] toggles right drawer
            if ((e.ctrlKey || e.metaKey) && e.key === ']') {
                if (this.options.rightEnabled) {
                    this.toggleDrawer('right');
                    e.preventDefault();
                }
            }
        });
    }

    /**
     * Toggle a drawer open/closed
     * 
     * @param {string} side - 'left' or 'right'
     */
    toggleDrawer(side) {
        if (side === 'left' && this.options.leftEnabled) {
            this.state.leftOpen = !this.state.leftOpen;
            this.updateDrawer('left');
        } else if (side === 'right' && this.options.rightEnabled) {
            this.state.rightOpen = !this.state.rightOpen;
            this.updateDrawer('right');
        }

        this.updateContentWrapper();

        if (this.options.persistState) {
            this.saveState();
        }

        // Fire custom event
        this.fireDrawerEvent(side, this.state[`${side}Open`]);
    }

    /**
     * Open a specific drawer
     * 
     * @param {string} side - 'left' or 'right'
     */
    openDrawer(side) {
        if ((side === 'left' && this.options.leftEnabled) ||
            (side === 'right' && this.options.rightEnabled)) {
            if (!this.state[`${side}Open`]) {
                this.toggleDrawer(side);
            }
        }
    }

    /**
     * Close a specific drawer
     * 
     * @param {string} side - 'left' or 'right'
     */
    closeDrawer(side) {
        if ((side === 'left' && this.options.leftEnabled) ||
            (side === 'right' && this.options.rightEnabled)) {
            if (this.state[`${side}Open`]) {
                this.toggleDrawer(side);
            }
        }
    }

    /**
     * Close all open drawers
     */
    closeAll() {
        if (this.state.leftOpen) {
            this.closeDrawer('left');
        }
        if (this.state.rightOpen) {
            this.closeDrawer('right');
        }
    }

    /**
     * Update drawer and handle visual state
     * 
     * @param {string} side - 'left' or 'right'
     */
    updateDrawer(side) {
        const drawer = this.elements[`${side}Drawer`];
        const handle = this.elements[`${side}Handle`];
        const isOpen = this.state[`${side}Open`];

        if (drawer) {
            if (isOpen) {
                drawer.classList.add('open');
            } else {
                drawer.classList.remove('open');
            }
        }

        if (handle) {
            if (isOpen) {
                handle.classList.add('drawer-open');
            } else {
                handle.classList.remove('drawer-open');
            }
        }
    }

    /**
     * Update content wrapper position based on open drawers
     */
    updateContentWrapper() {
        if (!this.elements.contentWrapper) return;

        // Remove all drawer-open classes
        this.elements.contentWrapper.classList.remove('drawer-left-open', 'drawer-right-open');

        // Add appropriate class based on state
        if (this.state.leftOpen) {
            this.elements.contentWrapper.classList.add('drawer-left-open');
        }
        if (this.state.rightOpen) {
            this.elements.contentWrapper.classList.add('drawer-right-open');
        }
    }

    /**
     * Save drawer state to localStorage
     */
    saveState() {
        try {
            const state = {
                leftOpen: this.state.leftOpen,
                rightOpen: this.state.rightOpen,
            };
            localStorage.setItem('datamapplot-drawer-state', JSON.stringify(state));
        } catch (e) {
            console.warn('Failed to save drawer state:', e);
        }
    }

    /**
     * Restore drawer state from localStorage
     */
    restoreState() {
        try {
            const saved = localStorage.getItem('datamapplot-drawer-state');
            if (saved) {
                const state = JSON.parse(saved);

                if (state.leftOpen && this.options.leftEnabled) {
                    this.state.leftOpen = true;
                    this.updateDrawer('left');
                }

                if (state.rightOpen && this.options.rightEnabled) {
                    this.state.rightOpen = true;
                    this.updateDrawer('right');
                }

                this.updateContentWrapper();
            }
        } catch (e) {
            console.warn('Failed to restore drawer state:', e);
        }
    }

    /**
     * Fire a custom event when drawer state changes
     * 
     * @param {string} side - 'left' or 'right'
     * @param {boolean} isOpen - Whether drawer is now open
     */
    fireDrawerEvent(side, isOpen) {
        const event = new CustomEvent('drawer-state-change', {
            detail: {
                side: side,
                isOpen: isOpen,
                state: { ...this.state },
            }
        });
        document.dispatchEvent(event);
    }

    /**
     * Get current drawer state
     * 
     * @returns {Object} Current state object
     */
    getState() {
        return { ...this.state };
    }

    /**
     * Check if a specific drawer is open
     * 
     * @param {string} side - 'left' or 'right'
     * @returns {boolean} Whether the drawer is open
     */
    isOpen(side) {
        return this.state[`${side}Open`] || false;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DrawerManager;
}
