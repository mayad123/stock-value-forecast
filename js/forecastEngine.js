/**
 * Forecast Engine Module
 * Generates forecasts based on selected stocks and news sentiment
 */

class ForecastEngine {
    constructor(newsFeed, stockManager) {
        this.newsFeed = newsFeed;
        this.stockManager = stockManager;
        this.forecastResults = document.getElementById('forecast-results');
        this.generateBtn = document.getElementById('generate-forecast-btn');
        
        if (!this.forecastResults || !this.generateBtn) {
            console.error('ForecastEngine: Required DOM elements not found', {
                forecastResults: !!this.forecastResults,
                generateBtn: !!this.generateBtn
            });
            return;
        }
        
        if (this.generateBtn) {
            this.generateBtn.addEventListener('click', () => {
                try {
                    this.generateForecast();
                } catch (error) {
                    console.error('Error generating forecast:', error);
                    this.showError('Failed to generate forecast. Please check the console for details.');
                }
            });
        }
    }

    /**
     * Generate all forecast types for selected stocks
     */
    async generateForecast() {
        if (!this.stockManager) {
            console.error('ForecastEngine: stockManager not initialized');
            this.showError('Stock manager not initialized. Please refresh the page.');
            return;
        }
        
        if (!this.generateBtn) {
            console.error('ForecastEngine: generateBtn not found');
            return;
        }
        
        const selectedStocks = this.stockManager.getSelectedStocks();
        
        if (!selectedStocks || selectedStocks.length === 0) {
            this.showError('Please select at least one stock to generate forecast.');
            return;
        }
        
        // Disable button during generation
        this.generateBtn.disabled = true;
        this.generateBtn.textContent = 'Generating...';
        
        try {
            // Get news data
            if (!this.newsFeed) {
                console.error('ForecastEngine: newsFeed not initialized');
                throw new Error('News feed not initialized');
            }
            
            const newsData = this.newsFeed.getNewsData() || [];
            
            // Generate all forecast types for each stock
            const stockForecasts = await Promise.all(
                selectedStocks.map(symbol => {
                    try {
                        return this.generateAllForecastsForStock(symbol, newsData);
                    } catch (error) {
                        console.error(`Error generating forecast for ${symbol}:`, error);
                        return null;
                    }
                })
            );
            
            // Filter out null results
            const validForecasts = stockForecasts.filter(f => f !== null);
            
            if (validForecasts.length === 0) {
                this.showError('Failed to generate forecasts for any stocks. Please try again.');
                return;
            }
            
            this.displayForecasts(validForecasts);
        } catch (error) {
            console.error('Error generating forecast:', error);
            this.showError('Failed to generate forecast. Please try again.');
        } finally {
            if (this.generateBtn) {
                this.generateBtn.disabled = false;
                this.generateBtn.textContent = 'Generate Forecast';
            }
        }
    }

    /**
     * Generate all forecast types for a single stock
     */
    async generateAllForecastsForStock(symbol, newsData) {
        if (!symbol) {
            throw new Error('Symbol is required');
        }
        
        try {
            // Analyze sentiment from news
            const sentiment = this.analyzeSentiment(symbol, newsData || []);
            
            // Generate all forecast types
            return {
                symbol: symbol.toUpperCase(),
                sentiment,
                forecasts: [
                    this.generateSentimentForecast(symbol, sentiment),
                    this.generateTrendForecast(symbol, sentiment),
                    this.generateVolatilityForecast(symbol, sentiment),
                    this.generatePriceForecast(symbol, sentiment)
                ]
            };
        } catch (error) {
            console.error(`Error in generateAllForecastsForStock for ${symbol}:`, error);
            throw error;
        }
    }

