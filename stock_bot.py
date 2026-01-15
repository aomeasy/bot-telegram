import os
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- ส่วนที่ 1: การตั้งค่า Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ส่วนที่ 2: ดึงค่า Config จาก Environment Variables ---
# แนะนำให้ตั้งค่าเหล่านี้ใน Render Dashboard -> Environment
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8336478185:AAF_OO9dQj4vjCictaD-aWoWWUGdi6vv_lY")
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "YOUR_API_KEY_HERE")
# URL ของแอปคุณบน Render (เช่น https://bot-telegram-vfmz.onrender.com)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") 

# --- ส่วนที่ 3: Stock Logic (คงเดิมตามที่คุณเขียนไว้) ---

def fetch_stock_data(symbol):
    try:
        url = f"https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": ALPHA_VANTAGE_KEY
        }
        logger.info(f"🔄 Fetching data for {symbol}...")
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if "Error Message" in data: return None
        if "Note" in data: return None, "rate_limit"
        if "Time Series (Daily)" not in data: return None
        
        df = pd.DataFrame.from_dict(data["Time Series (Daily)"], orient='index')
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        for col in df.columns:
            df[col] = df[col].astype(float)
        return df.last('180D')
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return None

def calculate_rsi(prices, period=14):
    try:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 0.0001)
        return (100 - (100 / (1 + rs))).iloc[-1]
    except: return 50

def calculate_macd(prices):
    try:
        exp1 = prices.ewm(span=12, adjust=False).mean()
        exp2 = prices.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd.iloc[-1], signal.iloc[-1]
    except: return 0, 0

def calculate_bollinger_bands(prices, period=20):
    try:
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        return (sma - (std * 2)).iloc[-1], (sma + (std * 2)).iloc[-1]
    except:
        p = prices.iloc[-1]
        return p * 0.95, p * 1.05

def calculate_ema(prices, period):
    try: return prices.ewm(span=period, adjust=False).mean().iloc[-1]
    except: return prices.iloc[-1]

def get_stock_analysis(symbol):
    try:
        df = fetch_stock_data(symbol)
        if df is None: return None
        if isinstance(df, tuple) and df[1] == "rate_limit": return "rate_limit"
        if len(df) < 50: return None
        
        prices = df['Close']
        current_price = prices.iloc[-1]
        prev_close = prices.iloc[-2]
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100
        
        rsi = calculate_rsi(prices)
        macd, signal = calculate_macd(prices)
        bb_lower, bb_upper = calculate_bollinger_bands(prices)
        ema_20, ema_50, ema_200 = calculate_ema(prices, 20), calculate_ema(prices, 50), calculate_ema(prices, 200)
        
        rsi_signal = "💚 Oversold (ซื้อ)" if rsi <= 30 else "❤️ Overbought (ขาย)" if rsi >= 70 else "⚪ Neutral"
        macd_signal = "🟢 Bullish" if macd > signal else "🔴 Bearish"
        price_trend = "📈 Uptrend" if current_price > ema_20 > ema_50 else "📉 Downtrend" if current_price < ema_20 < ema_50 else "➡️ Sideways"
        volume_trend = "📊 Increasing" if df['Volume'].iloc[-5:].mean() > df['Volume'].iloc[-10:-5].mean() else "📉 Decreasing"
        
        return f"""📊 **{symbol.upper()} Analysis**

💰 **ราคาปัจจุบัน:** ${current_price:.2f}
{"🟢" if change >= 0 else "🔴"} เปลี่ยนแปลง: ${change:+.2f} ({change_pct:+.2f}%)

📈 **โมเมนตัมและเทรนด์:**
• แนวโน้ม: {price_trend}
• RSI (14): {rsi:.1f} {rsi_signal}
• MACD: {macd_signal}
• Volume: {volume_trend}

📊 **ราคาเฉลี่ยเคลื่อนที่:**
• EMA 20: ${ema_20:.2f}
• EMA 50: ${ema_50:.2f}
• EMA 200: ${ema_200:.2f}

🎯 **Bollinger Bands (20):**
• Upper: ${bb_upper:.2f}
• Lower: ${bb_lower:.2f}
• ราคาอยู่ที่: {((current_price - bb_lower) / (bb_upper - bb_lower) * 100):.0f}% ของแบนด์

🛡️ **แนวรับ/แนวต้าน:**
• Support: ${bb_lower:.2f}
• Resistance: ${bb_upper:.2f}

⏰ อัพเดท: {datetime.now().strftime('%H:%M:%S')}

⚠️ *ข้อมูลนี้เพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำการลงทุน*"""
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return None

# --- ส่วนที่ 4: Telegram Handlers (คงเดิมตามที่คุณเขียนไว้) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """🤖 **ยินดีต้อนรับสู่ Stock Analysis Bot!** 📈\n\n💡 **วิธีใช้งาน:**\n• พิมพ์ชื่อหุ้น เช่น: AAPL, MSFT\n• /help - ดูคำแนะนำ\n\n✨ ข้อมูลจาก Alpha Vantage API"""
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """📚 **คู่มือการใช้งาน**\n\n1. พิมพ์ symbol หุ้นภาษาอังกฤษ (1-5 ตัวอักษร)\n2. รอผลการวิเคราะห์สักครู่\n\n⚠️ ข้อมูลเพื่อการศึกษาเท่านั้น"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def analyze_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    user_input = update.message.text.strip().upper()
    if len(user_input) < 1 or len(user_input) > 6 or not user_input.isalpha(): return
    
    processing = await update.message.reply_text(f"🔍 กำลังวิเคราะห์ {user_input}...")
    analysis = get_stock_analysis(user_input)
    
    if analysis == "rate_limit":
        await processing.edit_text("⚠️ **API Limit ครบแล้ว** (25 req/วัน) กรุณาลองใหม่พรุ่งนี้", parse_mode='Markdown')
    elif analysis:
        await processing.edit_text(analysis, parse_mode='Markdown')
    else:
        await processing.edit_text(f"❌ ไม่พบข้อมูลหุ้น {user_input} หรือเกิดข้อผิดพลาด", parse_mode='Markdown')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# --- ส่วนที่ 5: Main Deployment Function (แก้ไขเพื่อให้รันบน Render ได้) ---

def main():
    # ตรวจสอบการตั้งค่าพื้นฐาน
    if not WEBHOOK_URL or "onrender.com" not in WEBHOOK_URL:
        logger.error("❌ WEBHOOK_URL ไม่ถูกต้อง! กรุณาตั้งค่าใน Environment Variables")
        # กรณีรัน Test ในเครื่อง ให้เปลี่ยนไปใช้ polling ชั่วคราวได้
        # application.run_polling() 
        # return

    # สร้าง Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # เพิ่ม Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_stock))
    application.add_error_handler(error_handler)
    
    # ดึง Port จาก Render
    port = int(os.environ.get("PORT", 10000))
    
    # รัน Webhook (แทน Polling)
    # วิธีนี้จะเปิด Web Server เล็กๆ ในตัวเพื่อรับข้อมูลจาก Telegram
    logger.info(f"🚀 Starting Webhook on port {port}...")
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT_TOKEN,
        webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()
