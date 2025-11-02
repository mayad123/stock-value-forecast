/**
 * API Configuration Example
 * 
 * This file shows the configuration structure.
 * The app works WITHOUT any configuration using public RSS feeds.
 * 
 * OPTION 1: No configuration needed (recommended for public repos)
 * - Just use the app - it works with public RSS feeds
 * 
 * OPTION 2: Backend Proxy (recommended for production)
 * - Deploy the serverless function in /api/yahoo.js
 * - Set backendProxy URL below
 * - API credentials stay secure on the server
 * 
 * OPTION 3: Client-side credentials (not recommended for production)
 * - Copy this file to config.js (gitignored)
 * - Add your credentials
 * - Note: Credentials will be visible in browser source
 */

const CONFIG = {
    yahoo: {
        // Yahoo Finance API OAuth credentials (for client-side use - not recommended)
        consumerKey: null, // 'YOUR_YAHOO_CONSUMER_KEY_HERE',
        consumerSecret: null, // 'YOUR_YAHOO_CONSUMER_SECRET_HERE',
        
        // Optional: If using RapidAPI or similar service (client-side)
        apiKey: null,
        apiHost: null,
        
        // Yahoo Finance API base URLs
        apiBaseUrl: 'https://query1.finance.yahoo.com/v1',
        newsApiUrl: 'https://feeds.finance.yahoo.com/rss/2.0/headline'
    },
    
    // RECOMMENDED: Backend proxy URL (credentials stay on server)
    // Deploy serverless function and set this to your deployment URL
    // Example: 'https://your-app.vercel.app/api/yahoo'
    // Example: 'https://your-app.netlify.app/.netlify/functions/yahoo'
    backendProxy: null
};

