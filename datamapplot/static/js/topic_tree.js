// Helper to get the next nested list out of the topic tree.
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

function formatTopicTreeButtonHtml(icon, labelId) {
    return `<button class="topic-tree-btn" data-label-id="${labelId}">${icon}</button>`;
}

class TopicTree {
    constructor(
        topicTreeContainer,
        datamap,
        buttons,
        icon,
        options = {
            title: "Topic Tree",
            maxWidth: "30vw",
            maxHeight: "42vh",
            fontSize: "12pt",
            colorBullets: false,
        }
    ) {
        this.container = topicTreeContainer;
        this.datamap = datamap;
        this.colorBullets = options.colorBullets;
        this.maxWidth = options.maxWidth;
        this.maxHeight = options.maxHeight;
        this.title = options.title;
        this.fontSize = options.fontSize;
        this.elements = datamap.labelData;
        this.rootLayerNo = Math.max(...datamap.labelData.map(e => e.layer_no));
        this.parentChildMap = this.buildParentChildMap();

        this.container.style.fontSize = this.fontSize;

        this.showHideButton = document.createElement('button');
        this.showHideButton.classList.add('topic-tree-close-btn');
        this.showHideButton.innerHTML = '&#10095;';
        this.container.appendChild(this.showHideButton);

        this.topicTreeContainer = document.createElement('div');
        this.header = document.createElement('div');
        this.header.classList.add('topic-tree-header');
        this.heading = document.createElement('h3');
        this.heading.textContent = this.title;
        this.expandAllBtn = document.createElement('button');
        this.expandAllBtn.classList.add('expand-all-btn');
        this.expandAllBtn.dataset.expanded = 'false';
        this.expandAllBtn.textContent = 'Expand All';

        this.header.appendChild(this.heading);
        this.header.appendChild(this.expandAllBtn);
        this.topicTreeContainer.appendChild(this.header);

        this.topicTreeBody = document.createElement('div');
        this.topicTreeBody.id = 'topic-tree-body';
        this.topicTreeBody.style.maxWidth = this.maxWidth;
        this.topicTreeBody.style.maxHeight = this.maxHeight;
        this.topicTreeBody.innerHTML = this.buildTreeHtml(buttons, icon);
        this.topicTreeBody.style.textWrap = 'nowrap';
        this.topicTreeBody.style.overflowX = 'auto';
        this.topicTreeContainer.appendChild(this.topicTreeBody);

        this.container.appendChild(this.topicTreeContainer);
    
        this.spanCache = new Map();
        this.parentChainCache = new Map();
        this.setupCaretHandlers();
        this.setupLabelHandlers(datamap);
        this.setupExpandAllHandler();
        this.setupShowHideHandler();
        this.initializeSpanCache();
        this.initializeParentChainCache();
        this.highlightElements(this.elements);
    }
    

    buildParentChildMap() {
        const parentChildMap = new Map();
        
        // First, handle elements with actual parents
        this.elements.forEach(element => {
            const parentId = element.parent;
            if (!parentChildMap.has(parentId)) {
                parentChildMap.set(parentId, []);
            }
            parentChildMap.get(parentId).push(element);
        });
    
        return parentChildMap;
    }

    buildTreeHtml(buttons, icon, parentId = 'base') {
        const children = this.parentChildMap.get(parentId) || [];
        
        if (children.length === 0) return '';
        if (this.colorBullets) {
            return `
                <ul class="nested">
                    ${children.map(label => `
                        <li>
                            <span class="${label.lowest_layer ? 'bullet' : 'caret'} ${label.id.endsWith('-1') ? 'unlabeled' : ''}" data-element-id="${label.id}" style="color: rgb(${label.r}, ${label.g}, ${label.b});">
                            </span>${buttons ? formatTopicTreeButtonHtml(icon, label.id) : ''}
                            <span class="topic-tree-label" data-bounds="${JSON.stringify(label.bounds)}" data-label-id="${label.id}">
                                ${label.label || label.id}
                            </span>
                            ${this.buildTreeHtml(buttons, icon, label.id)}
                        </li>
                    `).join('')}
                </ul>
            `;
        } else {
            return `
            <ul class="nested">
                ${children.map(label => `
                    <li>
                        <span class="${label.lowest_layer ? 'bullet' : 'caret'} ${label.id.endsWith('-1') ? 'unlabeled' : ''}" data-element-id="${label.id}">
                        </span>${buttons ? formatTopicTreeButtonHtml(icon, label.id) : ''}
                        <span class="topic-tree-label" data-bounds="${JSON.stringify(label.bounds)}" data-label-id="${label.id}">
                            ${label.label || label.id}
                        </span>
                        ${this.buildTreeHtml(buttons, icon, label.id)}
                    </li>
                `).join('')}
            </ul>
        `;           
        }
    }