    /**
     * Analyze sentiment from news articles
     */
    analyzeSentiment(symbol, newsData) {
        if (!newsData || newsData.length === 0) {
            return { score: 0, confidence: 0 };
        }

        // Keywords that indicate positive/negative sentiment
        const positiveKeywords = ['up', 'gain', 'rise', 'surge', 'bullish', 'growth', 'profit', 'strong', 'beat', 'positive'];
        const negativeKeywords = ['down', 'fall', 'drop', 'decline', 'bearish', 'loss', 'weak', 'miss', 'negative', 'concern'];

        let positiveScore = 0;
        let negativeScore = 0;
        let totalArticles = 0;

        newsData.forEach(article => {
            const text = (article.title + ' ' + (article.contentSnippet || article.description || '')).toLowerCase();
            
            // Check if article mentions the stock symbol
            if (text.includes(symbol.toLowerCase()) || this.isRelevantToStock(symbol, article)) {
                totalArticles++;
                
                positiveKeywords.forEach(keyword => {
                    if (text.includes(keyword)) positiveScore++;
                });
                
                negativeKeywords.forEach(keyword => {
                    if (text.includes(keyword)) negativeScore++;
                });
            }
        });

        const netScore = positiveScore - negativeScore;
        const maxScore = Math.max(positiveScore, negativeScore, 1);
        const sentimentScore = totalArticles > 0 ? (netScore / maxScore) * 100 : 0;
        const confidence = Math.min(totalArticles * 10, 100);

        return {
            score: Math.round(sentimentScore),
            confidence: Math.round(confidence),
            positiveScore,
            negativeScore,
            totalArticles
        };
    }

    /**
     * Check if article is relevant to stock (simplified check)
     */
    isRelevantToStock(symbol, article) {
        // In a real implementation, this would use NLP or check for company names
        // For now, we'll consider all financial news as potentially relevant
        return true;
    }

    /**
     * Categorize articles by sentiment for a specific stock
     */
    categorizeArticles(symbol, newsData) {
        if (!newsData || newsData.length === 0) {
            return {
                positive: [],
                negative: [],
                neutral: []
            };
        }

        const positiveKeywords = ['up', 'gain', 'rise', 'surge', 'bullish', 'growth', 'profit', 'strong', 'beat', 'positive', 'win', 'success', 'outperform'];
        const negativeKeywords = ['down', 'fall', 'drop', 'decline', 'bearish', 'loss', 'weak', 'miss', 'negative', 'concern', 'fail', 'plunge', 'crash'];

        const categorized = {
            positive: [],
            negative: [],
            neutral: []
        };

        newsData.forEach(article => {
            const text = (article.title + ' ' + (article.contentSnippet || article.description || '')).toLowerCase();
            
            // Check if article mentions the stock symbol or is relevant
            if (text.includes(symbol.toLowerCase()) || this.isRelevantToStock(symbol, article)) {
                let positiveCount = 0;
                let negativeCount = 0;

                positiveKeywords.forEach(keyword => {
                    if (text.includes(keyword)) positiveCount++;
                });

                negativeKeywords.forEach(keyword => {
                    if (text.includes(keyword)) negativeCount++;
                });

                // Categorize based on keyword count
                if (positiveCount > negativeCount && positiveCount > 0) {
                    categorized.positive.push({
                        ...article,
                        sentiment: 'positive',
                        positiveScore: positiveCount,
                        negativeScore: negativeCount
                    });
                } else if (negativeCount > positiveCount && negativeCount > 0) {
                    categorized.negative.push({
                        ...article,
                        sentiment: 'negative',
                        positiveScore: positiveCount,
                        negativeScore: negativeCount
                    });
                } else {
                    categorized.neutral.push({
                        ...article,
                        sentiment: 'neutral',
                        positiveScore: positiveCount,
                        negativeScore: negativeCount
                    });
                }
            }
        });

        return categorized;
    }

