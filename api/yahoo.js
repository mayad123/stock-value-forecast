/**
 * Backend Proxy for Yahoo Finance API
 * 
 * This serverless function securely holds API credentials server-side
 * and proxies requests from the frontend, allowing anyone to use the app
 * without needing their own API keys.
 * 
 * Deploy this to:
 * - Vercel: Create a /api folder and deploy (vercel.json included)
 * - Netlify: Create a /netlify/functions folder
 * - AWS Lambda, Google Cloud Functions, etc.
 * 
 * Environment Variables Required:
 * - YAHOO_CONSUMER_KEY
 * - YAHOO_CONSUMER_SECRET
 * (or YAHOO_API_KEY and YAHOO_API_HOST for RapidAPI)
 */

// For Vercel serverless functions
export default async function handler(req, res) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    if (req.method !== 'GET') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const { type } = req.query;
        
        // Route: /api/yahoo?type=news
        if (type === 'news') {
            const newsData = await fetchYahooNews();
            return res.status(200).json(newsData);
        }

        return res.status(400).json({ error: 'Invalid type parameter' });
    } catch (error) {
        console.error('Yahoo API Proxy Error:', error);
        return res.status(500).json({ error: 'Internal server error' });
    }
}

/**
 * Fetch Yahoo Finance news
 * Uses environment variables for credentials
 */
async function fetchYahooNews() {
    // Option 1: Use RapidAPI if configured
    const apiKey = process.env.YAHOO_API_KEY;
    const apiHost = process.env.YAHOO_API_HOST;

    if (apiKey && apiHost) {
        try {
            const response = await fetch(`https://${apiHost}/finance/news`, {
                method: 'GET',
                headers: {
                    'X-RapidAPI-Key': apiKey,
                    'X-RapidAPI-Host': apiHost
                }
            });

            if (response.ok) {
                const data = await response.json();
                return { items: data.items || [] };
            }
        } catch (error) {
            console.error('RapidAPI error:', error);
        }
    }

    // Option 2: Use Yahoo OAuth API
    const consumerKey = process.env.YAHOO_CONSUMER_KEY;
    const consumerSecret = process.env.YAHOO_CONSUMER_SECRET;

    if (consumerKey && consumerSecret) {
        // Implement OAuth 1.0 signing here
        // This is a placeholder - implement based on your Yahoo API requirements
        try {
            // Add OAuth implementation
            const response = await fetch('https://query1.finance.yahoo.com/v1/finance/news', {
                method: 'GET',
                headers: {
                    // Add OAuth headers here
                }
            });

            if (response.ok) {
                const data = await response.json();
                return { items: data.items || [] };
            }
        } catch (error) {
            console.error('Yahoo OAuth API error:', error);
        }
    }

    // Option 3: Fallback to RSS feed parsing
    try {
        const rssUrl = 'https://feeds.finance.yahoo.com/rss/2.0/headline';
        const proxyUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(rssUrl)}`;
        
        const response = await fetch(proxyUrl);
        if (response.ok) {
            const wrapper = await response.json();
            if (wrapper.contents) {
                // Parse RSS XML and return items
                return parseRSSFeed(wrapper.contents);
            }
        }
    } catch (error) {
        console.error('RSS fallback error:', error);
    }

    return { items: [] };
}

/**
 * Parse RSS XML feed
 */
function parseRSSFeed(xmlText) {
    // Simple RSS parser (or use a library like fast-xml-parser)
    const items = [];
    const itemRegex = /<item>(.*?)<\/item>/gs;
    const matches = xmlText.match(itemRegex) || [];

    matches.slice(0, 10).forEach(itemXml => {
        const titleMatch = itemXml.match(/<title><!\[CDATA\[(.*?)\]\]><\/title>|<title>(.*?)<\/title>/);
        const descMatch = itemXml.match(/<description><!\[CDATA\[(.*?)\]\]><\/description>|<description>(.*?)<\/description>/);
        const linkMatch = itemXml.match(/<link>(.*?)<\/link>/);
        const dateMatch = itemXml.match(/<pubDate>(.*?)<\/pubDate>/);

        items.push({
            title: (titleMatch[1] || titleMatch[2] || '').trim(),
            description: (descMatch[1] || descMatch[2] || '').trim(),
            contentSnippet: (descMatch[1] || descMatch[2] || '').trim().substring(0, 200),
            link: (linkMatch ? linkMatch[1] : '').trim(),
            pubDate: (dateMatch ? dateMatch[1] : new Date().toISOString()),
            author: 'Yahoo Finance'
        });
    });

    return { items };
}

