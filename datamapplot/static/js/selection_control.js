/**
 * SelectionControl - UI for managing selection modes and selection groups
 */
class SelectionControl {
    constructor(container, datamap, options = {}) {
        this.container = container;
        this.datamap = datamap;
        this.selectionManager = datamap.dataSelectionManager;

        this.options = {
            showModes: options.showModes !== undefined ? options.showModes : true,
            showGroups: options.showGroups !== undefined ? options.showGroups : true,
            showClear: options.showClear !== undefined ? options.showClear : true,
            maxGroups: options.maxGroups || 10,
        };

        this.render();
        this.attachEventListeners();
    }

    render() {
        this.container.innerHTML = '';

        // Title
        const title = document.createElement('div');
        title.className = 'selection-control-title';
        title.textContent = 'Selection Control';
        this.container.appendChild(title);

        // Selection modes section
        if (this.options.showModes) {
            const modesSection = document.createElement('div');
            modesSection.className = 'selection-control-section';

            const modesLabel = document.createElement('div');
            modesLabel.className = 'selection-control-label';
            modesLabel.textContent = 'Selection Mode:';
            modesSection.appendChild(modesLabel);

            const modesContainer = document.createElement('div');
            modesContainer.className = 'selection-mode-buttons';

            const modes = [
                { id: 'replace', label: 'Replace', icon: '◉' },
                { id: 'add', label: 'Add', icon: '⊕' },
                { id: 'subtract', label: 'Remove', icon: '⊖' },
                { id: 'intersect', label: 'Intersect', icon: '∩' }
            ];

            modes.forEach(mode => {
                const button = document.createElement('button');
                button.className = 'selection-mode-button';
                button.dataset.mode = mode.id;
                button.innerHTML = `<span class="mode-icon">${mode.icon}</span><span class="mode-label">${mode.label}</span>`;
                button.title = `${mode.label} selection mode`;

                if (mode.id === this.selectionManager.getSelectionMode()) {
                    button.classList.add('active');
                }

                modesContainer.appendChild(button);
            });

            modesSection.appendChild(modesContainer);
            this.container.appendChild(modesSection);
        }

        // Clear selection button
        if (this.options.showClear) {
            const clearButton = document.createElement('button');
            clearButton.className = 'selection-control-clear-button';
            clearButton.textContent = 'Clear Selection';
            clearButton.id = 'clear-selection-btn';
            this.container.appendChild(clearButton);
        }

        // Selection groups section
        if (this.options.showGroups) {
            const groupsSection = document.createElement('div');
            groupsSection.className = 'selection-control-section';

            const groupsLabel = document.createElement('div');
            groupsLabel.className = 'selection-control-label';
            groupsLabel.textContent = 'Selection Groups:';
            groupsSection.appendChild(groupsLabel);

            // Save group controls
            const saveGroupContainer = document.createElement('div');
            saveGroupContainer.className = 'save-group-container';

            const groupInput = document.createElement('input');
            groupInput.type = 'text';
            groupInput.id = 'group-name-input';
            groupInput.className = 'group-name-input';
            groupInput.placeholder = 'Group name...';
            groupInput.maxLength = 30;

            const saveButton = document.createElement('button');
            saveButton.id = 'save-group-btn';
            saveButton.className = 'save-group-button';
            saveButton.textContent = 'Save';
            saveButton.disabled = true;

            saveGroupContainer.appendChild(groupInput);
            saveGroupContainer.appendChild(saveButton);
            groupsSection.appendChild(saveGroupContainer);

            // Groups list
            const groupsList = document.createElement('div');
            groupsList.id = 'selection-groups-list';
            groupsList.className = 'selection-groups-list';
            groupsSection.appendChild(groupsList);

            this.container.appendChild(groupsSection);

            // Render existing groups
            this.renderGroupsList();
        }
    }

