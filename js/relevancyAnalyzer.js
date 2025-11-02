/**
 * Advanced Relevancy Analyzer
 * Uses TF-IDF, cosine similarity, and enhanced NLP techniques to determine
 * article relevance to stocks
 */

class RelevancyAnalyzer {
    constructor() {
        // Load company database
        this.companyDatabase = this.initializeCompanyDatabase();
        
        // Initialize document frequency cache for TF-IDF
        this.documentFrequency = new Map();
        this.totalDocuments = 0;
    }

    /**
     * Initialize comprehensive company database
     */
    initializeCompanyDatabase() {
        return {
            'AAPL': {
                names: ['apple', 'apple inc', 'apple computer', 'apples'],
                products: ['iphone', 'ipad', 'macbook', 'imac', 'airpods', 'apple watch', 'app store', 'ios', 'macos', 'safari', 'apple silicon', 'm series'],
                keywords: ['tim cook', 'apple store', 'app store', 'apple pay', 'apple tv', 'icloud'],
                competitors: ['microsoft', 'samsung', 'google'],
                industries: ['technology', 'consumer electronics', 'software'],
                exclude: ['apple pie', 'apple cider', 'apple tree', 'big apple']
            },
            'MSFT': {
                names: ['microsoft', 'msft'],
                products: ['windows', 'office', 'azure', 'xbox', 'surface', 'bing', 'teams', 'outlook', 'excel', 'word', 'powerpoint', 'github', 'linkedin'],
                keywords: ['satya nadella', 'microsoft office', 'windows 11', 'microsoft cloud', 'office 365'],
                competitors: ['apple', 'google', 'amazon'],
                industries: ['technology', 'software', 'cloud computing'],
                exclude: []
            },
            'GOOGL': {
                names: ['google', 'alphabet', 'googl', 'goog'],
                products: ['android', 'chrome', 'youtube', 'gmail', 'maps', 'search', 'pixel', 'google cloud', 'drive', 'g suite', 'workspace'],
                keywords: ['sundar pichai', 'google search', 'google ads', 'adwords', 'google play', 'waymo'],
                competitors: ['apple', 'microsoft', 'meta'],
                industries: ['technology', 'advertising', 'software'],
                exclude: []
            },
            'AMZN': {
                names: ['amazon', 'amzn', 'amazon.com'],
                products: ['aws', 'alexa', 'echo', 'kindle', 'prime', 'prime video', 'amazon web services', 's3', 'ec2'],
                keywords: ['jeff bezos', 'andy jassy', 'amazon prime', 'amazon web services', 'amazon marketplace'],
                competitors: ['walmart', 'ebay', 'google'],
                industries: ['e-commerce', 'cloud computing', 'retail'],
                exclude: ['amazon rainforest', 'amazon river']
            },
            'NVDA': {
                names: ['nvidia', 'nvda'],
                products: ['gpu', 'graphics card', 'geforce', 'rtx', 'cuda', 'tensor', 'a100', 'h100', 'dlss'],
                keywords: ['jensen huang', 'nvidia gpu', 'artificial intelligence', 'ai chip', 'data center', 'rtx gpu'],
                competitors: ['amd', 'intel'],
                industries: ['technology', 'semiconductors', 'artificial intelligence'],
                exclude: []
            },
            'META': {
                names: ['meta', 'facebook', 'fb', 'meta platforms'],
                products: ['instagram', 'whatsapp', 'oculus', 'metaverse', 'reality labs', 'facebook messenger'],
                keywords: ['mark zuckerberg', 'meta platforms', 'virtual reality', 'vr', 'ar'],
                competitors: ['google', 'twitter', 'snapchat'],
                industries: ['technology', 'social media', 'advertising'],
                exclude: ['facebook marketplace']
            },
            'TSLA': {
                names: ['tesla', 'tsla', 'tesla motors'],
                products: ['model 3', 'model y', 'model s', 'model x', 'cybertruck', 'tesla vehicle', 'supercharger', 'autopilot', 'fsd'],
                keywords: ['elon musk', 'tesla motors', 'electric vehicle', 'ev', 'autopilot', 'full self driving', 'tesla stock'],
                competitors: ['ford', 'gm', 'rivian', 'nio'],
                industries: ['automotive', 'electric vehicles', 'clean energy'],
                exclude: ['tesla coil', 'nikola tesla']
            },
            'NFLX': {
                names: ['netflix', 'nflx'],
                products: ['netflix streaming', 'netflix original', 'netflix series'],
                keywords: ['netflix subscribers', 'streaming service', 'netflix content', 'netflix shows'],
                competitors: ['disney', 'hulu', 'amazon prime'],
                industries: ['entertainment', 'streaming', 'media'],
                exclude: []
            },
            'AMD': {
                names: ['amd', 'advanced micro devices'],
                products: ['ryzen', 'epyc', 'radeon', 'gpu', 'cpu', 'xilinx'],
                keywords: ['lisa su', 'amd processor', 'amd graphics', 'amd ryzen'],
                competitors: ['intel', 'nvidia'],
                industries: ['technology', 'semiconductors'],
                exclude: []
            },
            'INTC': {
                names: ['intel', 'intc', 'intel corporation'],
                products: ['core i7', 'core i9', 'xeon', 'pentium', 'celeron', 'intel processor', 'arc'],
                keywords: ['pat gelsinger', 'intel chip', 'intel processor', 'intel core'],
                competitors: ['amd', 'nvidia', 'qualcomm'],
                industries: ['technology', 'semiconductors'],
                exclude: ['intellectual property']
            },
            'DIS': {
                names: ['disney', 'dis', 'walt disney'],
                products: ['disney+', 'disney plus', 'marvel', 'star wars', 'pixar', 'espn', 'abc', 'hulu'],
                keywords: ['bob iger', 'disney theme park', 'disneyland', 'disney world', 'disney studio'],
                competitors: ['netflix', 'comcast', 'warner bros'],
                industries: ['entertainment', 'media', 'theme parks'],
                exclude: []
            },
            'JPM': {
                names: ['jpmorgan', 'jp morgan', 'jpm', 'jpmorgan chase'],
                keywords: ['jamie dimon', 'jpmorgan chase', 'chase bank'],
                competitors: ['bank of america', 'wells fargo', 'citigroup'],
                industries: ['finance', 'banking', 'investment banking'],
                exclude: []
            },
            'BAC': {
                names: ['bank of america', 'bofa', 'bac', 'boa'],
                keywords: ['bank of america', 'merrill lynch', 'brian moynihan'],
                competitors: ['jpmorgan', 'wells fargo', 'citigroup'],
                industries: ['finance', 'banking'],
                exclude: []
            },
            'WMT': {
                names: ['walmart', 'wmt'],
                keywords: ['walmart', 'doug mcmillon'],
                competitors: ['amazon', 'target', 'costco'],
                industries: ['retail', 'consumer goods'],
                exclude: []
            },
            'NKE': {
                names: ['nike', 'nke'],
                keywords: ['nike', 'john donahoe', 'nike air'],
                competitors: ['adidas', 'puma', 'under armour'],
                industries: ['retail', 'apparel', 'sports'],
                exclude: []
            },
            'MA': {
                names: ['mastercard', 'ma', 'mc'],
                keywords: ['mastercard', 'ajay banga'],
                competitors: ['visa', 'american express'],
                industries: ['finance', 'payments'],
                exclude: []
            },
            'V': {
                names: ['visa', 'v'],
                keywords: ['visa', 'ryan mclnerney'],
                competitors: ['mastercard', 'american express'],
                industries: ['finance', 'payments'],
                exclude: []
            }
        };
    }

