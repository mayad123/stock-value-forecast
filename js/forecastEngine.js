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
        
        // Initialize relevancy analyzer if available
        if (typeof RelevancyAnalyzer !== 'undefined') {
            this.relevancyAnalyzer = new RelevancyAnalyzer();
        } else {
            console.warn('RelevancyAnalyzer not loaded - using basic algorithm');
            this.relevancyAnalyzer = null;
        }
        
        // Initialize ML Forecast Engine if available
        if (typeof MLForecastEngine !== 'undefined') {
            this.mlEngine = new MLForecastEngine();
            // Train model on initialization (async, non-blocking)
            this.mlEngine.trainModelWithSampleData().catch(err => {
                console.warn('ML model training failed:', err);
            });
        } else {
            console.warn('MLForecastEngine not loaded - using rule-based predictions');
            this.mlEngine = null;
        }
        
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
            
            // Generate all forecast types (await ML-enhanced trend forecast)
            const trendForecast = await this.generateTrendForecast(symbol, sentiment, newsData || []);
            
            return {
                symbol: symbol.toUpperCase(),
                sentiment,
                forecasts: [
                    this.generateSentimentForecast(symbol, sentiment),
                    trendForecast,
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
     * Check if article is relevant to stock (quick check)
     * Uses advanced relevancy analyzer if available, falls back to basic algorithm
     */
    isRelevantToStock(symbol, article) {
        // Use advanced relevancy analyzer if available
        if (this.relevancyAnalyzer) {
            const score = this.relevancyAnalyzer.scoreArticleRelevance(symbol, article);
            return score >= 30;
        }
        
        // Fallback to basic algorithm
        const score = this.scoreArticleRelevance(symbol, article);
        return score >= 30;
    }

    /**
     * Score article relevance to a stock (higher = more relevant)
     * Improved algorithm with better company name matching and context
     */
    scoreArticleRelevance(symbol, article) {
        const title = (article.title || '').toLowerCase();
        const description = ((article.contentSnippet || article.description || '') + ' ' + (article.link || '')).toLowerCase();
        const fullText = title + ' ' + description;
        let score = 0;
        
        // Comprehensive company database with names, tickers, products, and key people
        const companyData = {
            'AAPL': {
                names: ['apple', 'apple inc', 'apple computer', 'apples'],
                products: ['iphone', 'ipad', 'macbook', 'imac', 'airpods', 'apple watch', 'app store', 'ios', 'macos', 'safari'],
                keywords: ['tim cook', 'apple store', 'app store', 'apple pay', 'apple tv'],
                exclude: ['apple pie', 'apple cider', 'apple tree'] // Avoid false positives
            },
            'MSFT': {
                names: ['microsoft', 'msft'],
                products: ['windows', 'office', 'azure', 'xbox', 'surface', 'bing', 'teams', 'outlook', 'excel', 'word', 'powerpoint'],
                keywords: ['satya nadella', 'microsoft office', 'windows 11', 'microsoft cloud'],
                exclude: []
            },
            'GOOGL': {
                names: ['google', 'alphabet', 'googl', 'goog'],
                products: ['android', 'chrome', 'youtube', 'gmail', 'maps', 'search', 'pixel', 'google cloud', 'drive'],
                keywords: ['sundar pichai', 'google search', 'google ads', 'adwords', 'google play'],
                exclude: []
            },
            'AMZN': {
                names: ['amazon', 'amzn', 'amazon.com'],
                products: ['aws', 'alexa', 'echo', 'kindle', 'prime', 'prime video', 'amazon web services'],
                keywords: ['jeff bezos', 'andy jassy', 'amazon prime', 'amazon web services'],
                exclude: ['amazon rainforest', 'amazon river']
            },
            'NVDA': {
                names: ['nvidia', 'nvda'],
                products: ['gpu', 'graphics card', 'geforce', 'rtx', 'cuda', 'tensor', 'a100', 'h100', 'dlss'],
                keywords: ['jensen huang', 'nvidia gpu', 'artificial intelligence', 'ai chip', 'data center'],
                exclude: []
            },
            'META': {
                names: ['meta', 'facebook', 'fb', 'meta platforms'],
                products: ['instagram', 'whatsapp', 'oculus', 'metaverse', 'reality labs', 'facebook messenger'],
                keywords: ['mark zuckerberg', 'meta platforms', 'virtual reality', 'vr', 'ar'],
                exclude: ['facebook marketplace'] // Can be ambiguous
            },
            'TSLA': {
                names: ['tesla', 'tsla'],
                products: ['model 3', 'model y', 'model s', 'model x', 'cybertruck', 'tesla vehicle', 'supercharger'],
                keywords: ['elon musk', 'tesla motors', 'electric vehicle', 'ev', 'autopilot', 'fsd', 'full self driving'],
                exclude: ['tesla coil', 'nikola tesla']
            },
            'NFLX': {
                names: ['netflix', 'nflx'],
                products: ['netflix streaming', 'netflix original'],
                keywords: ['netflix subscribers', 'streaming service', 'netflix content'],
                exclude: []
            },
            'AMD': {
                names: ['amd', 'advanced micro devices'],
                products: ['ryzen', 'epyc', 'radeon', 'gpu', 'cpu', 'xilinx'],
                keywords: ['lisa su', 'amd processor', 'amd graphics'],
                exclude: []
            },
            'INTC': {
                names: ['intel', 'intc'],
                products: ['core i7', 'core i9', 'xeon', 'pentium', 'celeron', 'intel processor'],
                keywords: ['pat gelsinger', 'intel chip', 'intel processor'],
                exclude: ['intellectual property']
            },
            'DIS': {
                names: ['disney', 'dis'],
                products: ['disney+', 'disney plus', 'marvel', 'star wars', 'pixar', 'espn', 'abc', 'hulu'],
                keywords: ['bob iger', 'disney theme park', 'disneyland', 'disney world'],
                exclude: []
            },
            'JPM': {
                names: ['jpmorgan', 'jp morgan', 'jpm', 'jpmorgan chase'],
                keywords: ['jamie dimon', 'jpmorgan chase', 'chase bank'],
                exclude: []
            },
            'BAC': {
                names: ['bank of america', 'bofa', 'bac'],
                keywords: ['bank of america', 'merrill lynch'],
                exclude: []
            }
        };
        
        const company = companyData[symbol];
        if (!company) {
            // For unknown stocks, use basic matching
            const symbolPattern = new RegExp(`\\b${symbol.toLowerCase()}\\b|\\$${symbol.toLowerCase()}\\b`);
            if (symbolPattern.test(fullText)) {
                score += 50;
            }
            return score;
        }
        
        // 1. Symbol match in title (highest relevance) - must be word boundary
        const symbolPattern = new RegExp(`\\b${symbol.toLowerCase()}\\b|\\$${symbol.toLowerCase()}\\b`);
        if (title && symbolPattern.test(title)) {
            score += 150; // Very high score for symbol in title
        } else if (symbolPattern.test(fullText)) {
            score += 80; // Good score for symbol anywhere
        }
        
        // 2. Company name match in title (high relevance)
        company.names.forEach(name => {
            // Use word boundary to avoid false matches
            const namePattern = new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
            if (title && namePattern.test(title)) {
                score += 100; // High score for company name in title
            } else if (namePattern.test(fullText)) {
                score += 60; // Medium score for company name in content
            }
        });
        
        // 3. Product names (medium-high relevance)
        if (company.products) {
            company.products.forEach(product => {
                const productPattern = new RegExp(`\\b${product.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
                if (title && productPattern.test(title)) {
                    score += 70;
                } else if (productPattern.test(fullText)) {
                    score += 40;
                }
            });
        }
        
        // 4. Key people and executives (medium relevance)
        if (company.keywords) {
            company.keywords.forEach(keyword => {
                const keywordPattern = new RegExp(`\\b${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
                if (keywordPattern.test(fullText)) {
                    score += 30;
                }
            });
        }
        
        // 5. Check for false positives (exclude terms) - reduce score if matched
        if (company.exclude && company.exclude.length > 0) {
            let hasExclusion = false;
            company.exclude.forEach(excludeTerm => {
                if (fullText.includes(excludeTerm)) {
                    hasExclusion = true;
                }
            });
            // If we only matched an exclusion term, reduce score significantly
            if (hasExclusion && score < 50) {
                score = 0; // Likely false positive
            } else if (hasExclusion) {
                score = Math.max(0, score - 50); // Reduce but don't eliminate
            }
        }
        
        // 6. Context boost: If article mentions both company and financial terms together
        const financialTerms = ['earnings', 'revenue', 'profit', 'loss', 'stock', 'shares', 'dividend', 'quarterly', 'analyst', 'forecast', 'price target'];
        const hasFinancialContext = financialTerms.some(term => fullText.includes(term));
        if (hasFinancialContext && score > 30) {
            score += 20; // Boost articles with financial context
        }
        
        // 7. Filter out very generic market news (lower score threshold)
        if (score < 50) {
            // Only accept generic market news if it has strong financial context AND mentions the stock
            if (hasFinancialContext && symbolPattern.test(fullText)) {
                score += 15; // Small boost for financial news mentioning symbol
            } else {
                // Too generic, don't include unless direct match
                return score < 50 ? 0 : score;
            }
        }
        
        return score;
    }

    /**
     * Categorize articles by sentiment for a specific stock and get top 100 most relevant
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

        // Score and filter relevant articles with advanced algorithm
        const scoredArticles = [];
        newsData.forEach(article => {
            // Use advanced relevancy analyzer if available
            const relevanceScore = this.relevancyAnalyzer 
                ? this.relevancyAnalyzer.scoreArticleRelevance(symbol, article, newsData)
                : this.scoreArticleRelevance(symbol, article);
            
            // Require minimum relevance score of 30 to filter out generic/barely relevant articles
            if (relevanceScore >= 30) {
                const text = (article.title + ' ' + (article.contentSnippet || article.description || '')).toLowerCase();
                
                let positiveCount = 0;
                let negativeCount = 0;

                positiveKeywords.forEach(keyword => {
                    if (text.includes(keyword)) positiveCount++;
                });

                negativeKeywords.forEach(keyword => {
                    if (text.includes(keyword)) negativeCount++;
                });

                scoredArticles.push({
                    ...article,
                    relevanceScore,
                    positiveCount,
                    negativeCount
                });
            }
        });

        // Sort by relevance (highest first) and take top 100 most relevant
        scoredArticles.sort((a, b) => {
            // First sort by relevance score
            if (b.relevanceScore !== a.relevanceScore) {
                return b.relevanceScore - a.relevanceScore;
            }
            // If same relevance, prefer articles with more sentiment keywords
            const aSentiment = a.positiveCount + a.negativeCount;
            const bSentiment = b.positiveCount + b.negativeCount;
            return bSentiment - aSentiment;
        });
        const topArticles = scoredArticles.slice(0, 100);

        const categorized = {
            positive: [],
            negative: [],
            neutral: []
        };

        topArticles.forEach(article => {
            // Categorize based on keyword count
            if (article.positiveCount > article.negativeCount && article.positiveCount > 0) {
                categorized.positive.push({
                    ...article,
                    sentiment: 'positive',
                    positiveScore: article.positiveCount,
                    negativeScore: article.negativeCount
                });
            } else if (article.negativeCount > article.positiveCount && article.negativeCount > 0) {
                categorized.negative.push({
                    ...article,
                    sentiment: 'negative',
                    positiveScore: article.positiveCount,
                    negativeScore: article.negativeCount
                });
            } else {
                categorized.neutral.push({
                    ...article,
                    sentiment: 'neutral',
                    positiveScore: article.positiveCount,
                    negativeScore: article.negativeCount
                });
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
                                <span style="display: inline-flex; align-items: center; gap: 4px;">
                                    <span style="display: inline-block; width: 12px; height: 12px; border-radius: 50%; background-color: #ef4444; flex-shrink: 0;"></span>
                                    Source: ${this.escapeHtml(article.author || 'Yahoo Finance')}
                                </span>
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
     * Generate trend forecast (with ML enhancement if available)
     */
    async generateTrendForecast(symbol, sentiment, newsData) {
        let trendScore = sentiment.score / 100; // Normalize to -1 to 1
        let trendConfidence = sentiment.confidence;
        let method = 'Rule-Based';
        
        // Try ML prediction if available
        if (this.mlEngine && this.mlEngine.isModelLoaded) {
            try {
                // Get categorized articles for better ML features
                const categorizedArticles = this.categorizeArticles(symbol, newsData);
                const allArticles = [
                    ...categorizedArticles.positive,
                    ...categorizedArticles.negative,
                    ...categorizedArticles.neutral
                ];
                
                const mlResult = await this.mlEngine.predictTrend(sentiment, allArticles, this.relevancyAnalyzer);
                trendScore = mlResult.score;
                trendConfidence = mlResult.confidence;
                method = mlResult.method;
            } catch (error) {
                console.warn('ML prediction failed, using rule-based:', error);
            }
        }
        
        // Convert score to trend direction
        const trend = trendScore > 0.1 ? 'Upward' : trendScore < -0.1 ? 'Downward' : 'Sideways';
        const trendColor = trendScore > 0.1 ? 'positive' : trendScore < -0.1 ? 'negative' : '';
        const sentimentColor = sentiment.score > 20 ? 'positive' : sentiment.score < -20 ? 'negative' : '';
        const strength = Math.abs(trendScore) > 0.5 ? 'Strong' : Math.abs(trendScore) > 0.2 ? 'Moderate' : 'Weak';
        
        return {
            symbol,
            type: 'Trend Prediction',
            metrics: [
                { label: 'Trend Direction', value: trend, class: trendColor },
                { label: 'Trend Strength', value: strength },
                { label: 'Prediction Method', value: method },
                { label: 'Confidence', value: `${Math.round(trendConfidence)}%` }
            ],
            description: `${symbol} shows a ${trend.toLowerCase()} trend with ${strength.toLowerCase()} strength based on ${method.toLowerCase()} analysis.`
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
            // Initialize chart when chart tab is opened
            if (chartPanel) {
                // Small delay to ensure panel is visible before chart renders
                setTimeout(() => {
                    this.initializeChart(symbol);
                }, 100);
            }
        }
    }

    /**
     * Fetch real stock price data from Yahoo Finance
     */
    async fetchStockPriceData(symbol, period = '1mo') {
        try {
            // Yahoo Finance API endpoint for historical prices
            const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=${period}`;
            
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();
            
            if (result.chart && result.chart.result && result.chart.result[0]) {
                const chartData = result.chart.result[0];
                const timestamps = chartData.timestamp || [];
                const prices = chartData.indicators?.quote?.[0]?.close || [];
                const volumes = chartData.indicators?.quote?.[0]?.volume || [];
                
                return {
                    timestamps,
                    prices,
                    volumes,
                    success: true
                };
            }
            
            return { success: false, error: 'No data found' };
        } catch (error) {
            console.error(`Error fetching stock data for ${symbol}:`, error);
            return { success: false, error: error.message };
        }
    }

    /**
     * Generate price data using real stock prices for the last 30 days
     */
    async generatePriceData(symbol, articles) {
        // Fetch real stock price data (1 month)
        const stockData = await this.fetchStockPriceData(symbol, '1mo');
        
        let data = [];
        let labels = [];
        let basePrice = 100;
        
        if (stockData.success && stockData.prices && stockData.prices.length > 0) {
            // Use real price data
            const prices = stockData.prices;
            const timestamps = stockData.timestamps;
            
            // Filter out null/undefined prices and get last 30 days
            const validData = [];
            for (let i = 0; i < prices.length; i++) {
                if (prices[i] !== null && prices[i] !== undefined && timestamps[i]) {
                    validData.push({
                        timestamp: timestamps[i] * 1000, // Convert to milliseconds
                        price: prices[i]
                    });
                }
            }
            
            // Take last 30 days or all available if less than 30
            const recentData = validData.slice(-30);
            
            if (recentData.length > 0) {
                basePrice = recentData[0].price;
                
                // Create article dates map - map articles to nearest trading day
                const articleDates = new Map();
                const tradingDates = recentData.map(point => {
                    const date = new Date(point.timestamp);
                    return date.toISOString().split('T')[0];
                });
                
                articles.forEach(article => {
                    if (article.pubDate) {
                        const articleDate = new Date(article.pubDate);
                        const articleDateKey = articleDate.toISOString().split('T')[0];
                        
                        // Try exact match first
                        if (tradingDates.includes(articleDateKey)) {
                            if (!articleDates.has(articleDateKey)) {
                                articleDates.set(articleDateKey, []);
                            }
                            articleDates.get(articleDateKey).push({
                                title: article.title || 'Article',
                                sentiment: article.sentiment || 'neutral',
                                link: article.link || '#'
                            });
                        } else {
                            // Find nearest trading day (within 3 days before or after)
                            let nearestDate = null;
                            let minDiff = Infinity;
                            
                            tradingDates.forEach(tradingDate => {
                                const tradingDateObj = new Date(tradingDate);
                                const diff = Math.abs(articleDate - tradingDateObj);
                                // Within 3 days
                                if (diff < 3 * 24 * 60 * 60 * 1000 && diff < minDiff) {
                                    minDiff = diff;
                                    nearestDate = tradingDate;
                                }
                            });
                            
                            if (nearestDate) {
                                if (!articleDates.has(nearestDate)) {
                                    articleDates.set(nearestDate, []);
                                }
                                articleDates.get(nearestDate).push({
                                    title: article.title || 'Article',
                                    sentiment: article.sentiment || 'neutral',
                                    link: article.link || '#'
                                });
                            }
                        }
                    }
                });
                
                // Generate data points
                recentData.forEach((point, index) => {
                    const date = new Date(point.timestamp);
                    const dateKey = date.toISOString().split('T')[0];
                    
                    labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
                    const articlesForDate = articleDates.get(dateKey) || [];
                    data.push({
                        x: index,
                        y: parseFloat(point.price.toFixed(2)),
                        date: dateKey,
                        hasArticle: articlesForDate.length > 0,
                        articles: articlesForDate
                    });
                });
                
                // Debug: Log article matches
                const articleCount = Array.from(articleDates.values()).reduce((sum, arr) => sum + arr.length, 0);
                const datesWithArticles = data.filter(d => d.hasArticle).length;
                if (articleCount > 0) {
                    console.log(`${symbol}: Found ${articleCount} articles, matched to ${datesWithArticles} trading days`);
                }
            }
        }
        
        // Fallback: If API fails or no data, use current price and generate recent trend
        if (data.length === 0) {
            try {
                // Try to get current price
                const currentPriceUrl = `https://query1.finance.yahoo.com/v7/finance/quote?symbols=${symbol}`;
                const currentResponse = await fetch(currentPriceUrl);
                
                if (currentResponse.ok) {
                    const currentData = await currentResponse.json();
                    if (currentData.quoteResponse && currentData.quoteResponse.result && currentData.quoteResponse.result[0]) {
                        basePrice = currentData.quoteResponse.result[0].regularMarketPrice || basePrice;
                    }
                }
            } catch (e) {
                console.error('Error fetching current price:', e);
            }
            
            // Generate last 30 days with slight variation around current price
            const days = 30;
            const today = new Date();
            const baseDate = new Date(today);
            baseDate.setDate(baseDate.getDate() - days);
            
            // Create article dates map - match articles to generated dates
            const articleDates = new Map();
            const generatedDates = [];
            
            // First, collect all generated dates
            for (let i = 0; i < days; i++) {
                const date = new Date(baseDate);
                date.setDate(date.getDate() + i);
                const dateKey = date.toISOString().split('T')[0];
                generatedDates.push(dateKey);
            }
            
            // Map articles to nearest date
            articles.forEach(article => {
                if (article.pubDate) {
                    const articleDate = new Date(article.pubDate);
                    const articleDateKey = articleDate.toISOString().split('T')[0];
                    
                    // Try exact match first
                    if (generatedDates.includes(articleDateKey)) {
                        if (!articleDates.has(articleDateKey)) {
                            articleDates.set(articleDateKey, []);
                        }
                        articleDates.get(articleDateKey).push({
                            title: article.title || 'Article',
                            sentiment: article.sentiment || 'neutral',
                            link: article.link || '#'
                        });
                    } else {
                        // Find nearest date (within 3 days)
                        let nearestDate = null;
                        let minDiff = Infinity;
                        
                        generatedDates.forEach(genDate => {
                            const genDateObj = new Date(genDate);
                            const diff = Math.abs(articleDate - genDateObj);
                            if (diff < 3 * 24 * 60 * 60 * 1000 && diff < minDiff) {
                                minDiff = diff;
                                nearestDate = genDate;
                            }
                        });
                        
                        if (nearestDate) {
                            if (!articleDates.has(nearestDate)) {
                                articleDates.set(nearestDate, []);
                            }
                            articleDates.get(nearestDate).push({
                                title: article.title || 'Article',
                                sentiment: article.sentiment || 'neutral',
                                link: article.link || '#'
                            });
                        }
                    }
                }
            });
            
            // Generate price data with small random variation
            let currentPrice = basePrice;
            for (let i = 0; i < days; i++) {
                const date = new Date(baseDate);
                date.setDate(date.getDate() + i);
                const dateKey = date.toISOString().split('T')[0];
                
                // Small random variation (±2%)
                const change = (Math.random() - 0.5) * basePrice * 0.04;
                currentPrice = basePrice + change;
                
                const articlesForDate = articleDates.get(dateKey) || [];
                labels.push(date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
                data.push({
                    x: i,
                    y: parseFloat(currentPrice.toFixed(2)),
                    date: dateKey,
                    hasArticle: articlesForDate.length > 0,
                    articles: articlesForDate
                });
            }
        }

        return { labels, data, basePrice };
    }

    /**
     * Initialize chart with price data and article markers
     */
    async initializeChart(symbol) {
        const canvasId = `chart-canvas-${symbol}`;
        const canvas = document.getElementById(canvasId);
        
        if (!canvas) {
            console.error(`Chart canvas not found: ${canvasId}`);
            return;
        }

        // Destroy existing chart if it exists
        if (this.charts && this.charts[symbol]) {
            this.charts[symbol].destroy();
        }

        // Get news data - filter for articles from last year
        const newsData = this.newsFeed ? this.newsFeed.getNewsData() || [] : [];
        const oneYearAgo = new Date();
        oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
        
        // Filter articles from the last year
        const lastYearNews = newsData.filter(article => {
            if (!article.pubDate) return true;
            const pubDate = new Date(article.pubDate);
            return pubDate >= oneYearAgo;
        });
        
        const categorizedArticles = this.categorizeArticles(symbol, lastYearNews);
        
        // Combine all articles (top 100 most relevant)
        const allArticles = [
            ...categorizedArticles.positive,
            ...categorizedArticles.negative,
            ...categorizedArticles.neutral
        ];
        
        // Debug: Log articles being passed to chart
        console.log(`${symbol}: Using ${allArticles.length} relevant articles for chart (from ${lastYearNews.length} total articles in last year)`);

        // Generate price data (async - needs await)
        // Show loading message
        const chartContainer = canvas.parentElement;
        if (chartContainer) {
            chartContainer.innerHTML = '<p style="text-align: center; padding: 2rem;">Loading price data...</p>';
        }
        
        try {
            const priceData = await this.generatePriceData(symbol, allArticles);
            
            // Recreate canvas after loading
            if (chartContainer) {
                chartContainer.innerHTML = `<canvas id="${canvasId}"></canvas>`;
                const newCanvas = document.getElementById(canvasId);
                if (!newCanvas) {
                    console.error(`Chart canvas not found after recreation: ${canvasId}`);
                    return;
                }
                this.renderChart(newCanvas, symbol, priceData, categorizedArticles);
            }
        } catch (error) {
            console.error(`Error generating price data for ${symbol}:`, error);
            if (chartContainer) {
                chartContainer.innerHTML = '<p style="text-align: center; padding: 2rem; color: red;">Error loading price data. Please try again.</p>';
            }
        }
    }

    /**
     * Render chart with price data
     */
    renderChart(canvas, symbol, priceData, categorizedArticles) {
        // Combine all articles for markers
        const allArticles = [
            ...categorizedArticles.positive,
            ...categorizedArticles.negative,
            ...categorizedArticles.neutral
        ];

        if (!this.charts) {
            this.charts = {};
        }

        // Create chart configuration with article markers
        const ctx = canvas.getContext('2d');
        
        // Store article info for tooltip and click handlers - map by data index
        const articleInfoMap = new Map();
        priceData.data.forEach((point, index) => {
            if (point.hasArticle && point.articles && point.articles.length > 0) {
                // Store all articles for this date point
                articleInfoMap.set(index, point.articles[0]); // Use first article for tooltip
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
                            // Always return a data point, but use NaN if no article (Chart.js will skip it)
                            if (p.hasArticle && p.articles && p.articles.length > 0) {
                                return p.y; // Return the y value (price) at this index
                            }
                            return NaN; // Use NaN instead of null - Chart.js will skip these points
                        }),
                        backgroundColor: 'rgb(239, 68, 68)', // Red color for document icon
                        borderColor: 'rgb(220, 38, 38)', // Darker red border
                        pointRadius: priceData.data.map((p, idx) => {
                            if (p.hasArticle && p.articles && p.articles.length > 0) return 12;
                            return 0;
                        }),
                        pointHoverRadius: priceData.data.map((p, idx) => {
                            if (p.hasArticle && p.articles && p.articles.length > 0) return 16;
                            return 0;
                        }),
                        pointHoverBackgroundColor: 'rgb(239, 68, 68)',
                        pointHoverBorderColor: 'rgb(220, 38, 38)',
                        pointHoverBorderWidth: 4,
                        pointStyle: 'rectRot', // Document/rectangular rotated style (looks like document)
                        showLine: false,
                        order: 0,
                        tension: 0
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

