/**
 * Netlify Function for Yahoo Finance API Proxy
 * 
 * Environment Variables (set in Netlify dashboard):
 * - YAHOO_CONSUMER_KEY
 * - YAHOO_CONSUMER_SECRET
 * (or YAHOO_API_KEY and YAHOO_API_HOST for RapidAPI)
 */

exports.handler = async (event, context) => {
    // Enable CORS
    const headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET, OPTIONS'
    };

    if (event.httpMethod === 'OPTIONS') {
        return {
            statusCode: 200,
            headers,
            body: ''
        };
    }

    if (event.httpMethod !== 'GET') {
        return {
            statusCode: 405,
            headers,
            body: JSON.stringify({ error: 'Method not allowed' })
        };
    }

    try {
        const { type } = event.queryStringParameters || {};
        
        // Route: /api/yahoo?type=news
        if (type === 'news') {
            const newsData = await fetchYahooNews();
            return {
                statusCode: 200,
                headers: {
                    ...headers,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(newsData)
            };
        }

        return {
            statusCode: 400,
            headers,
            body: JSON.stringify({ error: 'Invalid type parameter' })
        };
    } catch (error) {
        console.error('Yahoo API Proxy Error:', error);
        return {
            statusCode: 500,
            headers,
            body: JSON.stringify({ error: 'Internal server error' })
        };
    }
};

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

    // Option 2: Fallback to RSS feed parsing
    try {
        const rssUrl = 'https://feeds.finance.yahoo.com/rss/2.0/headline';
        const proxyUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(rssUrl)}`;
        
        const response = await fetch(proxyUrl);
        if (response.ok) {
            const wrapper = await response.json();
            if (wrapper.contents) {
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
    const items = [];
    const itemRegex = /<item>(.*?)<\/item>/gs;
    const matches = xmlText.match(itemRegex) || [];

    matches.slice(0, 10).forEach(itemXml => {
        const titleMatch = itemXml.match(/<title><!\[CDATA\[(.*?)\]\]><\/title>|<title>(.*?)<\/title>/);
        const descMatch = itemXml.match(/<description><!\[CDATA\[(.*?)\]\]><\/description>|<description>(.*?)<\/description>/);
        const linkMatch = itemXml.match(/<link>(.*?)<\/link>/);
        const dateMatch = itemXml.match(/<pubDate>(.*?)<\/pubDate>/);

        items.push({
            title: (titleMatch && (titleMatch[1] || titleMatch[2]) || '').trim(),
            description: (descMatch && (descMatch[1] || descMatch[2]) || '').trim(),
            contentSnippet: (descMatch && (descMatch[1] || descMatch[2]) || '').trim().substring(0, 200),
            link: (linkMatch ? linkMatch[1] : '').trim(),
            pubDate: (dateMatch ? dateMatch[1] : new Date().toISOString()),
            author: 'Yahoo Finance'
        });
    });

    return { items };
}

