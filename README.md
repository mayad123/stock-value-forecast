# 📈 Stock Value Forecast

Live at: `https://mayad123.github.io/stock-value-forecast/`

A GitHub Pages project showcasing a stock forecasting web application that integrates Yahoo Finance news feed and provides multiple forecast options based on sentiment analysis. This project demonstrates front-end web development skills including HTML5, CSS3, and vanilla JavaScript.

## Features

- **Real-time News Feed**: Automatically fetches and displays the latest market news from Yahoo Finance
- **Multi-Stock Selection**: Select multiple stocks to analyze simultaneously
- **Multiple Forecast Types**:
  - **Sentiment Analysis**: Analyzes news sentiment to determine bullish/bearish outlook
  - **Trend Prediction**: Predicts stock trend direction and strength
  - **Volatility Forecast**: Estimates expected market volatility
  - **Price Prediction**: Projects potential price movements based on sentiment

## File Structure

```
stock-value-forecast/
├── index.html          # Main HTML page
├── css/
│   └── style.css      # Stylesheet with responsive design
├── js/
│   ├── main.js        # Application entry point
│   ├── newsFeed.js    # Yahoo Finance news feed integration
│   ├── stockManager.js # Stock selection and management
│   └── forecastEngine.js # Forecast generation engine
├── README.md          # This file
└── .gitignore         # Git ignore file
```

## Portfolio Project

This is a portfolio project demonstrating:
- **Front-end Development**: Clean, semantic HTML5 structure
- **Responsive Design**: Modern CSS with CSS variables and mobile-first approach
- **JavaScript Architecture**: Modular code organization with ES6 classes
- **API Integration**: Fetching and parsing RSS feeds from Yahoo Finance
- **Data Processing**: Sentiment analysis and forecast generation algorithms
- **User Experience**: Interactive UI with real-time feedback and animations

## Live Demo

🌐 **View the live site**: [https://mayad123.github.io/stock-value-forecast/](https://mayad123.github.io/stock-value-forecast/)

## Setup Instructions

### Local Development

1. Clone the repository:
   ```bash
   git clone https://github.com/mayad123/stock-value-forecast.git
   cd stock-value-forecast
   ```

2. Open `index.html` in your browser, or use a local server:
   ```bash
   # Using Python
   python -m http.server 8000
   
   # Using Node.js (with http-server)
   npx http-server
   ```

### GitHub Pages Deployment

1. Push your code to GitHub:
   ```bash
   git add .
   git commit -m "Initial commit: Stock Value Forecast"
   git remote add origin https://github.com/mayad123/stock-value-forecast.git
   git push -u origin main
   ```

2. Go to your repository settings on GitHub
3. Navigate to "Pages" in the left sidebar
4. Under "Source", select "Deploy from a branch"
5. Choose the `main` branch and `/ (root)` folder
6. Click "Save"


## Notes

- The forecast engine uses sentiment analysis based on news articles
- This is a portfolio/demonstration project for educational purposes
- Forecasts are based on sentiment analysis and should not be considered financial advice

## Disclaimer

This tool is for educational and informational purposes only. Stock market predictions are inherently uncertain, and this application should not be used as the sole basis for investment decisions. Always do your own research and consult with financial advisors before making investment decisions.

