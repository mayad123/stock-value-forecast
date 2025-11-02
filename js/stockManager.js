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
        
        this.initializeEventListeners();
    }

    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        // Add stock on button click
        this.addStockBtn.addEventListener('click', () => this.addStock());
        
        // Add stock on Enter key press
        this.stockInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.addStock();
            }
        });

        // Clear input on focus
        this.stockInput.addEventListener('focus', () => {
            this.stockInput.value = '';
        });
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
        // Stock symbols are typically 1-5 uppercase letters
        return /^[A-Z]{1,5}$/.test(symbol);
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

