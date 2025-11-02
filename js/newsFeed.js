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
        // Try multiple RSS sources and proxy services
        const rssSources = [
            {
                url: 'https://feeds.finance.yahoo.com/rss/2.0/headline',
                proxy: 'https://api.rss2json.com/v1/api.json?rss_url='
            },
            {
                url: 'https://finance.yahoo.com/news/rssindex',
                proxy: 'https://api.rss2json.com/v1/api.json?rss_url='
            },
            {
                url: 'https://feeds.finance.yahoo.com/rss/2.0/headline',
                proxy: 'https://thingproxy.freeboard.io/fetch/'
            }
        ];

        // Try each source until one works
        for (const source of rssSources) {
            let timeoutId;
            try {
                const proxyUrl = `${source.proxy}${encodeURIComponent(source.url)}`;
                
                // Create timeout controller with fallback
                const abortController = new AbortController();
                timeoutId = setTimeout(() => abortController.abort(), 10000);
                
                const response = await fetch(proxyUrl, {
                    method: 'GET',
                    headers: {
                        'Accept': 'application/json',
                    },
                    signal: abortController.signal
                });
                
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    // 422 is expected for RSS feeds (rate limits, etc.)
                    if (response.status === 422) {
                        throw new Error('RSS feed unavailable (expected)');
                    }
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                
                // Check if data is valid
                if (data && data.items && Array.isArray(data.items) && data.items.length > 0) {
                    this.newsData = data.items.slice(0, 10); // Get latest 10 news items
                    this.displayNews();
                    return; // Success, exit function
                } else if (data && data.feed) {
                    // Some proxies return data in a 'feed' object
                    if (data.feed.items && Array.isArray(data.feed.items)) {
                        this.newsData = data.feed.items.slice(0, 10);
                        this.displayNews();
                        return;
                    }
                }
                
                throw new Error('Invalid data format');
            } catch (error) {
                if (timeoutId) clearTimeout(timeoutId);
                
                // Don't log timeout errors as warnings
                if (error.name !== 'AbortError') {
                    // Suppress 422 errors (expected for RSS feeds due to rate limits/CORS)
                    const errorMsg = error.message || '';
                    if (!errorMsg.includes('422') && !errorMsg.includes('RSS feed unavailable')) {
                        console.warn(`Failed to fetch from source ${source.url}:`, error.message);
                    }
                    // Silently continue - will use fallback data
                }
                // Continue to next source
                continue;
            }
        }

        // If all sources fail, use fallback sample data for demonstration
        // All news sources failed - using fallback sample data (expected for RSS feeds)
        this.useFallbackNews();
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

