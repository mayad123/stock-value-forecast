/**
 * Netlify Function for Advanced Article Relevancy Analysis
 * 
 * This function provides server-side relevancy scoring using advanced NLP techniques
 * POST to /.netlify/functions/relevancy
 * 
 * Body: { symbol: string, articles: array }
 * Response: { scores: array of { article, relevanceScore } }
 */

exports.handler = async (event, context) => {
    // Enable CORS
    const headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'POST, OPTIONS'
    };

    if (event.httpMethod === 'OPTIONS') {
        return {
            statusCode: 200,
            headers,
            body: ''
        };
    }

    if (event.httpMethod !== 'POST') {
        return {
            statusCode: 405,
            headers,
            body: JSON.stringify({ error: 'Method not allowed' })
        };
    }

    try {
        const { symbol, articles } = JSON.parse(event.body || '{}');
        
        if (!symbol || !articles || !Array.isArray(articles)) {
            return {
                statusCode: 400,
                headers,
                body: JSON.stringify({ error: 'Invalid request. Requires symbol and articles array.' })
            };
        }

        // Perform advanced relevancy analysis
        const scores = await analyzeRelevancy(symbol, articles);
        
        return {
            statusCode: 200,
            headers: {
                ...headers,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ scores })
        };
    } catch (error) {
        console.error('Relevancy Analysis Error:', error);
        return {
            statusCode: 500,
            headers,
            body: JSON.stringify({ error: 'Internal server error' })
        };
    }
};

/**
 * Company database
 */
const COMPANY_DATABASE = {
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
    }
    // Add more as needed...
};

/**
 * Main relevancy analysis function
 */
async function analyzeRelevancy(symbol, articles) {
    const companyData = COMPANY_DATABASE[symbol.toUpperCase()];
    
    if (!companyData) {
        return articles.map(article => ({
            article,
            relevanceScore: basicMatch(symbol, article)
        }));
    }

    // Initialize document frequency for TF-IDF
    const documentFrequency = calculateDocumentFrequency(articles, COMPANY_DATABASE);
    const totalDocs = articles.length;

    return articles.map(article => {
        const title = (article.title || '').toLowerCase();
        const description = ((article.contentSnippet || article.description || '') + ' ' + (article.link || '')).toLowerCase();
        const fullText = title + ' ' + description;

        let score = 0;

        // 1. Direct matching
        score += scoreDirectMatches(symbol, companyData, title, description, fullText);

        // 2. TF-IDF scoring
        score += scoreTFIDF(symbol, companyData, fullText, totalDocs, documentFrequency);

        // 3. Semantic similarity
        score += scoreSemanticSimilarity(symbol, companyData, fullText);

        // 4. Financial context
        score += scoreFinancialContext(fullText);

        // 5. Exclusion penalty
        score = penalizeExclusions(companyData, fullText, score);

        return {
            article,
            relevanceScore: Math.max(0, Math.round(score))
        };
    });
}

/**
 * Calculate document frequency for TF-IDF
 */
function calculateDocumentFrequency(articles, companyDatabase) {
    const freq = new Map();
    
    const allTerms = new Set();
    Object.values(companyDatabase).forEach(company => {
        allTerms.add(...company.names);
        if (company.products) allTerms.add(...company.products);
        if (company.keywords) allTerms.add(...company.keywords);
    });

    allTerms.forEach(term => {
        const termLower = term.toLowerCase();
        let count = 0;
        
        articles.forEach(article => {
            const text = ((article.title || '') + ' ' + (article.description || '')).toLowerCase();
            if (text.includes(termLower)) {
                count++;
            }
        });
        
        freq.set(termLower, count || 1);
    });

    return freq;
}

/**
 * Score direct matches
 */
function scoreDirectMatches(symbol, companyData, title, description, fullText) {
    let score = 0;
    
    const symbolPattern = new RegExp(`\\b${symbol.toLowerCase()}\\b|\\$${symbol.toLowerCase()}\\b`);
    if (title && symbolPattern.test(title)) {
        score += 150;
    } else if (symbolPattern.test(fullText)) {
        score += 80;
    }

    companyData.names.forEach(name => {
        const namePattern = new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
        if (title && namePattern.test(title)) {
            score += 100;
        } else if (namePattern.test(fullText)) {
            score += 60;
        }
    });

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
 * TF-IDF scoring
 */
function scoreTFIDF(symbol, companyData, text, totalDocs, docFreq) {
    let score = 0;
    
    const allTerms = [
        symbol.toLowerCase(),
        ...companyData.names,
        ...(companyData.products || []),
        ...(companyData.keywords || [])
    ];

    allTerms.forEach(term => {
        const tf = termFrequency(term, text);
        const idf = inverseDocumentFrequency(term, totalDocs, docFreq);
        score += (tf * idf) * 10;
    });

    return score;
}

/**
 * Term frequency
 */
function termFrequency(term, document) {
    const words = document.toLowerCase().split(/\s+/);
    const termCount = words.filter(word => word.includes(term.toLowerCase())).length;
    return termCount / words.length;
}

/**
 * Inverse document frequency
 */
function inverseDocumentFrequency(term, totalDocs, docFreq) {
    const docCount = docFreq.get(term.toLowerCase()) || 1;
    return Math.log(totalDocs / docCount);
}

/**
 * Semantic similarity
 */
function scoreSemanticSimilarity(symbol, companyData, text) {
    let score = 0;

    const financialTerms = [
        'earnings', 'revenue', 'profit', 'loss', 'stock', 'shares', 'dividend',
        'quarterly', 'analyst', 'forecast', 'price target', 'upgrade', 'downgrade',
        'ipo', 'merger', 'acquisition', 'quarterly results', 'guidance'
    ];

    const hasFinancialContext = financialTerms.some(term => text.includes(term));
    if (hasFinancialContext) {
        score += 25;
    }

    if (companyData.competitors) {
        const competitorMentions = companyData.competitors.filter(competitor => 
            text.includes(competitor.toLowerCase())
        ).length;
        if (competitorMentions > 0) {
            score += 15 * competitorMentions;
        }
    }

    if (companyData.industries) {
        companyData.industries.forEach(industry => {
            if (text.includes(industry.toLowerCase())) {
                score += 20;
            }
        });
    }

    return score;
}

/**
 * Financial context
 */
function scoreFinancialContext(text) {
    let score = 0;
    
    const strongFinancialTerms = [
        'earnings report', 'quarterly earnings', 'revenue growth',
        'stock price', 'market cap', 'trading volume', 'dividend yield'
    ];
    
    strongFinancialTerms.forEach(term => {
        if (text.includes(term)) {
            score += 20;
        }
    });

    const sentimentTerms = ['surge', 'plunge', 'rally', 'sell-off', 'upgrade', 'downgrade'];
    sentimentTerms.forEach(term => {
        if (text.includes(term)) {
            score += 15;
        }
    });

    return score;
}

/**
 * Exclusion penalty
 */
function penalizeExclusions(companyData, text, currentScore) {
    if (!companyData.exclude || companyData.exclude.length === 0) {
        return currentScore;
    }

    let hasExclusion = false;
    companyData.exclude.forEach(excludeTerm => {
        if (text.includes(excludeTerm)) {
            hasExclusion = true;
        }
    });

    if (hasExclusion && currentScore < 50) {
        return 0;
    } else if (hasExclusion) {
        return Math.max(0, currentScore - 50);
    }

    return currentScore;
}

/**
 * Basic match for unknown stocks
 */
function basicMatch(symbol, article) {
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

