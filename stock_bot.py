import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yfinance as yf
import pandas as pd
import numpy as np

# ตั้งค่า logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ใส่ Bot Token ของคุณที่นี่
BOT_TOKEN = "8336478185:AAF_OO9dQj4vjCictaD-aWoWWUGdi6vv_lY"

def calculate_rsi(prices, period=14):
    """คำนวณ RSI (Relative Strength Index)"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def calculate_macd(prices):
    """คำนวณ MACD"""
    exp1 = prices.ewm(span=12, adjust=False).mean()
    exp2 = prices.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd.iloc[-1], signal.iloc[-1]

def calculate_bollinger_bands(prices, period=20):
    """คำนวณ Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper_band = sma + (std * 2)
    lower_band = sma - (std * 2)
    return lower_band.iloc[-1], upper_band.iloc[-1]

def calculate_ema(prices, period):
    """คำนวณ EMA (Exponential Moving Average)"""
    return prices.ewm(span=period, adjust=False).mean().iloc[-1]

def get_stock_analysis(symbol):
    """วิเคราะห์หุ้นแบบครบวงจร"""
    try:
        # ดึงข้อมูลหุ้น
        stock = yf.Ticker(symbol)
        hist = stock.history(period="6mo")
        
        if hist.empty:
            return None
        
        current_price = hist['Close'].iloc[-1]
        prices = hist['Close']
        
        # คำนวณตัวชี้วัดทางเทคนิค
        rsi = calculate_rsi(prices)
        macd, signal = calculate_macd(prices)
        bb_lower, bb_upper = calculate_bollinger_bands(prices)
        ema_20 = calculate_ema(prices, 20)
        ema_50 = calculate_ema(prices, 50)
        ema_50_200_trend = "ขาขึ้น 🟢" if calculate_ema(prices, 50) > calculate_ema(prices, 200) else "โกลด์เดนครอส 🟢" if calculate_ema(prices, 50) > calculate_ema(prices, 200) else "โกลด์เดนครอส 🟢"
        
        # กำหนดสัญญาณ
        rsi_signal = "กลาง ⚪" if 30 < rsi < 70 else "ต่ำ 🟢" if rsi <= 30 else "สูง 🔴"
        macd_signal = "สัญญาณลบ 🔴" if macd < signal else "สัญญาณบวก 🟢"
        trend = "ต่ำ 🟢" if current_price > ema_20 else "ขาขึ้น 🟢"
        
        # สถานะ EMA
        ema_20_50_status = "ขาขึ้น 🟢" if ema_20 > ema_50 else "โกลด์เดนครอส 🟢"
        
        # คำนวณ OBV (On Balance Volume) - simplified
        obv_trend = "เพิ่มขึ้น 📈" if hist['Volume'].iloc[-5:].mean() > hist['Volume'].iloc[-10:-5].mean() else "ลดลง 📉"
        
        # สร้างข้อความวิเคราะห์
        analysis = f"""📊 {symbol.upper()}
โมเมนตัมราคา: {'แนวโน้มเป็นขาลง 📉' if current_price < ema_20 else 'แนวโน้มเป็นขาขึ้น 📈'}

RSI: {rsi_signal}  MACD: {macd_signal}
ผันผวน: {trend}  ราคาเฉลี่ย 5 วัน: {current_price:.2f} 📊
โบลลิงเจอร์ (20): {bb_lower:.2f} – {bb_upper:.2f} 🟡
EMA 20/50: {ema_20_50_status}
EMA 50/200: {ema_50_200_trend}
OBV สำสูด: {obv_trend}
แนวรับ: {bb_lower:.2f} แนวต้าน: {bb_upper:.2f}

*เพื่อเป็นข้อมูล ไม่ใช่คำแนะนำการลงทุน**"""
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ฟังก์ชันเริ่มต้นเมื่อใช้คำสั่ง /start"""
    welcome_message = """🤖 ยินดีต้อนรับสู่ Stock Analysis Bot!

📈 คำสั่งที่ใช้ได้:
• พิมพ์ชื่อหุ้น (เช่น AAPL, TSLA, GOOGL)
• /start - แสดงข้อความต้อนรับ
• /help - แสดงคำสั่งทั้งหมด

💡 ตัวอย่าง: พิมพ์ "AAPL" เพื่อวิเคราะห์หุ้น Apple"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ฟังก์ชันแสดงความช่วยเหลือ"""
    help_text = """📚 วิธีใช้งาน:

1️⃣ พิมพ์ symbol หุ้น (ตัวอักษรภาษาอังกฤษ)
   ตัวอย่าง: AAPL, MSFT, TSLA, GOOGL

2️⃣ รอสักครู่เพื่อดูผลการวิเคราะห์

📊 ตัวชี้วัดที่ใช้:
• RSI - Relative Strength Index
• MACD - Moving Average Convergence Divergence
• Bollinger Bands
• EMA - Exponential Moving Average
• OBV - On Balance Volume

⚠️ หมายเหตุ: ข้อมูลนี้เพื่อการศึกษาเท่านั้น
ไม่ใช่คำแนะนำการลงทุน"""
    
    await update.message.reply_text(help_text)

async def analyze_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """วิเคราะห์หุ้นตาม symbol ที่ผู้ใช้พิมพ์"""
    user_input = update.message.text.strip().upper()
    
    # ตรวจสอบว่าเป็น symbol หุ้นหรือไม่
    if len(user_input) > 10 or not user_input.isalpha():
        return
    
    # ส่งข้อความแจ้งว่ากำลังประมวลผล
    processing_msg = await update.message.reply_text(f"🔍 กำลังวิเคราะห์ {user_input}...")
    
    # วิเคราะห์หุ้น
    analysis = get_stock_analysis(user_input)
    
    if analysis:
        await processing_msg.edit_text(analysis)
    else:
        await processing_msg.edit_text(
            f"❌ ไม่พบข้อมูลหุ้น {user_input}\n"
            f"กรุณาตรวจสอบ symbol และลองใหม่อีกครั้ง"
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """จัดการ error"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """ฟังก์ชันหลักในการรัน bot"""
    # สร้าง Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # เพิ่ม handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_stock))
    
    # เพิ่ม error handler
    application.add_error_handler(error_handler)
    
    # เริ่มรัน bot
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
