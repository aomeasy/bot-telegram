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

def get_btc_data():
    """ดึงข้อมูล BTC จาก CoinCap API (Free, No Auth Required)"""
    try:
        url = "https://api.coincap.io/v2/assets/bitcoin"
        
        logger.info(f"🔍 Fetching CoinCap data: {url}")
        response = requests.get(url, timeout=10)
        
        logger.info(f"📡 CoinCap Response Status: {response.status_code}")
        logger.info(f"📡 CoinCap Response: {response.text[:200]}")
        
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data:
            btc = data['data']
            return {
                'price': float(btc['priceUsd']),
                'change_24h': float(btc['changePercent24Hr']),
                'volume_24h': float(btc['volumeUsd24Hr']),
                'market_cap': float(btc['marketCapUsd'])
            }
        else:
            logger.error(f"❌ No 'data' key in response: {data}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("❌ CoinCap API Timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ CoinCap API Error: {e}")
        logger.error(f"❌ Response content: {getattr(e.response, 'text', 'No response')}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"❌ Error parsing CoinCap data: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_btc_data: {e}")
        return None

def get_binance_ticker(symbol="BTCUSDT"):
    """ดึงข้อมูล Real-time จาก CoinCap (แทน Binance)"""
    try:
        # CoinCap ใช้ id แทน symbol
        coin_id = "bitcoin" if symbol == "BTCUSDT" else symbol.lower()
        url = f"https://api.coincap.io/v2/assets/{coin_id}"
        
        logger.info(f"🔍 Fetching CoinCap data for {coin_id}")
        response = requests.get(url, timeout=10)
        
        logger.info(f"📡 CoinCap Response Status: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data:
            btc = data['data']
            
            # คำนวณ high/low โดยประมาณจาก price และ change
            current_price = float(btc['priceUsd'])
            change_pct = float(btc['changePercent24Hr'])
            
            # ประมาณ high/low (เพราะ CoinCap ไม่มีข้อมูลนี้)
            estimated_range = abs(current_price * change_pct / 100)
            high_24h = current_price + estimated_range
            low_24h = current_price - estimated_range
            
            return {
                'price': current_price,
                'high_24h': high_24h,
                'low_24h': low_24h,
                'volume': float(btc['volumeUsd24Hr']) / current_price,  # แปลง USD เป็น BTC
                'price_change_pct': change_pct,
                'trades': 0  # CoinCap ไม่มีข้อมูลนี้
            }
        else:
            logger.error(f"❌ No data in response: {data}")
            return None
        
    except requests.exceptions.Timeout:
        logger.error("❌ CoinCap API Timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ CoinCap API Error: {e}")
        logger.error(f"❌ Response: {getattr(e.response, 'text', 'No response')}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"❌ Error parsing CoinCap data: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_binance_ticker: {e}")
        return None

def get_fear_greed_index():
    """ดึง Fear & Greed Index (Free API) - improved"""
    try:
        url = "https://api.alternative.me/fng/"
        params = {"limit": 1}
        
        logger.info("🔍 Fetching Fear & Greed Index")
        response = requests.get(url, params=params, timeout=10)
        
        logger.info(f"📡 F&G Response Status: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        if data.get('data') and len(data['data']) > 0:
            value = int(data['data'][0]['value'])
            classification = data['data'][0]['value_classification']
            return {'value': value, 'classification': classification}
        else:
            logger.error(f"❌ No data in F&G response: {data}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("❌ Fear & Greed API Timeout")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Fear & Greed API Error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error in get_fear_greed_index: {e}")
        return None

def get_btc_technical_signals():
    """วิเคราะห์สัญญาณทางเทคนิคของ BTC"""
    try:
        # ใช้ Binance data หรือ Twelve Data
        binance_data = get_binance_ticker("BTCUSDT")
        if not binance_data:
            return None
        
        # ดึง Technical Indicators (ถ้ามี Twelve Data Key)
        if TWELVE_DATA_KEY:
            rsi = get_rsi("BTC/USD")
            macd, macd_signal = get_macd("BTC/USD")
            ema_20 = get_ema("BTC/USD", 20)
            ema_50 = get_ema("BTC/USD", 50)
        else:
            rsi = None
            macd = None
            macd_signal = None
            ema_20 = None
            ema_50 = None
        
        current_price = binance_data['price']
        
        signals = []
        score = 0
        
        # RSI Analysis
        if rsi:
            if rsi <= 30:
                signals.append(f"📈 RSI: {rsi:.1f} - OVERSOLD (ซื้อ)")
                score += 30
            elif rsi >= 70:
                signals.append(f"📉 RSI: {rsi:.1f} - OVERBOUGHT (ขาย)")
                score -= 30
            elif rsi <= 40:
                signals.append(f"💚 RSI: {rsi:.1f} - ต่ำ (เริ่มน่าสนใจ)")
                score += 15
            elif rsi >= 60:
                signals.append(f"🔶 RSI: {rsi:.1f} - สูง (ระวัง)")
                score -= 15
            else:
                signals.append(f"➡️ RSI: {rsi:.1f} - Neutral")
        
        # MACD Analysis
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                signals.append("📊 MACD: Golden Cross (Bullish)")
                score += 25
            else:
                signals.append("📊 MACD: Death Cross (Bearish)")
                score -= 25
        
        # EMA Trend
        if ema_20 and ema_50 and current_price:
            if current_price > ema_20 > ema_50:
                signals.append("📈 EMA: Strong Uptrend")
                score += 20
            elif current_price < ema_20 < ema_50:
                signals.append("📉 EMA: Strong Downtrend")
                score -= 20
            else:
                signals.append("➡️ EMA: Sideways")
        
        # 24hr Price Movement
        price_change = binance_data['price_change_pct']
        if price_change >= 5:
            signals.append(f"🚀 ราคาพุ่ง +{price_change:.1f}% ใน 24hr")
            score += 15
        elif price_change <= -5:
            signals.append(f"📉 ราคาร่วง {price_change:.1f}% ใน 24hr")
            score -= 15
        
        return {
            'signals': signals,
            'score': score,
            'rsi': rsi,
            'macd': macd,
            'macd_signal': macd_signal,
            'current_price': current_price
        }
        
    except Exception as e:
        logger.error(f"Error analyzing BTC signals: {e}")
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

def get_trading_recommendation(symbol):
    """วิเคราะห์และให้คำแนะนำการซื้อ-ขาย"""
    try:
        quote = get_quote(symbol)
        if not quote or 'close' not in quote:
            return None, "ไม่มีข้อมูล"
        
        current = float(quote['close'])
        rsi = get_rsi(symbol)
        macd, macd_signal = get_macd(symbol)
        ema_20 = get_ema(symbol, 20)
        ema_50 = get_ema(symbol, 50)
        price_target = get_price_target(symbol)
        
        # คะแนนการวิเคราะห์
        score = 0
        signals = []
        
        # 1. Valuation (น้ำหนัก 40%)
        if price_target and price_target.get('target_mean'):
            target_mean = price_target['target_mean']
            upside_pct = ((target_mean - current) / current) * 100
            
            if upside_pct >= 20:
                score += 40
                signals.append(f"💎 Valuation: +{upside_pct:.1f}% (ถูกมาก)")
            elif upside_pct >= 10:
                score += 25
                signals.append(f"💎 Valuation: +{upside_pct:.1f}% (น่าสนใจ)")
            elif upside_pct >= 0:
                score += 10
                signals.append(f"💎 Valuation: +{upside_pct:.1f}% (ยุติธรรม)")
            elif upside_pct >= -10:
                score -= 10
                signals.append(f"⚠️ Valuation: {upside_pct:.1f}% (แพง)")
            else:
                score -= 30
                signals.append(f"🚨 Valuation: {upside_pct:.1f}% (แพงเกิน)")
        
        # 2. RSI (น้ำหนัก 20%)
        if rsi:
            if rsi <= 30:
                score += 20
                signals.append(f"📈 RSI: {rsi:.1f} (Oversold)")
            elif rsi <= 40:
                score += 10
                signals.append(f"📈 RSI: {rsi:.1f} (ต่ำ)")
            elif rsi >= 70:
                score -= 20
                signals.append(f"📉 RSI: {rsi:.1f} (Overbought)")
            elif rsi >= 60:
                score -= 10
                signals.append(f"📉 RSI: {rsi:.1f} (สูง)")
            else:
                signals.append(f"➡️ RSI: {rsi:.1f} (กลาง)")
        
        # 3. MACD (น้ำหนัก 20%)
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                score += 20
                signals.append("📊 MACD: Bullish")
            else:
                score -= 20
                signals.append("📊 MACD: Bearish")
        
        # 4. EMA Trend (น้ำหนัก 20%)
        if ema_20 and ema_50 and current:
            if current > ema_20 > ema_50:
                score += 20
                signals.append("📈 EMA: Uptrend")
            elif current < ema_20 < ema_50:
                score -= 20
                signals.append("📉 EMA: Downtrend")
            else:
                signals.append("➡️ EMA: Sideways")
        
        # ตัดสินใจตามคะแนน
        if score >= 60:
            recommendation = "🟢 STRONG BUY"
            emoji = "🚀"
        elif score >= 30:
            recommendation = "🟢 ACCUMULATE"
            emoji = "💰"
        elif score >= -10:
            recommendation = "🟡 HOLD"
            emoji = "✋"
        elif score >= -40:
            recommendation = "🔴 REDUCE"
            emoji = "📉"
        else:
            recommendation = "🔴 SELL"
            emoji = "⚠️"
        
        return {
            'symbol': symbol,
            'recommendation': recommendation,
            'emoji': emoji,
            'score': score,
            'price': current,
            'signals': signals
        }, None
        
    except Exception as e:
        logger.error(f"Error getting recommendation for {symbol}: {e}")
        return None, str(e)


# --- HTTP Health Check Handler (สำหรับป้องกัน Render Sleep) ---

#async def http_health_check(request):
#    """HTTP health check endpoint for UptimeRobot & Render"""
#    return web.Response(text="✅ Bot is running!", status=200)

# --- Telegram Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """🤖 **ยินดีต้อนรับสู่ Stock Analysis Bot!** 📈

💡 **วิธีใช้งาน:**
• พิมพ์ชื่อหุ้น เช่น: NVDA,NFLX,AMZN,GOOGL,RKLB,V,MSFT,IVV,AVGO,META
• /help - ดูคำแนะนำ
• /popular - ดูหุ้นยอดนิยม
• /a - คำสั่งด่วน
• /btc - วิเคราะห์ BTC แบบละเอียด 🪙
• /b - ดูราคา BTC แบบรวดเร็ว ⚡
• /health - สถานะbot 

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

**คำสั่ง Crypto:**
/btc - วิเคราะห์ Bitcoin แบบครบวงจร
/b หรือ /btcprice - ดูราคา BTC แบบรวดเร็ว

**ข้อมูลที่ได้:**
• ราคา Real-time จาก Binance
• Fear & Greed Index
• สัญญาณทางเทคนิค (RSI, MACD, EMA)
• คำแนะนำซื้อ-ขาย

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

async def quick_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """วิเคราะห์ด่วนหุ้นที่ถืออยู่"""
    portfolio = ["NVDA", "NFLX", "AMZN", "GOOGL", "RKLB", "V", "MSFT", "IVV", "AVGO", "META"]
    
    processing = await update.message.reply_text(
        f"🔍 กำลังวิเคราะห์ {len(portfolio)} หุ้นในพอร์ต...\n"
        f"⏳ กรุณารอสักครู่..."
    )
    
    results = []
    for symbol in portfolio:
        result, error = get_trading_recommendation(symbol)
        if result:
            results.append(result)
        else:
            results.append({
                'symbol': symbol,
                'recommendation': '❌ ไม่มีข้อมูล',
                'emoji': '❓',
                'score': 0,
                'price': 0,
                'signals': []
            })
    
    # สร้างรายงานสรุป
    report = "📊 **Portfolio Quick Analysis**\n\n"
    
    # แยกตามคำแนะนำ
    strong_buy = [r for r in results if 'STRONG BUY' in r['recommendation']]
    accumulate = [r for r in results if 'ACCUMULATE' in r['recommendation']]
    hold = [r for r in results if 'HOLD' in r['recommendation']]
    reduce = [r for r in results if 'REDUCE' in r['recommendation']]
    sell = [r for r in results if 'SELL' in r['recommendation'] and 'STRONG' not in r['recommendation']]
    
    # แสดงผลตามหมวดหมู่
    if strong_buy:
        report += "🟢 **STRONG BUY** (คะแนน 60+)\n"
        for r in sorted(strong_buy, key=lambda x: x['score'], reverse=True):
            report += f"{r['emoji']} {r['symbol']}: ${r['price']:.2f} (Score: {r['score']})\n"
        report += "\n"
    
    if accumulate:
        report += "🟢 **ACCUMULATE** (คะแนน 30-59)\n"
        for r in sorted(accumulate, key=lambda x: x['score'], reverse=True):
            report += f"{r['emoji']} {r['symbol']}: ${r['price']:.2f} (Score: {r['score']})\n"
        report += "\n"
    
    if hold:
        report += "🟡 **HOLD** (คะแนน -10 ถึง 29)\n"
        for r in sorted(hold, key=lambda x: x['score'], reverse=True):
            report += f"{r['emoji']} {r['symbol']}: ${r['price']:.2f} (Score: {r['score']})\n"
        report += "\n"
    
    if reduce:
        report += "🔴 **REDUCE** (คะแนน -40 ถึง -11)\n"
        for r in sorted(reduce, key=lambda x: x['score'], reverse=True):
            report += f"{r['emoji']} {r['symbol']}: ${r['price']:.2f} (Score: {r['score']})\n"
        report += "\n"
    
    if sell:
        report += "🔴 **SELL** (คะแนน ต่ำกว่า -40)\n"
        for r in sorted(sell, key=lambda x: x['score'], reverse=True):
            report += f"{r['emoji']} {r['symbol']}: ${r['price']:.2f} (Score: {r['score']})\n"
        report += "\n"
    
    # สรุปภาพรวม
    report += "📝 **สรุปภาพรวม:**\n"
    report += f"• Strong Buy/Accumulate: {len(strong_buy) + len(accumulate)} หุ้น\n"
    report += f"• Hold: {len(hold)} หุ้น\n"
    report += f"• Reduce/Sell: {len(reduce) + len(sell)} หุ้น\n\n"
    
    # แนะนำการดำเนินการ
    action_count = len(strong_buy) + len(accumulate)
    if action_count >= 5:
        report += "💡 **คำแนะนำ:** มีหลายหุ้นน่าสนใจ - พิจารณาเพิ่มสัดส่วนในหุ้นที่ Strong Buy\n"
    elif action_count >= 3:
        report += "💡 **คำแนะนำ:** มีบางหุ้นน่าสนใจ - Accumulate ตามจังหวะ\n"
    elif len(sell) + len(reduce) >= 4:
        report += "⚠️ **คำแนะนำ:** พอร์ตมีความเสี่ยง - พิจารณา Rebalance\n"
    else:
        report += "✅ **คำแนะนำ:** พอร์ตสมดุล - Hold และติดตามต่อ\n"
    
    report += f"\n⏰ อัพเดท: {datetime.now().strftime('%H:%M:%S')}"
    report += f"\n\n💬 พิมพ์ชื่อหุ้นเพื่อดูรายละเอียดเพิ่มเติม"
    
    await processing.edit_text(report, parse_mode='Markdown')


async def btc_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ระบบแจ้งเตือน BTC แบบครบวงจร - improved"""
    processing = await update.message.reply_text("🔍 กำลังวิเคราะห์ BTC...\n⏳ กำลังดึงข้อมูล...")
    
    # ดึงข้อมูลทั้งหมด - Binance is priority
    binance_data = get_binance_ticker("BTCUSDT")
    btc_data = get_btc_data()  # For market cap
    fear_greed = get_fear_greed_index()
    technical = get_btc_technical_signals()
    
    # Check if we have minimum required data
    if not binance_data:
        await processing.edit_text(
            "❌ ไม่สามารถดึงข้อมูลจาก Binance ได้\n\n"
            "กรุณาตรวจสอบ:\n"
            "• การเชื่อมต่ออินเทอร์เน็ต\n"
            "• Binance API status\n"
            "• Logs สำหรับรายละเอียด"
        )
        return
    
    # สร้างรายงาน
    report = "🪙 **Bitcoin Alert System**\n\n"
    
    # ส่วนที่ 1: ราคาและข้อมูลพื้นฐาน (from Binance)
    price = binance_data['price']
    change_24h = binance_data['price_change_pct']
    emoji = "🟢" if change_24h >= 0 else "🔴"
    
    report += f"💰 **ราคาปัจจุบัน:** ${price:,.2f}\n"
    report += f"{emoji} **24hr Change:** {change_24h:+.2f}%\n"
    report += f"📊 **Volume 24hr:** {binance_data['volume']:,.0f} BTC\n"
    
    # Add market cap if available from CoinGecko
    if btc_data and btc_data.get('market_cap'):
        report += f"📈 **Market Cap:** ${btc_data['market_cap']/1e9:.2f}B\n\n"
    else:
        report += "\n"
    
    # ส่วนที่ 2: ช่วงราคา 24hr
    report += f"📊 **ช่วงราคา 24hr:**\n"
    report += f"• สูงสุด: ${binance_data['high_24h']:,.2f}\n"
    report += f"• ต่ำสุด: ${binance_data['low_24h']:,.2f}\n"
    report += f"• Trades: {binance_data['trades']:,} รายการ\n\n"
    
    # ส่วนที่ 3: Fear & Greed Index (optional)
    if fear_greed:
        fg_value = fear_greed['value']
        fg_class = fear_greed['classification']
        
        report += f"🎭 **Fear & Greed Index:**\n"
        
        if fg_value <= 20:
            report += f"🟢 {fg_value} - {fg_class}\n"
            report += f"💡 **Extreme Fear** - เวลาที่ดีในการซื้อ!\n\n"
        elif fg_value <= 40:
            report += f"🟡 {fg_value} - {fg_class}\n"
            report += f"💡 ตลาดกลัว - พิจารณาซื้อเพิ่ม\n\n"
        elif fg_value <= 60:
            report += f"⚪ {fg_value} - {fg_class}\n"
            report += f"💡 ตลาดปกติ - รอสัญญาณชัดเจน\n\n"
        elif fg_value <= 80:
            report += f"🟠 {fg_value} - {fg_class}\n"
            report += f"⚠️ ตลาดโลภ - ระวังราคาปรับฐาน\n\n"
        else:
            report += f"🔴 {fg_value} - {fg_class}\n"
            report += f"⚠️ **Extreme Greed** - ควรระมัดระวัง!\n\n"
    
    # ส่วนที่ 4: สัญญาณทางเทคนิค (optional)
    if technical and technical.get('signals'):
        report += f"📈 **สัญญาณทางเทคนิค:**\n"
        for signal in technical['signals']:
            report += f"• {signal}\n"
        report += f"\n"
        
        # สรุปคะแนน
        score = technical['score']
        report += f"🎯 **คะแนนรวม:** {score}/100\n"
        
        if score >= 50:
            report += f"🟢 **คำแนะนำ: STRONG BUY**\n"
            report += f"💡 มีสัญญาณ Bullish หลายตัว - เหมาะซื้อเพิ่ม\n\n"
        elif score >= 20:
            report += f"🟢 **คำแนะนำ: ACCUMULATE**\n"
            report += f"💡 มีสัญญาณเชิงบวก - ซื้อค่อยๆ เพิ่ม\n\n"
        elif score >= -20:
            report += f"🟡 **คำแนะนำ: HOLD**\n"
            report += f"💡 สัญญาณไม่ชัดเจน - รอดูก่อน\n\n"
        elif score >= -50:
            report += f"🔴 **คำแนะนำ: REDUCE**\n"
            report += f"⚠️ มีสัญญาณ Bearish - พิจารณาลดสัดส่วน\n\n"
        else:
            report += f"🔴 **คำแนะนำ: SELL**\n"
            report += f"⚠️ สัญญาณ Bearish แข็งแกร่ง - ควระระมัดระวัง\n\n"
    
    # ส่วนที่ 5: แจ้งเตือนพิเศษ
    alerts = []
    
    # Price Movement Alert
    if abs(change_24h) >= 5:
        alerts.append(f"⚡ ราคาเคลื่อนไหวมาก {abs(change_24h):.1f}% ใน 24hr")
    
    # Volume Alert
    if binance_data['volume'] > 50000:  # BTC Volume สูงกว่าปกติ
        alerts.append(f"📊 Volume สูงผิดปกติ - อาจมี Big Move")
    
    # Fear & Greed Extreme
    if fear_greed:
        if fear_greed['value'] <= 20 or fear_greed['value'] >= 80:
            alerts.append(f"🎭 Fear & Greed ที่ระดับ Extreme")
    
    if alerts:
        report += f"🔔 **Alert พิเศษ:**\n"
        for alert in alerts:
            report += f"• {alert}\n"
        report += f"\n"
    
    # Footer
    report += f"⏰ อัพเดท: {datetime.now().strftime('%H:%M:%S')}\n"
    report += f"💬 พิมพ์ /btc เพื่อดูข้อมูลอีกครั้ง"
    
    await processing.edit_text(report, parse_mode='Markdown')


async def btc_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ดูราคา BTC แบบรวดเร็ว"""
    binance_data = get_binance_ticker("BTCUSDT")  # จริงๆ ใช้ CoinCap แล้ว
    btc_data = get_btc_data()
    
    if binance_data and btc_data:
        price = binance_data['price']
        change = btc_data['change_24h']
        emoji = "🟢" if change >= 0 else "🔴"
        
        report = f"🪙 **Bitcoin** (CoinCap API)\n\n"
        report += f"💰 ${price:,.2f}\n"
        report += f"{emoji} {change:+.2f}% (24hr)\n"
        report += f"📊 High: ${binance_data['high_24h']:,.2f} | Low: ${binance_data['low_24h']:,.2f}\n\n"
        report += f"💬 พิมพ์ /btc เพื่อดูรายละเอียดเพิ่มเติม"
        
        await update.message.reply_text(report, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ ไม่สามารถดึงข้อมูลได้ กรุณาลองใหม่")


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
    application.add_handler(CommandHandler("a", quick_analysis))
    application.add_handler(CommandHandler("btc", btc_alert))
    application.add_handler(CommandHandler("btcprice", btc_price))
    application.add_handler(CommandHandler("b", btc_price))  # คำสั่งลัด
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
