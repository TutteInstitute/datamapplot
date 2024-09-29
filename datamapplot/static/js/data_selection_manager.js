/**
 * DataSelectionManager is a class designed to manage the common selected indices across distinct items.
 */
class DataSelectionManager {
    constructor(specialItem) {
        this.excludeItem = specialItem; // The item key to exclude 
        this.selectedIndicesByItem = {}; // Dictionary<string: itemId, Set: selectedIndices> to store sets of selected indices by item
        this.selectedIndicesCommon = new Set(); // Set to store the the common selected indices across all items
        this.selectedIndicesBasicCommon = new Set(); // Set to store the the common selected indices across all items
    }

    /**
     * Adds or updates the selected indices for a specific item.
     * @param {number[]} indices - The array of indices to add or update.
     * @param {string} itemId - The item key associated with the indices.
     * @returns {undefined} No return value.
    */
    addOrUpdateSelectedIndicesOfItem(indices, itemId) {
        const isNewItem = !this.selectedIndicesByItem.hasOwnProperty(itemId);

        this.selectedIndicesByItem[itemId] = new Set(indices);
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