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
     * Display forecasts in the UI grouped by stock
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

        const forecastsHTML = validStockForecasts.map(stockData => {
            // Generate HTML for all forecast types for this stock
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

            // Wrap all forecasts for a stock in a container
            return `
                <div class="stock-forecast-group">
                    <h2 class="stock-header">
                        <span class="stock-symbol">${stockData.symbol}</span>
                        Forecasts
                    </h2>
                    <div class="forecasts-container">
                        ${forecastCardsHTML}
                    </div>
                </div>
            `;
        }).filter(html => html.trim().length > 0).join('');

        this.forecastResults.innerHTML = forecastsHTML;
    }

    /**
     * Show error message
     */
    showError(message) {
        this.forecastResults.innerHTML = `<p class="empty-message" style="color: var(--danger-color);">${message}</p>`;
    }
}