    setupLabelHandlers(datamap) {
        var topicTree = this
        this.container.querySelectorAll('.topic-tree-label').forEach(button => {
            button.addEventListener('click', function() {
                const bounds = JSON.parse(this.dataset.bounds);
                const labelId = this.dataset.labelId;
                topicTree.zoomToLabelBounds(bounds, labelId);
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

    initializeSpanCache() {
        this.spanCache.clear();
        this.container.querySelectorAll('[data-element-id]').forEach(span => {
            this.spanCache.set(span.dataset.elementId, span);
        });
    }

    initializeParentChainCache() {
        this.parentChainCache.clear();
        this.elements.forEach(element => {
            const chain = [];
            let current = element;
            while (current.parent) {
                chain.push(current.parent);
                current = this.elements.find(e => e.id === current.parent);
                if (!current) break;
            }
            this.parentChainCache.set(element.id, chain);
        });
    }
    
    highlightElements(elements) {
        // Clear all existing highlights first
        const highlightedElements = Array.from(this.container.querySelectorAll('.highlighted'));
        highlightedElements.forEach(el => el.classList.remove('highlighted'));
        
        elements.forEach(element => {
            this.highlightElementAndParents(element);
        });
    }
    
    highlightElementAndParents(element) {
        const elementSpan = this.spanCache.get(element.id);
        if (!elementSpan) return;
        
        // If this element is already highlighted, we can skip it and its entire parent chain
        if (elementSpan.classList.contains('highlighted')) return;
        
        elementSpan.classList.add('highlighted');
        
        // Use cached parent chain, but abort as soon as we hit a highlighted element
        const parentChain = this.parentChainCache.get(element.id);
        if (parentChain) {
            for (const parentId of parentChain) {
                const parentSpan = this.spanCache.get(parentId);
                if (!parentSpan) continue;
                
                // If we hit a highlighted parent, we can stop - its parents are already done
                if (parentSpan.classList.contains('highlighted')) break;
                
                parentSpan.classList.add('highlighted');
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
        this.expandAllBtn.addEventListener('click', function() {
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

    setupShowHideHandler() {
        const topicTreeBody = this.topicTreeBody;
        const header = this.header;
        const heading = this.heading;
        const expandAllBtn = this.expandAllBtn;
        const topicTreeContainer = this.topicTreeContainer;
        this.showHideButton.addEventListener('click', function() {
            const hidden = topicTreeContainer.hidden;
            if (hidden) {
                $(topicTreeContainer).animate({height: 'show', width: 'show', opacity: 'show'}, 250);
                topicTreeContainer.hidden = false;
                topicTreeBody.style.overflowX = 'auto';
                this.classList.remove('closed');
            } else {
                topicTreeBody.style.overflowX = 'hidden';
                const carets = document.querySelectorAll('.caret');
                carets.forEach(caret => {
                    const nestedList = getNextSibling(caret, '.nested');
                    // Collapse all
                    caret.classList.remove('caret-down');
                    if (nestedList) {
                        nestedList.classList.remove('active');
                    }
                });
                expandAllBtn.textContent = 'Expand All';
                expandAllBtn.dataset.expanded = 'false';
                $(topicTreeContainer).animate({height: 'hide', width: 'hide', opacity: 'hide'}, 250);
                topicTreeContainer.hidden = true;
                this.classList.add('closed');
            }
        });
    }
}