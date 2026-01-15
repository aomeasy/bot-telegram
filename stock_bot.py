import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import pandas as pd
import numpy as np
from flask import Flask
from threading import Thread
import time
from datetime import datetime

# ตั้งค่า logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ใส่ API Keys
BOT_TOKEN = "8336478185:AAF_OO9dQj4vjCictaD-aWoWWUGdi6vv_lY"
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "YOUR_API_KEY_HERE")

# สร้าง Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def fetch_stock_data(symbol):
    """ดึงข้อมูลหุ้นจาก Alpha Vantage"""
    try:
        # ดึงข้อมูลราคา Daily
        url = f"https://www.alphavantage.co/query"
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": ALPHA_VANTAGE_KEY
        }
        
        logger.info(f"🔄 Fetching data for {symbol} from Alpha Vantage...")
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # ตรวจสอบ error
        if "Error Message" in data:
            logger.error(f"❌ Invalid symbol: {symbol}")
            return None
        
        if "Note" in data:
            logger.error(f"❌ API limit reached")
            return None, "rate_limit"
        
        if "Time Series (Daily)" not in data:
            logger.error(f"❌ No data found for {symbol}")
            return None
        
        # แปลงเป็น DataFrame
        time_series = data["Time Series (Daily)"]
        df = pd.DataFrame.from_dict(time_series, orient='index')
        df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # แปลงเป็น float
        for col in df.columns:
            df[col] = df[col].astype(float)
        
        # เอาแค่ 6 เดือนล่าสุด
        df = df.last('180D')
        
        logger.info(f"✅ Got {len(df)} days of data for {symbol}")
        return df
        
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return None

def calculate_rsi(prices, period=14):
    """คำนวณ RSI"""
    try:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        # หลีกเลี่ยง division by zero
        rs = gain / loss.replace(0, 0.0001)
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except:
        return 50  # ค่า default

def calculate_macd(prices):
    """คำนวณ MACD"""
    try:
        exp1 = prices.ewm(span=12, adjust=False).mean()
        exp2 = prices.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd.iloc[-1], signal.iloc[-1]
    except:
        return 0, 0

def calculate_bollinger_bands(prices, period=20):
    """คำนวณ Bollinger Bands"""
    try:
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        return lower.iloc[-1], upper.iloc[-1]
    except:
        price = prices.iloc[-1]
        return price * 0.95, price * 1.05

def calculate_ema(prices, period):
    """คำนวณ EMA"""
    try:
        return prices.ewm(span=period, adjust=False).mean().iloc[-1]
    except:
        return prices.iloc[-1]

def get_stock_analysis(symbol):
    """วิเคราะห์หุ้นแบบครบวงจร"""
    try:
        # ดึงข้อมูล
        df = fetch_stock_data(symbol)
        
        if df is None:
            return None
        
        if isinstance(df, tuple) and df[1] == "rate_limit":
            return "rate_limit"
        
        if len(df) < 50:
            return None
        
        prices = df['Close']
        current_price = prices.iloc[-1]
        prev_close = prices.iloc[-2]
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100
        
        # คำนวณตัวชี้วัด
        rsi = calculate_rsi(prices)
        macd, signal = calculate_macd(prices)
        bb_lower, bb_upper = calculate_bollinger_bands(prices)
        ema_20 = calculate_ema(prices, 20)
        ema_50 = calculate_ema(prices, 50)
        ema_200 = calculate_ema(prices, 200)
        
        # กำหนดสัญญาณ
        rsi_signal = "💚 Oversold (ซื้อ)" if rsi <= 30 else "❤️ Overbought (ขาย)" if rsi >= 70 else "⚪ Neutral"
        macd_signal = "🟢 Bullish" if macd > signal else "🔴 Bearish"
        price_trend = "📈 Uptrend" if current_price > ema_20 > ema_50 else "📉 Downtrend" if current_price < ema_20 < ema_50 else "➡️ Sideways"
        
        # Volume trend (ง่ายๆ)
        volume_trend = "📊 Increasing" if df['Volume'].iloc[-5:].mean() > df['Volume'].iloc[-10:-5].mean() else "📉 Decreasing"
        
        # สร้างข้อความวิเคราะห์
        analysis = f"""📊 **{symbol.upper()} Analysis**

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
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """คำสั่ง /start"""
    logger.info(f"🚀 /start from user: {update.effective_user.id}")
    welcome = """🤖 **ยินดีต้อนรับสู่ Stock Analysis Bot!** 📈