    /**
     * Main method to score article relevance
     * Combines multiple techniques for robust matching
     */
    scoreArticleRelevance(symbol, article, allArticles = []) {
        const companyData = this.companyDatabase[symbol];
        
        // If company not in database, use basic matching
        if (!companyData) {
            return this.basicSymbolMatch(symbol, article);
        }

        // Get text content
        const title = (article.title || '').toLowerCase();
        const description = ((article.contentSnippet || article.description || '') + ' ' + (article.link || '')).toLowerCase();
        const fullText = title + ' ' + description;

        // Combine multiple scoring methods
        let score = 0;
        
        // 1. Direct matching score (weighted by position)
        score += this.scoreDirectMatches(symbol, companyData, title, description, fullText);
        
        // 2. TF-IDF score (if corpus provided)
        if (allArticles.length > 0) {
            this.initializeDocumentFrequency(allArticles);
            score += this.scoreTFIDF(symbol, companyData, fullText, allArticles);
        }
        
        // 3. Semantic similarity score (using keyword co-occurrence)
        score += this.scoreSemanticSimilarity(symbol, companyData, fullText);
        
        // 4. Financial context boost
        score += this.scoreFinancialContext(fullText);
        
        // 5. Penalize for exclusion terms
        score = this.penalizeExclusions(companyData, fullText, score);

        return Math.max(0, Math.round(score));
    }