    /**
     * Generate articles HTML by sentiment category
     */
    generateArticlesHTML(symbol, categorizedArticles) {
        const categories = [
            { key: 'positive', title: 'Positive Articles', class: 'positive', articles: categorizedArticles.positive },
            { key: 'negative', title: 'Negative Articles', class: 'negative', articles: categorizedArticles.negative },
            { key: 'neutral', title: 'Neutral Articles', class: 'neutral', articles: categorizedArticles.neutral }
        ];

        const categoriesHTML = categories.map(category => {
            const articlesHTML = category.articles.length > 0
                ? category.articles.map(article => {
                    const pubDate = new Date(article.pubDate).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });

                    return `
                        <div class="article-item ${category.class}">
                            <h4>${this.escapeHtml(article.title || 'Untitled')}</h4>
                            <p>${this.escapeHtml(article.contentSnippet || article.description || '')}</p>
                            <div class="article-meta">
                                <span>Source: ${this.escapeHtml(article.author || 'Unknown')}</span>
                                <span>${pubDate}</span>
                            </div>
                            ${article.link && article.link !== '#' ? `<a href="${article.link}" target="_blank" class="article-link">Read more →</a>` : ''}
                        </div>
                    `;
                }).join('')
                : `<p class="empty-message">No ${category.title.toLowerCase()} found.</p>`;

            return `
                <div class="article-category">
                    <h3 class="category-header ${category.class}">
                        ${category.title} 
                        <span class="article-count">(${category.articles.length})</span>
                    </h3>
                    <div class="articles-list">
                        ${articlesHTML}
                    </div>
                </div>
            `;
        }).join('');

        return `
            <div class="articles-tab-content">
                <h2 class="tab-section-header">
                    <span class="stock-symbol">${symbol}</span>
                    News Articles Analysis
                </h2>
                ${categoriesHTML}
            </div>
        `;
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Generate sentiment forecast
     */
    generateSentimentForecast(symbol, sentiment) {
        const sentimentLabel = sentiment.score > 20 ? 'Bullish' : sentiment.score < -20 ? 'Bearish' : 'Neutral';
        const sentimentColor = sentiment.score > 20 ? 'positive' : sentiment.score < -20 ? 'negative' : '';
        
        return {
            symbol,
            type: 'Sentiment Analysis',
            metrics: [
                { label: 'Sentiment Score', value: `${sentiment.score}`, class: sentimentColor },
                { label: 'Confidence', value: `${sentiment.confidence}%` },
                { label: 'Outlook', value: sentimentLabel, class: sentimentColor },
                { label: 'News Articles', value: sentiment.totalArticles }
            ],
            description: `Based on ${sentiment.totalArticles} relevant news articles, the market sentiment for ${symbol} is ${sentimentLabel.toLowerCase()}.`
        };
    }

    /**
     * Generate trend forecast
     */
    generateTrendForecast(symbol, sentiment) {
        const trend = sentiment.score > 10 ? 'Upward' : sentiment.score < -10 ? 'Downward' : 'Sideways';
        const trendColor = sentiment.score > 10 ? 'positive' : sentiment.score < -10 ? 'negative' : '';
        const sentimentColor = sentiment.score > 20 ? 'positive' : sentiment.score < -20 ? 'negative' : '';
        const strength = Math.abs(sentiment.score) > 50 ? 'Strong' : Math.abs(sentiment.score) > 20 ? 'Moderate' : 'Weak';
        
        return {
            symbol,
            type: 'Trend Prediction',
            metrics: [
                { label: 'Trend Direction', value: trend, class: trendColor },
                { label: 'Trend Strength', value: strength },
                { label: 'Sentiment Score', value: `${sentiment.score}`, class: sentimentColor },
                { label: 'Reliability', value: `${sentiment.confidence}%` }
            ],
            description: `${symbol} shows a ${trend.toLowerCase()} trend with ${strength.toLowerCase()} strength based on current market sentiment.`
        };
    }

    /**
     * Generate volatility forecast
     */
    generateVolatilityForecast(symbol, sentiment) {
        const volatility = Math.abs(sentiment.score) > 40 ? 'High' : Math.abs(sentiment.score) > 20 ? 'Moderate' : 'Low';
        const volatilityColor = volatility === 'High' ? 'negative' : volatility === 'Moderate' ? '' : 'positive';
        
        return {
            symbol,
            type: 'Volatility Forecast',
            metrics: [
                { label: 'Expected Volatility', value: volatility, class: volatilityColor },
                { label: 'Volatility Score', value: `${Math.abs(sentiment.score)}` },
                { label: 'Market Sentiment', value: sentiment.score > 0 ? 'Positive' : 'Negative', class: sentiment.score > 0 ? 'positive' : 'negative' },
                { label: 'Data Points', value: sentiment.totalArticles }
            ],
            description: `${symbol} is expected to experience ${volatility.toLowerCase()} volatility based on current market conditions and news sentiment.`
        };
    }

    /**
     * Generate price forecast
     */
    generatePriceForecast(symbol, sentiment) {
        // Simulate price prediction (in real app, this would use historical data and ML models)
        const basePrice = 100 + Math.random() * 200; // Simulated base price
        const changePercent = sentiment.score * 0.1; // Scale sentiment to percentage
        const predictedPrice = basePrice * (1 + changePercent / 100);
        
        const direction = sentiment.score > 0 ? 'Up' : sentiment.score < 0 ? 'Down' : 'Stable';
        const directionColor = sentiment.score > 0 ? 'positive' : sentiment.score < 0 ? 'negative' : '';
        
        return {
            symbol,
            type: 'Price Prediction',
            metrics: [
                { label: 'Direction', value: direction, class: directionColor },
                { label: 'Expected Change', value: `${changePercent > 0 ? '+' : ''}${changePercent.toFixed(2)}%`, class: directionColor },
                { label: 'Confidence', value: `${sentiment.confidence}%` },
                { label: 'Sentiment', value: sentiment.score > 0 ? 'Bullish' : sentiment.score < 0 ? 'Bearish' : 'Neutral', class: sentiment.score > 0 ? 'positive' : sentiment.score < 0 ? 'negative' : '' }
            ],
            description: `Based on sentiment analysis, ${symbol} is expected to move ${direction.toLowerCase()} with a projected change of ${changePercent > 0 ? '+' : ''}${changePercent.toFixed(2)}%.`
        };
    }

    /**
     * Display forecasts in the UI grouped by stock with tabs
     */
    displayForecasts(stockForecasts) {
        if (!this.forecastResults) {
            console.error('ForecastEngine: forecastResults element not found');
            return;
        }
        
        if (!stockForecasts || stockForecasts.length === 0) {
            this.showError('No forecasts generated.');
            return;
        }

        // Filter out invalid stockData entries before mapping
        const validStockForecasts = stockForecasts.filter(stockData => 
            stockData && stockData.forecasts && Array.isArray(stockData.forecasts) && stockData.forecasts.length > 0
        );

        if (validStockForecasts.length === 0) {
            this.showError('No valid forecasts generated.');
            return;
        }

        // Generate HTML for each stock with tabs
        const stocksHTML = validStockForecasts.map(stockData => {
            // Generate forecast summary HTML (first tab)
            const forecastCardsHTML = stockData.forecasts.map(forecast => {
                if (!forecast || !forecast.metrics || !Array.isArray(forecast.metrics)) {
                    console.error('Invalid forecast structure:', forecast);
                    return '';
                }
                
                const metricsHTML = forecast.metrics.map(metric => `
                    <div class="metric">
                        <div class="metric-label">${metric.label}</div>
                        <div class="metric-value ${metric.class || ''}">${metric.value}</div>
                    </div>
                `).join('');

                return `
                    <div class="forecast-card">
                        <h3>
                            <span class="stock-symbol">${forecast.symbol || stockData.symbol}</span>
                            ${forecast.type || 'Forecast'}
                        </h3>
                        <p>${forecast.description || ''}</p>
                        <div class="forecast-metrics">
                            ${metricsHTML}
                        </div>
                    </div>
                `;
            }).filter(html => html.trim().length > 0).join('');

            // Get news data and categorize articles
            const newsData = this.newsFeed ? this.newsFeed.getNewsData() || [] : [];
            const categorizedArticles = this.categorizeArticles(stockData.symbol, newsData);
            const articlesHTML = this.generateArticlesHTML(stockData.symbol, categorizedArticles);

            // Generate tabs
            const tabId = `tabs-${stockData.symbol}`;
            return `
                <div class="stock-forecast-group">
                    <h2 class="stock-header">
                        <span class="stock-symbol">${stockData.symbol}</span>
                        Forecasts
                    </h2>
                    <div class="tabs-container">
                        <div class="tabs-nav">
                            <button class="tab-btn active" data-tab="summary" data-symbol="${stockData.symbol}">
                                Forecast Summary
                            </button>
                            <button class="tab-btn" data-tab="articles" data-symbol="${stockData.symbol}">
                                News Articles
                            </button>
                            <button class="tab-btn" data-tab="chart" data-symbol="${stockData.symbol}">
                                Price Chart
                            </button>
                        </div>
                        <div class="tabs-content">
                            <div id="summary-${stockData.symbol}" class="tab-panel active">
                                <div class="forecasts-container">
                                    ${forecastCardsHTML}
                                </div>
                            </div>
                            <div id="articles-${stockData.symbol}" class="tab-panel">
                                <div class="articles-panel-content">
                                    ${articlesHTML}
                                </div>
                            </div>
                            <div id="chart-${stockData.symbol}" class="tab-panel">
                                <div class="chart-container">
                                    <canvas id="chart-canvas-${stockData.symbol}"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).filter(html => html.trim().length > 0).join('');

        this.forecastResults.innerHTML = stocksHTML;
        
        // Attach event listeners to tab buttons after HTML is inserted
        this.attachTabListeners();
    }

    /**
     * Attach event listeners to tab buttons
     */
    attachTabListeners() {
        const tabButtons = this.forecastResults.querySelectorAll('.tab-btn');
        tabButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const symbol = btn.getAttribute('data-symbol');
                const tabType = btn.getAttribute('data-tab');
                if (symbol && tabType) {
                    this.switchTab(symbol, tabType);
                }
            });
        });
    }

    /**
     * Switch between tabs
     */
    switchTab(symbol, tabType) {
        // Find panels by ID
        const summaryPanel = document.getElementById(`summary-${symbol}`);
        const articlesPanel = document.getElementById(`articles-${symbol}`);
        const chartPanel = document.getElementById(`chart-${symbol}`);
        
        // Find buttons by data attributes
        const summaryBtn = document.querySelector(`button[data-tab="summary"][data-symbol="${symbol}"]`);
        const articlesBtn = document.querySelector(`button[data-tab="articles"][data-symbol="${symbol}"]`);
        const chartBtn = document.querySelector(`button[data-tab="chart"][data-symbol="${symbol}"]`);

        // First, hide all panels explicitly
        if (summaryPanel) {
            summaryPanel.classList.remove('active');
            summaryPanel.style.display = 'none';
        }
        if (articlesPanel) {
            articlesPanel.classList.remove('active');
            articlesPanel.style.display = 'none';
        }
        if (chartPanel) {
            chartPanel.classList.remove('active');
            chartPanel.style.display = 'none';
        }
        
        // Remove active from all buttons
        [summaryBtn, articlesBtn, chartBtn].forEach(btn => {
            if (btn) btn.classList.remove('active');
        });

        // Add active class to selected tab and show it
        if (tabType === 'summary') {
            if (summaryPanel) {
                summaryPanel.classList.add('active');
                summaryPanel.style.display = 'block';
                summaryPanel.style.visibility = 'visible';
            } else {
                console.error(`Summary panel not found for ${symbol}`);
            }
            if (summaryBtn) {
                summaryBtn.classList.add('active');
            } else {
                console.error(`Summary button not found for ${symbol}`);
            }
        } else if (tabType === 'articles') {
            if (articlesPanel) {
                articlesPanel.classList.add('active');
                articlesPanel.style.display = 'block';
                articlesPanel.style.visibility = 'visible';
            } else {
                console.error(`Articles panel not found for ${symbol}`);
            }
            if (articlesBtn) {
                articlesBtn.classList.add('active');
            } else {
                console.error(`Articles button not found for ${symbol}`);
            }
        } else if (tabType === 'chart') {
            if (chartPanel) {
                chartPanel.classList.add('active');
                chartPanel.style.display = 'block';
                chartPanel.style.visibility = 'visible';
            } else {
                console.error(`Chart panel not found for ${symbol}`);
            }
            if (chartBtn) {
                chartBtn.classList.add('active');
            } else {
                console.error(`Chart button not found for ${symbol}`);
            }
            // Initialize chart when tab is opened
            if (chartPanel) {
                // Small delay to ensure panel is visible before chart renders
                setTimeout(() => {
                    this.initializeChart(symbol);
                }, 50);
            }
        }
    }

    /**
     * Generate simulated price data for the last 30 days
     */
    generatePriceData(symbol, articles) {
        // Generate 30 days of price data
        const days = 30;
        const data = [];
        const labels = [];
        const today = new Date();
        
        // Base price varies by symbol (simulated)
        const basePrices = {
            'AAPL': 180, 'MSFT': 380, 'GOOGL': 140, 'AMZN': 150, 'NVDA': 500,
            'META': 320, 'TSLA': 250, 'NFLX': 450, 'AMD': 120, 'INTC': 40
        };
        
        let basePrice = basePrices[symbol] || 100 + Math.random() * 200;
        const baseDate = new Date(today);
        baseDate.setDate(baseDate.getDate() - days);

        // Create article dates map
        const articleDates = {};
        articles.forEach(article => {
            if (article.pubDate) {
                const date = new Date(article.pubDate);
                const dateKey = date.toISOString().split('T')[0];
                if (!articleDates[dateKey]) {
                    articleDates[dateKey] = [];
                }
                articleDates[dateKey].push({
                    title: article.title || 'Article',
                    sentiment: article.sentiment || 'neutral',
                    link: article.link || '#'
                });
            }
        });

        // Generate price data
        let currentPrice = basePrice;
        for (let i = 0; i < days; i++) {
            const date = new Date(baseDate);
            date.setDate(date.getDate() + i);
            const dateKey = date.toISOString().split('T')[0];
            
            // Random walk with slight upward trend
            const change = (Math.random() - 0.45) * 5; // Slight upward bias
            currentPrice = Math.max(basePrice * 0.7, Math.min(basePrice * 1.3, currentPrice + change));
            
            labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
            data.push({
                x: i,
                y: parseFloat(currentPrice.toFixed(2)),
                date: dateKey,
                hasArticle: !!articleDates[dateKey],
                articles: articleDates[dateKey] || []
            });
        }

        return { labels, data, basePrice };
    }

    /**
     * Initialize chart with price data and article markers
     */
    initializeChart(symbol) {
        const canvasId = `chart-canvas-${symbol}`;
        const canvas = document.getElementById(canvasId);
        
        if (!canvas) {
            console.error(`Chart canvas not found: ${canvasId}`);
            return;
        }

        // Get news data
        const newsData = this.newsFeed ? this.newsFeed.getNewsData() || [] : [];
        const categorizedArticles = this.categorizeArticles(symbol, newsData);
        
        // Combine all articles
        const allArticles = [
            ...categorizedArticles.positive,
            ...categorizedArticles.negative,
            ...categorizedArticles.neutral
        ];

        // Generate price data
        const priceData = this.generatePriceData(symbol, allArticles);

        // Destroy existing chart if it exists
        if (this.charts && this.charts[symbol]) {
            this.charts[symbol].destroy();
        }

        if (!this.charts) {
            this.charts = {};
        }

        // Create chart configuration with article markers
        const ctx = canvas.getContext('2d');
        
        // Create article markers dataset - null for no article, value for article
        const articleMarkers = priceData.data.map((point, index) => {
            if (point.hasArticle && point.articles.length > 0) {
                const article = point.articles[0];
                return {
                    x: index,
                    y: point.y,
                    article: article
                };
            }
            return null;
        });

        // Store article info for tooltip and click handlers
        const articleInfoMap = new Map();
        articleMarkers.forEach((marker, index) => {
            if (marker) {
                articleInfoMap.set(index, marker.article);
            }
        });

        const chartConfig = {
            type: 'line',
            data: {
                labels: priceData.labels,
                datasets: [
                    {
                        label: `${symbol} Price`,
                        data: priceData.data.map(p => p.y),
                        borderColor: 'rgb(37, 99, 235)',
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        borderWidth: 2,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 5,
                        fill: true
                    },
                    {
                        label: 'Article Publication',
                        data: priceData.data.map((p, index) => {
                            if (p.hasArticle) return p.y;
                            return null;
                        }),
                        backgroundColor: priceData.data.map((p) => {
                            if (p.hasArticle && p.articles.length > 0) {
                                const article = p.articles[0];
                                if (article.sentiment === 'positive') return 'rgb(16, 185, 129)';
                                if (article.sentiment === 'negative') return 'rgb(239, 68, 68)';
                                return 'rgb(148, 163, 184)';
                            }
                            return 'rgba(0, 0, 0, 0)';
                        }),
                        borderColor: priceData.data.map((p) => {
                            if (p.hasArticle && p.articles.length > 0) {
                                const article = p.articles[0];
                                if (article.sentiment === 'positive') return 'rgb(16, 185, 129)';
                                if (article.sentiment === 'negative') return 'rgb(239, 68, 68)';
                                return 'rgb(148, 163, 184)';
                            }
                            return 'rgba(0, 0, 0, 0)';
                        }),
                        pointRadius: priceData.data.map(p => p.hasArticle ? 8 : 0),
                        pointHoverRadius: priceData.data.map(p => p.hasArticle ? 12 : 0),
                        pointHoverBackgroundColor: 'rgb(255, 255, 255)',
                        pointHoverBorderWidth: 3,
                        pointStyle: 'circle',
                        showLine: false,
                        order: 0
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 2,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.datasetIndex === 1 && context.parsed.y !== null) {
                                    // Article marker
                                    const article = articleInfoMap.get(context.dataIndex);
                                    if (article) {
                                        return [
                                            `Article: ${article.title.substring(0, 50)}${article.title.length > 50 ? '...' : ''}`,
                                            `Sentiment: ${article.sentiment}`,
                                            `Click to view article`
                                        ];
                                    }
                                    return `Article published`;
                                }
                                if (context.datasetIndex === 0) {
                                    return `${context.dataset.label}: $${context.parsed.y.toFixed(2)}`;
                                }
                                return '';
                            }
                        }
                    },
                    title: {
                        display: true,
                        text: `${symbol} Price Chart with News Events`,
                        font: {
                            size: 16,
                            weight: 'bold'
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        title: {
                            display: true,
                            text: 'Price ($)'
                        },
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Date'
                        },
                        grid: {
                            display: false
                        }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const element = elements[0];
                        if (element.datasetIndex === 1) {
                            // Clicked on article marker
                            const article = articleInfoMap.get(element.index);
                            if (article && article.link && article.link !== '#') {
                                window.open(article.link, '_blank');
                            }
                        }
                    }
                }
            }
        };
        
        // Store articleInfoMap for this chart
        if (!this.chartArticleMaps) {
            this.chartArticleMaps = {};
        }
        this.chartArticleMaps[symbol] = articleInfoMap;

        // Create and store chart
        this.charts[symbol] = new Chart(ctx, chartConfig);
    }

    /**
     * Show error message
     */
    showError(message) {
        this.forecastResults.innerHTML = `<p class="empty-message" style="color: var(--danger-color);">${message}</p>`;
    }
}

