/**
 * News Feed Module
 * Handles fetching and displaying Yahoo Finance news feed
 * Supports Yahoo API authentication via OAuth 1.0
 */

class NewsFeed {
    constructor() {
        this.newsContainer = document.getElementById('news-feed');
        this.newsData = [];
        this.hasApiCredentials = this.checkApiCredentials();
    }

    /**
     * Check if API credentials are configured
     */
    checkApiCredentials() {
        return typeof CONFIG !== 'undefined' && 
               CONFIG.yahoo && 
               CONFIG.yahoo.consumerKey && 
               CONFIG.yahoo.consumerKey !== 'YOUR_YAHOO_CONSUMER_KEY_HERE' &&
               CONFIG.yahoo.consumerSecret &&
               CONFIG.yahoo.consumerSecret !== 'YOUR_YAHOO_CONSUMER_SECRET_HERE';
    }

    /**
     * Generate OAuth 1.0 signature for Yahoo API requests
     * Note: For production, OAuth secrets should be kept on a backend server
     */
    async generateOAuthSignature(method, url, params = {}) {
        if (!this.hasApiCredentials) {
            throw new Error('API credentials not configured');
        }

        // OAuth 1.0 parameters
        const oauthParams = {
            oauth_consumer_key: CONFIG.yahoo.consumerKey,
            oauth_signature_method: 'HMAC-SHA1',
            oauth_timestamp: Math.floor(Date.now() / 1000).toString(),
            oauth_nonce: Math.random().toString(36).substring(2, 15),
            oauth_version: '1.0'
        };

        // Merge all parameters
        const allParams = { ...oauthParams, ...params };

        // Sort parameters alphabetically
        const sortedKeys = Object.keys(allParams).sort();
        const normalizedParams = sortedKeys.map(key => 
            `${encodeURIComponent(key)}=${encodeURIComponent(allParams[key])}`
        ).join('&');

        // Create signature base string
        const baseString = `${method.toUpperCase()}&${encodeURIComponent(url)}&${encodeURIComponent(normalizedParams)}`;

        // Create signing key
        const signingKey = `${encodeURIComponent(CONFIG.yahoo.consumerSecret)}&`;

        // Generate HMAC-SHA1 signature (using Web Crypto API)
        oauthParams.oauth_signature = await this.hmacSha1(baseString, signingKey);

        return oauthParams;
    }

    /**
     * Simple HMAC-SHA1 implementation
     * Note: For production, use a proper crypto library like crypto-js
     */
    async hmacSha1(message, key) {
        // Import key
        const encoder = new TextEncoder();
        const keyData = encoder.encode(key);
        const messageData = encoder.encode(message);

        const cryptoKey = await crypto.subtle.importKey(
            'raw',
            keyData,
            { name: 'HMAC', hash: 'SHA-1' },
            false,
            ['sign']
        );

        // Sign
        const signature = await crypto.subtle.sign('HMAC', cryptoKey, messageData);

        // Convert to base64
        return btoa(String.fromCharCode(...new Uint8Array(signature)));
    }