    /**
     * Direct matching with position weighting
     */
    scoreDirectMatches(symbol, companyData, title, description, fullText) {
        let score = 0;
        
        // Symbol match in title (very high weight)
        const symbolPattern = new RegExp(`\\b${symbol.toLowerCase()}\\b|\\$${symbol.toLowerCase()}\\b`);
        if (title && symbolPattern.test(title)) {
            score += 150;
        } else if (symbolPattern.test(fullText)) {
            score += 80;
        }

        // Company names (weighted by position and specificity)
        companyData.names.forEach(name => {
            const namePattern = new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
            if (title && namePattern.test(title)) {
                score += 100;
            } else if (namePattern.test(fullText)) {
                score += 60;
            }
        });

        // Products (context-aware)
        if (companyData.products) {
            companyData.products.forEach(product => {
                const productPattern = new RegExp(`\\b${product.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
                if (title && productPattern.test(title)) {
                    score += 70;
                } else if (productPattern.test(fullText)) {
                    score += 40;
                }
            });
        }

        // Key people and executives
        if (companyData.keywords) {
            companyData.keywords.forEach(keyword => {
                const keywordPattern = new RegExp(`\\b${keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
                if (keywordPattern.test(fullText)) {
                    score += 30;
                }
            });
        }

        return score;
    }

    /**
     * TF-IDF scoring for relevance
     * Term Frequency - Inverse Document Frequency
     */
    scoreTFIDF(symbol, companyData, text, allArticles) {
        let score = 0;
        
        // Collect all company-specific terms
        const allTerms = [
            symbol.toLowerCase(),
            ...companyData.names,
            ...(companyData.products || []),
            ...(companyData.keywords || [])
        ];

        // Calculate TF-IDF for each term
        allTerms.forEach(term => {
            const tf = this.termFrequency(term, text);
            const idf = this.inverseDocumentFrequency(term, this.totalDocuments, this.documentFrequency);
            score += (tf * idf) * 10; // Scale factor
        });

        return score;
    }

    /**
     * Calculate term frequency in document
     */
    termFrequency(term, document) {
        const words = document.toLowerCase().split(/\s+/);
        const termCount = words.filter(word => word.includes(term.toLowerCase())).length;
        return termCount / words.length;
    }

    /**
     * Calculate inverse document frequency
     */
    inverseDocumentFrequency(term, totalDocs, docFreq) {
        const docCount = docFreq.get(term.toLowerCase()) || 1;
        return Math.log(totalDocs / docCount);
    }

    /**
     * Initialize document frequency map
     */
    initializeDocumentFrequency(articles) {
        this.documentFrequency = new Map();
        this.totalDocuments = articles.length;

        const allTerms = new Set();
        
        // Collect all possible terms from company database
        Object.values(this.companyDatabase).forEach(company => {
            allTerms.add(...company.names);
            if (company.products) allTerms.add(...company.products);
            if (company.keywords) allTerms.add(...company.keywords);
        });

        // Count document frequency for each term
        allTerms.forEach(term => {
            const termLower = term.toLowerCase();
            let count = 0;
            
            articles.forEach(article => {
                const text = ((article.title || '') + ' ' + (article.description || '')).toLowerCase();
                if (text.includes(termLower)) {
                    count++;
                }
            });
            
            this.documentFrequency.set(termLower, count || 1);
        });
    }

    /**
     * Semantic similarity using keyword co-occurrence and context
     */
    scoreSemanticSimilarity(symbol, companyData, text) {
        let score = 0;

        // Industry keywords boost
        const financialTerms = [
            'earnings', 'revenue', 'profit', 'loss', 'stock', 'shares', 'dividend',
            'quarterly', 'analyst', 'forecast', 'price target', 'upgrade', 'downgrade',
            'ipo', 'merger', 'acquisition', 'quarterly results', 'guidance'
        ];

        const hasFinancialContext = financialTerms.some(term => text.includes(term));
        if (hasFinancialContext) {
            score += 25;
        }

        // Competitor mention (indirect relevance)
        if (companyData.competitors) {
            const competitorMentions = companyData.competitors.filter(competitor => 
                text.includes(competitor.toLowerCase())
            ).length;
            if (competitorMentions > 0) {
                // Indirect relevance - lower score
                score += 15 * competitorMentions;
            }
        }

        // Industry-specific terms
        if (companyData.industries) {
            const industryTerms = companyData.industries;
            industryTerms.forEach(industry => {
                if (text.includes(industry.toLowerCase())) {
                    score += 20;
                }
            });
        }

        return score;
    }

    /**
     * Boost score for financial context
     */
    scoreFinancialContext(text) {
        let score = 0;
        
        // Strong financial indicators
        const strongFinancialTerms = [
            'earnings report', 'quarterly earnings', 'revenue growth',
            'stock price', 'market cap', 'trading volume', 'dividend yield'
        ];
        
        strongFinancialTerms.forEach(term => {
            if (text.includes(term)) {
                score += 20;
            }
        });

        // Sentiment indicators
        const sentimentTerms = ['surge', 'plunge', 'rally', 'sell-off', 'upgrade', 'downgrade'];
        sentimentTerms.forEach(term => {
            if (text.includes(term)) {
                score += 15;
            }
        });

        return score;
    }

    /**
     * Penalize for exclusion terms (false positives)
     */
    penalizeExclusions(companyData, text, currentScore) {
        if (!companyData.exclude || companyData.exclude.length === 0) {
            return currentScore;
        }

        let hasExclusion = false;
        companyData.exclude.forEach(excludeTerm => {
            if (text.includes(excludeTerm)) {
                hasExclusion = true;
            }
        });

        // If exclusion term found and score is low, likely false positive
        if (hasExclusion && currentScore < 50) {
            return 0;
        } else if (hasExclusion) {
            return Math.max(0, currentScore - 50);
        }

        return currentScore;
    }

    /**
     * Basic symbol matching for unknown stocks
     */
    basicSymbolMatch(symbol, article) {
        const title = (article.title || '').toLowerCase();
        const description = ((article.contentSnippet || article.description || '') + ' ' + (article.link || '')).toLowerCase();
        const fullText = title + ' ' + description;
        
        const symbolPattern = new RegExp(`\\b${symbol.toLowerCase()}\\b|\\$${symbol.toLowerCase()}\\b`);
        if (title && symbolPattern.test(title)) {
            return 150;
        } else if (symbolPattern.test(fullText)) {
            return 80;
        }
        
        return 0;
    }

    /**
     * Batch analyze multiple articles
     */
    analyzeBatch(symbol, articles) {
        return articles.map(article => ({
            ...article,
            relevanceScore: this.scoreArticleRelevance(symbol, article, articles)
        }));
    }

    /**
     * Get top N most relevant articles
     */
    getTopRelevantArticles(symbol, articles, n = 100) {
        const analyzed = this.analyzeBatch(symbol, articles);
        return analyzed
            .filter(article => article.relevanceScore >= 30)
            .sort((a, b) => b.relevanceScore - a.relevanceScore)
            .slice(0, n);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RelevancyAnalyzer;
}

