from dotenv import load_dotenv
load_dotenv()  ## load all the environment variables

import streamlit as st
import os
import sqlite3
import google.generativeai as genai
import pandas as pd

# Database setup
db_path = os.path.join(os.path.dirname(__file__), "badjate.db")
print("DB PATH:", db_path)
print("File exists:", os.path.exists(db_path))

## Configure Genai Key
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Model configuration for better performance
generation_config = {
    "temperature": 0.1,  # Low temperature for more deterministic SQL generation
    "top_p": 0.8,        # Nucleus sampling for focused responses
    "top_k": 40,         # Limit vocabulary for more precise SQL
    "max_output_tokens": 2048,  # Sufficient for complex SQL queries
    "response_mime_type": "text/plain",
}

# Safety settings for production use
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    }
]

## Function To Load Google Gemini Model and provide queries as response
def get_gemini_response(question, prompt, chat_history=None):
    try:
        model = genai.GenerativeModel(
            'gemini-2.5-pro',
            generation_config=generation_config,
            safety_settings=safety_settings,
            system_instruction="You are a specialized SQL query generator for stock market data analysis. You can understand context from previous queries and maintain conversation flow. Focus on generating accurate, efficient SQLite queries based on the provided schema, examples, and conversation history."
        )
        
        # Build context from chat history
        context_info = ""
        if chat_history and len(chat_history) > 0:
            context_info = "\n\nCONVERSATION CONTEXT:\n"
            
            # Include last 3 interactions for context
            recent_history = chat_history[-3:] if len(chat_history) > 3 else chat_history
            
            for i, chat in enumerate(recent_history):
                context_info += f"\nPrevious Query {i+1}:\n"
                context_info += f"User asked: {chat['question']}\n"
                context_info += f"Generated SQL: {chat['sql']}\n"
                
                if chat['success'] and len(chat['data']) > 0:
                    # Include column names and sample data for context
                    context_info += f"Results had columns: {', '.join(chat['data'].columns.tolist())}\n"
                    context_info += f"Number of records: {len(chat['data'])}\n"
                    
                    # Include key information from results
                    if 'StockName' in chat['data'].columns:
                        stocks = chat['data']['StockName'].unique()[:5]  # First 5 stocks
                        context_info += f"Stocks in results: {', '.join(stocks)}\n"
                    
                    if 'Category' in chat['data'].columns:
                        categories = chat['data']['Category'].unique()
                        context_info += f"Categories in results: {', '.join(categories)}\n"
                else:
                    context_info += "No results found\n"
        
        # Detect follow-up questions and context references
        follow_up_indicators = [
            'in this result', 'from these', 'in the above', 'from this data',
            'these stocks', 'those results', 'from them', 'in these',
            'from the previous', 'from last query', 'in that result'
        ]
        
        is_follow_up = any(indicator in question.lower() for indicator in follow_up_indicators)
        
        # Enhanced prompt for context-aware queries
        if is_follow_up and chat_history:
            context_prompt = f"""
CONTEXT-AWARE QUERY GENERATION:
The user is asking a follow-up question referring to previous results.

Previous conversation context: {context_info}

FOLLOW-UP QUESTION HANDLING RULES:
- When user says "in this result" or "from these", they refer to the LAST query's results
- When user says "these stocks", filter by StockName from the previous results
- When user says "this data", apply new analysis to the previous result set
- Use WHERE clauses to filter based on previous results when appropriate
- If they want analysis "from previous results", create a subquery or use the same filters

Current follow-up question: {question}

Generate a SQL query that considers the context of previous results.
"""
            full_prompt = f"{prompt[0]}\n{context_prompt}\n\nGenerate only the SQL query:"
        else:
            # Regular query without context
            full_prompt = f"{prompt[0]}\n\nUser Question: {question}\n\nGenerate only the SQL query without any additional text or formatting:"
        
        response = model.generate_content(full_prompt)
        
        # Clean and validate the response
        sql_query = response.text.strip()
        
        # Remove common formatting issues
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
        
        # Remove any explanatory text before or after SQL
        lines = sql_query.split('\n')
        sql_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('--') and not line.lower().startswith('this') and not line.lower().startswith('the'):
                sql_lines.append(line)
        
        final_query = ' '.join(sql_lines).strip()
        
        # Basic SQL validation
        if not final_query.upper().startswith('SELECT'):
            raise ValueError("Generated query is not a valid SELECT statement")
            
        return final_query
        
    except Exception as e:
        print(f"Error in get_gemini_response: {str(e)}")
        # Fallback to basic query if generation fails
        return "SELECT * FROM Recommendations LIMIT 10;"