💡 **วิธีใช้งาน:**
• พิมพ์ชื่อหุ้น เช่น: AAPL, MSFT, GOOGL, TSLA
• /help - ดูคำแนะนำ
• /start - แสดงข้อความนี้

📊 **ตัวชี้วัดที่วิเคราะห์:**
• RSI - Relative Strength Index
• MACD - Moving Average Convergence Divergence  
• Bollinger Bands
• EMA - Exponential Moving Average
• Volume Analysis

🎯 **ตัวอย่าง:** พิมพ์ "AAPL" เพื่อวิเคราะห์หุ้น Apple

✨ ข้อมูลจาก Alpha Vantage API"""
    
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """คำสั่ง /help"""
    help_text = """📚 **คู่มือการใช้งาน**

**🔍 วิธีใช้:**
1. พิมพ์ symbol หุ้นภาษาอังกฤษ (1-5 ตัวอักษร)
2. รอสักครู่เพื่อดูผลการวิเคราะห์

**📊 ตัวอย่าง Symbol:**
• AAPL - Apple Inc.
• MSFT - Microsoft
• GOOGL - Google/Alphabet
• TSLA - Tesla
• AMZN - Amazon
• META - Meta/Facebook
• NVDA - NVIDIA

**📈 การอ่านสัญญาณ:**
• RSI < 30 = Oversold (ควรซื้อ)
• RSI > 70 = Overbought (ควรขาย)
• MACD Bullish = แนวโน้มขาขึ้น
• MACD Bearish = แนวโน้มขาลง

**⚡ API Limit:**
• ฟรี 25 requests ต่อวัน
• หากเกินให้รอ 24 ชั่วโมง

⚠️ **ข้อจำกัด:** ข้อมูลเพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำการลงทุน"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def analyze_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """วิเคราะห์หุ้น"""
    if not update.message or not update.message.text:
        return
    
    user_input = update.message.text.strip().upper()
    logger.info(f"📩 Received: {user_input} from user {update.effective_user.id}")
    
    # ตรวจสอบ symbol (1-5 ตัวอักษร)
    if len(user_input) < 1 or len(user_input) > 6 or not user_input.isalpha():
        return
    
    # แสดงข้อความกำลังประมวลผล
    processing = await update.message.reply_text(f"🔍 กำลังวิเคราะห์ {user_input}...")
    
    # วิเคราะห์
    analysis = get_stock_analysis(user_input)
    
    if analysis == "rate_limit":
        await processing.edit_text(
            "⚠️ **API Limit ครบแล้ว**\n\n"
            "Alpha Vantage ฟรีมี 25 requests/วัน\n"
            "กรุณารอ 24 ชั่วโมงแล้วลองใหม่\n\n"
            "หรือติดต่อ Admin เพื่ออัพเกรด API 🚀",
            parse_mode='Markdown'
        )
    elif analysis:
        await processing.edit_text(analysis, parse_mode='Markdown')
    else:
        await processing.edit_text(
            f"❌ **ไม่พบข้อมูลหุ้น {user_input}**\n\n"
            f"กรุณาตรวจสอบ:\n"
            f"• Symbol ถูกต้องหรือไม่\n"
            f"• ใช้ US Stock เท่านั้น (NYSE, NASDAQ)\n"
            f"• ลองหุ้นอื่น เช่น AAPL, MSFT, GOOGL",
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """จัดการ error"""
    logger.error(f"Update {update} caused error {context.error}")

def run_flask():
    """รัน Flask server"""
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Flask starting on port {port}")
    app.run(host='0.0.0.0', port=port, use_reloader=False)

def main():
    """ฟังก์ชันหลัก"""
    try:
        # เช็ค API Key
        if ALPHA_VANTAGE_KEY == "YOUR_API_KEY_HERE":
            logger.error("❌ กรุณาตั้งค่า ALPHA_VANTAGE_KEY environment variable")
            logger.error("   ไปสมัครฟรีที่: https://www.alphavantage.co/support/#api-key")
        
        # รัน Flask ใน thread
        flask_thread = Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        
        logger.info("🚀 Starting Telegram Bot...")
        
        # สร้าง Bot Application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # เพิ่ม handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.UpdateType.EDITED_MESSAGE,
            analyze_stock
        ))
        application.add_error_handler(error_handler)
        
        # รัน bot
        logger.info("✅ Bot is running!")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ Failed: {e}")
        raise

if __name__ == '__main__':
    main()
