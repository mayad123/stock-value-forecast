/**
 * Main Application Entry Point
 * Initializes all modules and coordinates functionality
 */

// Initialize global instances
let newsFeed;
let stockManager;
let forecastEngine;

// Make forecastEngine globally accessible for onclick handlers
window.forecastEngine = null;

/**
 * Initialize the application when DOM is loaded
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Stock Value Forecast - Initializing...');
    
    // Initialize modules
    newsFeed = new NewsFeed();
    stockManager = new StockManager();
    forecastEngine = new ForecastEngine(newsFeed, stockManager);
    window.forecastEngine = forecastEngine; // Make accessible globally
    
    // Load news feed on startup
    newsFeed.fetchNews();
    
    // Refresh news feed every 5 minutes
    setInterval(() => {
        console.log('Refreshing news feed...');
        newsFeed.fetchNews();
    }, 5 * 60 * 1000);
    
    console.log('Stock Value Forecast - Ready!');
});

