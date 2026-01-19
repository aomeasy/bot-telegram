import os
import logging
import requests
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.ext import CallbackContext
# from aiohttp import web

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Config ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8336478185:AAF_OO9dQj4vjCictaD-aWoWWUGdi6vv_lY")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# --- API Functions ---

def get_quote(symbol):
    """ดึงราคาปัจจุบัน"""
    try:
        url = "https://api.twelvedata.com/quote"
        params = {"symbol": symbol, "apikey": TWELVE_DATA_KEY}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('status') == 'error':
            logger.error(f"Quote error: {data.get('message')}")
            return None
        return data
    except Exception as e:
        logger.error(f"Error fetching quote: {e}")
        return None

def get_rsi(symbol):
    """ดึง RSI (14)"""
    try:
        url = "https://api.twelvedata.com/rsi"
        params = {
            "symbol": symbol,
            "interval": "1day",
            "time_period": 14,
            "apikey": TWELVE_DATA_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('values'):
            return float(data['values'][0]['rsi'])
        return None
    except:
        return None

def get_macd(symbol):
    """ดึง MACD"""
    try:
        url = "https://api.twelvedata.com/macd"
        params = {
            "symbol": symbol,
            "interval": "1day",
            "apikey": TWELVE_DATA_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('values'):
            latest = data['values'][0]
            return float(latest['macd']), float(latest['macd_signal'])
        return None, None
    except:
        return None, None

def get_ema(symbol, period):
    """ดึง EMA"""
    try:
        url = "https://api.twelvedata.com/ema"
        params = {
            "symbol": symbol,
            "interval": "1day",
            "time_period": period,
            "apikey": TWELVE_DATA_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('values'):
            return float(data['values'][0]['ema'])
        return None
    except:
        return None

def get_bbands(symbol):
    """ดึง Bollinger Bands"""
    try:
        url = "https://api.twelvedata.com/bbands"
        params = {
            "symbol": symbol,
            "interval": "1day",
            "time_period": 20,
            "apikey": TWELVE_DATA_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('status') == 'ok' and data.get('values'):
            latest = data['values'][0]
            return float(latest['lower_band']), float(latest['upper_band'])
        return None, None
    except:
        return None, None

def get_analyst_recommendations(symbol):
    """ดึงคำแนะนำจากนักวิเคราะห์ (จาก Finnhub)"""
    try:
        if not FINNHUB_KEY or FINNHUB_KEY == "":
            return None
            
        url = f"https://finnhub.io/api/v1/stock/recommendation"
        params = {"symbol": symbol, "token": FINNHUB_KEY}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return data[0] if data and len(data) > 0 else None
    except Exception as e:
        logger.error(f"Error fetching recommendations: {e}")
        return None

def get_price_target(symbol):
    """ดึงราคาเป้าหมายจากนักวิเคราะห์ (จาก Finnhub)"""
    try:
        if not FINNHUB_KEY or FINNHUB_KEY == "":
            logger.warning("⚠️ FINNHUB_KEY not set - Valuation data unavailable")
            return None
            
        url = f"https://finnhub.io/api/v1/stock/price-target"
        params = {"symbol": symbol, "token": FINNHUB_KEY}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        logger.info(f"📊 Price Target Response for {symbol}: {data}")
        
        if data and 'targetMean' in data and data['targetMean']:
            return {
                'target_mean': data.get('targetMean'),
                'target_high': data.get('targetHigh'),
                'target_low': data.get('targetLow'),
                'number_of_analysts': data.get('numberOfAnalysts', 0)
            }
        else:
            logger.warning(f"⚠️ No price target data for {symbol}")
            return None
    except Exception as e:
        logger.error(f"❌ Error fetching price target: {e}")
        return None

def get_stock_analysis(symbol):
    """วิเคราะห์หุ้นแบบครบถ้วน"""
    try:
        if not TWELVE_DATA_KEY or TWELVE_DATA_KEY == "":
            return "no_key"
        
        logger.info(f"🔄 Analyzing {symbol}...")
        
        # ดึงข้อมูลทั้งหมด
        quote = get_quote(symbol)
        if not quote or 'close' not in quote:
            return None
        
        rsi = get_rsi(symbol)
        macd, macd_signal = get_macd(symbol)
        ema_20 = get_ema(symbol, 20)
        ema_50 = get_ema(symbol, 50)
        ema_200 = get_ema(symbol, 200)
        bb_lower, bb_upper = get_bbands(symbol)
        recommendations = get_analyst_recommendations(symbol)
        price_target = get_price_target(symbol)
        
        # คำนวณข้อมูลพื้นฐาน
        current = float(quote['close'])
        prev_close = float(quote.get('previous_close', current))
        change = current - prev_close
        change_pct = (change / prev_close) * 100
        high = float(quote.get('high', current))
        low = float(quote.get('low', current))
        open_price = float(quote.get('open', current))
        
        # สร้างรายงาน
        report = f"""📊 **{symbol.upper()} Analysis**\n\n"""
        
        if quote.get('name'):
            report += f"🏢 **{quote['name']}**\n\n"
        
        # ราคา
        report += f"💰 **ราคาปัจจุบัน:** ${current:.2f}\n"
        emoji = "🟢" if change >= 0 else "🔴"
        report += f"{emoji} เปลี่ยนแปลง: ${change:+.2f} ({change_pct:+.2f}%)\n\n"
        
        # ข้อมูลวันนี้
        report += f"📊 **ข้อมูลวันนี้:**\n"
        report += f"• เปิด: ${open_price:.2f}\n"
        report += f"• สูงสุด: ${high:.2f}\n"
        report += f"• ต่ำสุด: ${low:.2f}\n"
        report += f"• ปิดก่อนหน้า: ${prev_close:.2f}\n\n"
        
        # ============ Valuation & Margin of Safety ============
        if price_target and price_target.get('target_mean'):
            report += f"💎 **Valuation & Margin of Safety:**\n"
            
            target_mean = price_target['target_mean']
            target_high = price_target.get('target_high')
            target_low = price_target.get('target_low')
            num_analysts = price_target.get('number_of_analysts', 0)
            
            # คำนวณ Upside/Downside Potential
            upside_pct = ((target_mean - current) / current) * 100
            
            report += f"• ราคาเป้าหมาย: ${target_mean:.2f}"
            
            if target_high and target_low:
                report += f" (${target_low:.2f}-${target_high:.2f})\n"
            else:
                report += f"\n"
            
            if num_analysts > 0:
                report += f"• นักวิเคราะห์: {num_analysts} คน\n"
            
            # แสดง Upside/Downside พร้อม Margin of Safety
            if upside_pct >= 20:
                report += f"🎯 Upside: +{upside_pct:.1f}% ⭐⭐⭐\n"
                report += f"✅ ราคาถูกมาก - Margin of Safety สูง\n\n"
            elif upside_pct >= 10:
                report += f"🎯 Upside: +{upside_pct:.1f}% ⭐⭐\n"
                report += f"👍 ราคาน่าสนใจ - Margin of Safety ปานกลาง\n\n"
            elif upside_pct >= 0:
                report += f"🎯 Upside: +{upside_pct:.1f}% ⭐\n"
                report += f"⚖️ ราคายุติธรรม - Margin of Safety น้อย\n\n"
            elif upside_pct >= -10:
                report += f"⚠️ Downside: {upside_pct:.1f}%\n"
                report += f"🔶 ราคาสูงกว่าเป้า - ไม่มี Margin of Safety\n\n"
            else:
                report += f"🚨 Downside: {upside_pct:.1f}%\n"
                report += f"⛔ ราคาแพงเกินไป - ควรระมัดระวัง\n\n"
        
        # RSI Analysis
        if rsi:
            report += f"📈 **RSI (14):** {rsi:.1f}\n"
            if rsi <= 30:
                report += f"💚 Oversold - สัญญาณซื้อ\n\n"
            elif rsi >= 70:
                report += f"❤️ Overbought - สัญญาณขาย\n\n"
            else:
                report += f"⚪ Neutral - ไม่มีสัญญาณชัดเจน\n\n"
        
        # MACD Analysis
        if macd is not None and macd_signal is not None:
            report += f"📊 **MACD:**\n"
            report += f"• MACD: {macd:.2f}\n"
            report += f"• Signal: {macd_signal:.2f}\n"
            if macd > macd_signal:
                report += f"🟢 Bullish - แนวโน้มขึ้น\n\n"
            else:
                report += f"🔴 Bearish - แนวโน้มลง\n\n"
        
        # EMA Analysis
        if ema_20 and ema_50 and ema_200:
            report += f"📊 **EMA:**\n"
            report += f"• EMA 20: ${ema_20:.2f}\n"
            report += f"• EMA 50: ${ema_50:.2f}\n"
            report += f"• EMA 200: ${ema_200:.2f}\n"
            
            if current > ema_20 > ema_50:
                report += f"📈 Uptrend แข็งแกร่ง\n\n"
            elif current < ema_20 < ema_50:
                report += f"📉 Downtrend\n\n"
            else:
                report += f"➡️ Sideways\n\n"
        
        # Bollinger Bands (กระชับลง)
        if bb_lower and bb_upper:
            report += f"🎯 **Bollinger Bands:**\n"
            report += f"• Support: ${bb_lower:.2f}\n"
            report += f"• Resistance: ${bb_upper:.2f}\n"
            
            if current >= bb_upper:
                report += f"⚠️ ราคาสูงกว่าแบนด์บน\n\n"
            elif current <= bb_lower:
                report += f"💡 ราคาต่ำกว่าแบนด์ล่าง\n\n"
            else:
                report += f"\n"
        
        # คำแนะนำจากนักวิเคราะห์ (กระชับลง)
        if recommendations:
            buy = recommendations.get('buy', 0)
            hold = recommendations.get('hold', 0)
            sell = recommendations.get('sell', 0)
            total = buy + hold + sell
            
            if total > 0:
                buy_pct = (buy / total) * 100
                sell_pct = (sell / total) * 100
                
                report += f"🎯 **คำแนะนำนักวิเคราะห์:**\n"
                report += f"• ซื้อ: {buy} ({buy_pct:.0f}%) • ถือ: {hold} • ขาย: {sell} ({sell_pct:.0f}%)\n"
                
                if buy_pct >= 60:
                    report += f"💚 ส่วนใหญ่แนะนำ 'ซื้อ'\n\n"
                elif sell_pct >= 40:
                    report += f"❤️ หลายคนแนะนำ 'ขาย'\n\n"
                else:
                    report += f"⚪ ความเห็นแบ่งออกเป็น 2 ฝ่าย\n\n"
        
        # สรุปภาพรวม
        report += f"📝 **สรุป:**\n"
        signals = []
        
        # เพิ่ม Valuation signal
        if price_target and price_target.get('target_mean'):
            target_mean = price_target['target_mean']
            upside_pct = ((target_mean - current) / current) * 100
            
            if upside_pct >= 20:
                signals.append("💎 Valuation: ราคาถูกมาก ⭐⭐⭐")
            elif upside_pct >= 10:
                signals.append("💎 Valuation: ราคาน่าสนใจ ⭐⭐")
            elif upside_pct >= 0:
                signals.append("💎 Valuation: ราคายุติธรรม ⭐")
            else:
                signals.append("💎 Valuation: ราคาแพง ⚠️")
        
        if rsi and rsi <= 30:
            signals.append("📈 RSI: ซื้อ")
        elif rsi and rsi >= 70:
            signals.append("📈 RSI: ขาย")
        
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                signals.append("📊 MACD: Bullish")
            else:
                signals.append("📊 MACD: Bearish")
        
        if ema_20 and ema_50 and current > ema_20 > ema_50:
            signals.append("📈 EMA: Uptrend")
        elif ema_20 and ema_50 and current < ema_20 < ema_50:
            signals.append("📉 EMA: Downtrend")
        
        if signals:
            for signal in signals:
                report += f"• {signal}\n"
        else:
            report += f"• ไม่มีสัญญาณชัดเจน\n"
        
        report += f"\n⏰ อัพเดท: {datetime.now().strftime('%H:%M:%S')}" 
        
        return report
        
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        return None
        
# --- HTTP Health Check Handler (สำหรับป้องกัน Render Sleep) ---

#async def http_health_check(request):
#    """HTTP health check endpoint for UptimeRobot & Render"""
#    return web.Response(text="✅ Bot is running!", status=200)

# --- Telegram Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """🤖 **ยินดีต้อนรับสู่ Stock Analysis Bot!** 📈

💡 **วิธีใช้งาน:**
• พิมพ์ชื่อหุ้น เช่น: AAPL, MSFT, TSLA
• /help - ดูคำแนะนำ
• /popular - ดูหุ้นยอดนิยม

✨ วิเคราะห์ด้วย:
• RSI, MACD, EMA, Bollinger Bands
• Valuation & Margin of Safety
• คำแนะนำจากนักวิเคราะห์"""
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """📚 **คู่มือการใช้งาน**

**ตัวชี้วัดที่มี:**
• RSI (14) - Relative Strength Index
• MACD - Moving Average Convergence Divergence
• EMA (20, 50, 200) - Exponential Moving Average
• Bollinger Bands (20) - แนวรับ/แนวต้าน
• Valuation - ราคาเป้าหมายจากนักวิเคราะห์
• Margin of Safety - ความปลอดภัยของราคา

**ตัวอย่างการใช้:**
พิมพ์: AAPL
พิมพ์: MSFT
พิมพ์: TSLA

**คำสั่ง:**
/popular - ดูหุ้นยอดนิยม

⚠️ รองรับหุ้นอเมริกา และบางหุ้นนานาชาติ
⚠️ ข้อมูลเพื่อการศึกษาเท่านั้น"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def popular_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    popular = """📈 หุ้นยอดนิยม

เทคโนโลยี:AAPL, MSFT, GOOGL, META, NVDA, TSLA, AMZN, AVGO, CRM, ADBE, ORCL, TSM, QCOM, ASML, RKLB 

การเงิน:JPM, BAC, V, MA, GS, MS, BRK.B, BLK, WFC, AXP, PYPL, SCHW

พลังงาน:XOM, CVX, COP, SLB, EOG, MPC, PSX, VLO, HES

อุปโภคบริโภค:WMT, KO, PG, MCD, NKE, COST, PEP, HD, SBUX, PM, TGT, LOW

สุขภาพ:JNJ, UNH, PFE, ABBV, LLY, NVO, ISRG, AMGN, MDT, BMY

อุตสาหกรรมและการขนส่ง:GE, CAT, LMT, HON, UPS, RTX, BA, DE, MMM, FEDEX

บริการสื่อสารและบันเทิง:NFLX, DIS, TMUS, CMCSA, VZ, T, CHTR

วัสดุและอุปกรณ์:LIN, APD, FCX, SHW, ECL, NEM

สาธารณูปโภค:NEE, DUKE, SO, D, AEP, EXC

อสังหาริมทรัพย์ (REITs):AMT, PLD, EQIX, CCI, SPG, O"""
    await update.message.reply_text(popular, parse_mode='Markdown')

async def analyze_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: 
        return
    
    user_input = update.message.text.strip().upper()
    
    if len(user_input) < 1 or len(user_input) > 6 or not user_input.isalpha(): 
        return
    
    processing = await update.message.reply_text(f"🔍 กำลังวิเคราะห์ {user_input}...\n⏳ กำลังดึงข้อมูล RSI, MACD, EMA, Bollinger Bands, Valuation...")
    analysis = get_stock_analysis(user_input)
    
    if analysis == "no_key":
        await processing.edit_text(
            "⚠️ **ไม่พบ API Key**\n\n"
            "กรุณาตั้งค่า TWELVE_DATA_KEY ใน Environment\n"
            "รับ Free API Key: https://twelvedata.com/apikey", 
            parse_mode='Markdown'
        )
    elif analysis:
        # ตรวจสอบความยาวข้อความ (Telegram limit 4096)
        if len(analysis) > 4000:
            # แบ่งข้อความออกเป็น 2 ส่วน
            mid_point = analysis.rfind('\n\n', 0, 2000)
            if mid_point == -1:
                mid_point = 2000
            
            part1 = analysis[:mid_point]
            part2 = analysis[mid_point:]
            
            await processing.edit_text(part1, parse_mode='Markdown')
            await update.message.reply_text(part2, parse_mode='Markdown')
        else:
            await processing.edit_text(analysis, parse_mode='Markdown')
    else:
        await processing.edit_text(
            f"❌ ไม่พบข้อมูลหุ้น {user_input}\n\n"
            f"กรุณาตรวจสอบ Symbol หรือลอง /popular", 
            parse_mode='Markdown'
        )

# Health check handler
async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /health command"""
    await update.message.reply_text("✅ Bot is running!")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# --- Main ---

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("popular", popular_stocks))
    application.add_handler(CommandHandler("health", health_check))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_stock))
    application.add_error_handler(error_handler)
    
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
