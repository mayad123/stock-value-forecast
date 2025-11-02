/**
 * News Feed Module
 * Handles fetching and displaying Yahoo Finance news feed
 */

class NewsFeed {
    constructor() {
        this.newsContainer = document.getElementById('news-feed');
        this.newsData = [];
    }

    /**
     * Fetch news from Yahoo Finance RSS feed
     * Note: Yahoo Finance RSS feeds are publicly available
     * Uses multiple fallback strategies for reliability
     */
    async fetchNews() {
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
                    if (response.status === 422) {
                        lastErrorWas422 = true;
                        continue; // Try next source instead of breaking
                    }
                    throw new Error(`HTTP ${response.status}`);
                }
                
                // Parse response based on method
                let data;
                if (parseMethod === 'xml') {
                    // Parse RSS XML directly
                    const xmlText = await response.text();
                    data = this.parseRSSXML(xmlText);
                } else if (parseMethod === 'allorigins') {
                    const wrapper = await response.json();
                    if (wrapper.contents) {
                        data = this.parseRSSXML(wrapper.contents);
                    } else {
                        throw new Error('AllOrigins format error');
                    }
                } else {
                    // Standard JSON response
                    data = await response.json();
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
                    this.newsData = items.slice(0, 10); // Get latest 10 news items
                    this.displayNews();
                    return; // Success!
                }
                
                throw new Error('No valid items found');
            } catch (error) {
                if (timeoutId) clearTimeout(timeoutId);
                
                // Don't log timeout errors
                if (error.name !== 'AbortError') {
                    // Only log non-422 errors
                    const errorMsg = error.message || '';
                    if (!errorMsg.includes('422') && !errorMsg.includes('RSS feed unavailable') && !errorMsg.includes('CORS')) {
                        // Silently continue - try next source
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
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(xmlText, 'text/xml');
            
            // Check for parsing errors
            const parserError = xmlDoc.querySelector('parsererror');
            if (parserError) {
                throw new Error('XML parsing error');
            }
            
            const items = xmlDoc.querySelectorAll('item');
            const parsedItems = [];
            
            items.forEach(item => {
                const title = item.querySelector('title')?.textContent || '';
                const description = item.querySelector('description')?.textContent || '';
                const link = item.querySelector('link')?.textContent || '';
                const pubDate = item.querySelector('pubDate')?.textContent || '';
                const author = item.querySelector('author')?.textContent || 
                              item.querySelector('dc\\:creator')?.textContent || 
                              item.querySelector('creator')?.textContent || '';
                
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
            console.error('Error parsing RSS XML:', error);
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
    displayNews() {
        if (this.newsData.length === 0) {
            this.newsContainer.innerHTML = '<p class="empty-message">No news available at the moment.</p>';
            return;
        }

        const newsHTML = this.newsData.map(item => {
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
                        <span>Source: ${this.escapeHtml(item.author || 'Yahoo Finance')}</span>
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

