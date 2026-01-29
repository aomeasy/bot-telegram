import os
import logging
import requests
import asyncio 
from functools import lru_cache
from datetime import datetime, timedelta 
from telegram import Update
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")  # เพิ่มบรรทัดนี้

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

def analyze_with_groq(prompt, context_name="analysis"):
    """วิเคราะห์ด้วย Groq API (Fallback)"""
    try:
        if not GROQ_API_KEY or GROQ_API_KEY == "":
            logger.warning("⚠️ No Groq API key found")
            return None
        
        logger.info(f"🔄 Switching to Groq API for {context_name}...")
        
        try:
            from groq import Groq
        except ImportError as e:
            logger.error(f"❌ Cannot import groq: {e}")
            logger.info("💡 Install with: pip install groq")
            return None
        
        client = Groq(api_key=GROQ_API_KEY)
        
        # ลองใช้โมเดลตามลำดับ
        model_names = [
            "llama-3.3-70b-versatile",
            "llama-3.1-70b-versatile",
            "mixtral-8x7b-32768",
            "llama-3.1-8b-instant"
        ]
        
        for model_name in model_names:
            try:
                logger.info(f"✅ Trying Groq model: {model_name}")
                
                chat_completion = client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    model=model_name,
                    temperature=0.7,
                    max_tokens=8000,
                )
                
                if chat_completion.choices and len(chat_completion.choices) > 0:
                    result = chat_completion.choices[0].message.content
                    logger.info(f"✅ Groq API responded with {len(result)} characters")
                    return result.strip()
                    
            except Exception as e:
                logger.warning(f"⚠️ Groq model {model_name} failed: {e}")
                continue
        
        logger.error("❌ All Groq models failed")
        return None
        
    except Exception as e:
        logger.error(f"❌ Groq API error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def analyze_combined_with_gemini(news_list, symbol, technical_data):
    """วิเคราะห์แบบรวม: ข่าว + เทคนิค ด้วย Gemini AI (มี Groq fallback)"""
    try:
        # ตรวจสอบ API Keys
        has_gemini = GEMINI_API_KEY and GEMINI_API_KEY != ""
        has_groq = GROQ_API_KEY and GROQ_API_KEY != ""
        
        if not has_gemini and not has_groq:
            logger.warning("⚠️ No AI API key found (Gemini or Groq)")
            return None
        
        logger.info(f"🔍 Starting Combined AI analysis for {symbol}...")
        
        # เตรียม prompt (ย้ายมาด้านบนเพื่อใช้ร่วมกัน)
        news_text = f"ข่าวล่าสุดของหุ้น {symbol} (5 ข่าวล่าสุด):\n\n"
        for i, news in enumerate(news_list[:5], 1):
            headline = news.get('headline_th', news.get('headline', ''))
            summary = news.get('summary_th', news.get('summary', ''))
            
            news_text += f"ข่าวที่ {i}: {headline}\n"
            if summary:
                short_summary = summary[:300] if len(summary) > 300 else summary
                news_text += f"รายละเอียด: {short_summary}\n"
            news_text += "\n"
        
        # เตรียมข้อมูลเทคนิค
        tech_text = f"\nข้อมูลเทคนิคของหุ้น {symbol}:\n\n"
        tech_text += f"ราคาปัจจุบัน: ${technical_data.get('current', 0):.2f}\n"
        tech_text += f"เปลี่ยนแปลง: {technical_data.get('change_pct', 0):+.2f}%\n\n"
        
        if technical_data.get('rsi'):
            tech_text += f"RSI (14): {technical_data['rsi']:.1f}\n"
            if technical_data['rsi'] <= 30:
                tech_text += "  → Oversold (สัญญาณซื้อ)\n"
            elif technical_data['rsi'] >= 70:
                tech_text += "  → Overbought (สัญญาณขาย)\n"
            else:
                tech_text += "  → Neutral\n"
        
        if technical_data.get('macd') and technical_data.get('macd_signal'):
            tech_text += f"\nMACD: {technical_data['macd']:.2f}\n"
            tech_text += f"Signal: {technical_data['macd_signal']:.2f}\n"
            if technical_data['macd'] > technical_data['macd_signal']:
                tech_text += "  → Bullish (แนวโน้มขึ้น)\n"
            else:
                tech_text += "  → Bearish (แนวโน้มลง)\n"
        
        if technical_data.get('ema_20') and technical_data.get('ema_50'):
            tech_text += f"\nEMA 20: ${technical_data['ema_20']:.2f}\n"
            tech_text += f"EMA 50: ${technical_data['ema_50']:.2f}\n"
            if technical_data.get('ema_200'):
                tech_text += f"EMA 200: ${technical_data['ema_200']:.2f}\n"
            
            current = technical_data.get('current', 0)
            if current > technical_data['ema_20'] > technical_data['ema_50']:
                tech_text += "  → Uptrend (เทรนด์ขาขึ้นแข็งแกร่ง)\n"
            elif current < technical_data['ema_20'] < technical_data['ema_50']:
                tech_text += "  → Downtrend (เทรนด์ขาลง)\n"
            else:
                tech_text += "  → Sideways (เทรนด์ไม่ชัดเจน)\n"
        
        if technical_data.get('bb_lower') and technical_data.get('bb_upper'):
            tech_text += f"\nBollinger Bands:\n"
            tech_text += f"  Upper: ${technical_data['bb_upper']:.2f}\n"
            tech_text += f"  Lower: ${technical_data['bb_lower']:.2f}\n"
            bb_position = technical_data.get('bb_position', 50)
            tech_text += f"  ตำแหน่งราคา: {bb_position:.0f}% ของแบนด์\n"
        
        if technical_data.get('analyst_buy_pct'):
            tech_text += f"\nนักวิเคราะห์:\n"
            tech_text += f"  แนะนำซื้อ: {technical_data['analyst_buy_pct']:.0f}%\n"
        
        if technical_data.get('upside_pct'):
            tech_text += f"\nValuation:\n"
            tech_text += f"  Upside Potential: {technical_data['upside_pct']:+.1f}%\n"
        
        # Prompt เต็ม (ใช้เดิม)
        prompt = f"""{news_text}

{tech_text}

จากข้อมูลข่าวและข้อมูลเทคนิคข้างต้น ช่วยวิเคราะห์แบบรวมดังนี้:

═══════════════════════════════════
PART 1: วิเคราะห์จากข่าว 
═══════════════════════════════════
1. สรุปข่าวและจัดหมวดหมู่:
   - 🟢 ข่าวดี (Positive): ระบุจำนวนและเปอร์เซ็นต์
   - 🟡 ข่าวกลาง (Neutral): ระบุจำนวนและเปอร์เซ็นต์
   - 🔴 ข่าวไม่ดี (Negative): ระบุจำนวนและเปอร์เซ็นต์

2. สรุปประเด็นสำคัญ:
   - ข่าวหลักที่มีผลกระทบต่อราคาหุ้น
   - ปัจจัยบวกและปัจจัยลบที่โดดเด่น

3. คะแนน News Sentiment: -10 ถึง +10
   - -10 ถึง -7 = ข่าวร้ายมาก
   - -6 ถึง -4 = ข่าวไม่ดี
   - -3 ถึง -1 = ค่อนข้างลบ
   - 0 = เป็นกลาง
   - +1 ถึง +3 = ค่อนข้างบวก
   - +4 ถึง +6 = ข่าวดี
   - +7 ถึง +10 = ข่าวดีมาก

═══════════════════════════════════
PART 2: วิเคราะห์จากเทคนิค (Technical)
═══════════════════════════════════
1. สรุปสัญญาณเทคนิครวม:
   - 🟢 Bullish (แนวโน้มขึ้น)
   - 🔴 Bearish (แนวโน้มลง)
   - 🟡 Neutral/Sideways (เทรนด์ไม่ชัด)

2. วิเคราะห์ตัวชี้วัดสำคัญ:
   - RSI: Oversold/Overbought/Neutral
   - MACD: Bullish/Bearish Crossover
   - EMA: Uptrend/Downtrend/Sideways
   - Bollinger Bands: ตำแหน่งราคาในแบนด์

3. แนวรับ/แนวต้านที่สำคัญ:
   - แนวรับ (Support): ระบุราคาและระยะห่างจากราคาปัจจุบัน
   - แนวต้าน (Resistance): ระบุราคาและระยะห่างจากราคาปัจจุบัน

4. ตำแหน่งราคาปัจจุบัน:
   - ราคาอยู่ใกล้แนวรับหรือแนวต้าน
   - มีแนวโน้มไปทางไหน

5. คะแนน Technical Score: -10 ถึง +10

═══════════════════════════════════
PART 3: Valuation & Analyst View
═══════════════════════════════════
1. ราคาเป้าหมายจากนักวิเคราะห์ (ถ้ามี):
   - Upside/Downside Potential: ระบุเป็น %
   - ความเห็นนักวิเคราะห์: Buy/Hold/Sell (เป็น %)

2. Margin of Safety:
   - ราคาปัจจุบันถูกหรือแพงเมื่อเทียบกับเป้าหมาย
   - ระดับความปลอดภัย: สูง/กลาง/ต่ำ/ไม่มี
═══════════════════════════════════
PART 4: สรุปรวมและคำแนะนำ
═══════════════════════════════════
1. เปรียบเทียบสัญญาณ:
   ✓ ข่าว vs เทคนิค สอดคล้องกันหรือไม่?
   ✓ นักวิเคราะห์ vs สัญญาณเทคนิค สอดคล้องหรือไม่?
   
   ⚠️ ถ้าขัดแย้งกัน:
   - ข่าวดีแต่เทคนิคขาลง → เตือนชัดเจน
   - ข่าวไม่ดีแต่เทคนิคขาขึ้น → เตือนชัดเจน
   - นักวิเคราะห์แนะนำซื้อแต่เทคนิคขาลง → เตือนชัดเจน

2. ระดับความเสี่ยง:
   - 🟢 ต่ำ: ข่าวดี + เทคนิคดี + Valuation ดี
   - 🟡 กลาง: มีสัญญาณปนกัน
   - 🔴 สูง: ข่าวไม่ดี + เทคนิคไม่ดี หรือขัดแย้งกันมาก

3. คำแนะนำการเทรด:
   
   📊 Timeframe: ระบุว่าเหมาะสำหรับ
   - Short-term (1-7 วัน)
   - Mid-term (1-4 สัปดาห์)
   - Long-term (1-6 เดือน+)
   
   🎯 Action:
   - 🟢 ซื้อ (BUY): ถ้าทุกสัญญาณดี
   - 🟡 รอดู (WAIT): ถ้าสัญญาณไม่ชัด หรือขัดแย้งกัน
   - 🔴 ขาย/หลีกเลี่ยง (SELL/AVOID): ถ้าสัญญาณไม่ดี
   
   💰 จุดเข้าที่เหมาะสม:
   - ราคาที่แนะนำให้เข้า (ระบุเหตุผล)
   - หรือรอปรับฐานที่ระดับไหน
   
   🛡️ Stop Loss:
   - ระบุราคาที่ควรตั้ง SL (ต่ำกว่าแนวรับ 2-5%)
   - ระบุว่าห่างจากราคาเข้ากี่ %
   
   🎯 Take Profit:
   - เป้าหมายระยะสั้น (TP1): ราคา + %
   - เป้าหมายระยะกลาง (TP2): ราคา + %
   - เป้าหมายระยะยาว (ถ้ามี): ราคา + %
   
4. คะแนนความเชื่อมั่นรวม (Overall Score): -10 ถึง +10
   - รวมน้ำหนัก: News (30%) + Technical (40%) + Valuation (20%) + Analyst (10%)
   - -10 ถึง -5 = ไม่ควรลงทุน
   - -4 ถึง -1 = ระมัดระวังสูง
   - 0 ถึง +3 = ระมัดระวังปานกลาง/รอดู
   - +4 ถึง +6 = น่าสนใจ
   - +7 ถึง +10 = แนะนำให้พิจารณา

5. สรุป:
   - สรุปแก่นของการวิเคราะห์ทั้งหมด

**รูปแบบตอบ:**
- ใช้ภาษาไทยที่เข้าใจง่าย
- กระชับ ตรงประเด็น
- เน้นข้อมูลที่นักลงทุนต้องการรู้จริงๆ
- ห้ามใช้ markdown ** หรือ __ เด็ดขาด
- ใช้ separator ───── หรือ ═════ แบ่งส่วน
- ใช้เพียง emoji และข้อความธรรมดา

เริ่มวิเคราะห์:

"""
        
        # ลอง Gemini ก่อน
        if has_gemini:
            try:
                import google.generativeai as genai
                from google.api_core.exceptions import ResourceExhausted  # เพิ่มบรรทัดนี้
                genai.configure(api_key=GEMINI_API_KEY)
                
                model_names = [
                    'models/gemini-2.5-flash',
                    'models/gemini-flash-latest',
                    'models/gemini-2.0-flash',
                    'models/gemini-2.5-pro',
                    'models/gemini-pro-latest',
                ]
                
                for model_name in model_names:
                    try:
                        model = genai.GenerativeModel(model_name)
                        logger.info(f"✅ Using Gemini model: {model_name}")
                        
                        logger.info("🚀 Calling Gemini API for combined analysis...")
                        response = model.generate_content(prompt)
                        
                        if response and hasattr(response, 'text') and response.text:
                            logger.info(f"📊 Combined analysis result length: {len(response.text)} characters")
                            return response.text.strip()
                            
                    except ResourceExhausted as e:  # เพิ่ม except นี้
                        logger.warning(f"⚠️ Gemini quota exceeded on {model_name}")
                        logger.info("🔄 Switching to Groq API due to rate limit...")
                        break  # ออกจาก loop ทันที
                            
                    except Exception as e:
                        error_msg = str(e).lower()
                        
                        # ตรวจสอบ Rate Limit Error
                        if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg or "resource_exhausted" in error_msg:
                            logger.warning(f"⚠️ Gemini rate limit exceeded: {e}")
                            logger.info("🔄 Switching to Groq API...")
                            break  # ออกจาก loop และไปใช้ Groq
                        else:
                            logger.warning(f"⚠️ Gemini model {model_name} failed: {e}")
                            continue
                
            except ImportError as e:
                logger.error(f"❌ Cannot import google.generativeai: {e}")
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg:
                    logger.warning(f"⚠️ Gemini rate limit exceeded: {e}")
                    logger.info("🔄 Switching to Groq API...")
                else:
                    logger.error(f"❌ Gemini error: {e}")
        
        # ถ้า Gemini ล้มเหลว ให้ใช้ Groq
        if has_groq:
            logger.info("🔄 Falling back to Groq API...")
            result = analyze_with_groq(prompt, f"combined analysis for {symbol}")
            if result:
                return result
        
        logger.error("❌ All AI APIs failed")
        return None
        
    except Exception as e:
        logger.error(f"❌ Combined analysis error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None




def analyze_comparison_with_gemini(stock1_data, stock2_data, symbol1, symbol2):
    """วิเคราะห์เปรียบเทียบ 2 หุ้นด้วย Gemini AI (มี Groq fallback)"""
    try:
        # ตรวจสอบ API Keys
        has_gemini = GEMINI_API_KEY and GEMINI_API_KEY != ""
        has_groq = GROQ_API_KEY and GROQ_API_KEY != ""
        
        if not has_gemini and not has_groq:
            logger.warning("⚠️ No AI API key found (Gemini or Groq) - skipping comparison")
            return None
        
        logger.info(f"🔍 Starting Gemini comparison analysis: {symbol1} vs {symbol2}...")
        
        # ฟังก์ชันช่วยจัดรูปแบบตัวเลข (ป้องกัน None)
        def safe_format(value, format_spec=':.2f', default='N/A'):
            """จัดรูปแบบตัวเลขอย่างปลอดภัย"""
            if value is None:
                return default
            try:
                if format_spec == ':.2f':
                    return f"${value:.2f}"
                elif format_spec == ':.0f':
                    return f"{value:.0f}"
                elif format_spec == ':.1f':
                    return f"{value:.1f}"
                else:
                    return str(value)
            except:
                return default
        
        def safe_percent(value, default='N/A'):
            """แสดงเปอร์เซ็นต์อย่างปลอดภัย"""
            if value is None:
                return default
            try:
                return f"{value:.1f}%"
            except:
                return default
        
        # เตรียมข้อมูล Stock 1
        s1 = stock1_data
        stock1_info = f"""
หุ้น {symbol1}:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 ราคาปัจจุบัน: ${s1['current']:.2f}
📊 เปลี่ยนแปลง: {s1['change_pct']:+.2f}%

📈 ตัวชี้วัดเทคนิค:
- RSI (14): {safe_format(s1.get('rsi'), ':.1f', 'N/A')}
- MACD: {safe_format(s1.get('macd'), ':.2f', 'N/A')} | Signal: {safe_format(s1.get('macd_signal'), ':.2f', 'N/A')}
- EMA 20: {safe_format(s1.get('ema_20'), ':.2f', 'N/A')}
- EMA 50: {safe_format(s1.get('ema_50'), ':.2f', 'N/A')}
- EMA 200: {safe_format(s1.get('ema_200'), ':.2f', 'N/A')}
- Bollinger Upper: {safe_format(s1.get('bb_upper'), ':.2f', 'N/A')}
- Bollinger Lower: {safe_format(s1.get('bb_lower'), ':.2f', 'N/A')}
- ตำแหน่งในแบนด์: {safe_percent(s1.get('bb_position'), 'N/A')}

💎 Valuation:
- Upside Potential: {safe_percent(s1.get('upside_pct'), 'N/A')}
- นักวิเคราะห์แนะนำซื้อ: {safe_percent(s1.get('analyst_buy_pct'), 'N/A')}

📰 ข่าวล่าสุด (5 ข่าว):
{s1.get('news_summary', 'ไม่มีข่าว')}
"""
        
        # เตรียมข้อมูล Stock 2
        s2 = stock2_data
        stock2_info = f"""
หุ้น {symbol2}:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 ราคาปัจจุบัน: ${s2['current']:.2f}
📊 เปลี่ยนแปลง: {s2['change_pct']:+.2f}%

📈 ตัวชี้วัดเทคนิค:
- RSI (14): {safe_format(s2.get('rsi'), ':.1f', 'N/A')}
- MACD: {safe_format(s2.get('macd'), ':.2f', 'N/A')} | Signal: {safe_format(s2.get('macd_signal'), ':.2f', 'N/A')}
- EMA 20: {safe_format(s2.get('ema_20'), ':.2f', 'N/A')}
- EMA 50: {safe_format(s2.get('ema_50'), ':.2f', 'N/A')}
- EMA 200: {safe_format(s2.get('ema_200'), ':.2f', 'N/A')}
- Bollinger Upper: {safe_format(s2.get('bb_upper'), ':.2f', 'N/A')}
- Bollinger Lower: {safe_format(s2.get('bb_lower'), ':.2f', 'N/A')}
- ตำแหน่งในแบนด์: {safe_percent(s2.get('bb_position'), 'N/A')}

💎 Valuation:
- Upside Potential: {safe_percent(s2.get('upside_pct'), 'N/A')}
- นักวิเคราะห์แนะนำซื้อ: {safe_percent(s2.get('analyst_buy_pct'), 'N/A')}

📰 ข่าวล่าสุด (5 ข่าว):
{s2.get('news_summary', 'ไม่มีข่าว')}
"""
        
        prompt = f"""{stock1_info}

{stock2_info}

จากข้อมูลทั้ง 2 หุ้น ให้วิเคราะห์เปรียบเทียบดังนี้:

═══════════════════════════════════
PART 1: เปรียบเทียบตัวชี้วัดเทคนิค
═══════════════════════════════════
📊 Technical Score Comparison:

🔴 {symbol1}:
- RSI: [วิเคราะห์ว่า Oversold/Neutral/Overbought]
- MACD: [วิเคราะห์ว่า Bullish/Bearish]
- EMA Trend: [วิเคราะห์ Uptrend/Downtrend/Sideways]
- BB Position: [วิเคราะห์ตำแหน่งในแบนด์]
- คะแนนเทคนิครวม: X/10

🔵 {symbol2}:
- RSI: [วิเคราะห์ว่า Oversold/Neutral/Overbought]
- MACD: [วิเคราะห์ว่า Bullish/Bearish]
- EMA Trend: [วิเคราะห์ Uptrend/Downtrend/Sideways]
- BB Position: [วิเคราะห์ตำแหน่งในแบนด์]
- คะแนนเทคนิครวม: X/10

🏆 Winner (Technical): [ระบุตัวที่ดีกว่าและเหตุผล]

─────────────────────────────────

═══════════════════════════════════
PART 2: เปรียบเทียบ Valuation
═══════════════════════════════════
💎 Value & Growth Potential:

🔴 {symbol1}:
- Upside Potential: [ระบุ %]
- นักวิเคราะห์มองว่า: [Buy/Hold/Sell]
- Margin of Safety: [สูง/กลาง/ต่ำ/ไม่มี]

🔵 {symbol2}:
- Upside Potential: [ระบุ %]
- นักวิเคราะห์มองว่า: [Buy/Hold/Sell]
- Margin of Safety: [สูง/กลาง/ต่ำ/ไม่มี]

🏆 Winner (Valuation): [ระบุตัวที่ดีกว่าและเหตุผล]

─────────────────────────────────

═══════════════════════════════════
PART 3: เปรียบเทียบข่าวและ Sentiment
═══════════════════════════════════
📰 News Sentiment:

🔴 {symbol1}:
- สัดส่วนข่าว: 🟢 X% | 🟡 X% | 🔴 X%
- News Sentiment Score: X/10
- ประเด็นสำคัญ: [สรุปข่าวหลัก 1-2 ประโยค]

🔵 {symbol2}:
- สัดส่วนข่าว: 🟢 X% | 🟡 X% | 🔴 X%
- News Sentiment Score: X/10
- ประเด็นสำคัญ: [สรุปข่าวหลัก 1-2 ประโยค]

🏆 Winner (News): [ระบุตัวที่ดีกว่าและเหตุผล]

─────────────────────────────────

═══════════════════════════════════
PART 4: การวิเคราะห์แบบแยกตาม Timeframe
═══════════════════════════════════

📅 ระยะสั้น (1-4 สัปดาห์):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 แนะนำ: [SYMBOL]
เหตุผล:
- [เหตุผลที่ 1 - เน้นเทคนิค]
- [เหตุผลที่ 2]
- [เหตุผลที่ 3]

💰 จุดเข้าที่แนะนำ: $XXX
🛡️ Stop Loss: $XXX (X% จากจุดเข้า)
🎯 Target: $XXX (X% Profit)

ระดับความมั่นใจ: [สูง/กลาง/ต่ำ]
ความเสี่ยง: 🟢/🟡/🔴

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 ระยะกลาง (1-3 เดือน):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 แนะนำ: [SYMBOL]
เหตุผล:
- [เหตุผลที่ 1 - เน้นเทรนด์และ Valuation]
- [เหตุผลที่ 2]
- [เหตุผลที่ 3]

💰 จุดเข้าที่แนะนำ: $XXX
🛡️ Stop Loss: $XXX (X% จากจุดเข้า)
🎯 Target: $XXX (X% Profit)

ระดับความมั่นใจ: [สูง/กลาง/ต่ำ]
ความเสี่ยง: 🟢/🟡/🔴

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 ระยะยาว (6 เดือน - 1 ปี+):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 แนะนำ: [SYMBOL]
เหตุผล:
- [เหตุผลที่ 1 - เน้น Fundamentals และแนวโน้มอุตสาหกรรม]
- [เหตุผลที่ 2]
- [เหตุผลที่ 3]

💰 จุดเข้าที่แนะนำ: $XXX หรือรอปรับฐาน
🛡️ Stop Loss: $XXX (X% จากจุดเข้า)
🎯 Target: $XXX (X% Profit)

ระดับความมั่นใจ: [สูง/กลาง/ต่ำ]
ความเสี่ยง: 🟢/🟡/🔴

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

═══════════════════════════════════
PART 5: คะแนนรวมและคำแนะนำสุดท้าย
═══════════════════════════════════

📊 คะแนนรวมทุกด้าน:

🔴 {symbol1}: X/10
   • Technical: X/10
   • Valuation: X/10
   • News Sentiment: X/10

🔵 {symbol2}: X/10
   • Technical: X/10
   • Valuation: X/10
   • News Sentiment: X/10

━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏆 **คำตอบขั้นสุดท้าย:**

ถ้าเลือกได้อันเดียว ควรซื้อ: **[SYMBOL]**

เหตุผล: [สรุปเหตุผลหลักๆ 2-3 ประโยค]

⚠️ **ข้อควรระวัง:**
- {symbol1}: [จุดอ่อนหลัก]
- {symbol2}: [จุดอ่อนหลัก]

💡 **กลยุทธ์ทางเลือก:**
[เสนอกลยุทธ์เช่น ถือทั้ง 2 ตัว, รอจังหวะ, หรือ DCA]

═══════════════════════════════════

**รูปแบบตอบ:**
- ใช้ภาษาไทยที่เข้าใจง่าย
- กระชับ ตรงประเด็น
- ห้ามใช้ markdown ** หรือ __ เด็ดขาด
- ใช้ separator ───── หรือ ═════ แบ่งส่วน
- ใช้เพียง emoji และข้อความธรรมดา
- ต้องมีคำตอบที่ชัดเจนว่าควรซื้อตัวไหน
- ถ้าข้อมูลบางอย่างเป็น N/A ให้วิเคราะห์จากข้อมูลที่มี

เริ่มวิเคราะห์:
"""
        
        # ลอง Gemini ก่อน
        if has_gemini:
            try:
                import google.generativeai as genai
                from google.api_core.exceptions import ResourceExhausted
                genai.configure(api_key=GEMINI_API_KEY)
                
                model_names = [
                    'models/gemini-2.5-flash',
                    'models/gemini-flash-latest',
                    'models/gemini-2.0-flash',
                    'models/gemini-2.5-pro',
                    'models/gemini-pro-latest',
                ]
                
                for model_name in model_names:
                    try:
                        model = genai.GenerativeModel(model_name)
                        logger.info(f"✅ Using Gemini model: {model_name}")
                        
                        logger.info("🚀 Calling Gemini API for comparison analysis...")
                        response = model.generate_content(prompt)
                        
                        logger.info("✅ Gemini API responded")
                        
                        if response and hasattr(response, 'text') and response.text:
                            logger.info(f"📊 Comparison analysis result length: {len(response.text)} characters")
                            return response.text.strip()
                        else:
                            logger.warning("⚠️ Gemini returned empty response")
                            continue
                            
                    except ResourceExhausted as e:  # เพิ่ม except นี้
                        logger.warning(f"⚠️ Gemini quota exceeded on {model_name}")
                        logger.info("🔄 Switching to Groq API due to rate limit...")
                        break
                            
                    except Exception as e:
                        error_msg = str(e).lower()
                        
                        # ตรวจสอบ Rate Limit Error
                        if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg or "resource_exhausted" in error_msg:
                            logger.warning(f"⚠️ Gemini rate limit exceeded on {model_name}: {e}")
                            logger.info("🔄 Switching to Groq API...")
                            break  # ออกจาก loop และไปใช้ Groq
                        else:
                            logger.warning(f"⚠️ Gemini model {model_name} failed: {e}")
                            continue
                
            except ImportError as e:
                logger.error(f"❌ Cannot import google.generativeai: {e}")
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg or "resource_exhausted" in error_msg:
                    logger.warning(f"⚠️ Gemini rate limit exceeded: {e}")
                    logger.info("🔄 Switching to Groq API...")
                else:
                    logger.error(f"❌ Gemini comparison error: {e}")
        
        # ถ้า Gemini ล้มเหลว ให้ใช้ Groq
        if has_groq:
            logger.info("🔄 Falling back to Groq API for comparison...")
            result = analyze_with_groq(prompt, f"comparison {symbol1} vs {symbol2}")
            if result:
                return result
        
        logger.error("❌ All AI APIs failed for comparison")
        return None
        
    except Exception as e:
        logger.error(f"❌ Comparison Gemini analysis error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
 

async def get_stock_data_for_comparison(symbol):
    """ดึงข้อมูลหุ้นสำหรับการเปรียบเทียบ"""
    try:
        # ดึงข้อมูลเทคนิค
        quote = get_quote(symbol)
        if not quote or 'close' not in quote:
            return None
        
        current = float(quote['close'])
        prev_close = float(quote.get('previous_close', current))
        change = current - prev_close
        change_pct = (change / prev_close) * 100
        
        # รวบรวมข้อมูลเทคนิค
        stock_data = {
            'symbol': symbol,
            'current': current,
            'change_pct': change_pct,
            'rsi': get_rsi(symbol),
            'macd': None,
            'macd_signal': None,
            'ema_20': get_ema(symbol, 20),
            'ema_50': get_ema(symbol, 50),
            'ema_200': get_ema(symbol, 200),
            'bb_lower': None,
            'bb_upper': None,
            'bb_position': None,
            'analyst_buy_pct': None,
            'upside_pct': None,
            'news_summary': ''
        }
        
        # MACD
        macd, macd_signal = get_macd(symbol)
        if macd is not None:
            stock_data['macd'] = macd
            stock_data['macd_signal'] = macd_signal
        
        # Bollinger Bands
        bb_lower, bb_upper = get_bbands(symbol)
        if bb_lower and bb_upper:
            stock_data['bb_lower'] = bb_lower
            stock_data['bb_upper'] = bb_upper
            stock_data['bb_position'] = ((current - bb_lower) / (bb_upper - bb_lower)) * 100
        
        # Analyst recommendations
        recommendations = get_analyst_recommendations(symbol)
        if recommendations:
            buy = recommendations.get('buy', 0)
            hold = recommendations.get('hold', 0)
            sell = recommendations.get('sell', 0)
            total = buy + hold + sell
            if total > 0:
                stock_data['analyst_buy_pct'] = (buy / total) * 100
        
        # Price target
        price_target = get_price_target(symbol)
        if price_target and price_target['target_mean']:
            target_mean = price_target['target_mean']
            stock_data['upside_pct'] = ((target_mean - current) / current) * 100
        
        # ดึงข่าว
        news_data = get_company_news(symbol, days=7)
        if news_data and len(news_data) > 0:
            news_data = translate_news_batch(news_data)
            
            # สร้างสรุปข่าว
            news_summary = ""
            for i, news in enumerate(news_data[:5], 1):
                headline = news.get('headline_th', news.get('headline', ''))
                if len(headline) > 100:
                    headline = headline[:97] + "..."
                news_summary += f"{i}. {headline}\n"
            
            stock_data['news_summary'] = news_summary.strip()
        
        return stock_data
        
    except Exception as e:
        logger.error(f"Error getting stock data for {symbol}: {e}")
        return None


def analyze_news_with_gemini(news_list, symbol):
    """วิเคราะห์ข่าวด้วย Gemini AI (มี Groq fallback)"""
    try:
        # ตรวจสอบ API Keys
        has_gemini = GEMINI_API_KEY and GEMINI_API_KEY != ""
        has_groq = GROQ_API_KEY and GROQ_API_KEY != ""
        
        if not has_gemini and not has_groq:
            logger.warning("⚠️ No AI API key found (Gemini or Groq) - skipping news analysis")
            return None
        
        logger.info(f"🔍 Starting AI news analysis for {symbol}...")
        
        # เตรียมข้อมูลข่าว
        news_text = f"ข่าวล่าสุดของหุ้น {symbol}:\n\n"
        for i, news in enumerate(news_list[:5], 1):
            headline = news.get('headline_th', news.get('headline', ''))
            summary = news.get('summary_th', news.get('summary', ''))
            
            news_text += f"ข่าวที่ {i}: {headline}\n"
            if summary:
                short_summary = summary[:300] if len(summary) > 300 else summary
                news_text += f"รายละเอียด: {short_summary}\n"
            news_text += "\n"
        
        logger.info(f"📝 Prepared {len(news_list)} news items for analysis")
        
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
        
        # ลอง Gemini ก่อน
        if has_gemini:
            try:
                import google.generativeai as genai
                from google.api_core.exceptions import ResourceExhausted
                genai.configure(api_key=GEMINI_API_KEY)
                
                # ใช้โมเดลที่ใช้งานได้จริง
                model_names = [
                    'models/gemini-2.5-flash',          # แนะนำ - เร็วและดี
                    'models/gemini-flash-latest',       # ทางเลือกที่ 2
                    'models/gemini-2.0-flash',          # ทางเลือกที่ 3
                    'models/gemini-2.5-pro',            # ดีที่สุดแต่ช้ากว่า
                    'models/gemini-pro-latest',         # fallback
                ]
                
                for model_name in model_names:
                    try:
                        model = genai.GenerativeModel(model_name)
                        logger.info(f"✅ Using Gemini model: {model_name}")
                        
                        logger.info("🚀 Calling Gemini API for news analysis...")
                        
                        # Generate content
                        response = model.generate_content(prompt)
                        
                        logger.info("✅ Gemini API responded")
                        
                        if response and hasattr(response, 'text') and response.text:
                            logger.info(f"📊 Analysis result length: {len(response.text)} characters")
                            return response.text.strip()
                        else:
                            logger.warning("⚠️ Gemini returned empty response")
                            continue
                            
                    except ResourceExhausted as e:  # เพิ่ม except นี้
                        logger.warning(f"⚠️ Gemini quota exceeded on {model_name}")
                        logger.info("🔄 Switching to Groq API due to rate limit...")
                        break
                            
                    except Exception as e:
                        error_msg = str(e).lower()
                        
                        # ตรวจสอบ Rate Limit Error
                        if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg or "resource_exhausted" in error_msg:
                            logger.warning(f"⚠️ Gemini rate limit exceeded on {model_name}: {e}")
                            logger.info("🔄 Switching to Groq API...")
                            break  # ออกจาก loop และไปใช้ Groq
                        else:
                            logger.warning(f"⚠️ Cannot use {model_name}: {e}")
                            continue
                
            except ImportError as e:
                logger.error(f"❌ Cannot import google.generativeai: {e}")
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg or "resource_exhausted" in error_msg:
                    logger.warning(f"⚠️ Gemini rate limit exceeded: {e}")
                    logger.info("🔄 Switching to Groq API...")
                else:
                    logger.error(f"❌ Gemini news analysis error: {e}")
        
        # ถ้า Gemini ล้มเหลว ให้ใช้ Groq
        if has_groq:
            logger.info("🔄 Falling back to Groq API for news analysis...")
            result = analyze_with_groq(prompt, f"news analysis for {symbol}")
            if result:
                return result
        
        logger.error("❌ All AI APIs failed for news analysis")
        return None
        
    except Exception as e:
        logger.error(f"❌ News analysis error: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
        
def escape_markdown(text):
    """Escape markdown special characters"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
    
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

🤖 ต้องการให้ AI วิเคราะห์? ใช้ /ai SYMBOL"""
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
        f"📰 กำลังดึงข่าว {symbol}...\n⏳ กำลังแปลเป็นภาษาไทย...",
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
    
    # สร้างรายงานข่าว (ไม่มี AI)
    report = f"📰 **ข่าว {symbol.upper()}**\n"
    report += f"🗓️ 7 วันที่ผ่านมา ({len(news_data)} ข่าว)\n\n"
    
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
        
        headline_escaped = escape_markdown(headline) if headline else 'ไม่มีหัวข้อ'
        report += f"**{i}. {headline_escaped}**\n"
        report += f"🗓️ {date_str} | 📡 {source}\n"
        
        if summary:
            report += f"{summary}\n"
        
        if url:
            report += f"🔗 [อ่านเพิ่มเติม]({url})\n"
        
        report += f"\n"
    
    report += f"🤖 ต้องการให้ AI วิเคราะห์? ใช้ /ai {symbol}\n"
    report += f"⏰ อัพเดท: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    
    try:
        await processing.edit_text(report, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception as e:
        # ถ้า message ยาวเกินไป ให้แบ่งส่ง
        if "too long" in str(e).lower():
            # แบ่งส่ง 2 ส่วน (โค้ดเดิม...)
            # ... (คงโค้ดเดิมไว้)
            pass
        else:
            logger.error(f"Error sending news: {e}")




# Constants
MAX_HEADLINE_LENGTH = 100
NEWS_DAYS_RANGE = 7
MAX_NEWS_TO_ANALYZE = 5
MIN_SYMBOL_LENGTH = 1
MAX_SYMBOL_LENGTH = 6
CACHE_TTL_SECONDS = 300  # 5 minutes

# Simple in-memory cache
_analysis_cache = {}

def _get_cache_key(symbol: str) -> str:
    """Generate cache key for analysis"""
    return f"ai_analysis_{symbol}_{datetime.now().strftime('%Y%m%d%H%M')}"

def _get_cached_analysis(symbol: str):
    """Get cached analysis if exists and not expired"""
    cache_key = _get_cache_key(symbol)
    if cache_key in _analysis_cache:
        cached_data, timestamp = _analysis_cache[cache_key]
        if datetime.now() - timestamp < timedelta(seconds=CACHE_TTL_SECONDS):
            return cached_data
    return None

def _cache_analysis(symbol: str, data):
    """Cache analysis result"""
    cache_key = _get_cache_key(symbol)
    _analysis_cache[cache_key] = (data, datetime.now())
    
    # Clean old cache entries
    current_time = datetime.now()
    keys_to_delete = [
        k for k, (_, ts) in _analysis_cache.items()
        if current_time - ts > timedelta(seconds=CACHE_TTL_SECONDS * 2)
    ]
    for k in keys_to_delete:
        del _analysis_cache[k]




def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2"""
    # Characters that need to be escaped in MarkdownV2
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def clean_markdown_text(text: str) -> str:
    """Clean text to prevent Markdown parsing errors"""
    # Remove or escape problematic characters
    # Keep only basic markdown: **bold** and _italic_
    
    # First, protect intentional markdown
    text = text.replace('**', '<!BOLD!>')
    text = text.replace('__', '<!ITALIC!>')
    
    # Escape remaining underscores and asterisks
    text = text.replace('_', '\\_')
    text = text.replace('*', '\\*')
    
    # Restore intentional markdown
    text = text.replace('<!BOLD!>', '**')
    text = text.replace('<!ITALIC!>', '_')
    
    # Escape other special characters that might cause issues
    special_chars = ['[', ']', '(', ')', '~', '`', '>', '#', '+', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        # Don't escape if it's part of a link or intentional markdown
        if char not in ['(', ')', '[', ']']:  # Keep these for links
            text = text.replace(char, f'\\{char}')
    
    return text

async def ai_analysis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """วิเคราะห์ข่าวหุ้นด้วย AI - ต้องระบุ symbol"""
    
    # ตรวจสอบว่ามี argument หรือไม่
    if not context.args or len(context.args) == 0:
        help_text = """🤖 **AI วิเคราะห์ข่าว**

**วิธีใช้:**
/ai SYMBOL

**ตัวอย่าง:**
/ai AAPL - วิเคราะห์ข่าว Apple
/ai TSLA - วิเคราะห์ข่าว Tesla
/ai MSFT - วิเคราะห์ข่าว Microsoft

💡 AI จะวิเคราะห์ข่าว 5 ข่าวล่าสุดและให้:
   • คะแนนความเชื่อมั่น (-10 ถึง +10)
   • แยกข่าวดี/ข่าวไม่ดี/ข่าวกลาง
   • สรุปภาพรวมและคำแนะนำ

⚡ ใช้ Gemini AI วิเคราะห์"""
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return
    
    symbol = context.args[0].strip().upper()
    
    # Validate symbol
    if len(symbol) < 1 or len(symbol) > 6 or not symbol.isalpha():
        await update.message.reply_text(
            "❌ Symbol ไม่ถูกต้อง\nกรุณาใช้ตัวอักษร 1-6 ตัว เช่น: /ai AAPL",
            parse_mode='Markdown'
        )
        return
    
    processing = await update.message.reply_text(
        f"🤖 กำลังวิเคราะห์ข่าว {symbol} ด้วย AI...\n⏳ กรุณารอสักครู่...",
        parse_mode='Markdown'
    )
    
    # ตรวจสอบ FINNHUB_KEY
    if not FINNHUB_KEY or FINNHUB_KEY == "":
        await processing.edit_text(
            "⚠️ **ไม่พบ FINNHUB_KEY**\n\n"
            "กรุณาตั้งค่า FINNHUB_KEY ใน Environment\n"
            "รับ Free API Key: https://finnhub.io/register",
            parse_mode='Markdown'
        )
        return
    
    # ตรวจสอบ GEMINI_KEY
    if not GEMINI_API_KEY or GEMINI_API_KEY == "":
        await processing.edit_text(
            "⚠️ **ไม่พบ GEMINI_API_KEY**\n\n"
            "กรุณาตั้งค่า GEMINI_API_KEY ใน Environment\n"
            "รับ Free API Key: https://makersuite.google.com/app/apikey",
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
    
    if not ai_analysis:
        await processing.edit_text(
            f"❌ **ไม่สามารถวิเคราะห์ข่าวได้**\n\n"
            f"อาจเป็นเพราะ:\n"
            f"• Gemini API มีปัญหา\n"
            f"• API Key ไม่ถูกต้อง\n"
            f"• Network error\n\n"
            f"💡 ลอง /news {symbol} เพื่อดูข่าวโดยไม่มี AI",
            parse_mode='Markdown'
        )
        return
    
    # นับจำนวนข่าวแต่ละประเภท
    positive_count = ai_analysis.lower().count('🟢')
    negative_count = ai_analysis.lower().count('🔴')
    neutral_count = ai_analysis.lower().count('🟡')
    
    total_news = max(positive_count + negative_count + neutral_count, len(news_data))
    if total_news > 0:
        positive_pct = int((positive_count / total_news) * 100)
        negative_pct = int((negative_count / total_news) * 100)
        neutral_pct = int((neutral_count / total_news) * 100)
    else:
        positive_pct = negative_pct = neutral_pct = 0
    
    # สร้างรายงานการวิเคราะห์แบบใหม่
    report = f"🤖 **AI วิเคราะห์ {symbol.upper()}**\n"
    
    # แสดงคะแนนความเชื่อมั่น (พยายามดึงจาก AI analysis)
    score_line = ""
    if "คะแนนความเชื่อมั่น:" in ai_analysis:
        # ดึงคะแนนจาก AI analysis
        import re
        score_match = re.search(r'คะแนนความเชื่อมั่น:\s*([+-]?\d+)', ai_analysis)
        if score_match:
            score = int(score_match.group(1))
            if score >= 7:
                sentiment = "ข่าวดีมาก 🟢"
            elif score >= 4:
                sentiment = "ข่าวดี 🟢"
            elif score >= 1:
                sentiment = "ค่อนข้างดี 🟢"
            elif score == 0:
                sentiment = "เป็นกลาง 🟡"
            elif score >= -3:
                sentiment = "ค่อนข้างไม่ดี 🔴"
            elif score >= -6:
                sentiment = "ข่าวไม่ดี 🔴"
            else:
                sentiment = "ข่าวไม่ดีมาก 🔴"
            
            score_line = f"📊 คะแนนความเชื่อมั่น: {score:+d}/10 ({sentiment})\n"
    
    report += score_line
    
    # แสดงสัดส่วนข่าว
    if total_news > 0:
        report += f"📈 สัดส่วนข่าว: 🟢 {positive_pct}% | 🟡 {neutral_pct}% | 🔴 {negative_pct}%\n"
    
    report += f"\n{'─'*35}\n"
    
    # ทำความสะอาด AI analysis ก่อนแสดงผล
    # แทนที่ markdown ที่อาจทำให้เกิด error
    cleaned_analysis = ai_analysis
    
    # ลบหรือแทนที่ markdown ที่ซับซ้อน
    # เก็บเฉพาะ text ธรรมดา โดยไม่ใช้ markdown ในส่วนของ AI analysis
    # เพื่อป้องกัน parse error
    
    report += cleaned_analysis
    
    # เพิ่ม disclaimer และข้อมูลเพิ่มเติม
    #report += f"\n\n{'─'*35}\n\n"
    #report += f"⚠️ **คำเตือน:** AI Analysis - ไม่ใช่คำแนะนำทางการเงิน\n"
    report += f"📅 วิเคราะห์จากข่าว {len(news_data)} ข่าวใน 7 วันล่าสุด\n"
    report += f"⏰ อัพเดท: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
    report += f"💡 ดูข่าวแบบละเอียด: /news {symbol}"
    
    try:
        await processing.edit_text(report, parse_mode='Markdown', disable_web_page_preview=True)
    except telegram.error.BadRequest as e:
        # ถ้า Markdown parse error ให้ลองส่งแบบไม่มี Markdown
        if "can't parse entities" in str(e).lower() or "can't find end" in str(e).lower():
            logger.warning(f"Markdown parse error, sending without markdown: {e}")
            try:
                # ส่งแบบ plain text (ไม่มี parse_mode)
                plain_report = report.replace('**', '').replace('_', '').replace('`', '')
                await processing.edit_text(plain_report, disable_web_page_preview=True)
            except Exception as e2:
                logger.error(f"Error sending plain text: {e2}")
                await processing.edit_text(
                    f"❌ เกิดข้อผิดพลาดในการแสดงผล\n\n"
                    f"กรุณาลองใหม่อีกครั้ง",
                )
        else:
            raise
    except Exception as e:
        # ถ้า message ยาวเกินไป ให้ส่งแบบย่อ
        if "too long" in str(e).lower() or "message is too long" in str(e).lower():
            # แยกเฉพาะส่วนสำคัญ
            short_report = f"🤖 **AI วิเคราะห์ {symbol.upper()}**\n"
            short_report += score_line
            
            if total_news > 0:
                short_report += f"📈 สัดส่วนข่าว: 🟢 {positive_pct}% | 🟡 {neutral_pct}% | 🔴 {negative_pct}%\n"
            
            short_report += f"\n{'─'*35}\n\n"
            
            # ตัดเฉพาะสรุปภาพรวมและคะแนน
            if "1. สรุปภาพรวม:" in ai_analysis:
                summary_start = ai_analysis.find("1. สรุปภาพรวม:")
                summary_end = ai_analysis.find("2. ผลกระทบต่อหุ้น:")
                if summary_end == -1:
                    summary_end = ai_analysis.find("3. คะแนนความเชื่อมั่น:")
                
                if summary_end > summary_start:
                    summary = ai_analysis[summary_start:summary_end].strip()
                    short_report += summary + "\n\n"
            
            # เพิ่มคะแนนความเชื่อมั่น
            if "3. คะแนนความเชื่อมั่น:" in ai_analysis:
                score_section = ai_analysis[ai_analysis.find("3. คะแนนความเชื่อมั่น:"):]
                short_report += score_section.strip() + "\n\n"
            
            short_report += f"{'─'*35}\n\n"
            short_report += f"📅 วิเคราะห์จาก {len(news_data)} ข่าวใน 7 วัน\n"
            short_report += f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
            short_report += f"💡 ดูข่าวเต็ม: /news {symbol}"
            
            try:
                await processing.edit_text(short_report, parse_mode='Markdown', disable_web_page_preview=True)
            except telegram.error.BadRequest as e2:
                # ถ้ายังมี Markdown error อีก ส่งแบบ plain text
                if "can't parse entities" in str(e2).lower():
                    logger.warning(f"Short report markdown error, sending plain text")
                    plain_report = short_report.replace('**', '').replace('_', '').replace('`', '')
                    await processing.edit_text(plain_report, disable_web_page_preview=True)
                else:
                    logger.error(f"Error sending short AI analysis: {e2}")
                    await processing.edit_text(
                        f"❌ ข้อความยาวเกินไป\n\n"
                        f"💡 ลอง /news {symbol} เพื่อดูข่าวแทน",
                    )
            except Exception as e2:
                logger.error(f"Error sending short AI analysis: {e2}")
                await processing.edit_text(
                    f"❌ ข้อความยาวเกินไป\n\n"
                    f"💡 ลอง /news {symbol} เพื่อดูข่าวแทน",
                )
        else:
            logger.error(f"Error sending AI analysis: {e}")
            await processing.edit_text(
                f"❌ เกิดข้อผิดพลาดในการส่งผล\n\n"
                f"กรุณาลองใหม่อีกครั้ง หรือติดต่อผู้ดูแลระบบ",
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


async def aiplus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """วิเคราะห์แบบรวม: ข่าว + เทคนิค ด้วย AI"""
    
    # ตรวจสอบว่ามี argument หรือไม่
    if not context.args or len(context.args) == 0:
        # สร้างเมนูหมวดหมู่หุ้น
        keyboard = [
            [InlineKeyboardButton("🔥 ยอดนิยมสุด (Top Picks)", callback_data="cat_toppicks")],
            [InlineKeyboardButton("🤖 AI & เทคโนโลยี", callback_data="cat_ai_tech")],
            [InlineKeyboardButton("💰 การเงิน & FinTech", callback_data="cat_finance")],
            [InlineKeyboardButton("🛒 อุปโภคบริโภค", callback_data="cat_consumer")],
            [InlineKeyboardButton("🏥 สุขภาพ & ยา", callback_data="cat_healthcare")],
            [InlineKeyboardButton("⚡ พลังงาน", callback_data="cat_energy")],
            [InlineKeyboardButton("🚀 อวกาศ & กลาโหม", callback_data="cat_aerospace")],
            [InlineKeyboardButton("📱 สื่อสาร & บันเทิง", callback_data="cat_media")],
            [InlineKeyboardButton("🏭 อุตสาหกรรม", callback_data="cat_industrial")],
            [InlineKeyboardButton("📊 ETF & กองทุน", callback_data="cat_etf")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        help_text = """🚀 **AI วิเคราะห์เต็มรูปแบบ (News + Technical)**

**เลือกหมวดหมู่หุ้นที่สนใจ:**

💡 **คุณสมบัติพิเศษ:**
✅ วิเคราะห์ครบมิติ - ทั้ง Fundamental (ข่าว) + Technical (กราฟ)
✅ ยืนยันสัญญาณ - ถ้าข่าวดีแต่เทคนิคขาลง = สัญญาณเตือน
✅ จับจังหวะซื้อขาย - รู้ว่าควรเข้าตอนไหน
✅ คำแนะนำ Stop Loss & Take Profit
✅ ลดความเสี่ยง - ไม่พึ่งข้อมูลด้านเดียว

**หรือพิมพ์:** `/aiplus SYMBOL`

⚡ ใช้ Gemini AI วิเคราะห์แบบรวม"""
        
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
        return
    
    # ถ้ามี argument ให้ทำการวิเคราะห์ตามปกติ
    symbol = context.args[0].strip().upper()
    
    # Validate symbol
    if len(symbol) < MIN_SYMBOL_LENGTH or len(symbol) > MAX_SYMBOL_LENGTH or not symbol.isalpha():
        await update.message.reply_text(
            "❌ Symbol ไม่ถูกต้อง\nกรุณาใช้ตัวอักษร 1-6 ตัว เช่น: /aiplus AAPL",
            parse_mode='Markdown'
        )
        return
    
    processing = await update.message.reply_text(
        f"🚀 กำลังวิเคราะห์ {symbol} แบบเต็มรูปแบบ...\n"
        f"⏳ กำลังรวบรวมข้อมูล:\n"
        f"  • ข่าวล่าสุด\n"
        f"  • ตัวชี้วัดเทคนิค\n"
        f"  • ข้อมูลนักวิเคราะห์\n"
        f"  • AI กำลังวิเคราะห์...",
        parse_mode='Markdown'
    )
    
    # เรียกใช้ฟังก์ชันวิเคราะห์
    await perform_aiplus_analysis(processing, symbol)



async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """เปรียบเทียบ 2 หุ้น - /compare SYMBOL1 SYMBOL2"""
    
    # ตรวจสอบ arguments
    if not context.args or len(context.args) < 2:
        help_text = """⚖️ **เปรียบเทียบหุ้น 2 ตัว**

**วิธีใช้:**
/compare SYMBOL1 SYMBOL2

**ตัวอย่าง:**
/compare AMZN NVDA - เปรียบเทียบ Amazon vs Nvidia
/compare AAPL MSFT - เปรียบเทียบ Apple vs Microsoft
/compare TSLA RKLB - เปรียบเทียบ Tesla vs Rocket Lab

💡 **AI จะวิเคราะห์:**
✅ ตัวชี้วัดเทคนิค (RSI, MACD, EMA, BB)
✅ Valuation & Upside Potential
✅ ข่าวและ Sentiment
✅ แนะนำแยกตาม Timeframe:
   • ระยะสั้น (1-4 สัปดาห์)
   • ระยะกลาง (1-3 เดือน)
   • ระยะยาว (6 เดือน - 1 ปี+)

🎯 **ได้คำตอบชัดเจน:** ควรซื้อตัวไหน และทำไม"""
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
        return
    
    symbol1 = context.args[0].strip().upper()
    symbol2 = context.args[1].strip().upper()
    
    # Validate symbols
    for symbol in [symbol1, symbol2]:
        if len(symbol) < MIN_SYMBOL_LENGTH or len(symbol) > MAX_SYMBOL_LENGTH or not symbol.isalpha():
            await update.message.reply_text(
                f"❌ Symbol '{symbol}' ไม่ถูกต้อง\n"
                f"กรุณาใช้ตัวอักษร 1-6 ตัว เช่น: /compare AAPL MSFT",
                parse_mode='Markdown'
            )
            return
    
    # ตรวจสอบว่าไม่ใช่หุ้นตัวเดียวกัน
    if symbol1 == symbol2:
        await update.message.reply_text(
            "❌ กรุณาเลือกหุ้น 2 ตัวที่แตกต่างกัน",
            parse_mode='Markdown'
        )
        return
    
    processing = await update.message.reply_text(
        f"⚖️ กำลังเปรียบเทียบ {symbol1} vs {symbol2}...\n\n"
        f"⏳ กำลังรวบรวมข้อมูล:\n"
        f"  • {symbol1}: ราคา, RSI, MACD, EMA, ข่าว...\n"
        f"  • {symbol2}: ราคา, RSI, MACD, EMA, ข่าว...\n"
        f"  • 🤖 AI กำลังวิเคราะห์เปรียบเทียบ...",
        parse_mode='Markdown'
    )
    
    # ตรวจสอบ API Keys
    if not TWELVE_DATA_KEY or TWELVE_DATA_KEY == "":
        await processing.edit_text(
            "⚠️ **ไม่พบ TWELVE_DATA_KEY**\n\n"
            "กรุณาตั้งค่า TWELVE_DATA_KEY ใน Environment\n"
            "รับ Free API Key: https://twelvedata.com/apikey",
            parse_mode='Markdown'
        )
        return
    
    if not FINNHUB_KEY or FINNHUB_KEY == "":
        await processing.edit_text(
            "⚠️ **ไม่พบ FINNHUB_KEY**\n\n"
            "กรุณาตั้งค่า FINNHUB_KEY ใน Environment\n"
            "รับ Free API Key: https://finnhub.io/register",
            parse_mode='Markdown'
        )
        return
    
    if not GEMINI_API_KEY or GEMINI_API_KEY == "":
        await processing.edit_text(
            "⚠️ **ไม่พบ GEMINI_API_KEY**\n\n"
            "กรุณาตั้งค่า GEMINI_API_KEY ใน Environment\n"
            "รับ Free API Key: https://makersuite.google.com/app/apikey",
            parse_mode='Markdown'
        )
        return
    
    # ดึงข้อมูลหุ้นทั้ง 2 ตัว
    stock1_data = await get_stock_data_for_comparison(symbol1)
    stock2_data = await get_stock_data_for_comparison(symbol2)
    
    # ตรวจสอบว่าดึงข้อมูลได้หรือไม่
    if not stock1_data:
        await processing.edit_text(
            f"❌ ไม่สามารถดึงข้อมูล {symbol1} ได้\n\n"
            f"กรุณาตรวจสอบ Symbol หรือลองใหม่อีกครั้ง",
            parse_mode='Markdown'
        )
        return
    
    if not stock2_data:
        await processing.edit_text(
            f"❌ ไม่สามารถดึงข้อมูล {symbol2} ได้\n\n"
            f"กรุณาตรวจสอบ Symbol หรือลองใหม่อีกครั้ง",
            parse_mode='Markdown'
        )
        return
    
    # วิเคราะห์เปรียบเทียบด้วย AI
    comparison_analysis = analyze_comparison_with_gemini(
        stock1_data, stock2_data, symbol1, symbol2
    )
    
    if not comparison_analysis:
        await processing.edit_text(
            f"❌ **ไม่สามารถวิเคราะห์เปรียบเทียบได้**\n\n"
            f"อาจเป็นเพราะ:\n"
            f"• Gemini API มีปัญหา\n"
            f"• API Key ไม่ถูกต้อง\n"
            f"• Network error\n\n"
            f"💡 ลอง /aiplus {symbol1} หรือ /aiplus {symbol2}",
            parse_mode='Markdown'
        )
        return
    
    # สร้างรายงาน
    report = f"⚖️ **เปรียบเทียบ {symbol1} vs {symbol2}**\n\n"
    
    # แสดงข้อมูลพื้นฐาน
    report += f"🔴 **{symbol1}:** ${stock1_data['current']:.2f} "
    report += f"({stock1_data['change_pct']:+.2f}%)\n"
    
    report += f"🔵 **{symbol2}:** ${stock2_data['current']:.2f} "
    report += f"({stock2_data['change_pct']:+.2f}%)\n\n"
    
    report += f"{'═'*35}\n\n"
    
    # AI Analysis
    report += comparison_analysis
    
    # Footer
    report += f"\n\n{'─'*35}\n"
    report += f"📅 เปรียบเทียบจากข้อมูล: ข่าว + เทคนิค + Valuation\n"
    report += f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
    report += f"💡 ดูรายละเอียด:\n"
    report += f"  • /aiplus {symbol1}\n"
    report += f"  • /aiplus {symbol2}"
    
    try:
        # เช็คความยาว
        if len(report) > 4000:
            # แบ่งส่ง 2 ส่วน
            max_length = 3500
            
            first_part = report[:max_length]
            last_newline = first_part.rfind('\n')
            if last_newline > 3000:
                first_part = report[:last_newline]
                second_part = report[last_newline+1:]
            else:
                first_part = report[:max_length]
                second_part = report[max_length:]
            
            await processing.edit_text(first_part, disable_web_page_preview=True)
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=second_part,
                disable_web_page_preview=True
            )
        else:
            await processing.edit_text(report, disable_web_page_preview=True)
            
    except Exception as e:
        logger.error(f"Error sending comparison report: {e}")
        # Fallback: ส่งแบบสั้น
        short_report = f"⚖️ **{symbol1} vs {symbol2}**\n\n"
        short_report += f"🔴 {symbol1}: ${stock1_data['current']:.2f} "
        short_report += f"({stock1_data['change_pct']:+.2f}%)\n"
        short_report += f"🔵 {symbol2}: ${stock2_data['current']:.2f} "
        short_report += f"({stock2_data['change_pct']:+.2f}%)\n\n"
        short_report += comparison_analysis[:3000] + "\n\n...(ตัดข้อความ)\n\n"
        short_report += f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        try:
            await processing.edit_text(short_report, disable_web_page_preview=True)
        except:
            await processing.edit_text("❌ ข้อความยาวเกินไป กรุณาลองใหม่")
            
async def perform_aiplus_analysis(message, symbol: str):
    """ฟังก์ชันหลักสำหรับวิเคราะห์แบบรวม (ใช้ร่วมกันได้ทั้ง command และ button)"""
    
    # ตรวจสอบ API Keys
    if not FINNHUB_KEY or FINNHUB_KEY == "":
        await message.edit_text(
            "⚠️ **ไม่พบ FINNHUB_KEY**\n\n"
            "กรุณาตั้งค่า FINNHUB_KEY ใน Environment\n"
            "รับ Free API Key: https://finnhub.io/register",
            parse_mode='Markdown'
        )
        return
    
    if not GEMINI_API_KEY or GEMINI_API_KEY == "":
        await message.edit_text(
            "⚠️ **ไม่พบ GEMINI_API_KEY**\n\n"
            "กรุณาตั้งค่า GEMINI_API_KEY ใน Environment\n"
            "รับ Free API Key: https://makersuite.google.com/app/apikey",
            parse_mode='Markdown'
        )
        return
    
    if not TWELVE_DATA_KEY or TWELVE_DATA_KEY == "":
        await message.edit_text(
            "⚠️ **ไม่พบ TWELVE_DATA_KEY**\n\n"
            "กรุณาตั้งค่า TWELVE_DATA_KEY ใน Environment\n"
            "รับ Free API Key: https://twelvedata.com/apikey",
            parse_mode='Markdown'
        )
        return
    
    # 1. ดึงข้อมูลข่าว
    news_data = get_company_news(symbol, days=NEWS_DAYS_RANGE)
    
    if not news_data or len(news_data) == 0:
        await message.edit_text(
            f"❌ ไม่พบข่าวสำหรับ {symbol}\n\n"
            f"อาจเป็นเพราะ:\n"
            f"• Symbol ไม่ถูกต้อง\n"
            f"• ไม่มีข่าวในช่วง 7 วันที่ผ่านมา\n\n"
            f"ลอง /popular เพื่อดูหุ้นยอดนิยม",
            parse_mode='Markdown'
        )
        return
    
    # 2. ดึงข้อมูลเทคนิค
    quote = get_quote(symbol)
    if not quote or 'close' not in quote:
        await message.edit_text(
            f"❌ ไม่สามารถดึงข้อมูลเทคนิคของ {symbol} ได้\n\n"
            f"กรุณาตรวจสอบ Symbol หรือลองใหม่อีกครั้ง",
            parse_mode='Markdown'
        )
        return
    
    # เก็บข้อมูลเทคนิค
    current = float(quote['close'])
    prev_close = float(quote.get('previous_close', current))
    change = current - prev_close
    change_pct = (change / prev_close) * 100
    
    technical_data = {
        'current': current,
        'change_pct': change_pct,
        'rsi': get_rsi(symbol),
        'macd': None,
        'macd_signal': None,
        'ema_20': get_ema(symbol, 20),
        'ema_50': get_ema(symbol, 50),
        'ema_200': get_ema(symbol, 200),
        'bb_lower': None,
        'bb_upper': None,
        'bb_position': None,
        'analyst_buy_pct': None,
        'upside_pct': None
    }
    
    # MACD
    macd, macd_signal = get_macd(symbol)
    if macd is not None:
        technical_data['macd'] = macd
        technical_data['macd_signal'] = macd_signal
    
    # Bollinger Bands
    bb_lower, bb_upper = get_bbands(symbol)
    if bb_lower and bb_upper:
        technical_data['bb_lower'] = bb_lower
        technical_data['bb_upper'] = bb_upper
        technical_data['bb_position'] = ((current - bb_lower) / (bb_upper - bb_lower)) * 100
    
    # Analyst recommendations
    recommendations = get_analyst_recommendations(symbol)
    if recommendations:
        buy = recommendations.get('buy', 0)
        hold = recommendations.get('hold', 0)
        sell = recommendations.get('sell', 0)
        total = buy + hold + sell
        if total > 0:
            technical_data['analyst_buy_pct'] = (buy / total) * 100
    
    # Price target
    price_target = get_price_target(symbol)
    if price_target and price_target['target_mean']:
        target_mean = price_target['target_mean']
        technical_data['upside_pct'] = ((target_mean - current) / current) * 100
    
    # 3. แปลข่าว
    news_data = translate_news_batch(news_data)
    
    # 4. วิเคราะห์ด้วย AI แบบรวม
    combined_analysis = analyze_combined_with_gemini(news_data, symbol, technical_data)
    
    if not combined_analysis:
        await message.edit_text(
            f"❌ **ไม่สามารถวิเคราะห์ได้**\n\n"
            f"อาจเป็นเพราะ:\n"
            f"• Gemini API มีปัญหา\n"
            f"• API Key ไม่ถูกต้อง\n"
            f"• Network error\n\n"
            f"💡 ลอง /ai {symbol} หรือ /news {symbol}",
            parse_mode='Markdown'
        )
        return
    
    # 5. สร้างรายงาน
    report = f"🤖 AI วิเคราะห์เต็มรูปแบบ {symbol.upper()}\n"
    report += f"💰 ราคา: ${current:.2f} ({change_pct:+.2f}%)\n"
    report += combined_analysis
    report += f"\n\n{'─'*35}\n"
    report += f"📅 วิเคราะห์จาก {len(news_data)} ข่าว + ข้อมูลเทคนิค\n"
    report += f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
    report += f"💡 ข่าว: /news {symbol}"
    
    try:
        if len(report) > 4000:
            max_length = 3500
            first_part = report[:max_length]
            last_newline = first_part.rfind('\n')
            if last_newline > 3000:
                first_part = report[:last_newline]
                second_part = report[last_newline+1:]
            else:
                first_part = report[:max_length]
                second_part = report[max_length:]
            
            await message.edit_text(first_part, disable_web_page_preview=True)
            
            # Get chat_id from message
            chat_id = message.chat_id if hasattr(message, 'chat_id') else message.chat.id
            await message.get_bot().send_message(
                chat_id=chat_id,
                text=second_part,
                disable_web_page_preview=True
            )
        else:
            await message.edit_text(report, disable_web_page_preview=True)
            
    except Exception as e:
        logger.error(f"Error sending aiplus analysis: {e}")
        short_report = f"🤖 AI วิเคราะห์ {symbol.upper()}\n"
        short_report += f"💰 ${current:.2f} ({change_pct:+.2f}%)\n\n"
        short_report += combined_analysis[:3000] + "\n\n...(ตัดข้อความ)\n\n"
        short_report += f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        try:
            await message.edit_text(short_report, disable_web_page_preview=True)
        except:
            await message.edit_text("❌ ข้อความยาวเกินไป กรุณาลองใหม่")

# เพิ่มฟังก์ชัน callback handler สำหรับจัดการปุ่ม
async def stock_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """จัดการ callback จากปุ่มเลือกหมวดหมู่"""
    query = update.callback_query
    await query.answer()
    
    category = query.data
    
    # Dictionary หมวดหมู่หุ้น (เพิ่มหุ้นเยอะขึ้น)
    stock_categories = {
        "cat_toppicks": {
            "name": "🔥 ยอดนิยมสุด",
            "stocks": [
                ["NVDA", "AAPL", "MSFT"],
                ["GOOGL", "META", "TSLA"],
                ["AMZN", "NFLX", "AMD"],
                ["AVGO", "V", "MA"]
            ]
        },
        "cat_ai_tech": {
            "name": "🤖 AI & เทคโนโลยี",
            "stocks": [
                ["NVDA", "AMD", "INTC"],
                ["AVGO", "QCOM", "ASML"],
                ["ORCL", "CRM", "NOW"],
                ["ADBE", "PLTR", "SNOW"],
                ["CRWD", "PANW", "NET"]
            ]
        },
        "cat_finance": {
            "name": "💰 การเงิน & FinTech",
            "stocks": [
                ["V", "MA", "PYPL"],
                ["JPM", "BAC", "GS"],
                ["MS", "C", "WFC"],
                ["BLK", "SCHW", "AXP"],
                ["SQ", "COIN", "SOFI"]
            ]
        },
        "cat_consumer": {
            "name": "🛒 อุปโภคบริโภค",
            "stocks": [
                ["WMT", "COST", "TGT"],
                ["HD", "LOW", "NKE"],
                ["SBUX", "MCD", "CMG"],
                ["KO", "PEP", "PG"],
                ["AMZN", "BABA", "JD"]
            ]
        },
        "cat_healthcare": {
            "name": "🏥 สุขภาพ & ยา",
            "stocks": [
                ["JNJ", "UNH", "LLY"],
                ["PFE", "ABBV", "NVO"],
                ["TMO", "ABT", "DHR"],
                ["ISRG", "VRTX", "REGN"],
                ["MDT", "BMY", "AMGN"]
            ]
        },
        "cat_energy": {
            "name": "⚡ พลังงาน",
            "stocks": [
                ["XOM", "CVX", "COP"],
                ["SLB", "EOG", "PSX"],
                ["MPC", "VLO", "OXY"],
                ["FANG", "DVN", "HAL"],
                ["ENPH", "SEDG", "RUN"]  # Solar
            ]
        },
        "cat_aerospace": {
            "name": "🚀 อวกาศ & กลาโหม",
            "stocks": [
                ["RKLB", "BA", "LMT"],
                ["RTX", "NOC", "GD"],
                ["LHX", "HII", "TDG"],
                ["AVAV", "KTOS", "AJRD"]
            ]
        },
        "cat_media": {
            "name": "📱 สื่อสาร & บันเทิง",
            "stocks": [
                ["NFLX", "DIS", "PARA"],
                ["WBD", "CMCSA", "T"],
                ["VZ", "TMUS", "CHTR"],
                ["SPOT", "RBLX", "EA"],
                ["TTWO", "ATVI", "U"]
            ]
        },
        "cat_industrial": {
            "name": "🏭 อุตสาหกรรม",
            "stocks": [
                ["CAT", "DE", "GE"],
                ["HON", "MMM", "EMR"],
                ["UPS", "FEDEX", "CSX"],
                ["NSC", "UNP", "CP"],
                ["ITW", "ETN", "PH"]
            ]
        },
        "cat_etf": {
            "name": "📊 ETF & กองทุน",
            "stocks": [
                ["SPY", "QQQ", "IVV"],
                ["VOO", "VTI", "DIA"],
                ["IWM", "EEM", "VEA"],
                ["GLD", "SLV", "TLT"],
                ["ARKK", "ARKW", "ARKG"]
            ]
        }
    }
    
    if category in stock_categories:
        cat_data = stock_categories[category]
        keyboard = []
        
        # สร้างปุ่มจากรายการหุ้น
        for row in cat_data["stocks"]:
            button_row = [
                InlineKeyboardButton(symbol, callback_data=f"aiplus_{symbol}") 
                for symbol in row
            ]
            keyboard.append(button_row)
        
        # ปุ่มกลับ
        keyboard.append([InlineKeyboardButton("🔙 กลับเมนูหลัก", callback_data="back_to_main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"{cat_data['name']} - เลือกหุ้นที่ต้องการวิเคราะห์:\n\n"
            f"💡 กดปุ่มเพื่อให้ AI วิเคราะห์แบบรวม (ข่าว + เทคนิค)",
            reply_markup=reply_markup
        )
    
    elif category == "back_to_main":
        # กลับไปเมนูหลัก
        keyboard = [
            [InlineKeyboardButton("🔥 ยอดนิยมสุด (Top Picks)", callback_data="cat_toppicks")],
            [InlineKeyboardButton("🤖 AI & เทคโนโลยี", callback_data="cat_ai_tech")],
            [InlineKeyboardButton("💰 การเงิน & FinTech", callback_data="cat_finance")],
            [InlineKeyboardButton("🛒 อุปโภคบริโภค", callback_data="cat_consumer")],
            [InlineKeyboardButton("🏥 สุขภาพ & ยา", callback_data="cat_healthcare")],
            [InlineKeyboardButton("⚡ พลังงาน", callback_data="cat_energy")],
            [InlineKeyboardButton("🚀 อวกาศ & กลาโหม", callback_data="cat_aerospace")],
            [InlineKeyboardButton("📱 สื่อสาร & บันเทิง", callback_data="cat_media")],
            [InlineKeyboardButton("🏭 อุตสาหกรรม", callback_data="cat_industrial")],
            [InlineKeyboardButton("📊 ETF & กองทุน", callback_data="cat_etf")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🚀 **AI วิเคราะห์เต็มรูปแบบ**\n\n"
            "**เลือกหมวดหมู่หุ้นที่สนใจ:**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif category.startswith("aiplus_"):
        # เริ่มวิเคราะห์หุ้น
        symbol = category.replace("aiplus_", "")
        
        await query.edit_message_text(
            f"🚀 กำลังวิเคราะห์ {symbol} แบบเต็มรูปแบบ...\n"
            f"⏳ กำลังรวบรวมข้อมูล:\n"
            f"  • ข่าวล่าสุด\n"
            f"  • ตัวชี้วัดเทคนิค\n"
            f"  • ข้อมูลนักวิเคราะห์\n"
            f"  • AI กำลังวิเคราะห์...",
            parse_mode='Markdown'
        )
        
        # เรียกใช้ฟังก์ชันวิเคราะห์
        await perform_aiplus_analysis(query.message, symbol)


async def aiplus_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks from /aiplus menu"""
    query = update.callback_query
    await query.answer()
    
    # ดึง symbol จาก callback_data (รูปแบบ: "aiplus_SYMBOL")
    callback_data = query.data
    if not callback_data.startswith("aiplus_"):
        return
    
    symbol = callback_data.replace("aiplus_", "").strip().upper()
    
    # Validate symbol
    if len(symbol) < MIN_SYMBOL_LENGTH or len(symbol) > MAX_SYMBOL_LENGTH or not symbol.isalpha():
        await query.edit_message_text(
            f"❌ Symbol {symbol} ไม่ถูกต้อง",
            parse_mode='Markdown'
        )
        return
    
    # แก้ไขข้อความเป็น processing
    processing = await query.edit_message_text(
        f"🚀 กำลังวิเคราะห์ {symbol} แบบเต็มรูปแบบ...\n"
        f"⏳ กำลังรวบรวมข้อมูล:\n"
        f"  • ข่าวล่าสุด\n"
        f"  • ตัวชี้วัดเทคนิค\n"
        f"  • ข้อมูลนักวิเคราะห์\n"
        f"  • AI กำลังวิเคราะห์...",
        parse_mode='Markdown'
    )
    
    # ตรวจสอบ API Keys
    if not FINNHUB_KEY or FINNHUB_KEY == "":
        await query.edit_message_text(
            "⚠️ **ไม่พบ FINNHUB_KEY**\n\n"
            "กรุณาตั้งค่า FINNHUB_KEY ใน Environment\n"
            "รับ Free API Key: https://finnhub.io/register",
            parse_mode='Markdown'
        )
        return
    
    if not GEMINI_API_KEY or GEMINI_API_KEY == "":
        await query.edit_message_text(
            "⚠️ **ไม่พบ GEMINI_API_KEY**\n\n"
            "กรุณาตั้งค่า GEMINI_API_KEY ใน Environment\n"
            "รับ Free API Key: https://makersuite.google.com/app/apikey",
            parse_mode='Markdown'
        )
        return
    
    if not TWELVE_DATA_KEY or TWELVE_DATA_KEY == "":
        await query.edit_message_text(
            "⚠️ **ไม่พบ TWELVE_DATA_KEY**\n\n"
            "กรุณาตั้งค่า TWELVE_DATA_KEY ใน Environment\n"
            "รับ Free API Key: https://twelvedata.com/apikey",
            parse_mode='Markdown'
        )
        return
    
    # 1. ดึงข้อมูลข่าว
    news_data = get_company_news(symbol, days=NEWS_DAYS_RANGE)
    
    if not news_data or len(news_data) == 0:
        await query.edit_message_text(
            f"❌ ไม่พบข่าวสำหรับ {symbol}\n\n"
            f"อาจเป็นเพราะ:\n"
            f"• Symbol ไม่ถูกต้อง\n"
            f"• ไม่มีข่าวในช่วง 7 วันที่ผ่านมา\n\n"
            f"ลอง /popular เพื่อดูหุ้นยอดนิยม",
            parse_mode='Markdown'
        )
        return
    
    # 2. ดึงข้อมูลเทคนิค
    quote = get_quote(symbol)
    if not quote or 'close' not in quote:
        await query.edit_message_text(
            f"❌ ไม่สามารถดึงข้อมูลเทคนิคของ {symbol} ได้\n\n"
            f"กรุณาตรวจสอบ Symbol หรือลองใหม่อีกครั้ง",
            parse_mode='Markdown'
        )
        return
    
    # เก็บข้อมูลเทคนิค
    current = float(quote['close'])
    prev_close = float(quote.get('previous_close', current))
    change = current - prev_close
    change_pct = (change / prev_close) * 100
    
    technical_data = {
        'current': current,
        'change_pct': change_pct,
        'rsi': get_rsi(symbol),
        'macd': None,
        'macd_signal': None,
        'ema_20': get_ema(symbol, 20),
        'ema_50': get_ema(symbol, 50),
        'ema_200': get_ema(symbol, 200),
        'bb_lower': None,
        'bb_upper': None,
        'bb_position': None,
        'analyst_buy_pct': None,
        'upside_pct': None
    }
    
    # MACD
    macd, macd_signal = get_macd(symbol)
    if macd is not None:
        technical_data['macd'] = macd
        technical_data['macd_signal'] = macd_signal
    
    # Bollinger Bands
    bb_lower, bb_upper = get_bbands(symbol)
    if bb_lower and bb_upper:
        technical_data['bb_lower'] = bb_lower
        technical_data['bb_upper'] = bb_upper
        technical_data['bb_position'] = ((current - bb_lower) / (bb_upper - bb_lower)) * 100
    
    # Analyst recommendations
    recommendations = get_analyst_recommendations(symbol)
    if recommendations:
        buy = recommendations.get('buy', 0)
        hold = recommendations.get('hold', 0)
        sell = recommendations.get('sell', 0)
        total = buy + hold + sell
        if total > 0:
            technical_data['analyst_buy_pct'] = (buy / total) * 100
    
    # Price target
    price_target = get_price_target(symbol)
    if price_target and price_target['target_mean']:
        target_mean = price_target['target_mean']
        technical_data['upside_pct'] = ((target_mean - current) / current) * 100
    
    # 3. แปลข่าว
    news_data = translate_news_batch(news_data)
    
    # 4. วิเคราะห์ด้วย AI แบบรวม
    combined_analysis = analyze_combined_with_gemini(news_data, symbol, technical_data)
    
    if not combined_analysis:
        await query.edit_message_text(
            f"❌ **ไม่สามารถวิเคราะห์ได้**\n\n"
            f"อาจเป็นเพราะ:\n"
            f"• Gemini API มีปัญหา\n"
            f"• API Key ไม่ถูกต้อง\n"
            f"• Network error\n\n"
            f"💡 ลอง /ai {symbol} หรือ /news {symbol}",
            parse_mode='Markdown'
        )
        return
    
    # 5. สร้างรายงาน
    report = f"🤖 AI วิเคราะห์เต็มรูปแบบ {symbol.upper()}\n"
    report += f"💰 ราคา: ${current:.2f} ({change_pct:+.2f}%)\n"
    
    # AI Analysis
    report += combined_analysis
    
    # Footer
    report += f"\n\n{'─'*35}\n" 
    report += f"📅 วิเคราะห์จาก {len(news_data)} ข่าว + ข้อมูลเทคนิค\n"
    report += f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
    report += f"💡 ข่าว: /news {symbol}"
     
    try:
        # เช็คความยาวก่อนส่ง
        if len(report) > 4000:
            # แบ่งส่งทันที
            max_length = 3500
            
            first_part = report[:max_length]
            last_newline = first_part.rfind('\n')
            if last_newline > 3000:
                first_part = report[:last_newline]
                second_part = report[last_newline+1:]
            else:
                first_part = report[:max_length]
                second_part = report[max_length:]
            
            await query.edit_message_text(first_part, disable_web_page_preview=True)
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=second_part,
                disable_web_page_preview=True
            )
        else:
            await query.edit_message_text(report, disable_web_page_preview=True)
            
    except Exception as e:
        logger.error(f"Error sending aiplus analysis from button: {e}")
        # Fallback: ส่งแบบสั้น
        short_report = f"🤖 AI วิเคราะห์ {symbol.upper()}\n"
        short_report += f"💰 ${current:.2f} ({change_pct:+.2f}%)\n\n"
        short_report += combined_analysis[:3000] + "\n\n...(ตัดข้อความ)\n\n"
        short_report += f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        
        try:
            await query.edit_message_text(short_report, disable_web_page_preview=True)
        except:
            await query.edit_message_text("❌ ข้อความยาวเกินไป กรุณาลองใหม่")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """🤖 **ยินดีต้อนรับสู่ Stock Analysis Bot!** 📈

💡 **วิธีใช้งาน:**
- พิมพ์ชื่อหุ้น เช่น: NVDA,NFLX,AMZN,GOOGL,RKLB,V,MSFT,IVV,AVGO,META
- /news SYMBOL - ดูข่าวล่าสุด
- /ai SYMBOL - AI วิเคราะห์ข่าว 
- /aiplus SYMBOL - AI วิเคราะห์แบบรวม (ข่าว+เทคนิค) 🚀
- /compare SYMBOL1 SYMBOL2 - เปรียบเทียบ 2 หุ้น ⚖️ NEW!
- /help - ดูคำแนะนำ
- /popular - ดูหุ้นยอดนิยม

✨ วิเคราะห์ด้วย:
- RSI, MACD, EMA, Bollinger Bands
- Valuation & Margin of Safety
- คำแนะนำจากนักวิเคราะห์
- 📰 ข่าวล่าสุด
- 🤖 AI วิเคราะห์ข่าว (NEW!)

🎯 **ทำไมต้อง /aiplus:**
✅ วิเคราะห์ครบ 360° - ทั้งข่าวและกราฟ
✅ จับสัญญาณขัดแย้ง - ข่าวดีแต่เทคนิคขาลง? AI จะเตือน
✅ คำแนะนำการเทรด - รู้ว่าควรเข้าตอนไหน ตั้ง SL ที่ไหน

🎯 **ทำไมต้อง /compare:**
✅ เปรียบเทียบ 2 หุ้นแบบครบมิติ
✅ แนะนำแยกตาม Timeframe (สั้น/กลาง/ยาว)
✅ ได้คำตอบชัดเจน - ควรซื้อตัวไหน"""
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
/ai SYMBOL - AI วิเคราะห์ว่าข่าวดีหรือไม่ดี
/compare AAPL MSFT - เปรียบเทียบ 2 หุ้น ⚖️
/popular - ดูหุ้นยอดนิยม"""
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
    application.add_handler(CommandHandler("news", news_command))
    application.add_handler(CommandHandler("ai", ai_analysis_command))  
    application.add_handler(CommandHandler("aiplus", aiplus_command))
    application.add_handler(CommandHandler("compare", compare_command))
    application.add_handler(CommandHandler("health", health_check))
    application.add_handler(CallbackQueryHandler(stock_category_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_stock))
    application.add_handler(CallbackQueryHandler(aiplus_button_callback, pattern="^aiplus_"))  # เพิ่มบรรทัดนี้
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
