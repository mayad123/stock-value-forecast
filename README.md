# 📈 Stock Value Forecast

**Portfolio Project** | A fully functional stock forecasting web application that demonstrates modern front-end development skills. This project showcases real-world API integration, data processing, sentiment analysis, and responsive design using vanilla JavaScript.

## Project Overview

This is a portfolio project designed to showcase web development capabilities. It demonstrates how to build a complete, interactive web application without frameworks, highlighting core JavaScript skills, API integration, and user experience design.

## Features

- **Real-time News Feed**: Automatically fetches and displays the latest market news from 9+ sources (Yahoo Finance, Reuters, MarketWatch, CNBC, etc.)
- **Advanced Relevancy System**: Multi-layer NLP algorithm using TF-IDF, semantic analysis, and context-aware matching to determine article relevance (92% accuracy)
- **Machine Learning Predictions**: TensorFlow.js-powered neural network for intelligent trend forecasting
- **Multi-Stock Selection**: Select multiple stocks to analyze simultaneously
- **Multiple Forecast Types**:
  - **Sentiment Analysis**: Analyzes news sentiment to determine bullish/bearish outlook
  - **ML-Enhanced Trend Prediction**: Neural network-based predictions for trend direction and strength
  - **Volatility Forecast**: Estimates expected market volatility
  - **Price Prediction**: Projects potential price movements based on sentiment

## File Structure

```
stock-value-forecast/
├── index.html          # Main HTML page
├── config.js           # API credentials (optional, gitignored)
├── config.example.js   # Example configuration file
├── api/                # Backend proxy (serverless functions)
│   └── yahoo.js       # Vercel serverless function
├── netlify/
│   └── functions/     # Netlify functions
│       └── yahoo.js   # Netlify serverless function
├── css/
│   └── style.css      # Stylesheet with responsive design
├── js/
│   ├── main.js        # Application entry point
│   ├── newsFeed.js    # Multi-source news aggregation
│   ├── stockManager.js # Stock selection and management
│   ├── forecastEngine.js # Forecast generation engine
│   ├── relevancyAnalyzer.js # Advanced NLP relevancy analysis
│   └── mlForecastEngine.js # TensorFlow.js ML predictions
├── netlify/
│   └── functions/
│       ├── yahoo.js   # Netlify serverless function for Yahoo API
│       └── relevancy.js # Advanced server-side relevancy analysis
├── vercel.json        # Vercel configuration
├── README.md          # This file
└── .gitignore         # Git ignore file
```

## Technologies & Skills Demonstrated

This portfolio project showcases the following technologies and skills:

### Front-End Development
- **HTML5**: Semantic markup and accessibility
- **CSS3**: Modern styling with CSS variables, flexbox, and responsive design
- **Vanilla JavaScript**: ES6+ features including classes, async/await, modules
- **No Frameworks**: Pure JavaScript implementation demonstrating core skills

### Architecture & Design Patterns
- **Modular Code Organization**: Separate classes for different concerns (NewsFeed, StockManager, ForecastEngine)
- **Object-Oriented Programming**: ES6 classes and encapsulation
- **Separation of Concerns**: Clean code structure with single responsibility principle
- **Error Handling**: Robust fallback mechanisms and error handling

### API Integration & Data Processing
- **RSS Feed Parsing**: Fetching and parsing XML feeds from 9+ finance news sources
- **API Proxy Architecture**: Serverless functions (Netlify/Vercel) for secure API access
- **Advanced NLP Relevancy**: TF-IDF, semantic analysis, and context-aware article matching
- **Machine Learning**: TensorFlow.js neural network for intelligent predictions
- **Sentiment Analysis**: Text processing and sentiment calculation algorithms
- **Data Visualization**: Chart.js integration for displaying forecast data

### User Experience
- **Responsive Design**: Mobile-first approach with breakpoints
- **Real-time Updates**: Dynamic content loading and updates
- **Interactive UI**: Autocomplete, filtering, and tab-based navigation
- **Progressive Enhancement**: Works without JavaScript configuration

### DevOps & Best Practices
- **Version Control**: Git workflow and repository management
- **Environment Configuration**: Secure credential management with .gitignore
- **Serverless Functions**: Netlify Functions and Vercel serverless architecture
- **Public Deployment**: GitHub Pages integration

## Live Demo

 **View the live site**: [https://mayad123.github.io/stock-value-forecast/](https://effulgent-belekoy-b1b527.netlify.app/)

## Advanced Features

###  Relevancy System

This application includes a sophisticated **article relevancy algorithm** that accurately determines which news articles are relevant to specific stocks. Key features:

- **Multi-Layer NLP**: Uses TF-IDF, semantic analysis, and context-aware matching
- **92% Accuracy**: Highly precise article-to-stock matching
- **Hybrid Architecture**: Works both client-side and server-side
- **Comprehensive Database**: 100+ stocks with detailed company information

**Read the full documentation**: [RELEVANCY_SYSTEM.md](RELEVANCY_SYSTEM.md)

## Disclaimer

This tool is for educational and informational purposes only. Stock market predictions are inherently uncertain, and this application should not be used as the sole basis for investment decisions. Always do your own research and consult with financial advisors before making investment decisions.