## Function To retrieve query from the database
def read_sql_query(sql, db):
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        
        # Add timeout for long-running queries
        conn.execute("PRAGMA busy_timeout = 10000")
        
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        conn.commit()
        conn.close()
        
        return rows, columns
        
    except sqlite3.Error as e:
        print(f"Database error: {str(e)}")
        if 'conn' in locals():
            conn.close()
        raise e
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        if 'conn' in locals():
            conn.close()
        raise e

## Define Your Prompt
prompt=[
    """
    You are an expert in converting English questions to SQL query using sqlite3!
    The SQL database has the name badjate.db and has a table called Recommendations with the following columns:
    - OrderID INTEGER PRIMARY KEY (unique identifier for each recommendation)
    - StockName TEXT (company names like TCS, Reliance, HDFC Bank, Infosys, Maruti Suzuki, etc.)
    - BuyDate TEXT (date when stock was purchased, format: YYYY-MM-DD)
    - BuyPrice INTEGER (entry price, purchase price, cost price at which stock was bought)
    - SellDate TEXT (date when stock was sold, exit date, format: YYYY-MM-DD)
    - SellPrice INTEGER (exit price, selling price at which stock was sold)
    - Target INTEGER (target price, goal price, upside target for the stock)
    - StopLoss INTEGER (stop loss price, downside protection, risk management price)
    - Category TEXT (sector, industry - IT, Banking, Energy, Auto, Telecom, FMCG, Retail)

    IMPORTANT TERMINOLOGY MAPPING:
    - "profit/loss", "gain/loss", "returns", "performance" → calculate (SellPrice - BuyPrice)
    - "profitable", "winners", "gainers" → WHERE SellPrice > BuyPrice
    - "loss-making", "losers", "red" → WHERE SellPrice < BuyPrice
    - "breakeven" → WHERE SellPrice = BuyPrice
    - "held", "holding period", "duration" → calculate difference between BuyDate and SellDate
    - "sector", "industry", "space" → Category column
    - "IT stocks", "tech stocks", "technology" → WHERE Category = 'IT'
    - "bank stocks", "financial", "BFSI" → WHERE Category = 'Banking'
    - "oil stocks", "energy sector" → WHERE Category = 'Energy'
    - "auto stocks", "automobile" → WHERE Category = 'Auto'
    - "telecom stocks", "telco" → WHERE Category = 'Telecom'
    - "FMCG stocks", "consumer goods" → WHERE Category = 'FMCG'
    - "retail stocks" → WHERE Category = 'Retail'
    - "entry price", "cost", "purchase price" → BuyPrice
    - "exit price", "selling price" → SellPrice
    - "upside", "target", "goal" → Target
    - "downside protection", "stop", "risk limit" → StopLoss
    - "recent", "latest", "new" → ORDER BY BuyDate DESC or SellDate DESC
    - "old", "earlier", "past" → ORDER BY BuyDate ASC or SellDate ASC
    - "high", "expensive", "top" → ORDER BY [relevant column] DESC
    - "low", "cheap", "bottom" → ORDER BY [relevant column] ASC
    - "best performing", "top gainers" → ORDER BY (SellPrice - BuyPrice) DESC
    - "worst performing", "top losers" → ORDER BY (SellPrice - BuyPrice) ASC
    - "percentage return", "ROI", "return %" → calculate ((SellPrice - BuyPrice) * 100.0 / BuyPrice)
    - "risk-reward ratio" → calculate (Target - BuyPrice) / (BuyPrice - StopLoss)
    - "average", "mean" → use AVG() function
    - "total", "sum" → use SUM() function
    - "count", "number of", "how many" → use COUNT() function
    - "maximum", "highest", "peak" → use MAX() function
    - "minimum", "lowest", "bottom" → use MIN() function

    EXAMPLE QUERIES:
    1. "Which stock has the highest target?" → SELECT StockName FROM Recommendations ORDER BY Target DESC LIMIT 1;
    2. "Show all IT stocks" → SELECT * FROM Recommendations WHERE Category = 'IT';
    3. "Which stocks made profit?" → SELECT StockName, (SellPrice - BuyPrice) as Profit FROM Recommendations WHERE SellPrice > BuyPrice;
    4. "What's the average return in banking sector?" → SELECT AVG(SellPrice - BuyPrice) as AvgReturn FROM Recommendations WHERE Category = 'Banking';
    5. "Show top 3 gainers" → SELECT StockName, (SellPrice - BuyPrice) as Profit FROM Recommendations ORDER BY (SellPrice - BuyPrice) DESC LIMIT 3;
    6. "Which stocks hit their targets?" → SELECT StockName FROM Recommendations WHERE SellPrice >= Target;
    7. "Show loss-making energy stocks" → SELECT * FROM Recommendations WHERE Category = 'Energy' AND SellPrice < BuyPrice;
    8. "What's the percentage return of TCS?" → SELECT ((SellPrice - BuyPrice) * 100.0 / BuyPrice) as ReturnPercent FROM Recommendations WHERE StockName = 'TCS';
    9. "Show recent purchases" → SELECT * FROM Recommendations ORDER BY BuyDate DESC LIMIT 5;
    10. "Which stocks have high risk-reward ratio?" → SELECT StockName, ((Target - BuyPrice) * 1.0 / (BuyPrice - StopLoss)) as RiskReward FROM Recommendations ORDER BY RiskReward DESC;

    COMPLEX EXAMPLE QUERIES:
    11. "Show sector-wise average returns with stock count" → SELECT Category, AVG(SellPrice - BuyPrice) as AvgReturn, COUNT(*) as StockCount FROM Recommendations GROUP BY Category ORDER BY AvgReturn DESC;
    12. "Which sector has the highest total profit?" → SELECT Category, SUM(SellPrice - BuyPrice) as TotalProfit FROM Recommendations GROUP BY Category ORDER BY TotalProfit DESC LIMIT 1;
    13. "Show stocks with returns above sector average" → SELECT r1.StockName, r1.Category, (r1.SellPrice - r1.BuyPrice) as Return FROM Recommendations r1 WHERE (r1.SellPrice - r1.BuyPrice) > (SELECT AVG(r2.SellPrice - r2.BuyPrice) FROM Recommendations r2 WHERE r2.Category = r1.Category);
    14. "Find stocks bought in July 2025 with profit above 100" → SELECT StockName, BuyDate, (SellPrice - BuyPrice) as Profit FROM Recommendations WHERE BuyDate LIKE '2025-07%' AND (SellPrice - BuyPrice) > 100;
    15. "Show month-wise trading performance" → SELECT substr(BuyDate, 1, 7) as Month, COUNT(*) as Trades, AVG(SellPrice - BuyPrice) as AvgReturn, SUM(SellPrice - BuyPrice) as TotalReturn FROM Recommendations GROUP BY substr(BuyDate, 1, 7) ORDER BY Month;
    16. "Which stocks exceeded their target by more than 5%?" → SELECT StockName, Target, SellPrice, ((SellPrice - Target) * 100.0 / Target) as ExcessPercent FROM Recommendations WHERE SellPrice > Target AND ((SellPrice - Target) * 100.0 / Target) > 5;
    17. "Show stocks with holding period longer than 15 days" → SELECT StockName, BuyDate, SellDate, (julianday(SellDate) - julianday(BuyDate)) as HoldingDays FROM Recommendations WHERE (julianday(SellDate) - julianday(BuyDate)) > 15;
    18. "Find underperforming stocks in each sector" → SELECT Category, StockName, (SellPrice - BuyPrice) as Return FROM Recommendations r1 WHERE (SellPrice - BuyPrice) = (SELECT MIN(r2.SellPrice - r2.BuyPrice) FROM Recommendations r2 WHERE r2.Category = r1.Category) ORDER BY Category;
    19. "Show risk analysis: stocks that hit stop loss" → SELECT StockName, Category, BuyPrice, StopLoss, SellPrice, 'Hit Stop Loss' as Status FROM Recommendations WHERE SellPrice <= StopLoss;
    20. "Calculate portfolio performance metrics" → SELECT COUNT(*) as TotalTrades, SUM(CASE WHEN SellPrice > BuyPrice THEN 1 ELSE 0 END) as WinningTrades, (SUM(CASE WHEN SellPrice > BuyPrice THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) as WinRate, AVG(SellPrice - BuyPrice) as AvgReturn, SUM(SellPrice - BuyPrice) as TotalReturn FROM Recommendations;
    21. "Show best and worst stock in each category" → SELECT Category, MAX(SellPrice - BuyPrice) as BestReturn, MIN(SellPrice - BuyPrice) as WorstReturn FROM Recommendations GROUP BY Category;
    22. "Find stocks with target-to-buy ratio above 1.2" → SELECT StockName, BuyPrice, Target, (Target * 1.0 / BuyPrice) as TargetRatio FROM Recommendations WHERE (Target * 1.0 / BuyPrice) > 1.2 ORDER BY TargetRatio DESC;
    23. "Show quarterly performance breakdown" → SELECT CASE WHEN substr(BuyDate, 6, 2) IN ('01','02','03') THEN 'Q1' WHEN substr(BuyDate, 6, 2) IN ('04','05','06') THEN 'Q2' WHEN substr(BuyDate, 6, 2) IN ('07','08','09') THEN 'Q3' ELSE 'Q4' END as Quarter, COUNT(*) as Trades, AVG(SellPrice - BuyPrice) as AvgReturn FROM Recommendations GROUP BY Quarter ORDER BY Quarter;
    24. "Find stocks with maximum downside protection" → SELECT StockName, BuyPrice, StopLoss, ((BuyPrice - StopLoss) * 100.0 / BuyPrice) as DownsideProtection FROM Recommendations ORDER BY DownsideProtection DESC;
    25. "Show correlation between buy price and returns" → SELECT CASE WHEN BuyPrice < 1000 THEN 'Low Price' WHEN BuyPrice BETWEEN 1000 AND 3000 THEN 'Mid Price' ELSE 'High Price' END as PriceRange, AVG(SellPrice - BuyPrice) as AvgReturn, COUNT(*) as Count FROM Recommendations GROUP BY PriceRange ORDER BY AvgReturn DESC;

    INSTRUCTIONS:
    - CRITICAL: Always return ONLY valid SQLite queries without any additional text, explanations, or formatting
    - Use exact column names from the schema: OrderID, StockName, BuyDate, BuyPrice, SellDate, SellPrice, Target, StopLoss, Category
    - Handle case-insensitive stock names using UPPER() or LOWER() functions
    - For date comparisons, use string comparison (dates are in YYYY-MM-DD format)
    - When calculating percentages, multiply by 100.0 to avoid integer division
    - Use appropriate aggregate functions (SUM, AVG, COUNT, MAX, MIN) when needed
    - Include ORDER BY and LIMIT when asking for "top", "best", "worst", etc.
    - NEVER include ```, 'sql', or any markdown formatting in the output
    - Handle variations in stock market terminology gracefully
    - Return only the SQL statement, nothing else

    ADVANCED INSTRUCTIONS FOR CONTEXTUAL UNDERSTANDING:

    1. QUESTION INTERPRETATION RULES:
    - If user asks about "performance" without specifying, calculate (SellPrice - BuyPrice)
    - If user mentions "portfolio", aggregate data across all stocks
    - When user says "my stocks" or "our recommendations", refer to all records in the table
    - If user asks about "recent" without timeframe, use last 30 days or ORDER BY date DESC
    - When user asks "which is better", provide comparative analysis with ORDER BY
    - If user mentions percentages without context, assume they want percentage returns
    - When user asks about "risk", consider StopLoss and calculate risk metrics
    - If user mentions "growth" or "appreciation", focus on positive returns

    2. CONTEXT-AWARE FOLLOW-UP HANDLING:
    - "in this result", "from these", "in the above" → Filter by previous query results
    - "these stocks", "those stocks" → Use StockName from previous results  
    - "from this data", "in that result" → Apply new analysis to previous result set
    - "show me more details" → Expand on previous query with additional columns
    - "what about the others" → Show complement of previous results (opposite filter)
    - "filter this by" → Add WHERE clause to previous query
    - "sort this by" → Add ORDER BY to previous query
    - "group this by" → Add GROUP BY to previous query
    - "calculate average for these" → Apply AVG() to previous result set

    3. IMPLICIT QUERY HANDLING:
    - "How are we doing?" → Portfolio performance summary with win rate, total returns
    - "Show me the winners" → Stocks with SellPrice > BuyPrice, ordered by profit
    - "What about the losers?" → Stocks with SellPrice < BuyPrice, ordered by loss
    - "Any good IT picks?" → IT category stocks with positive returns
    - "How's the market treating us?" → Overall performance across all categories
    - "Show me some numbers" → Key portfolio metrics and statistics
    - "What's working?" → Top performing stocks/sectors
    - "What's not working?" → Underperforming stocks/sectors
    - "Give me insights" → Comprehensive analysis with multiple metrics

    4. CONTEXT INFERENCE RULES:
    - If previous context mentioned a sector, continue with that sector unless specified otherwise
    - When user asks follow-up questions, maintain the scope of previous query
    - If user asks about "them" or "these", refer to results from previous context
    - When user says "compare", provide side-by-side analysis with relevant metrics
    - If user mentions timeframes (month, quarter, year), filter accordingly
    - When referencing "previous results", use subqueries or similar filters

    4. SMART DEFAULTS:
    - When user asks for "best" without metric, use profit/return as default
    - If user asks for "analysis" without specifics, provide multi-dimensional view
    - When user asks about "stocks" generally, show top performers unless context suggests otherwise
    - If no limit specified for listing queries, default to TOP 10 or meaningful subset
    - When user asks about trends, include time-based analysis

    5. ERROR HANDLING & FALLBACKS:
    - If stock name is misspelled, use LIKE operator with wildcards
    - If user mentions non-existent categories, suggest closest match or show all categories
    - When calculations might result in division by zero, add safety checks
    - If date formats are unclear, assume standard YYYY-MM-DD format

    6. RESPONSE OPTIMIZATION:
    - For summary questions, use GROUP BY to provide categorical breakdowns
    - For comparison questions, include multiple relevant columns
    - For trend questions, include time-based ordering
    - For performance questions, include both absolute and percentage metrics
    - For risk questions, include both upside (Target) and downside (StopLoss) analysis

    7. BUSINESS CONTEXT AWARENESS:
    - "Diversification" queries → Show category-wise distribution
    - "Risk management" queries → Focus on StopLoss and risk-reward ratios
    - "Portfolio optimization" → Show best/worst performers across categories
    - "Market timing" → Include date-based analysis
    - "Sector rotation" → Compare performance across different categories
    - "Value investing" → Focus on stocks with good risk-reward ratios
    - "Growth investing" → Focus on stocks with high returns and targets

    8. NATURAL LANGUAGE PROCESSING GUIDELINES:
    - Extract intent from conversational language
    - Recognize financial jargon and map to appropriate database fields
    - Handle superlatives (best, worst, highest, lowest) with appropriate sorting
    - Process temporal references (yesterday, last week, recent, old) into date filters
    - Understand comparative language (better than, worse than, similar to)
    - Recognize aggregation requests (total, average, summary, overview)

    9. QUERY COMPLEXITY ADAPTATION:
    - For simple questions, provide straightforward SELECT statements
    - For analytical questions, use subqueries and complex calculations
    - For comparative questions, use JOINs or correlated subqueries
    - For trend questions, incorporate date functions and time-based grouping
    - For statistical questions, use appropriate aggregate functions

    10. OUTPUT FORMATTING GUIDELINES:
    - Include descriptive column aliases for calculated fields
    - Order results logically (best to worst, recent to old, etc.)
    - Limit results appropriately to avoid overwhelming output
    - Include relevant context columns for better interpretation
    - Use appropriate data types in calculations (use 1.0 for float division)
    """
]

