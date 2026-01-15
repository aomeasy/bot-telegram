import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yfinance as yf
import pandas as pd
import numpy as np
from flask import Flask
from threading import Thread
import time

# ตั้งค่า logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ใส่ Bot Token ของคุณที่นี่
BOT_TOKEN = "8336478185:AAF_OO9dQj4vjCictaD-aWoWWUGdi6vv_lY"

# กำหนด User-Agent เพื่อหลีกเลี่ยงการถูกบล็อก
yf.set_tz_cache_location(os.path.join(os.getcwd(), ".cache"))

# สร้าง Flask app สำหรับ Render
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

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
        # ดึงข้อมูลหุ้น - เพิ่ม headers เพื่อหลีกเลี่ยง rate limit
        logger.info(f"🔄 Fetching data for {symbol}...")
        
        # ลอง download แทนการใช้ history
        try:
            hist = yf.download(
                symbol, 
                period="6mo", 
                progress=False,
                show_errors=False
            )
        except Exception as e:
            logger.error(f"Download failed: {e}")
            # Fallback ใช้ Ticker
            stock = yf.Ticker(symbol)
            hist = stock.history(period="3mo")
        
        if hist is None or hist.empty or len(hist) < 20:
            logger.error(f"❌ No data found for {symbol}")
            return None
        
        logger.info(f"✅ Got {len(hist)} days of data for {symbol}")
        
        # ถ้าเป็น MultiIndex (จาก download) ให้แปลงเป็น simple index
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.droplevel(1)
        
        current_price = hist['Close'].iloc[-1]
        prices = hist['Close']
        
        # คำนวณตัวชี้วัดทางเทคนิค
        rsi = calculate_rsi(prices)
        macd, signal = calculate_macd(prices)
        bb_lower, bb_upper = calculate_bollinger_bands(prices)
        ema_20 = calculate_ema(prices, 20)
        ema_50 = calculate_ema(prices, 50)
        
        # กำหนดสัญญาณ
        rsi_signal = "กลาง ⚪" if 30 < rsi < 70 else "ต่ำ 🟢" if rsi <= 30 else "สูง 🔴"
        macd_signal = "สัญญาณลบ 🔴" if macd < signal else "สัญญาณบวก 🟢"
        trend = "ต่ำ 🟢" if current_price > ema_20 else "ขาขึ้น 🟢"
        
        # สถานะ EMA
        ema_20_50_status = "ขาขึ้น 🟢" if ema_20 > ema_50 else "โกลด์เดนครอส 🟢"
        ema_50_200_trend = "ขาขึ้น 🟢" if calculate_ema(prices, 50) > calculate_ema(prices, 200) else "โกลด์เดนครอส 🟢"
        
        # คำนวณ OBV (On Balance Volume) - simplified
        obv_trend = "เพิ่มขึ้น 📈" if hist['Volume'].iloc[-5:].mean() > hist['Volume'].iloc[-10:-5].mean() else "ลดลง 📉"
        
        # สร้างข้อความวิเคราะห์
        analysis = f"""📊 {symbol.upper()}

โมเมนตัมราคา: {'แนวโน้มเป็นขาลง 📉' if current_price < ema_20 else 'แนวโน้มเป็นขาขึ้น 📈'}
RSI: {rsi_signal}
MACD: {macd_signal}
ผันผวน: {trend}

ราคาเฉลี่ย 5 วัน: {current_price:.2f}

📊 โบลลิงเจอร์ (20): {bb_lower:.2f} – {bb_upper:.2f}

🟡 EMA 20/50: {ema_20_50_status}
EMA 50/200: {ema_50_200_trend}

OBV สำสูด: {obv_trend}

แนวรับ: {bb_lower:.2f}
แนวต้าน: {bb_upper:.2f}

*เพื่อเป็นข้อมูล ไม่ใช่คำแนะนำการลงทุน**"""
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ฟังก์ชันเริ่มต้นเมื่อใช้คำสั่ง /start"""
    logger.info(f"🚀 /start command from user: {update.effective_user.id}")
    welcome_message = """🤖 ยินดีต้อนรับสู่ Stock Analysis Bot! 📈

คำสั่งที่ใช้ได้:
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

⚠️ หมายเหตุ: ข้อมูลนี้เพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำการลงทุน"""
    
    await update.message.reply_text(help_text)

async def analyze_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """วิเคราะห์หุ้นตาม symbol ที่ผู้ใช้พิมพ์"""
    # ตรวจสอบว่ามี message และ text หรือไม่
    if not update.message or not update.message.text:
        return
    
    user_input = update.message.text.strip().upper()
    logger.info(f"📩 Received message: {user_input}")
    
    # ตรวจสอบว่าเป็น symbol หุ้นหรือไม่ (1-10 ตัวอักษร)
    if len(user_input) < 1 or len(user_input) > 10 or not user_input.isalpha():
        logger.info(f"❌ Invalid symbol: {user_input}")
        return
    
    # ส่งข้อความแจ้งว่ากำลังประมวลผล
    processing_msg = await update.message.reply_text(f"🔍 กำลังวิเคราะห์ {user_input}...")
    
    # เพิ่ม delay เล็กน้อยเพื่อหลีกเลี่ยง rate limit
    time.sleep(0.5)
    
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

def run_flask():
    """รัน Flask web server ใน thread แยก"""
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Flask server starting on port {port}")
    app.run(host='0.0.0.0', port=port, use_reloader=False)

def main():
    """ฟังก์ชันหลัก - รัน Flask และ Bot พร้อมกัน"""
    try:
        # รัน Flask ใน thread แยก (ไม่ใช่ bot)
        flask_thread = Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        
        logger.info("🚀 Starting Telegram Bot in main thread...")
        
        # สร้าง Application และรันใน main thread
        application = Application.builder().token(BOT_TOKEN).build()
        
        # เพิ่ม handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & ~filters.UpdateType.EDITED_MESSAGE, 
            analyze_stock
        ))
        
        # เพิ่ม error handler
        application.add_error_handler(error_handler)
        
        # เริ่มรัน bot ใน main thread
        logger.info("✅ Telegram Bot is now running!")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to start: {e}")
        raise

if __name__ == '__main__':
    main()
