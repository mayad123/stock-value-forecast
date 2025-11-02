/**
 * Stock Manager Module
 * Handles stock selection, storage, and management
 */

class StockManager {
    constructor() {
        this.selectedStocks = new Set();
        this.stockInput = document.getElementById('stock-input');
        this.addStockBtn = document.getElementById('add-stock-btn');
        this.selectedStocksContainer = document.getElementById('selected-stocks');
        this.autocompleteDropdown = document.getElementById('autocomplete-dropdown');
        this.currentSuggestions = [];
        this.selectedSuggestionIndex = -1;
        
        // Check if elements exist
        if (!this.stockInput || !this.addStockBtn || !this.selectedStocksContainer || !this.autocompleteDropdown) {
            console.error('StockManager: Required DOM elements not found', {
                stockInput: !!this.stockInput,
                addStockBtn: !!this.addStockBtn,
                selectedStocksContainer: !!this.selectedStocksContainer,
                autocompleteDropdown: !!this.autocompleteDropdown
            });
        }
        
        // Popular stock symbols database
        this.stockDatabase = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B', 'V', 'JNJ',
            'WMT', 'MA', 'PG', 'UNH', 'HD', 'DIS', 'PYPL', 'BAC', 'ADBE', 'NFLX',
            'CRM', 'XOM', 'VZ', 'CVX', 'CSCO', 'ABT', 'COST', 'NKE', 'MRK', 'ACN',
            'PEP', 'TMO', 'AVGO', 'TXN', 'QCOM', 'DHR', 'ABBV', 'WFC', 'CMCSA', 'HON',
            'LIN', 'NEE', 'PM', 'RTX', 'BMY', 'ADP', 'UPS', 'GE', 'ELV', 'SBUX',
            'IBM', 'TJX', 'AMD', 'AMGN', 'SPGI', 'CAT', 'AXP', 'DE', 'INTU', 'GILD',
            'AMAT', 'BKNG', 'MU', 'ISRG', 'MCO', 'MDT', 'LRCX', 'ADI', 'EQIX', 'ADSK',
            'CL', 'WM', 'SHW', 'KLAC', 'APH', 'FIS', 'APH', 'CRWD', 'SNPS', 'CDNS',
            'FTNT', 'ANSS', 'ZS', 'PLTR', 'RBLX', 'SOFI', 'NIO', 'LCID', 'RIVN', 'GME',
            'AMC', 'BBBY', 'SPCE', 'HOOD', 'OPEN', 'WISH', 'CLOV', 'PROG', 'SNDL', 'CLNE'
        ].sort();
        
