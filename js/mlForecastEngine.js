/**
 * Machine Learning Enhanced Forecast Engine
 * Uses TensorFlow.js for intelligent trend predictions
 * Based on sentiment analysis and relevancy scoring
 */

class MLForecastEngine {
    constructor() {
        this.model = null;
        this.isModelLoaded = false;
        this.trainingData = [];
        this.featureStats = null;
        
        // Check if TensorFlow.js is available
        if (typeof tf === 'undefined') {
            console.warn('TensorFlow.js not loaded - ML features disabled');
            return;
        }
        
        // Initialize model on construction
        this.initializeModel();
    }

    /**
     * Initialize TensorFlow.js model
     * Uses a simple neural network for regression
     */
    async initializeModel() {
        if (typeof tf === 'undefined') return;
        
        try {
            // Create a sequential model
            this.model = tf.sequential({
                layers: [
                    // Input layer with 8 features
                    tf.layers.dense({
                        inputShape: [8],
                        units: 16,
                        activation: 'relu',
                        kernelInitializer: 'heNormal'
                    }),
                    // Dropout for regularization
                    tf.layers.dropout({ rate: 0.3 }),
                    // Hidden layer
                    tf.layers.dense({
                        units: 8,
                        activation: 'relu'
                    }),
                    // Output layer (single prediction)
                    tf.layers.dense({
                        units: 1,
                        activation: 'tanh' // Output range: -1 to 1
                    })
                ]
            });

            // Compile the model
            this.model.compile({
                optimizer: tf.train.adam(0.001),
                loss: 'meanSquaredError',
                metrics: ['meanAbsoluteError']
            });

            console.log('ML Model initialized successfully');
            this.isModelLoaded = true;
        } catch (error) {
            console.error('Failed to initialize ML model:', error);
        }
    }

    /**
     * Extract features from sentiment and article data
     */
    extractFeatures(sentiment, articles, relevancyAnalyzer) {
        const features = [];
        
        // Feature 1: Sentiment score (normalized to -1 to 1)
        features.push(Math.max(-1, Math.min(1, sentiment.score / 100)));
        
        // Feature 2: Confidence level (normalized to 0 to 1)
        features.push(sentiment.confidence / 100);
        
        // Feature 3: Positive/Negative ratio
        const posNegRatio = sentiment.positiveScore / (sentiment.negativeScore + 1);
        features.push(Math.min(1, Math.log(posNegRatio + 1) / 10));
        
        // Feature 4: Total article count (normalized)
        features.push(Math.min(1, sentiment.totalArticles / 100));
        
        // Feature 5: Average relevance score
        let avgRelevance = 0;
        if (articles && articles.length > 0) {
            const totalRelevance = articles.reduce((sum, article) => {
                return sum + (article.relevanceScore || 0);
            }, 0);
            avgRelevance = totalRelevance / articles.length / 200; // Normalize
        }
        features.push(Math.min(1, avgRelevance));
        
        // Feature 6: High relevance article ratio
        const highRelevanceRatio = articles ? 
            articles.filter(a => a.relevanceScore >= 100).length / Math.max(1, articles.length) :
            0;
        features.push(highRelevanceRatio);
        
        // Feature 7: Recent articles ratio (last 3 days)
        const recentRatio = articles ? this.calculateRecentRatio(articles) : 0;
        features.push(recentRatio);
        
        // Feature 8: Sentiment volatility
        const volatility = this.calculateSentimentVolatility(articles);
        features.push(Math.min(1, volatility));
        
        return features;
    }

    /**
     * Calculate ratio of recent articles
     */
    calculateRecentRatio(articles) {
        if (!articles || articles.length === 0) return 0;
        
        const threeDaysAgo = new Date();
        threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);
        
        const recentCount = articles.filter(article => {
            if (!article.pubDate) return false;
            const pubDate = new Date(article.pubDate);
            return pubDate >= threeDaysAgo;
        }).length;
        