    renderGroupsList() {
        const groupsList = document.getElementById('selection-groups-list');
        if (!groupsList) return;

        groupsList.innerHTML = '';

        const groups = this.selectionManager.getSelectionGroups();

        if (groups.length === 0) {
            const emptyMsg = document.createElement('div');
            emptyMsg.className = 'groups-empty-message';
            emptyMsg.textContent = 'No saved groups';
            groupsList.appendChild(emptyMsg);
            return;
        }

        groups.forEach((groupName, index) => {
            const groupItem = document.createElement('div');
            groupItem.className = 'selection-group-item';
            if (this.selectionManager.activeGroup === groupName) {
                groupItem.classList.add('active');
            }

            const groupInfo = document.createElement('div');
            groupInfo.className = 'group-info';

            const colorIndicator = document.createElement('span');
            colorIndicator.className = 'group-color-indicator';
            const colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
                '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'];
            colorIndicator.style.backgroundColor = colors[index % colors.length];

            const groupLabel = document.createElement('span');
            groupLabel.className = 'group-label';
            groupLabel.textContent = groupName;

            const groupCount = document.createElement('span');
            groupCount.className = 'group-count';
            const indices = this.selectionManager.getGroupIndices(groupName);
            groupCount.textContent = `(${indices.size})`;

            groupInfo.appendChild(colorIndicator);
            groupInfo.appendChild(groupLabel);
            groupInfo.appendChild(groupCount);

            const groupActions = document.createElement('div');
            groupActions.className = 'group-actions';

            const loadButton = document.createElement('button');
            loadButton.className = 'group-action-button load-button';
            loadButton.textContent = 'Load';
            loadButton.title = 'Load this selection group';
            loadButton.dataset.groupName = groupName;

            const deleteButton = document.createElement('button');
            deleteButton.className = 'group-action-button delete-button';
            deleteButton.textContent = '×';
            deleteButton.title = 'Delete this group';
            deleteButton.dataset.groupName = groupName;

            groupActions.appendChild(loadButton);
            groupActions.appendChild(deleteButton);

            groupItem.appendChild(groupInfo);
            groupItem.appendChild(groupActions);
            groupsList.appendChild(groupItem);
        });
    }

    attachEventListeners() {
        // Mode button clicks
        if (this.options.showModes) {
            const modeButtons = this.container.querySelectorAll('.selection-mode-button');
            modeButtons.forEach(button => {
                button.addEventListener('click', () => {
                    const mode = button.dataset.mode;
                    this.selectionManager.setSelectionMode(mode);

                    // Update active state
                    modeButtons.forEach(btn => btn.classList.remove('active'));
                    button.classList.add('active');
                });
            });
        }

        // Clear button
        if (this.options.showClear) {
            const clearButton = document.getElementById('clear-selection-btn');
            if (clearButton) {
                clearButton.addEventListener('click', () => {
                    this.selectionManager.clearAllSelections();
                    this.datamap.refreshSelection();
                    this.renderGroupsList();
                });
            }
        }

        // Group input and save button
        if (this.options.showGroups) {
            const groupInput = document.getElementById('group-name-input');
            const saveButton = document.getElementById('save-group-btn');

            if (groupInput && saveButton) {
                groupInput.addEventListener('input', () => {
                    const hasSelection = this.selectionManager.getSelectedIndices().size > 0;
                    const hasName = groupInput.value.trim().length > 0;
                    saveButton.disabled = !(hasSelection && hasName);
                });

                groupInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter' && !saveButton.disabled) {
                        this.saveGroup();
                    }
                });

                saveButton.addEventListener('click', () => {
                    this.saveGroup();
                });
            }

            // Delegate events for group actions
            const groupsList = document.getElementById('selection-groups-list');
            if (groupsList) {
                groupsList.addEventListener('click', (e) => {
                    const loadButton = e.target.closest('.load-button');
                    const deleteButton = e.target.closest('.delete-button');

                    if (loadButton) {
                        const groupName = loadButton.dataset.groupName;
                        this.loadGroup(groupName);
                    } else if (deleteButton) {
                        const groupName = deleteButton.dataset.groupName;
                        this.deleteGroup(groupName);
                    }
                });
            }
        }
    }

    saveGroup() {
        const groupInput = document.getElementById('group-name-input');
        if (!groupInput) return;

        const groupName = groupInput.value.trim();
        if (!groupName) return;

        const currentSelection = this.selectionManager.getSelectedIndices();
        if (currentSelection.size === 0) {
            alert('No points selected to save as group');
            return;
        }

        const existingGroups = this.selectionManager.getSelectionGroups();
        if (existingGroups.includes(groupName)) {
            if (!confirm(`Group "${groupName}" already exists. Overwrite?`)) {
                return;
            }
        }

        if (existingGroups.length >= this.options.maxGroups && !existingGroups.includes(groupName)) {
            alert(`Maximum of ${this.options.maxGroups} groups allowed`);
            return;
        }

        this.selectionManager.saveSelectionAsGroup(groupName);
        groupInput.value = '';
        this.renderGroupsList();
    }

    loadGroup(groupName) {
        if (this.selectionManager.loadSelectionGroup(groupName)) {
            // Update the datamap visualization
            const indices = Array.from(this.selectionManager.getSelectedIndices());
            this.datamap.addSelection(indices, `group-${groupName}`);
            this.renderGroupsList();
        }
    }

    deleteGroup(groupName) {
        if (confirm(`Delete group "${groupName}"?`)) {
            this.selectionManager.deleteSelectionGroup(groupName);
            if (this.selectionManager.activeGroup === groupName) {
                this.datamap.removeSelection(`group-${groupName}`);
            }
            this.renderGroupsList();
        }
    }

    // Allow external updates (e.g., when selection changes)
    updateSaveButtonState() {
        const saveButton = document.getElementById('save-group-btn');
        const groupInput = document.getElementById('group-name-input');
        if (saveButton && groupInput) {
            const hasSelection = this.selectionManager.getSelectedIndices().size > 0;
            const hasName = groupInput.value.trim().length > 0;
            saveButton.disabled = !(hasSelection && hasName);
        }
    }
}
