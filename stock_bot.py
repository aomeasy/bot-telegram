import os
import logging
import requests
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- ส่วนที่ 1: การตั้งค่า Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ส่วนที่ 2: Config ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8336478185:AAF_OO9dQj4vjCictaD-aWoWWUGdi6vv_lY")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")  # ต้องตั้งค่าใน Render
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# --- ส่วนที่ 3: Stock Functions ใช้ Finnhub API ---

def get_stock_quote(symbol):
    """ดึงราคาปัจจุบัน"""
    try:
        url = f"https://finnhub.io/api/v1/quote"
        params = {"symbol": symbol, "token": FINNHUB_KEY}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('c', 0) == 0:  # ไม่มีข้อมูล
            return None
        return data
    except Exception as e:
        logger.error(f"Error fetching quote: {e}")
        return None

def get_company_profile(symbol):
    """ดึงข้อมูลบริษัท"""
    try:
        url = f"https://finnhub.io/api/v1/stock/profile2"
        params = {"symbol": symbol, "token": FINNHUB_KEY}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return data if data else None
    except:
        return None

def get_recommendation_trends(symbol):
    """ดึงคำแนะนำจากนักวิเคราะห์"""
    try:
        url = f"https://finnhub.io/api/v1/stock/recommendation"
        params = {"symbol": symbol, "token": FINNHUB_KEY}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return data[0] if data and len(data) > 0 else None
    except:
        return None

def calculate_simple_metrics(quote_data):
    """คำนวณตัวชี้วัดเบื้องต้น"""
    try:
        current = quote_data['c']  # current price
        open_price = quote_data['o']  # open price
        high = quote_data['h']  # high
        low = quote_data['l']  # low
        prev_close = quote_data['pc']  # previous close
        
        change = current - prev_close
        change_pct = (change / prev_close) * 100
        
        # Day range position
        if high != low:
            range_pos = ((current - low) / (high - low)) * 100
        else:
            range_pos = 50
        
        # Volatility indicator
        daily_range = ((high - low) / low) * 100
        
        return {
            'current': current,
            'change': change,
            'change_pct': change_pct,
            'open': open_price,
            'high': high,
            'low': low,
            'prev_close': prev_close,
            'range_pos': range_pos,
            'volatility': daily_range
        }
    except:
        return None

def get_stock_analysis(symbol):
    """วิเคราะห์หุ้น"""
    try:
        # ตรวจสอบ API Key
        if not FINNHUB_KEY or FINNHUB_KEY == "":
            return "no_key"
        
        logger.info(f"🔄 Analyzing {symbol}...")
        
        # ดึงข้อมูล
        quote = get_stock_quote(symbol)
        if not quote:
            return None
        
        profile = get_company_profile(symbol)
        recommendation = get_recommendation_trends(symbol)
        metrics = calculate_simple_metrics(quote)
        
        if not metrics:
            return None
        
        # สร้างรายงาน
        report = f"""📊 **{symbol.upper()} Analysis**\n\n"""
        
        # ข้อมูลบริษัท
        if profile and profile.get('name'):
            report += f"🏢 **{profile['name']}**\n"
            if profile.get('finnhubIndustry'):
                report += f"🏭 อุตสาหกรรม: {profile['finnhubIndustry']}\n\n"
        
        # ราคา
        report += f"💰 **ราคาปัจจุบัน:** ${metrics['current']:.2f}\n"
        emoji = "🟢" if metrics['change'] >= 0 else "🔴"
        report += f"{emoji} เปลี่ยนแปลง: ${metrics['change']:+.2f} ({metrics['change_pct']:+.2f}%)\n\n"
        
        # ข้อมูลวันนี้
        report += f"📊 **ข้อมูลวันนี้:**\n"
        report += f"• เปิด: ${metrics['open']:.2f}\n"
        report += f"• สูงสุด: ${metrics['high']:.2f}\n"
        report += f"• ต่ำสุด: ${metrics['low']:.2f}\n"
        report += f"• ปิดก่อนหน้า: ${metrics['prev_close']:.2f}\n\n"
        
        # วิเคราะห์เบื้องต้น
        report += f"📈 **การวิเคราะห์:**\n"
        
        # Day Range Position
        if metrics['range_pos'] > 70:
            report += f"• ราคาอยู่ใกล้จุดสูงสุดของวัน ({metrics['range_pos']:.0f}% ของช่วง)\n"
        elif metrics['range_pos'] < 30:
            report += f"• ราคาอยู่ใกล้จุดต่ำสุดของวัน ({metrics['range_pos']:.0f}% ของช่วง)\n"
        else:
            report += f"• ราคาอยู่กลางช่วงของวัน ({metrics['range_pos']:.0f}% ของช่วง)\n"
        
        # Momentum
        if metrics['change_pct'] > 2:
            report += f"• โมเมนตัม: 🚀 แรงมาก (Bullish)\n"
        elif metrics['change_pct'] > 0.5:
            report += f"• โมเมนตัม: 📈 เป็นบวก (Positive)\n"
        elif metrics['change_pct'] < -2:
            report += f"• โมเมนตัม: 📉 อ่อนแอมาก (Bearish)\n"
        elif metrics['change_pct'] < -0.5:
            report += f"• โมเมนตัม: ⬇️ เป็นลบ (Negative)\n"
        else:
            report += f"• โมเมนตัม: ➡️ นิ่ง (Neutral)\n"
        
        # Volatility
        if metrics['volatility'] > 3:
            report += f"• ความผันผวน: ⚠️ สูง ({metrics['volatility']:.1f}%)\n"
        elif metrics['volatility'] > 1.5:
            report += f"• ความผันผวน: 📊 ปานกลาง ({metrics['volatility']:.1f}%)\n"
        else:
            report += f"• ความผันผวน: ✅ ต่ำ ({metrics['volatility']:.1f}%)\n"
        
        # คำแนะนำจากนักวิเคราะห์
        if recommendation:
            report += f"\n🎯 **คำแนะนำจากนักวิเคราะห์:**\n"
            total = recommendation.get('buy', 0) + recommendation.get('hold', 0) + recommendation.get('sell', 0)
            if total > 0:
                buy_pct = (recommendation.get('buy', 0) / total) * 100
                report += f"• ซื้อ: {recommendation.get('buy', 0)} ({buy_pct:.0f}%)\n"
                report += f"• ถือ: {recommendation.get('hold', 0)}\n"
                report += f"• ขาย: {recommendation.get('sell', 0)}\n"
        
        report += f"\n⏰ อัพเดท: {datetime.now().strftime('%H:%M:%S')}\n"
        report += f"\n⚠️ *ข้อมูลนี้เพื่อการศึกษาเท่านั้น ไม่ใช่คำแนะนำการลงทุน*"
        
        return report
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return None