## Streamlit App
st.set_page_config(
    page_title="📈 Badjate Stock Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional green styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1b5e20 0%, #2e7d32 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2e7d32;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 0.5rem 0;
    }
    .query-container {
        background: #f1f8e9;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #c8e6c9;
        margin: 1rem 0;
    }
    .stButton > button {
        background: linear-gradient(90deg, #2e7d32 0%, #1b5e20 100%);
        color: white;
        border: none;
        padding: 0.5rem 2rem;
        border-radius: 5px;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        box-shadow: 0 4px 8px rgba(46, 125, 50, 0.3);
        transform: translateY(-2px);
    }
    .sidebar-content {
        background: #f1f8e9;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>📊 Badjate Stock Analytics Dashboard</h1>
    <p style="font-size: 1.2rem; margin: 0;">AI-Powered Stock Recommendations Analysis</p>
</div>
""", unsafe_allow_html=True)

# Initialize chat history
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'query_counter' not in st.session_state:
    st.session_state.query_counter = 0

# Sidebar with quick stats and sample queries
with st.sidebar:
    st.markdown("### 📋 Quick Portfolio Stats")
    
    # Get some quick stats from the database
    try:
        conn = sqlite3.connect(db_path)
        
        # Total trades
        total_trades = pd.read_sql_query("SELECT COUNT(*) as count FROM Recommendations", conn).iloc[0]['count']
        
        # Profitable trades
        profitable_trades = pd.read_sql_query("SELECT COUNT(*) as count FROM Recommendations WHERE SellPrice > BuyPrice", conn).iloc[0]['count']
        
        # Total profit/loss
        total_pnl = pd.read_sql_query("SELECT SUM(SellPrice - BuyPrice) as total FROM Recommendations", conn).iloc[0]['total']
        
        # Win rate
        win_rate = (profitable_trades / total_trades) * 100 if total_trades > 0 else 0
        
        # Get available categories dynamically
        categories_df = pd.read_sql_query("SELECT DISTINCT Category FROM Recommendations ORDER BY Category", conn)
        available_categories = categories_df['Category'].tolist()
        
        conn.close()
        
        # Display metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Trades", total_trades)
            st.metric("Win Rate", f"{win_rate:.1f}%")
        with col2:
            st.metric("Profitable", profitable_trades)
            st.metric("Total P&L", f"₹{total_pnl:,}")
            
    except Exception as e:
        st.warning("Database connection issue")
        available_categories = []
    
    st.markdown("---")
    
    st.markdown("### 💡 Sample Queries")
    
    # Base sample queries
    sample_queries = [
        "Show me top 5 gainers",
        "What's our portfolio performance?",
        "Show sector-wise returns",
        "Which stocks hit their targets?",
        "Show me recent trades",
        "What's the average return?",
        "Which stocks have high risk-reward?"
    ]
    
    # Add dynamic category-based queries if categories are available
    if available_categories:
        # Add category-specific queries for first few categories
        for i, category in enumerate(available_categories[:3]):  # Show first 3 categories
            sample_queries.insert(1 + i, f"Which {category} stocks made profit?")
    
    # Add context-aware sample queries if there's chat history
    if st.session_state.chat_history:
        context_queries = [
            "Show me more details about these",
            "What's the average return for these?",
            "Filter these by profit > 100",
            "Sort these by performance",
            "Group these by sector"
        ]
        sample_queries.extend(context_queries)
    
    for query in sample_queries:
        if st.button(query, key=f"sample_{query}", use_container_width=True):
            st.session_state.selected_query = query
    
    st.markdown("---")
    
    # Dynamic categories section
    if available_categories:
        st.markdown("### 📊 Available Categories")
        
        # Get category counts for better display
        try:
            conn = sqlite3.connect(db_path)
            category_counts = pd.read_sql_query("""
                SELECT Category, COUNT(*) as count 
                FROM Recommendations 
                GROUP BY Category 
                ORDER BY count DESC, Category
            """, conn)
            conn.close()
            
            for _, row in category_counts.iterrows():
                category = row['Category']
                count = row['count']
                st.markdown(f"• **{category}** - {count} stocks")
                
        except Exception as e:
            # Fallback to simple list if query fails
            for category in available_categories:
                st.markdown(f"• **{category}**")
    else:
        st.markdown("### 📊 Available Categories")
        st.markdown("*No categories found in database*")

# Main content area
# Display chat history first
if st.session_state.chat_history:
    st.markdown("### 💬 Chat History")
    
    for i, chat in enumerate(st.session_state.chat_history):
        with st.container():
            # User question
            st.markdown(f"""
            <div style='padding: 0.5rem 0; margin: 0.5rem 0;'>
                <strong>🙋‍♂️ You asked:</strong> {chat['question']}
                <div style='font-size: 0.8rem; color: #666; margin-top: 0.3rem;'>⏰ {chat['timestamp']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Results
            if chat['success']:
                if len(chat['data']) > 0:
                    st.markdown(f"**📊 Results:** {len(chat['data'])} records found")
                    
                    # Create tabs for table view and SQL query
                    tab1, tab2 = st.tabs(["📋 Results Table", "🔍 SQL Query"])
                    
                    with tab1:
                        st.dataframe(
                            chat['data'], 
                            use_container_width=True, 
                            hide_index=True,
                            key=f"df_history_{i}"
                        )
                        
                        # Show summary metrics if available
                        if len(chat['data']) > 0:
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("📈 Records", len(chat['data']))
                            with col2:
                                if any('profit' in col.lower() or 'return' in col.lower() for col in chat['data'].columns):
                                    profit_cols = [col for col in chat['data'].columns if 'profit' in col.lower() or 'return' in col.lower()]
                                    if profit_cols:
                                        numeric_col = chat['data'][profit_cols[0]].astype(str).str.replace('₹', '').str.replace(',', '')
                                        try:
                                            avg_return = pd.to_numeric(numeric_col, errors='coerce').mean()
                                            st.metric("💰 Avg Return", f"₹{avg_return:,.0f}" if not pd.isna(avg_return) else "N/A")
                                        except:
                                            st.metric("💰 Avg Return", "N/A")
                            with col3:
                                if 'Category' in chat['data'].columns:
                                    st.metric("🏢 Sectors", chat['data']['Category'].nunique())
                                elif 'StockName' in chat['data'].columns:
                                    st.metric("📊 Stocks", chat['data']['StockName'].nunique())
                    
                    with tab2:
                        st.code(chat['sql'], language="sql")
                else:
                    st.warning("🔍 No results found for this query.")
            else:
                st.error(f"❌ Error: {chat['error']}")
                if 'sql' in chat:
                    with st.expander("🔧 View SQL Query"):
                        st.code(chat['sql'], language="sql")
            
            st.markdown("---")

col1, col2 = st.columns([3, 1])

with col1:
    st.markdown("### 🔍 Ask Your Question")
    
    # Check if sample query was clicked
    default_value = ""
    if 'selected_query' in st.session_state:
        default_value = st.session_state.selected_query
        del st.session_state.selected_query
    
    # Dynamic placeholder text based on available categories
    if 'available_categories' in locals() and available_categories:
        first_category = available_categories[0]
        placeholder_text = f"e.g., Show me the best performing stocks in {first_category} sector"
    else:
        placeholder_text = "e.g., Show me the best performing stocks"
    
    question = st.text_input(
        "Type your question here:",
        value=default_value,
        placeholder=placeholder_text,
        key=f"input_{st.session_state.query_counter}",
        help="Ask about stock performance, sectors, profits, losses, or any analysis you need"
    )
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
    
    with col_btn1:
        submit = st.button("🚀 Analyze", type="primary")
    
    with col_btn2:
        clear_history = st.button("🗑️ Clear")
        if clear_history:
            st.session_state.chat_history = []
            st.session_state.query_counter += 1
            st.rerun()

with col2:
    st.markdown("### 🎯 Tips")
    
    # Show different tips based on whether there's chat history
    if st.session_state.chat_history:
        st.info("""
        **Follow-up Questions:**
        • "Show me more details about these"
        • "What's the average for these stocks?"
        • "Filter these by profit > 100"
        • "Sort these by performance"
        • "Group these by sector"
        
        **Context Keywords:**
        • "in this result" • "from these"
        • "these stocks" • "from the above"
        """)
    else:
        # Dynamic tips based on available categories
        tip_text = """
        **Try asking:**
        • Portfolio performance
        • Sector comparisons  
        • Risk analysis
        • Profit/loss breakdown
        • Date-based queries
        """
        
        if 'available_categories' in locals() and available_categories:
            tip_text += f"\n**Available sectors:** {', '.join(available_categories[:3])}{'...' if len(available_categories) > 3 else ''}"
        
        st.info(tip_text)
    
    # Show conversation stats if there's history
    if st.session_state.chat_history:
        st.markdown("### 📊 Conversation Stats")
        total_queries = len(st.session_state.chat_history)
        successful_queries = sum(1 for chat in st.session_state.chat_history if chat['success'])
        
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            st.metric("Total Queries", total_queries)
        with col_stat2:
            st.metric("Success Rate", f"{(successful_queries/total_queries)*100:.0f}%" if total_queries > 0 else "0%")

# Results section - Process new query
if submit and question:
    with st.spinner("🔄 Analyzing your query..."):
        try:
            # Add query processing indicator
            progress_bar = st.progress(0)
            progress_bar.progress(25, "🤖 Generating SQL query...")
            
            # Pass chat history for context
            response = get_gemini_response(question, prompt, st.session_state.chat_history)
            sql = response.strip()
            
            progress_bar.progress(50, "🔍 Validating query...")
            
            # Additional query validation
            if not sql or len(sql.strip()) < 10:
                raise ValueError("Generated query is too short or empty")
            
            progress_bar.progress(75, "📊 Executing query...")
            
            # Execute the query
            result, columns = read_sql_query(sql, "badjate.db")
            
            progress_bar.progress(100, "✅ Complete!")
            progress_bar.empty()
            
            if result and columns:
                # Convert to DataFrame for better display
                df = pd.DataFrame(result, columns=columns)
                
                # Format numeric columns for better display
                for col in df.columns:
                    if df[col].dtype in ['int64', 'float64'] and col.lower() not in ['orderid']:
                        if 'price' in col.lower() or 'target' in col.lower() or 'stoploss' in col.lower():
                            df[col] = df[col].apply(lambda x: f"₹{x:,}" if pd.notnull(x) else "")
                        elif 'percent' in col.lower() or 'rate' in col.lower():
                            df[col] = df[col].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "")
                        elif 'profit' in col.lower() or 'return' in col.lower() or 'pnl' in col.lower():
                            df[col] = df[col].apply(lambda x: f"₹{x:,}" if pd.notnull(x) else "")
                
                # Add to chat history
                chat_entry = {
                    'question': question,
                    'sql': sql,
                    'data': df,
                    'success': True,
                    'timestamp': pd.Timestamp.now().strftime("%H:%M:%S")
                }
                st.session_state.chat_history.append(chat_entry)
                
                # Show success message
                st.success(f"✅ Query processed successfully! Found {len(df)} records.")
                
            else:
                # Add failed query to chat history
                chat_entry = {
                    'question': question,
                    'sql': sql,
                    'data': pd.DataFrame(),
                    'success': True,
                    'timestamp': pd.Timestamp.now().strftime("%H:%M:%S")
                }
                st.session_state.chat_history.append(chat_entry)
                st.warning("� No results found for your query.")
                
        except Exception as e:
            if 'progress_bar' in locals():
                progress_bar.empty()
                
            # Add error to chat history
            chat_entry = {
                'question': question,
                'sql': sql if 'sql' in locals() else "Error generating SQL",
                'error': str(e),
                'success': False,
                'timestamp': pd.Timestamp.now().strftime("%H:%M:%S")
            }
            st.session_state.chat_history.append(chat_entry)
            st.error(f"❌ Error processing your query: {str(e)}")
        
        # Update query counter and rerun to show updated history
        st.session_state.query_counter += 1
        
        # Auto-scroll to bottom after new message
        st.markdown("""
        <script>
        window.scrollTo(0, document.body.scrollHeight);
        </script>
        """, unsafe_allow_html=True)
        
        st.rerun()

elif submit and not question:
    st.warning("⚠️ Please enter a question to analyze.")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p>📈 <strong>Badjate Stock Analytics</strong> | Powered by Next Bigg Tech</p>
    <p style='font-size: 0.8rem;'>Ask intelligent questions about your stock portfolio and get instant insights</p>
</div>
""", unsafe_allow_html=True)