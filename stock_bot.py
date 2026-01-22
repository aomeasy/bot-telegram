import os
import logging
import requests
from datetime import datetime, timedelta 
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.ext import CallbackContext 

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
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")  

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
            return None
            
        url = f"https://finnhub.io/api/v1/stock/price-target"
        params = {"symbol": symbol, "token": FINNHUB_KEY}
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data and 'targetMean' in data:
            return {
                'target_mean': data.get('targetMean'),
                'target_high': data.get('targetHigh'),
                'target_low': data.get('targetLow'),
                'number_of_analysts': data.get('numberOfAnalysts', 0)
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching price target: {e}")
        return None

def get_company_news(symbol, days=7):
    """ดึงข่าวบริษัท (จาก Finnhub)"""
    try:
        if not FINNHUB_KEY or FINNHUB_KEY == "":
            return None
        
        from datetime import datetime, timedelta
        
        # คำนวณวันที่ย้อนหลัง
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)
        
        url = f"https://finnhub.io/api/v1/company-news"
        params = {
            "symbol": symbol,
            "from": from_date.strftime('%Y-%m-%d'),
            "to": to_date.strftime('%Y-%m-%d'),
            "token": FINNHUB_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # กรองและเรียงตามวันที่ล่าสุด
        if data and isinstance(data, list):
            # เอาแค่ 5 ข่าวล่าสุด
            return data[:5]
        return None
        
    except Exception as e:
        logger.error(f"Error fetching company news: {e}")
        return None


def analyze_news_with_gemini(news_list, symbol):
    """วิเคราะห์ข่าวด้วย Gemini AI - สรุปว่าดีหรือไม่ดี"""
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "":
            logger.warning("No Gemini API key, skipping analysis")
            return None
        
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        
        # ใช้โมเดล Gemini Flash (เร็วและฟรี)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # เตรียมข้อมูลข่าวสำหรับ AI
        news_text = f"ข่าวล่าสุดของหุ้น {symbol}:\n\n"
        for i, news in enumerate(news_list[:5], 1):  # วิเคราะห์ 5 ข่าวล่าสุด
            headline = news.get('headline_th', news.get('headline', ''))
            summary = news.get('summary_th', news.get('summary', ''))
            
            news_text += f"ข่าวที่ {i}: {headline}\n"
            if summary:
                # จำกัดความยาว summary
                short_summary = summary[:300] if len(summary) > 300 else summary
                news_text += f"รายละเอียด: {short_summary}\n"
            news_text += "\n"
        
        # Prompt สำหรับ Gemini
        prompt = f"""{news_text}

จากข่าวเหล่านี้ ช่วยวิเคราะห์และสรุปดังนี้:

1. **สรุปภาพรวม**: สรุปประเด็นสำคัญของข่าวทั้งหมดในรอบสัปดาห์นี้ (2-3 ประโยค)

2. **ผลกระทบต่อหุ้น**: วิเคราะห์ว่าข่าวเหล่านี้มีผลกระทบต่อราคาหุ้นอย่างไร
   - ใช้ 🟢 สำหรับข่าวดี (Positive)
   - ใช้ 🔴 สำหรับข่าวไม่ดี (Negative)  
   - ใช้ 🟡 สำหรับข่าวกลางๆ (Neutral)

3. **คะแนนความเชื่อมั่น**: ให้คะแนน sentiment จาก -10 ถึง +10
   - -10 ถึง -5 = ข่าวร้ายมาก
   - -4 ถึง -1 = ข่าวไม่ดี
   - 0 = กลางๆ
   - +1 ถึง +4 = ข่าวดี
   - +5 ถึง +10 = ข่าวดีมาก

ตอบเป็นภาษาไทยที่เข้าใจง่าย กระชับ ตรงประเด็น"""

        # เรียก Gemini API
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text.strip()
        
        return None
        
    except Exception as e:
        logger.error(f"Gemini analysis error: {e}")
        return None
        
def translate_news_batch(news_list):
    """แปลข่าวทั้งหมดในคราวเดียวด้วย Deep Translator"""
    try:
        from deep_translator import GoogleTranslator
        
        for news in news_list:
            headline = news.get('headline', '')
            summary = news.get('summary', '')
            
            # แปลหัวข้อ
            if headline:
                try:
                    translator = GoogleTranslator(source='en', target='th')
                    news['headline_th'] = translator.translate(headline)
                except Exception as e:
                    logger.warning(f"Failed to translate headline: {e}")
                    news['headline_th'] = headline
            else:
                news['headline_th'] = ''
            
            # แปลสรุป (Deep Translator จำกัดที่ 5000 ตัวอักษร)
            if summary:
                try:
                    translator = GoogleTranslator(source='en', target='th')
                    if len(summary) > 4500:
                        # ตัดให้สั้นลงถ้ายาวเกินไป
                        news['summary_th'] = translator.translate(summary[:4500]) + "..."
                    else:
                        news['summary_th'] = translator.translate(summary)
                except Exception as e:
                    logger.warning(f"Failed to translate summary: {e}")
                    news['summary_th'] = summary
            else:
                news['summary_th'] = ''
        
        return news_list
        
    except ImportError:
        logger.error("deep-translator not installed, using English")
        for news in news_list:
            news['headline_th'] = news.get('headline', '')
            news['summary_th'] = news.get('summary', '')
        return news_list
    except Exception as e:
        logger.error(f"Translation error: {e}")
        for news in news_list:
            news['headline_th'] = news.get('headline', '')
            news['summary_th'] = news.get('summary', '')
        return news_list

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """แสดงข่าวหุ้น - ต้องระบุ symbol"""
    
    # ตรวจสอบว่ามี argument หรือไม่
    if not context.args or len(context.args) == 0:
        help_text = """📰 **คำสั่งดูข่าว**

**วิธีใช้:**
/news SYMBOL

**ตัวอย่าง:**
/news AAPL - ดูข่าว Apple
/news TSLA - ดูข่าว Tesla
/news MSFT - ดูข่าว Microsoft

💡 จะแสดงข่าว 5 ข่าวล่าสุดใน 7 วันที่ผ่านมา
🌐 ข่าวจะแปลเป็นภาษาไทยอัตโนมัติ
🤖 AI จะวิเคราะห์ว่าเป็นข่าวดีหรือไม่ดี"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return
    
    symbol = context.args[0].strip().upper()
    
    # Validate symbol
    if len(symbol) < 1 or len(symbol) > 6 or not symbol.isalpha():
        await update.message.reply_text(
            "❌ Symbol ไม่ถูกต้อง\nกรุณาใช้ตัวอักษร 1-6 ตัว เช่น: /news AAPL",
            parse_mode='Markdown'
        )
        return
    
    processing = await update.message.reply_text(
        f"📰 กำลังดึงข่าว {symbol}...\n⏳ กำลังแปลและวิเคราะห์...",
        parse_mode='Markdown'
    )
    
    # ตรวจสอบ API Key
    if not FINNHUB_KEY or FINNHUB_KEY == "":
        await processing.edit_text(
            "⚠️ **ไม่พบ FINNHUB_KEY**\n\n"
            "กรุณาตั้งค่า FINNHUB_KEY ใน Environment\n"
            "รับ Free API Key: https://finnhub.io/register",
            parse_mode='Markdown'
        )
        return
    
    # ดึงข้อมูลข่าว
    news_data = get_company_news(symbol)
    
    if not news_data or len(news_data) == 0:
        await processing.edit_text(
            f"❌ ไม่พบข่าวสำหรับ {symbol}\n\n"
            f"อาจเป็นเพราะ:\n"
            f"• Symbol ไม่ถูกต้อง\n"
            f"• ไม่มีข่าวในช่วง 7 วันที่ผ่านมา\n\n"
            f"ลอง /popular เพื่อดูหุ้นยอดนิยม",
            parse_mode='Markdown'
        )
        return
    
    # แปลข่าวเป็นภาษาไทย
    news_data = translate_news_batch(news_data)
    
    # วิเคราะห์ด้วย Gemini AI
    ai_analysis = analyze_news_with_gemini(news_data, symbol)
    
    # สร้างรายงานข่าว
    report = f"📰 **ข่าว {symbol.upper()}**\n"
    report += f"🗓️ 7 วันที่ผ่านมา ({len(news_data)} ข่าว)\n\n"
    
    # เพิ่มการวิเคราะห์จาก AI (ถ้ามี)
    if ai_analysis:
        report += f"🤖 **การวิเคราะห์โดย AI:**\n{ai_analysis}\n\n"
        report += f"{'='*40}\n\n"
    
    # แสดงข่าวแต่ละข่าว
    for i, news in enumerate(news_data, 1):
        headline = news.get('headline_th', news.get('headline', 'ไม่มีหัวข้อ'))
        summary = news.get('summary_th', news.get('summary', ''))
        url = news.get('url', '')
        source = news.get('source', 'Unknown')
        
        # จำกัดความยาว
        if len(headline) > 150:
            headline = headline[:147] + "..."
        
        if summary and len(summary) > 200:
            summary = summary[:197] + "..."
        
        # แปลง timestamp
        timestamp = news.get('datetime', 0)
        if timestamp:
            news_date = datetime.fromtimestamp(timestamp)
            months_th = {
                'Jan': 'ม.ค.', 'Feb': 'ก.พ.', 'Mar': 'มี.ค.', 
                'Apr': 'เม.ย.', 'May': 'พ.ค.', 'Jun': 'มิ.ย.',
                'Jul': 'ก.ค.', 'Aug': 'ส.ค.', 'Sep': 'ก.ย.',
                'Oct': 'ต.ค.', 'Nov': 'พ.ย.', 'Dec': 'ธ.ค.'
            }
            month_en = news_date.strftime('%b')
            month_th = months_th.get(month_en, month_en)
            date_str = f"{news_date.strftime('%d')} {month_th} {news_date.strftime('%H:%M')}"
        else:
            date_str = 'N/A'
        
        report += f"**{i}. {headline}**\n"
        report += f"🗓️ {date_str} | 📡 {source}\n"
        
        if summary:
            report += f"{summary}\n"
        
        if url:
            report += f"🔗 [อ่านเพิ่มเติม]({url})\n"
        
        report += f"\n"
    
    report += f"⏰ อัพเดท: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    
    try:
        await processing.edit_text(report, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception as e:
        # ถ้า message ยาวเกินไป
        if "too long" in str(e).lower():
            # ส่ง AI Analysis แยก
            if ai_analysis:
                analysis_report = f"📰 **ข่าว {symbol.upper()}**\n\n"
                analysis_report += f"🤖 **การวิเคราะห์โดย AI:**\n{ai_analysis}\n\n"
                analysis_report += f"{'='*40}\n\n"
                analysis_report += f"📋 รายละเอียดข่าวจะส่งในข้อความถัดไป..."
                
                await processing.edit_text(analysis_report, parse_mode='Markdown')
            
            # แบ่งส่งข่าว
            half = len(news_data) // 2
            
            # ส่วนที่ 1
            report1 = f"📰 **ข่าว {symbol.upper()}** (1/2)\n\n"
            
            for i, news in enumerate(news_data[:half], 1):
                headline = news.get('headline_th', news.get('headline', 'ไม่มีหัวข้อ'))
                summary = news.get('summary_th', news.get('summary', ''))
                url = news.get('url', '')
                source = news.get('source', 'Unknown')
                
                if len(headline) > 150:
                    headline = headline[:147] + "..."
                if summary and len(summary) > 200:
                    summary = summary[:197] + "..."
                
                timestamp = news.get('datetime', 0)
                if timestamp:
                    news_date = datetime.fromtimestamp(timestamp)
                    months_th = {
                        'Jan': 'ม.ค.', 'Feb': 'ก.พ.', 'Mar': 'มี.ค.', 
                        'Apr': 'เม.ย.', 'May': 'พ.ค.', 'Jun': 'มิ.ย.',
                        'Jul': 'ก.ค.', 'Aug': 'ส.ค.', 'Sep': 'ก.ย.',
                        'Oct': 'ต.ค.', 'Nov': 'พ.ย.', 'Dec': 'ธ.ค.'
                    }
                    month_en = news_date.strftime('%b')
                    month_th = months_th.get(month_en, month_en)
                    date_str = f"{news_date.strftime('%d')} {month_th} {news_date.strftime('%H:%M')}"
                else:
                    date_str = 'N/A'
                
                report1 += f"**{i}. {headline}**\n"
                report1 += f"🗓️ {date_str} | 📡 {source}\n"
                if summary:
                    report1 += f"{summary}\n"
                if url:
                    report1 += f"🔗 [อ่านเพิ่มเติม]({url})\n"
                report1 += f"\n"
            
            await update.message.reply_text(report1, parse_mode='Markdown', disable_web_page_preview=True)
            
            # ส่วนที่ 2
            report2 = f"📰 **ข่าว {symbol.upper()}** (2/2)\n\n"
            
            for i, news in enumerate(news_data[half:], half + 1):
                headline = news.get('headline_th', news.get('headline', 'ไม่มีหัวข้อ'))
                summary = news.get('summary_th', news.get('summary', ''))
                url = news.get('url', '')
                source = news.get('source', 'Unknown')
                
                if len(headline) > 150:
                    headline = headline[:147] + "..."
                if summary and len(summary) > 200:
                    summary = summary[:197] + "..."
                
                timestamp = news.get('datetime', 0)
                if timestamp:
                    news_date = datetime.fromtimestamp(timestamp)
                    months_th = {
                        'Jan': 'ม.ค.', 'Feb': 'ก.พ.', 'Mar': 'มี.ค.', 
                        'Apr': 'เม.ย.', 'May': 'พ.ค.', 'Jun': 'มิ.ย.',
                        'Jul': 'ก.ค.', 'Aug': 'ส.ค.', 'Sep': 'ก.ย.',
                        'Oct': 'ต.ค.', 'Nov': 'พ.ย.', 'Dec': 'ธ.ค.'
                    }
                    month_en = news_date.strftime('%b')
                    month_th = months_th.get(month_en, month_en)
                    date_str = f"{news_date.strftime('%d')} {month_th} {news_date.strftime('%H:%M')}"
                else:
                    date_str = 'N/A'
                
                report2 += f"**{i}. {headline}**\n"
                report2 += f"🗓️ {date_str} | 📡 {source}\n"
                if summary:
                    report2 += f"{summary}\n"
                if url:
                    report2 += f"🔗 [อ่านเพิ่มเติม]({url})\n"
                report2 += f"\n"
            
            report2 += f"⏰ อัพเดท: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            
            await update.message.reply_text(report2, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            logger.error(f"Error sending news: {e}")
            await processing.edit_text(
                f"❌ เกิดข้อผิดพลาดในการส่งข่าว\n{str(e)}",
                parse_mode='Markdown'
            )


def translate_to_thai(text):
    """แปลข้อความเป็นภาษาไทยด้วย Google Translate"""
    try:
        from googletrans import Translator
        translator = Translator()
        result = translator.translate(text, src='en', dest='th')
        return result.text
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text  # ถ้าแปลไม่ได้ ให้ใช้ภาษาอังกฤษเดิม



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
        if price_target and price_target['target_mean']:
            report += f"💎 **มูลค่าและความปลอดภัย (Valuation & Margin of Safety):**\n"
            
            target_mean = price_target['target_mean']
            target_high = price_target['target_high']
            target_low = price_target['target_low']
            num_analysts = price_target['number_of_analysts']
            
            # คำนวณ Upside/Downside Potential
            upside_pct = ((target_mean - current) / current) * 100
            
            report += f"• ราคาเป้าหมายเฉลี่ย: ${target_mean:.2f}\n"
            
            if target_high and target_low:
                report += f"• ช่วงราคาเป้าหมาย: ${target_low:.2f} - ${target_high:.2f}\n"
            
            if num_analysts > 0:
                report += f"• จำนวนนักวิเคราะห์: {num_analysts} คน\n"
            
            # แสดง Upside/Downside
            if upside_pct > 0:
                report += f"\n🎯 **Upside Potential:** +{upside_pct:.1f}%\n"
            else:
                report += f"\n⚠️ **Downside Risk:** {upside_pct:.1f}%\n"
            
            # Margin of Safety Analysis
            report += f"\n📐 **Margin of Safety:**\n"
            
            if upside_pct >= 20:
                report += f"✅ **ดีเยี่ยม** - ราคาต่ำกว่าเป้าหมาย {abs(upside_pct):.1f}%\n"
                report += f"💡 มี Margin of Safety สูง เหมาะสำหรับการลงทุน\n"
            elif upside_pct >= 10:
                report += f"👍 **ดี** - ราคาต่ำกว่าเป้าหมาย {abs(upside_pct):.1f}%\n"
                report += f"💡 มี Margin of Safety ปานกลาง ยังน่าสนใจ\n"
            elif upside_pct >= 0:
                report += f"⚖️ **ยุติธรรม** - ราคาต่ำกว่าเป้าหมาย {abs(upside_pct):.1f}%\n"
                report += f"💡 Margin of Safety น้อย พิจารณาระมัดระวัง\n"
            elif upside_pct >= -10:
                report += f"⚠️ **ระวัง** - ราคาสูงกว่าเป้าหมาย {abs(upside_pct):.1f}%\n"
                report += f"💡 ไม่มี Margin of Safety อาจรอจังหวะที่ดีกว่า\n"
            else:
                report += f"🚨 **เสี่ยง** - ราคาสูงกว่าเป้าหมาย {abs(upside_pct):.1f}%\n"
                report += f"💡 ราคาแพงเกินไป ควรระมัดระวังหรือรอปรับฐาน\n"
            
            report += f"\n"
        
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
            report += f"📊 **ราคาเฉลี่ยเคลื่อนที่:**\n"
            report += f"• EMA 20: ${ema_20:.2f}\n"
            report += f"• EMA 50: ${ema_50:.2f}\n"
            report += f"• EMA 200: ${ema_200:.2f}\n"
            
            if current > ema_20 > ema_50:
                report += f"📈 Uptrend - เทรนด์ขาขึ้นแข็งแกร่ง\n\n"
            elif current < ema_20 < ema_50:
                report += f"📉 Downtrend - เทรนด์ขาลง\n\n"
            else:
                report += f"➡️ Sideways - เทรนด์ไม่ชัดเจน\n\n"
        
        # Bollinger Bands
        if bb_lower and bb_upper:
            report += f"🎯 **Bollinger Bands (20):**\n"
            report += f"• Upper: ${bb_upper:.2f}\n"
            report += f"• Lower: ${bb_lower:.2f}\n"
            bb_position = ((current - bb_lower) / (bb_upper - bb_lower)) * 100
            report += f"• ราคาอยู่ที่: {bb_position:.0f}% ของแบนด์\n"
            
            if current >= bb_upper:
                report += f"⚠️ ราคาสูงกว่าแบนด์บน (อาจปรับตัวลง)\n\n"
            elif current <= bb_lower:
                report += f"💡 ราคาต่ำกว่าแบนด์ล่าง (อาจปรับตัวขึ้น)\n\n"
            else:
                report += f"\n"
            
            report += f"🛡️ **แนวรับ/แนวต้าน:**\n"
            report += f"• Support: ${bb_lower:.2f}\n"
            report += f"• Resistance: ${bb_upper:.2f}\n\n"
        
        # คำแนะนำจากนักวิเคราะห์
        if recommendations:
            report += f"🎯 **คำแนะนำจากนักวิเคราะห์:**\n"
            buy = recommendations.get('buy', 0)
            hold = recommendations.get('hold', 0)
            sell = recommendations.get('sell', 0)
            total = buy + hold + sell
            
            if total > 0:
                buy_pct = (buy / total) * 100
                sell_pct = (sell / total) * 100
                
                report += f"• ซื้อ: {buy} คน ({buy_pct:.0f}%)\n"
                report += f"• ถือ: {hold} คน\n"
                report += f"• ขาย: {sell} คน ({sell_pct:.0f}%)\n"
                
                if buy_pct >= 60:
                    report += f"💚 นักวิเคราะห์ส่วนใหญ่แนะนำ 'ซื้อ'\n\n"
                elif sell_pct >= 40:
                    report += f"❤️ นักวิเคราะห์หลายคนแนะนำ 'ขาย'\n\n"
                else:
                    report += f"⚪ ความเห็นนักวิเคราะห์แบ่งออกเป็น 2 ฝ่าย\n\n"
            else:
                report += f"ไม่มีข้อมูล\n\n"
        
        # สรุปภาพรวม
        report += f"📝 **สรุป:**\n"
        signals = []
        
        # เพิ่ม Valuation signal
        if price_target and price_target['target_mean']:
            target_mean = price_target['target_mean']
            upside_pct = ((target_mean - current) / current) * 100
            
            if upside_pct >= 20:
                signals.append("Valuation: ราคาถูกมาก ⭐⭐⭐")
            elif upside_pct >= 10:
                signals.append("Valuation: ราคาน่าสนใจ ⭐⭐")
            elif upside_pct >= 0:
                signals.append("Valuation: ราคายุติธรรม ⭐")
            else:
                signals.append("Valuation: ราคาแพง ⚠️")
        
        if rsi and rsi <= 30:
            signals.append("RSI: ซื้อ")
        elif rsi and rsi >= 70:
            signals.append("RSI: ขาย")
        
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                signals.append("MACD: Bullish")
            else:
                signals.append("MACD: Bearish")
        
        if ema_20 and ema_50 and current > ema_20 > ema_50:
            signals.append("EMA: Uptrend")
        elif ema_20 and ema_50 and current < ema_20 < ema_50:
            signals.append("EMA: Downtrend")
        
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

# --- Telegram Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """🤖 **ยินดีต้อนรับสู่ Stock Analysis Bot!** 📈

💡 **วิธีใช้งาน:**
- พิมพ์ชื่อหุ้น เช่น: NVDA,NFLX,AMZN,GOOGL,RKLB,V,MSFT,IVV,AVGO,META
- /news SYMBOL - ดูข่าวล่าสุด
- /help - ดูคำแนะนำ
- /popular - ดูหุ้นยอดนิยม

✨ วิเคราะห์ด้วย:
- RSI, MACD, EMA, Bollinger Bands
- Valuation & Margin of Safety
- คำแนะนำจากนักวิเคราะห์
- 📰 ข่าวล่าสุด (NEW!)"""
    await update.message.reply_text(welcome, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """📚 **คู่มือการใช้งาน**

**ตัวชี้วัดที่มี:**
- RSI (14) - Relative Strength Index
เหนือ 70 = Overbought (ซื้อมากเกิน) → สัญญาณขาย อาจมีการปรับตัวลง
ต่ำกว่า 30 = Oversold (ขายมากเกิน) → สัญญาณซื้อ อาจมีการตีกลับ
50 = จุดกลาง แสดงแนวโน้มสมดุล
- MACD - Moving Average Convergence Divergence
MACD ตัดขึ้น Signal = สัญญาณซื้อ (Bullish)
MACD ตัดลง Signal = สัญญาณขาย (Bearish)
Histogram เป็นบวก = แนวโน้มขึ้น
- EMA (20, 50, 200) - Exponential Moving Average
ความหมาย:
EMA 20 = แนวโน้มระยะสั้น (1 เดือน)
EMA 50 = แนวโน้มระยะกลาง (2-3 เดือน)
EMA 200 = แนวโน้มระยะยาว (1 ปี)
การใช้งาน:
ราคาเหนือ EMA → เทรนด์ขึ้น (Uptrend)
ราคาต่ำกว่า EMA → เทรนด์ลง (Downtrend)
Golden Cross: EMA 50 ตัดขึ้น EMA 200 = สัญญาณซื้อแรง
Death Cross: EMA 50 ตัดลง EMA 200 = สัญญาณขายแรง
- Bollinger Bands (20) - แนวรับ/แนวต้าน
- Valuation - ราคาเป้าหมายจากนักวิเคราะห์
- Margin of Safety - ความปลอดภัยของราคา
30-50% = ปลอดภัยมาก เหมาะลงทุนระยะยาว
20-30% = ปลอดภัยปานกลาง
< 20% = ความปลอดภัยต่ำ มีความเสี่ยง
เป็นลบ = ราคาแพงเกินมูลค่า ไม่ควรซื้อ

**ตัวอย่างการใช้:**
พิมพ์: AAPL - วิเคราะห์หุ้น
/news AAPL - ดูข่าวล่าสุด

**คำสั่ง:**
/news SYMBOL - ดูข่าวของหุ้น
/popular - ดูหุ้นยอดนิยม """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def popular_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    popular = """📈 **หุ้นยอดนิยม**

เทคโนโลยี:AAPL, MSFT, GOOGL, META, NVDA, TSLA, AMZN, AVGO, CRM, ADBE, ORCL, TSM, QCOM, ASML, RKLB 

การเงิน:JPM, BAC, V, MA, GS, MS, BRK.B, BLK, WFC, AXP, PYPL, SCHW

พลังงาน:XOM, CVX, COP, SLB, EOG, MPC, PSX, VLO, HES

อุปโภคบริโภค:WMT, KO, PG, MCD, NKE, COST, PEP, HD, SBUX, PM, TGT, LOW

สุขภาพ:JNJ, UNH, PFE, ABBV, LLY, NVO, ISRG, AMGN, MDT, BMY

อุตสาหกรรมและการขนส่ง:GE, CAT, LMT, HON, UPS, RTX, BA, DE, MMM, FEDEX

บริการสื่อสารและบันเทิง:NFLX, DIS, TMUS, CMCSA, VZ, T, CHTR

วัสดุและอุปกรณ์:LIN, APD, FCX, SHW, ECL, NEM

สาธารณูปโภค:NEE, DUKE, SO, D, AEP, EXC

อสังหาริมทรัพย์ (REITs):AMT, PLD, EQIX, CCI, SPG, O

แค่พิมพ์ symbol เพื่อดูข้อมูลและตัวชี้วัด! 🚀"""
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
    application.add_handler(CommandHandler("news", news_command))  # ← เพิ่มบรรทัดนี้
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
