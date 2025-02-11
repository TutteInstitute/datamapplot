// Helper to get the next nested list out of the table of contents.
var getNextSibling = function (elem, selector) {
    // Get the next sibling element
    var sibling = elem.nextElementSibling;

    // If there's no selector, return the first sibling
    if (!selector) return sibling;

    // If the sibling matches our selector, use it
    // If not, jump to the next sibling and continue the loop
    while (sibling) {
        if (sibling.matches(selector)) return sibling;
        sibling = sibling.nextElementSibling
    }
};

function formatTocButtonHtml(icon, labelId) {
    return `<button class="toc-btn" data-label-id="${labelId}">${icon}</button>`;
}

class TableOfContents {
    constructor(
        tocContainer,
        datamap,
        buttons,
        icon,
    ) {
        this.container = tocContainer;
        this.datamap = datamap;
        this.elements = datamap.labelData;
        this.rootLayerNo = Math.max(...datamap.labelData.map(e => e.layer_no));
        this.parentChildMap = this.buildParentChildMap();
        
        this.container.innerHTML = `
            <button class="expand-all-btn" data-expanded="false">Expand All</button>
            ${this.buildTreeHtml(buttons, icon)}
        `;
    
        this.setupCaretHandlers();
        this.setupLabelHandlers(datamap);
        this.setupExpandAllHandler();
        this.highlightElements(this.elements);
    }
    

    buildParentChildMap() {
        const parentChildMap = new Map();
        
        // First, handle elements with actual parents
        this.elements.forEach(element => {
            const parentId = element.parent;
            if (parentId) {
                if (!parentChildMap.has(parentId)) {
                    parentChildMap.set(parentId, []);
                }
                parentChildMap.get(parentId).push(element);
            } else {
                // Handle root level elements
                if (!parentChildMap.has(null)) {
                    parentChildMap.set(null, []);
                }
                parentChildMap.get(null).push(element);
            }
        });
    
        return parentChildMap;
    }

    buildTreeHtml(buttons, icon, parentId = null) {
        const children = this.parentChildMap.get(parentId) || [];
        
        if (children.length === 0) return '';
    //.map(x=>datamap.pointData[x]
        return `
            <ul class="nested">
                ${children.map(label => `
                    <li>
                        <span class="${label.lowest_layer ? 'bullet' : 'caret'} ${label.id.endsWith('-1') ? 'unlabeled' : ''}" data-element-id="${label.id}">
                        </span>${buttons ? formatTocButtonHtml(icon, label.id) : ''}
                        <span class="toc-label" data-bounds="${JSON.stringify(label.bounds)}" data-label-id="${label.id}">
                            ${label.label || label.id}
                        </span>
                        ${this.buildTreeHtml(buttons, icon, label.id)}
                    </li>
                `).join('')}
            </ul>
        `;
    }

    setupLabelHandlers(datamap) {
        var toc = this
        this.container.querySelectorAll('.toc-label').forEach(button => {
            button.addEventListener('click', function() {
                const bounds = JSON.parse(this.dataset.bounds);
                const labelId = this.dataset.labelId;
                toc.zoomToLabelBounds(bounds, labelId);
            });
        });
    }

    zoomToLabelBounds(bounds, labelId) {
        const { viewportWidth, viewportHeight } = getInitialViewportSize();
        const { zoomLevel, dataCenter } = calculateZoomLevel(bounds, viewportWidth, viewportHeight);
        const viewState = {
            latitude: dataCenter[1],
            longitude: dataCenter[0],
            zoom: zoomLevel,
            transitionDuration: 1000,
        };
        this.datamap.deckgl.setProps({
            initialViewState: {...viewState},
        });
    }

    highlightElements(elements) {
        this.container.querySelectorAll('.highlighted').forEach(element => {
            element.classList.remove('highlighted');
        });
        
        elements.forEach(element => {
            this.highlightElementAndParents(element);
        });
    }

    highlightElementAndParents(element) {
        const elementSpan = this.container.querySelector(`[data-element-id="${element.id}"]`);
        if (elementSpan) {
            elementSpan.classList.add('highlighted');
            
            let currentElement = element;
            while (currentElement.parent) {
                const parentElement = this.elements.find(e => e.id === currentElement.parent);
                if (parentElement) {
                    const parentSpan = this.container.querySelector(`[data-element-id="${parentElement.id}"]`);
                    if (parentSpan) {
                        parentSpan.classList.add('highlighted');
                    }
                    currentElement = parentElement;
                } else {
                    break;
                }
            }
        }
    }

    setupCaretHandlers() {
        this.container.querySelectorAll('.caret').forEach(caret => {
            caret.addEventListener('click', function() {
                this.classList.toggle('caret-down');
                const nestedList = getNextSibling(this, '.nested');
                if (nestedList) {
                    nestedList.classList.toggle('active');
                }
            });
        });
    }

    setupExpandAllHandler() {
        const expandAllBtn = this.container.querySelector('.expand-all-btn');
        expandAllBtn.addEventListener('click', function() {
            const isExpanded = this.dataset.expanded === 'true';
            const carets = document.querySelectorAll('.caret');
            
            carets.forEach(caret => {
                const nestedList = getNextSibling(caret, '.nested');
                if (isExpanded) {
                    // Collapse all
                    caret.classList.remove('caret-down');
                    if (nestedList) {
                        nestedList.classList.remove('active');
                    }
                } else {
                    // Expand all
                    caret.classList.add('caret-down');
                    if (nestedList) {
                        nestedList.classList.add('active');
                    }
                }
            });
            
            // Toggle button state
            this.dataset.expanded = (!isExpanded).toString();
            this.textContent = isExpanded ? 'Expand All' : 'Collapse All';
        });
    }
}