        return recentCount / articles.length;
    }

    /**
     * Calculate sentiment volatility
     */
    calculateSentimentVolatility(articles) {
        if (!articles || articles.length < 3) return 0;
        
        // Group articles by day
        const sentimentByDay = {};
        articles.forEach(article => {
            if (!article.pubDate) return;
            const day = new Date(article.pubDate).toISOString().split('T')[0];
            
            if (!sentimentByDay[day]) {
                sentimentByDay[day] = { positive: 0, negative: 0 };
            }
            
            // Simple sentiment detection
            const text = ((article.title || '') + ' ' + (article.contentSnippet || '')).toLowerCase();
            if (/up|gain|rise|surge|bullish|growth|profit|strong|beat|positive/.test(text)) {
                sentimentByDay[day].positive++;
            }
            if (/down|fall|drop|decline|bearish|loss|weak|miss|negative|concern/.test(text)) {
                sentimentByDay[day].negative++;
            }
        });
        
        // Calculate daily sentiment scores
        const dailyScores = Object.values(sentimentByDay).map(day => {
            return (day.positive - day.negative) / (day.positive + day.negative + 1);
        });
        
        // Calculate standard deviation as volatility measure
        if (dailyScores.length < 2) return 0;
        
        const mean = dailyScores.reduce((sum, val) => sum + val, 0) / dailyScores.length;
        const variance = dailyScores.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / dailyScores.length;
        return Math.sqrt(variance);
    }

    /**
     * Predict trend using trained ML model
     * Returns: prediction value (-1 to 1) and confidence
     */
    async predictTrend(sentiment, articles, relevancyAnalyzer) {
        if (!this.isModelLoaded || !this.model) {
            console.warn('ML model not loaded, using rule-based prediction');
            return this.ruleBasedPrediction(sentiment, articles);
        }
        
        try {
            // Extract features
            const features = this.extractFeatures(sentiment, articles, relevancyAnalyzer);
            
            // Normalize features using statistics
            const normalizedFeatures = this.normalizeFeatures(features);
            
            // Create tensor and predict
            const inputTensor = tf.tensor2d([normalizedFeatures]);
            const prediction = await this.model.predict(inputTensor);
            const predictionValue = await prediction.data();
            
            // Clean up tensors
            inputTensor.dispose();
            prediction.dispose();
            
            const trendScore = predictionValue[0];
            const confidence = Math.min(100, Math.abs(trendScore) * 100);
            
            return {
                score: trendScore,
                confidence: confidence,
                method: 'ML Model'
            };
        } catch (error) {
            console.error('ML prediction error:', error);
            return this.ruleBasedPrediction(sentiment, articles);
        }
    }

    /**
     * Normalize features using statistics
     */
    normalizeFeatures(features) {
        if (!this.featureStats) {
            // Use default normalization if no stats available
            return features;
        }
        
        return features.map((val, idx) => {
            const stats = this.featureStats[idx];
            if (stats.std === 0) return 0;
            return (val - stats.mean) / stats.std;
        });
    }

    /**
     * Fallback rule-based prediction if ML fails
     */
    ruleBasedPrediction(sentiment, articles) {
        const sentimentScore = sentiment.score / 100;
        const confidence = sentiment.confidence;
        
        return {
            score: Math.max(-1, Math.min(1, sentimentScore)),
            confidence: confidence,
            method: 'Rule-Based'
        };
    }

    /**
     * Train model with historical data (for demonstration)
     * In production, this would use actual stock price movements
     */
    async trainModelWithSampleData() {
        if (!this.isModelLoaded || !this.model) {
            console.warn('Model not initialized');
            return;
        }
        
        console.log('Training ML model with sample data...');
        
        try {
            // Generate synthetic training data based on patterns
            const syntheticData = this.generateSyntheticTrainingData();
            
            // Prepare training data
            const xs = tf.tensor2d(syntheticData.map(d => d.features));
            const ys = tf.tensor2d(syntheticData.map(d => [d.label]));
            
            // Train the model
            const history = await this.model.fit(xs, ys, {
                epochs: 50,
                batchSize: 32,
                validationSplit: 0.2,
                shuffle: true,
                verbose: 0
            });
            
            // Calculate feature statistics from training data
            this.calculateFeatureStats(syntheticData.map(d => d.features));
            
            // Clean up tensors
            xs.dispose();
            ys.dispose();
            
            console.log('Model training completed. Loss:', history.history.loss[history.history.loss.length - 1].toFixed(4));
            
            return history;
        } catch (error) {
            console.error('Training error:', error);
        }
    }

    /**
     * Generate synthetic training data based on financial patterns
     */
    generateSyntheticTrainingData() {
        const data = [];
        
        for (let i = 0; i < 500; i++) {
            // Generate realistic feature values
            const sentimentScore = (Math.random() - 0.5) * 2; // -1 to 1
            const confidence = Math.random();
            const posNegRatio = Math.random() * 2;
            const totalArticles = Math.random() * 100;
            const avgRelevance = Math.random();
            const highRelevanceRatio = Math.random();
            const recentRatio = Math.random();
            const volatility = Math.random();
            
            const features = [
                sentimentScore,
                confidence,
                Math.min(1, Math.log(posNegRatio + 1) / 10),
                Math.min(1, totalArticles / 100),
                avgRelevance,
                highRelevanceRatio,
                recentRatio,
                volatility
            ];
            
            // Generate label: trend direction influenced by sentiment
            // But with some noise (70% correlation with sentiment)
            const noise = (Math.random() - 0.5) * 0.6;
            const label = Math.max(-1, Math.min(1, sentimentScore * 0.7 + noise));
            
            data.push({ features, label });
        }
        
        return data;
    }

    /**
     * Calculate feature statistics for normalization
     */
    calculateFeatureStats(featuresArray) {
        const numFeatures = featuresArray[0].length;
        const stats = [];
        
        for (let i = 0; i < numFeatures; i++) {
            const values = featuresArray.map(f => f[i]);
            const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
            const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
            const std = Math.sqrt(variance);
            
            stats.push({ mean, std });
        }
        
        this.featureStats = stats;
    }

    /**
     * Get model information
     */
    getModelInfo() {
        if (!this.model) {
            return { loaded: false };
        }
        
        return {
            loaded: this.isModelLoaded,
            layers: this.model.layers.length,
            trainableParams: this.model.countParams()
        };
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MLForecastEngine;
}