    /**
     * Fetch news using backend proxy (recommended for shared access)
     * The backend proxy holds API credentials securely server-side
     */
    async fetchNewsWithBackendProxy() {
        if (!CONFIG || !CONFIG.backendProxy) {
            return null;
        }

        try {
            const response = await fetch(`${CONFIG.backendProxy}?type=news`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data && data.items && Array.isArray(data.items)) {
                    // Filter articles from the last year
                    const oneYearAgo = new Date();
                    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
                    
                    const filteredItems = data.items
                        .filter(item => {
                            if (!item.pubDate) return true;
                            const pubDate = new Date(item.pubDate);
                            return pubDate >= oneYearAgo;
                        })
                        .sort((a, b) => {
                            const dateA = new Date(a.pubDate || 0);
                            const dateB = new Date(b.pubDate || 0);
                            return dateB - dateA;
                        });
                    
                    // Store all filtered articles (not just 10)
                    this.newsData = filteredItems;
                    this.displayNews(filteredItems.slice(0, 10));
                    return true;
                }
            }
        } catch (error) {
            console.error('Error fetching news via backend proxy:', error);
        }
        return null;
    }

    /**
     * Fetch news using Yahoo API with OAuth authentication
     */
    async fetchNewsWithYahooAPI() {
        if (!this.hasApiCredentials) {
            return null;
        }

        try {
            // Yahoo Finance API endpoint for news
            // Note: Adjust endpoint based on your Yahoo API version
            const apiUrl = 'https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved';
            
            // Generate OAuth signature
            const oauthParams = await this.generateOAuthSignature('GET', apiUrl);
            
            // Build authorization header
            const authHeader = 'OAuth ' + Object.keys(oauthParams)
                .map(key => `${encodeURIComponent(key)}="${encodeURIComponent(oauthParams[key])}"`)
                .join(', ');

            // Alternative: Use RapidAPI if configured
            if (CONFIG.yahoo.apiKey && CONFIG.yahoo.apiHost) {
                const response = await fetch(`https://${CONFIG.yahoo.apiHost}/finance/news`, {
                    method: 'GET',
                    headers: {
                        'X-RapidAPI-Key': CONFIG.yahoo.apiKey,
                        'X-RapidAPI-Host': CONFIG.yahoo.apiHost
                    }
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data && data.items) {
                        // Filter articles from the last year
                        const oneYearAgo = new Date();
                        oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
                        
                        const filteredItems = data.items
                            .filter(item => {
                                if (!item.pubDate) return true;
                                const pubDate = new Date(item.pubDate);
                                return pubDate >= oneYearAgo;
                            })
                            .sort((a, b) => {
                                const dateA = new Date(a.pubDate || 0);
                                const dateB = new Date(b.pubDate || 0);
                                return dateB - dateA;
                            });
                        
                        this.newsData = filteredItems;
                        this.displayNews(filteredItems.slice(0, 10));
                        return true;
                    }
                }
            }

            // For direct Yahoo API (may require backend proxy due to CORS)
            // This is a placeholder - adjust based on actual Yahoo API endpoints
            console.log('Yahoo API OAuth configured. Note: Direct API calls may require a backend proxy due to CORS restrictions.');
            
            return null;
        } catch (error) {
            console.error('Error fetching news with Yahoo API:', error);
            return null;
        }
    }

    /**
     * Fetch news from Yahoo Finance RSS feed
     * Priority order:
     * 1. Backend proxy (if configured - recommended for shared access)
     * 2. Yahoo API with OAuth (if credentials are configured)
     * 3. Public RSS feeds (works for everyone without setup)
     * Note: Yahoo Finance RSS feeds are publicly available
     */
    async fetchNews() {
        // Try backend proxy first (best option - credentials stay on server)
        if (CONFIG && CONFIG.backendProxy) {
            const proxyResult = await this.fetchNewsWithBackendProxy();
            if (proxyResult) {
                return; // Successfully fetched from backend proxy
            }
        }

        // Try Yahoo API with OAuth if credentials are configured
        if (this.hasApiCredentials) {
            const apiResult = await this.fetchNewsWithYahooAPI();
            if (apiResult) {
                return; // Successfully fetched from API
            }
            // If API fails, fall back to RSS methods below
        }

        // Use public RSS feeds (no credentials needed)
        // Try multiple RSS sources and proxy services with different approaches
        const rssSources = [
            // Method 1: RSS2JSON API (may require API key for unlimited access)
            {
                url: 'https://feeds.finance.yahoo.com/rss/2.0/headline',
                proxy: 'https://api.rss2json.com/v1/api.json?rss_url=',
                method: 'rss2json'
            },
            // Method 2: AllOrigins proxy (more reliable)
            {
                url: 'https://feeds.finance.yahoo.com/rss/2.0/headline',
                proxy: 'https://api.allorigins.win/get?url=',
                method: 'allorigins'
            },
            // Method 3: Different RSS endpoint
            {
                url: 'https://finance.yahoo.com/news/rssindex',
                proxy: 'https://api.rss2json.com/v1/api.json?rss_url=',
                method: 'rss2json'
            },
            // Method 4: Alternative proxy service
            {
                url: 'https://feeds.finance.yahoo.com/rss/2.0/headline',
                proxy: 'https://thingproxy.freeboard.io/fetch/',
                method: 'proxy'
            },
            // Method 5: Try direct RSS fetch (if CORS allows)
            {
                url: 'https://feeds.finance.yahoo.com/rss/2.0/headline',
                proxy: null,
                method: 'direct'
            }
        ];

        let lastErrorWas422 = false;

        // Try each source until one works
        for (const source of rssSources) {
            let timeoutId;
            try {
                let fetchUrl;
                let parseMethod = 'json';
                
                // Build URL based on proxy method
                if (source.method === 'direct') {
                    // Try direct fetch (will fail if CORS blocked, but worth trying)
                    fetchUrl = source.url;
                    parseMethod = 'xml';
                } else if (source.method === 'allorigins') {
                    // AllOrigins returns data in a different format
                    fetchUrl = `${source.proxy}${encodeURIComponent(source.url)}`;
                    parseMethod = 'allorigins';
                } else {
                    // Standard proxy
                    fetchUrl = `${source.proxy}${encodeURIComponent(source.url)}`;
                }
                
                // Create timeout controller
                const abortController = new AbortController();
                timeoutId = setTimeout(() => abortController.abort(), 8000); // 8 second timeout
                
                const response = await fetch(fetchUrl, {
                    method: 'GET',
                    headers: {
                        'Accept': parseMethod === 'xml' ? 'application/rss+xml, application/xml, text/xml' : 'application/json',
                    },
                    signal: abortController.signal
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    if (response.status === 422 || response.status === 429) {
                        // 422 = Unprocessable Entity, 429 = Too Many Requests (rate limit)
                        lastErrorWas422 = true;
                        continue; // Try next source instead of breaking
                    }
                    // For other errors, try next source
                    continue;
                }
                
                // Parse response based on method
                let data;
                if (parseMethod === 'xml') {
                    // Parse RSS XML directly
                    const contentType = response.headers.get('content-type') || '';
                    // Check if response is actually XML
                    if (!contentType.includes('xml') && !contentType.includes('text/xml') && !contentType.includes('application/xml')) {
                        // Not XML content type, skip
                        continue;
                    }
                    
                    const xmlText = await response.text();
                    // Check if response is actually XML, not HTML error page
                    const trimmed = xmlText.trim();
                    if (!trimmed.startsWith('<?xml') && !trimmed.startsWith('<rss') && !trimmed.startsWith('<feed')) {
                        // Likely an HTML error page or JSON error, skip
                        continue;
                    }
                    data = this.parseRSSXML(xmlText);
                    if (!data || !data.items || data.items.length === 0) {
                        continue; // Invalid XML, try next source
                    }
                } else if (parseMethod === 'allorigins') {
                    try {
                        const wrapper = await response.json();
                        if (wrapper.contents) {
                            // Check if contents is valid XML
                            const contents = wrapper.contents.trim();
                            if (!contents.startsWith('<?xml') && !contents.startsWith('<rss')) {
                                // Likely an HTML error page, skip
                                continue;
                            }
                            data = this.parseRSSXML(wrapper.contents);
                            if (!data || !data.items || data.items.length === 0) {
                                continue; // Invalid XML, try next source
                            }
                        } else {
                            continue; // No contents, try next source
                        }
                    } catch (e) {
                        // JSON parse error, try next source
                        continue;
                    }
                } else {
                    // Standard JSON response (RSS2JSON or similar)
                    try {
                        const contentType = response.headers.get('content-type') || '';
                        // Check if response is JSON
                        if (!contentType.includes('json') && !contentType.includes('application/json')) {
                            // Not JSON, might be HTML error page, skip
                            continue;
                        }
                        
                        data = await response.json();
                        // Check if response is an error
                        if (data.error || data.status === 'error' || (data.message && data.status)) {
                            // API returned error (common for rate limits like 422)
                            continue; // Try next source
                        }
                        // Validate data structure
                        if (!data || (!data.items && !data.feed)) {
                            continue; // Invalid structure, try next source
                        }
                    } catch (e) {
                        // JSON parse error, try next source
                        continue;
                    }
                }
                
                // Check if data is valid and extract items
                let items = [];
                if (data && data.items && Array.isArray(data.items) && data.items.length > 0) {
                    items = data.items;
                } else if (data && data.feed && data.feed.items && Array.isArray(data.feed.items)) {
                    items = data.feed.items;
                } else if (data && Array.isArray(data)) {
                    items = data;
                }
                
                if (items.length > 0) {
                    // Get more articles and filter by date (last year)
                    const oneYearAgo = new Date();
                    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
                    
                    // Filter articles from the last year and sort by date (newest first)
                    const filteredItems = items
                        .filter(item => {
                            if (!item.pubDate) return true; // Include if no date
                            const pubDate = new Date(item.pubDate);
                            return pubDate >= oneYearAgo;
                        })
                        .sort((a, b) => {
                            const dateA = new Date(a.pubDate || 0);
                            const dateB = new Date(b.pubDate || 0);
                            return dateB - dateA; // Newest first
                        });
                    
                    // Store all filtered articles (not just 10)
                    this.newsData = filteredItems;
                    // Display only the latest 10 in the news feed
                    this.displayNews(filteredItems.slice(0, 10));
                    return; // Success!
                }
                
                throw new Error('No valid items found');
            } catch (error) {
                if (timeoutId) clearTimeout(timeoutId);
                
                // Don't log timeout errors or 422/429 errors (rate limits)
                if (error.name !== 'AbortError') {
                    const errorMsg = error.message || '';
                    const statusCode = errorMsg.match(/HTTP (\d+)/);
                    // Skip logging for common non-critical errors
                    if (statusCode && (statusCode[1] === '422' || statusCode[1] === '429')) {
                        // Rate limit or unprocessable entity - silently continue
                    } else if (!errorMsg.includes('422') && !errorMsg.includes('429') && 
                               !errorMsg.includes('RSS feed unavailable') && 
                               !errorMsg.includes('CORS') &&
                               !errorMsg.includes('XML parsing')) {
                        // Only log unexpected errors
                        console.warn(`RSS source failed: ${errorMsg}`);
                    }
                }
                // Continue to next source
                continue;
            }
        }

        // If all sources fail, use fallback sample data
        // Note: Most free RSS proxies have rate limits - consider using a backend proxy for production
        this.useFallbackNews();
    }

    /**
     * Parse RSS XML into JSON format
     */
    parseRSSXML(xmlText) {
        try {
            // Validate that we have XML content
            if (!xmlText || typeof xmlText !== 'string' || xmlText.trim().length === 0) {
                return { items: [] };
            }
            
            // Check if it's actually XML/RSS, not HTML error page
            const trimmed = xmlText.trim();
            if (trimmed.startsWith('<!DOCTYPE') || trimmed.startsWith('<html')) {
                // This is HTML, not XML - likely an error page
                return { items: [] };
            }
            
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(xmlText, 'text/xml');
            
            // Check for parsing errors
            const parserError = xmlDoc.querySelector('parsererror');
            if (parserError) {
                // XML parsing failed, return empty items
                return { items: [] };
            }
            
            const items = xmlDoc.querySelectorAll('item');
            const parsedItems = [];
            
            items.forEach(item => {
                const title = item.querySelector('title')?.textContent || '';
                const description = item.querySelector('description')?.textContent || '';
                const link = item.querySelector('link')?.textContent || '';
                const pubDate = item.querySelector('pubDate')?.textContent || '';
                
                // Try multiple ways to get author/source
                let author = item.querySelector('author')?.textContent || 
                            item.querySelector('dc\\:creator')?.textContent || 
                            item.querySelector('creator')?.textContent || '';
                
                // Try to get source from source tag
                const sourceTag = item.querySelector('source');
                if (sourceTag) {
                    const sourceText = sourceTag.textContent || sourceTag.getAttribute('url') || '';
                    if (sourceText && !author) {
                        author = sourceText;
                    }
                }
                
                // Extract source from link domain if no author found
                if (!author && link) {
                    try {
                        const url = new URL(link);
                        // Extract domain and clean it up
                        let domain = url.hostname.replace('www.', '');
                        // Capitalize common news domains
                        const domainMap = {
                            'yahoo.com': 'Yahoo Finance',
                            'bloomberg.com': 'Bloomberg',
                            'reuters.com': 'Reuters',
                            'cnbc.com': 'CNBC',
                            'wsj.com': 'Wall Street Journal',
                            'marketwatch.com': 'MarketWatch',
                            'fool.com': 'Motley Fool',
                            'benzinga.com': 'Benzinga',
                            'seekingalpha.com': 'Seeking Alpha',
                            'businesswire.com': 'Business Wire',
                            'prnewswire.com': 'PR Newswire'
                        };
                        if (domainMap[domain]) {
                            author = domainMap[domain];
                        } else {
                            // Format domain nicely
                            const parts = domain.split('.');
                            if (parts.length >= 2) {
                                author = parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
                            } else {
                                author = domain;
                            }
                        }
                    } catch (e) {
                        // Invalid URL, keep default
                    }
                }
                
                // Clean HTML from description if present
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = description;
                const cleanDescription = tempDiv.textContent || tempDiv.innerText || description;
                
                parsedItems.push({
                    title: title.trim(),
                    description: cleanDescription.trim(),
                    contentSnippet: cleanDescription.trim().substring(0, 200),
                    link: link.trim(),
                    pubDate: pubDate || new Date().toISOString(),
                    author: author.trim() || 'Yahoo Finance'
                });
            });
            
            return { items: parsedItems };
        } catch (error) {
            // Only log parsing errors that aren't expected (HTML pages, etc.)
            if (!error.message || !error.message.includes('XML parsing')) {
                // Silently return empty items for expected failures
                return { items: [] };
            }
            // Log unexpected parsing errors
            console.warn('RSS XML parsing issue:', error.message);
            return { items: [] };
        }
    }

    /**
     * Use fallback sample news data when all feeds fail
     */
    useFallbackNews() {
        const sampleNews = [
            {
                title: 'Market Opens Higher on Positive Economic Data',
                contentSnippet: 'Stocks rose in early trading following release of stronger-than-expected economic indicators...',
                pubDate: new Date().toISOString(),
                author: 'Financial News',
                link: '#'
            },
            {
                title: 'Tech Sector Sees Increased Volatility',
                contentSnippet: 'Technology stocks experienced mixed trading as investors digest quarterly earnings reports...',
                pubDate: new Date(Date.now() - 3600000).toISOString(),
                author: 'Market Watch',
                link: '#'
            },
            {
                title: 'Energy Stocks Rally on Oil Price Surge',
                contentSnippet: 'Energy sector outperformed broader market as oil prices climbed amid supply concerns...',
                pubDate: new Date(Date.now() - 7200000).toISOString(),
                author: 'Bloomberg',
                link: '#'
            },
            {
                title: 'Fed Holds Interest Rates Steady',
                contentSnippet: 'Federal Reserve maintains current interest rate policy, citing balanced economic outlook...',
                pubDate: new Date(Date.now() - 10800000).toISOString(),
                author: 'Reuters',
                link: '#'
            },
            {
                title: 'Retail Sector Faces Headwinds',
                contentSnippet: 'Retail companies report mixed earnings as consumer spending patterns shift...',
                pubDate: new Date(Date.now() - 14400000).toISOString(),
                author: 'CNBC',
                link: '#'
            }
        ];

        // Add a note that this is sample data
        this.newsData = sampleNews;
        this.displayNews();
        
        // Show a subtle indicator that sample data is being used
        const note = document.createElement('div');
        note.style.cssText = 'text-align: center; padding: 0.5rem; background-color: #fff3cd; color: #856404; border-radius: 4px; margin-bottom: 1rem; font-size: 0.9rem;';
        note.textContent = 'ℹ️ Displaying sample news data. Live feed will resume when connection is restored.';
        this.newsContainer.insertBefore(note, this.newsContainer.firstChild);
    }

    /**
     * Display news items in the UI
     */
    displayNews(itemsToDisplay = null) {
        const items = itemsToDisplay || this.newsData;
        
        if (!items || items.length === 0) {
            this.newsContainer.innerHTML = '<p class="empty-message">No news available at the moment.</p>';
            return;
        }

        const newsHTML = items.map(item => {
            const pubDate = new Date(item.pubDate).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });

            return `
                <div class="news-item">
                    <h3>${this.escapeHtml(item.title)}</h3>
                    <p>${this.escapeHtml(item.contentSnippet || item.description || '')}</p>
                    <div class="news-meta">
                        <span style="display: inline-flex; align-items: center; gap: 4px;">
                            <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background-color: #ef4444; flex-shrink: 0;"></span>
                            Source: ${this.escapeHtml(item.author || 'Yahoo Finance')}
                        </span>
                        <span>${pubDate}</span>
                    </div>
                    ${item.link ? `<a href="${item.link}" target="_blank" style="color: var(--primary-color); text-decoration: none; font-size: 0.9rem;">Read more →</a>` : ''}
                </div>
            `;
        }).join('');

        this.newsContainer.innerHTML = newsHTML;
    }

    /**
     * Display error message
     */
    displayError(message) {
        this.newsContainer.innerHTML = `<p class="empty-message" style="color: var(--danger-color);">${message}</p>`;
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Get latest news data (for use by forecast engine)
     */
    getNewsData() {
        return this.newsData;
    }
}

