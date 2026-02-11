/**
 * DataSelectionManager is a class designed to manage the common selected indices across distinct items.
 */
class DataSelectionManager {
    constructor(specialItem) {
        this.excludeItem = specialItem; // The item key to exclude 
        this.selectedIndicesByItem = {}; // Dictionary<string: itemId, Set: selectedIndices> to store sets of selected indices by item
        this.selectedIndicesCommon = new Set(); // Set to store the the common selected indices across all items
        this.selectedIndicesBasicCommon = new Set(); // Set to store the the common selected indices across all items

        // Selection mode and groups for advanced selection control
        this.selectionMode = 'replace'; // 'replace', 'add', 'subtract', 'intersect'
        this.selectionGroups = new Map(); // Map<groupName, Set<indices>>
        this.activeGroup = null; // Currently active group name
    }

    /**
     * Sets the selection mode for subsequent selection operations.
     * @param {string} mode - One of 'replace', 'add', 'subtract', 'intersect'.
     * @returns {undefined} No return value.
     */
    setSelectionMode(mode) {
        if (['replace', 'add', 'subtract', 'intersect'].includes(mode)) {
            this.selectionMode = mode;
        }
    }

    /**
     * Gets the current selection mode.
     * @returns {string} The current selection mode.
     */
    getSelectionMode() {
        return this.selectionMode;
    }

    /**
     * Adds or updates the selected indices for a specific item.
     * @param {number[]} indices - The array of indices to add or update.
     * @param {string} itemId - The item key associated with the indices.
     * @returns {undefined} No return value.
    */
    addOrUpdateSelectedIndicesOfItem(indices, itemId) {
        const isNewItem = !this.selectedIndicesByItem.hasOwnProperty(itemId);
        const newIndices = new Set(indices);

        if (this.selectionMode === 'replace' || isNewItem) {
            // Replace mode or first selection for this item
            this.selectedIndicesByItem[itemId] = newIndices;
        } else if (this.selectionMode === 'add') {
            // Add/Union mode
            const existing = this.selectedIndicesByItem[itemId] || new Set();
            this.selectedIndicesByItem[itemId] = existing.union(newIndices);
        } else if (this.selectionMode === 'subtract') {
            // Subtract mode
            const existing = this.selectedIndicesByItem[itemId] || new Set();
            this.selectedIndicesByItem[itemId] = existing.difference(newIndices);
        } else if (this.selectionMode === 'intersect') {
            // Intersect mode
            const existing = this.selectedIndicesByItem[itemId] || new Set();
            this.selectedIndicesByItem[itemId] = existing.intersection(newIndices);
        }

        this.#updateSelectedIndicesCommon(isNewItem ? itemId : null);
    }

    /**
     * Removes the selected indices for a specific item.
     * @param {string} itemId - The item key associated with the indices to be removed.
     * @returns {undefined} No return value.
     */
    removeSelectedIndicesOfItem(itemId) {
        if (this.selectedIndicesByItem.hasOwnProperty(itemId)) {
            delete this.selectedIndicesByItem[itemId];
            this.#updateSelectedIndicesCommon();
        }
    }

    /**
     * Gets the current set of selected indices that are common across all items.
     * @returns {Set<number>} The set of common selected indices.
     */
    getSelectedIndices() {
        return this.selectedIndicesCommon;
    }

    getBasicSelectedIndices() {
        return this.selectedIndicesBasicCommon;
    }

    hasSpecialSelection() {
        return this.selectedIndicesByItem.hasOwnProperty(this.excludeItem);
    }

    /**
     * Clears all current selections.
     * @returns {undefined} No return value.
     */
    clearAllSelections() {
        this.selectedIndicesByItem = {};
        this.selectedIndicesCommon = new Set();
        this.selectedIndicesBasicCommon = new Set();
        this.activeGroup = null;
    }

    /**
     * Saves the current selection as a named group.
     * @param {string} groupName - The name for this selection group.
     * @returns {string} The group name.
     */
    saveSelectionAsGroup(groupName) {
        this.selectionGroups.set(groupName, new Set(this.selectedIndicesCommon));
        return groupName;
    }

    /**
     * Loads a saved selection group.
     * @param {string} groupName - The name of the group to load.
     * @returns {boolean} True if group was found and loaded, false otherwise.
     */
    loadSelectionGroup(groupName) {
        if (this.selectionGroups.has(groupName)) {
            const groupIndices = this.selectionGroups.get(groupName);
            this.activeGroup = groupName;
            // Clear current selections and load group
            this.selectedIndicesByItem = {};
            this.selectedIndicesByItem[`group-${groupName}`] = new Set(groupIndices);
            this.#updateSelectedIndicesCommon();
            return true;
        }
        return false;
    }

    /**
     * Gets all saved selection group names.
     * @returns {string[]} Array of group names.
     */
    getSelectionGroups() {
        return Array.from(this.selectionGroups.keys());
    }

    /**
     * Deletes a saved selection group.
     * @param {string} groupName - The name of the group to delete.
     * @returns {boolean} True if group was deleted, false if it didn't exist.
     */
    deleteSelectionGroup(groupName) {
        if (this.activeGroup === groupName) {
            this.activeGroup = null;
        }
        return this.selectionGroups.delete(groupName);
    }

    /**
     * Gets the indices for a specific group.
     * @param {string} groupName - The name of the group.
     * @returns {Set<number>|undefined} The set of indices or undefined if group doesn't exist.
     */
    getGroupIndices(groupName) {
        return this.selectionGroups.get(groupName);
    }

    /**
     * Updates the common selected indices across all items.
     * @param {Set<number>} [newSet=null] - The new set of indices to intersect with the current common selection.
     * @returns {undefined} No return value.
     * @private
     */
    #updateSelectedIndicesCommon(newItem = null) {
        const sets = Object.values(this.selectedIndicesByItem);

        if (sets.length === 0) {
            this.selectedIndicesCommon = new Set();
            this.selectedIndicesBasicCommon = new Set();
            return;
        }
        if (sets.length === 1) {
            this.selectedIndicesCommon = sets[0];
            if (Object.keys(this.selectedIndicesByItem)[0] !== this.excludeItem) {
                this.selectedIndicesBasicCommon = sets[0];
            } else {
                this.selectedIndicesBasicCommon = new Set();
            }
            return;
        }
        if (newItem) {
            const newSet = this.selectedIndicesByItem[newItem];
            this.selectedIndicesCommon = this.selectedIndicesCommon.intersection(newSet);
            if (newItem !== this.excludeItem) {
                this.selectedIndicesBasicCommon = this.selectedIndicesBasicCommon.intersection(newSet);
            }
            return;
        }

        // Use the first set as the starting point
        this.selectedIndicesCommon = sets[0];

        // Iteratively intersect with the remaining sets
        for (let i = 1; i < sets.length; i++) {
            this.selectedIndicesCommon = this.selectedIndicesCommon.intersection(sets[i]);
            if (this.selectedIndicesCommon.size === 0) {
                break; // Early exit if the intersection is empty
            }
        }

        const otherSelectionItems = Object.keys(this.selectedIndicesByItem)
            .filter(key => key !== this.excludeItem);
        this.selectedIndicesBasicCommon = this.selectedIndicesByItem[otherSelectionItems[0]];
        for (let i = 1; i < otherSelectionItems.length; i++) {
            const otherSelection = this.selectedIndicesByItem[otherSelectionItems[i]];
            this.selectedIndicesBasicCommon = this.selectedIndicesBasicCommon.intersection(otherSelection);
        }
    }
}