# --- ส่วนที่ 4: Telegram Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """🤖 **ยินดีต้อนรับสู่ Stock Analysis Bot!** 📈

💡 **วิธีใช้งาน:**
• พิมพ์ชื่อหุ้นอเมริกัน เช่น: AAPL, MSFT, TSLA, GOOGL
• /help - ดูคำแนะนำ
• /popular - ดูหุ้นยอดนิยม

✨ ข้อมูลจาก Finnhub API"""
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """📚 **คู่มือการใช้งาน**

**คำสั่ง:**
• พิมพ์ symbol หุ้น (1-5 ตัวอักษร)
• /popular - ดูหุ้นยอดนิยม

**ตัวอย่าง:**
AAPL (Apple)
MSFT (Microsoft)
TSLA (Tesla)
GOOGL (Google)
AMZN (Amazon)
NVDA (NVIDIA)

⚠️ รองรับเฉพาะหุ้นอเมริกา
⚠️ ข้อมูลเพื่อการศึกษาเท่านั้น"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def popular_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    popular = """📈 **หุ้นยอดนิยม**

**เทคโนโลยี:**
• AAPL - Apple
• MSFT - Microsoft
• GOOGL - Google
• META - Meta (Facebook)
• NVDA - NVIDIA
• TSLA - Tesla
• AMZN - Amazon

**การเงิน:**
• JPM - JP Morgan
• BAC - Bank of America
• V - Visa
• MA - Mastercard

**พลังงาน:**
• XOM - Exxon Mobil
• CVX - Chevron

**อุปโภคบริโภค:**
• WMT - Walmart
• KO - Coca-Cola
• PG - Procter & Gamble

แค่พิมพ์ symbol เพื่อดูข้อมูล! 🚀"""
    await update.message.reply_text(popular, parse_mode='Markdown')

async def analyze_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: 
        return
    
    user_input = update.message.text.strip().upper()
    
    # ตรวจสอบความถูกต้อง
    if len(user_input) < 1 or len(user_input) > 6 or not user_input.isalpha(): 
        return
    
    processing = await update.message.reply_text(f"🔍 กำลังวิเคราะห์ {user_input}...")
    analysis = get_stock_analysis(user_input)
    
    if analysis == "no_key":
        await processing.edit_text(
            "⚠️ **ไม่พบ API Key**\n\n"
            "กรุณาตั้งค่า FINNHUB_KEY ใน Environment Variables\n"
            "รับ Free API Key ได้ที่: https://finnhub.io", 
            parse_mode='Markdown'
        )
    elif analysis:
        await processing.edit_text(analysis, parse_mode='Markdown')
    else:
        await processing.edit_text(
            f"❌ ไม่พบข้อมูลหุ้น {user_input}\n\n"
            f"กรุณาตรวจสอบ:\n"
            f"• Symbol ถูกต้องหรือไม่\n"
            f"• เป็นหุ้นในตลาดอเมริกาหรือไม่\n"
            f"• ลอง /popular เพื่อดูหุ้นยอดนิยม", 
            parse_mode='Markdown'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# --- ส่วนที่ 5: Main Function ---

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # เพิ่ม Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("popular", popular_stocks))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_stock))
    application.add_error_handler(error_handler)
    
    # เลือก Mode
    if WEBHOOK_URL and "onrender.com" in WEBHOOK_URL:
        try:
            port = int(os.environ.get("PORT", 10000))
            logger.info(f"🚀 Starting Webhook on port {port}...")
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=BOT_TOKEN,
                webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
                drop_pending_updates=True
            )
        except RuntimeError as e:
            if "webhooks" in str(e):
                logger.warning("⚠️ Falling back to polling...")
                application.run_polling(drop_pending_updates=True)
            else:
                raise
    else:
        logger.info("🚀 Starting Polling mode...")
        application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