        this.initializeEventListeners();
    }

    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        if (!this.stockInput || !this.addStockBtn) {
            console.error('StockManager: Cannot initialize event listeners - elements missing');
            return;
        }
        
        // Add stock on button click
        this.addStockBtn.addEventListener('click', () => {
            try {
                this.addStock();
            } catch (error) {
                console.error('Error adding stock:', error);
            }
        });
        
        // Handle input for autocomplete
        this.stockInput.addEventListener('input', (e) => {
            try {
                this.handleInput(e.target.value);
            } catch (error) {
                console.error('Error handling input:', error);
            }
        });

        // Handle keyboard navigation in autocomplete
        this.stockInput.addEventListener('keydown', (e) => {
            try {
                this.handleKeydown(e);
            } catch (error) {
                console.error('Error handling keydown:', error);
            }
        });

        // Hide dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.autocompleteDropdown) return;
            
            const isInputClick = e.target === this.stockInput || (this.stockInput && this.stockInput.contains(e.target));
            const isDropdownClick = this.autocompleteDropdown && 
                                   (this.autocompleteDropdown.contains(e.target) || 
                                    e.target.closest('.autocomplete-dropdown'));
            
            if (!isInputClick && !isDropdownClick && 
                this.autocompleteDropdown.style.display === 'block') {
                this.hideDropdown();
            }
        });

        // Show suggestions on focus if there's text
        this.stockInput.addEventListener('focus', () => {
            if (this.stockInput.value.length > 0) {
                this.handleInput(this.stockInput.value);
            }
        });
    }

    /**
     * Handle input changes for autocomplete
     */
    handleInput(value) {
        const query = value.trim().toUpperCase();
        
        if (query.length === 0) {
            this.hideDropdown();
            return;
        }

        // Filter stock symbols that match the query
        const matches = this.stockDatabase.filter(symbol => 
            symbol.startsWith(query) && !this.selectedStocks.has(symbol)
        ).slice(0, 10); // Limit to 10 suggestions

        this.currentSuggestions = matches;
        this.selectedSuggestionIndex = -1;

        if (matches.length > 0) {
            this.showSuggestions(matches, query);
        } else {
            this.hideDropdown();
        }
    }

    /**
     * Show autocomplete suggestions
     */
    showSuggestions(suggestions, query) {
        if (!this.autocompleteDropdown) return;
        
        const suggestionsHTML = suggestions.map((symbol, index) => {
            const highlightedSymbol = this.highlightMatch(symbol, query);
            return `
                <div class="suggestion-item" data-index="${index}" data-symbol="${symbol}">
                    ${highlightedSymbol}
                </div>
            `;
        }).join('');

        this.autocompleteDropdown.innerHTML = suggestionsHTML;
        this.autocompleteDropdown.style.display = 'block';

        // Add click handlers to suggestions
        this.autocompleteDropdown.querySelectorAll('.suggestion-item').forEach(item => {
            item.addEventListener('click', () => {
                const symbol = item.getAttribute('data-symbol');
                this.selectSuggestion(symbol);
            });
        });
    }

    /**
     * Highlight matching part of the symbol
     */
    highlightMatch(symbol, query) {
        if (query.length === 0) return symbol;
        const index = symbol.toUpperCase().indexOf(query.toUpperCase());
        if (index === -1) return symbol;
        
        const before = symbol.substring(0, index);
        const match = symbol.substring(index, index + query.length);
        const after = symbol.substring(index + query.length);
        
        return `${before}<strong>${match}</strong>${after}`;
    }

    /**
     * Hide autocomplete dropdown
     */
    hideDropdown() {
        if (this.autocompleteDropdown) {
            this.autocompleteDropdown.style.display = 'none';
        }
        this.currentSuggestions = [];
        this.selectedSuggestionIndex = -1;
    }

    /**
     * Handle keyboard navigation
     */
    handleKeydown(e) {
        if (!this.autocompleteDropdown || 
            !this.autocompleteDropdown.style.display || 
            this.autocompleteDropdown.style.display === 'none') {
            if (e.key === 'Enter') {
                this.addStock();
            }
            return;
        }

        const suggestions = this.autocompleteDropdown.querySelectorAll('.suggestion-item');
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedSuggestionIndex = Math.min(
                    this.selectedSuggestionIndex + 1,
                    suggestions.length - 1
                );
                this.updateHighlightedSuggestion(suggestions);
                break;
            
            case 'ArrowUp':
                e.preventDefault();
                this.selectedSuggestionIndex = Math.max(this.selectedSuggestionIndex - 1, -1);
                this.updateHighlightedSuggestion(suggestions);
                break;
            
            case 'Enter':
                e.preventDefault();
                if (this.selectedSuggestionIndex >= 0 && suggestions[this.selectedSuggestionIndex]) {
                    const symbol = suggestions[this.selectedSuggestionIndex].getAttribute('data-symbol');
                    this.selectSuggestion(symbol);
                } else {
                    this.addStock();
                }
                break;
            
            case 'Escape':
                e.preventDefault();
                this.hideDropdown();
                break;
        }
    }

    /**
     * Update highlighted suggestion in dropdown
     */
    updateHighlightedSuggestion(suggestions) {
        suggestions.forEach((item, index) => {
            if (index === this.selectedSuggestionIndex) {
                item.classList.add('highlighted');
            } else {
                item.classList.remove('highlighted');
            }
        });
    }

    /**
     * Select a suggestion from autocomplete
     */
    selectSuggestion(symbol) {
        this.stockInput.value = symbol;
        this.addStock();
        this.hideDropdown();
    }

    /**
     * Add a stock to the selection
     */
    addStock() {
        const symbol = this.stockInput.value.trim().toUpperCase();
        
        if (!symbol) {
            this.showMessage('Please enter a stock symbol', 'error');
            return;
        }

        if (!this.isValidSymbol(symbol)) {
            this.showMessage('Please enter a valid stock symbol (e.g., AAPL, MSFT)', 'error');
            return;
        }

        if (this.selectedStocks.has(symbol)) {
            this.showMessage(`${symbol} is already selected`, 'error');
            return;
        }

        this.selectedStocks.add(symbol);
        this.updateDisplay();
        this.stockInput.value = '';
        this.hideDropdown();
        this.showMessage(`${symbol} added successfully`, 'success');
    }

    /**
     * Remove a stock from the selection
     */
    removeStock(symbol) {
        this.selectedStocks.delete(symbol);
        this.updateDisplay();
        this.showMessage(`${symbol} removed`, 'success');
    }

    /**
     * Validate stock symbol format
     */
    isValidSymbol(symbol) {
        // Stock symbols are typically 1-5 uppercase letters, can include dots (e.g., BRK.B)
        return /^[A-Z]{1,5}(\.[A-Z])?$/.test(symbol);
    }

    /**
     * Update the display of selected stocks
     */
    updateDisplay() {
        if (this.selectedStocks.size === 0) {
            this.selectedStocksContainer.innerHTML = '<p class="empty-message">No stocks selected yet. Add stocks above to see forecasts.</p>';
            return;
        }

        const stocksHTML = Array.from(this.selectedStocks)
            .map(symbol => `
                <div class="stock-tag">
                    <span>${symbol}</span>
                    <button class="remove-btn" onclick="stockManager.removeStock('${symbol}')" aria-label="Remove ${symbol}">×</button>
                </div>
            `).join('');

        this.selectedStocksContainer.innerHTML = stocksHTML;
    }

    /**
     * Get all selected stocks
     */
    getSelectedStocks() {
        return Array.from(this.selectedStocks);
    }

    /**
     * Check if any stocks are selected
     */
    hasStocks() {
        return this.selectedStocks.size > 0;
    }

    /**
     * Clear all selected stocks
     */
    clearAll() {
        this.selectedStocks.clear();
        this.updateDisplay();
    }

    /**
     * Show temporary message
     */
    showMessage(message, type = 'info') {
        // Create a temporary message element
        const messageEl = document.createElement('div');
        messageEl.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 1.5rem;
            background-color: ${type === 'error' ? 'var(--danger-color)' : 'var(--secondary-color)'};
            color: white;
            border-radius: 8px;
            box-shadow: var(--shadow-lg);
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        `;
        messageEl.textContent = message;
        
        document.body.appendChild(messageEl);
        
        setTimeout(() => {
            messageEl.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => messageEl.remove(), 300);
        }, 3000);
    }
}

// Add CSS animations for messages
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

