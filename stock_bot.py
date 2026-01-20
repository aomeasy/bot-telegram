import os
import logging
import requests
import time
from collections import deque
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.ext import CallbackContext
from functools import lru_cache
from datetime import datetime, timedelta

 

# Rate limiter
class RateLimiter:
    def __init__(self, max_calls=6, period=60):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
    
    def wait_if_needed(self):
        now = time.time()
        # ลบ calls เก่าที่เกิน period
        while self.calls and self.calls[0] < now - self.period:
            self.calls.popleft()
        
        # ถ้าเกิน limit ให้รอ
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0]) + 0.5
            if sleep_time > 0:
                logger.warning(f"⏳ Rate limit - waiting {sleep_time:.1f}s")
                time.sleep(sleep_time)
                self.calls.clear()
        
        self.calls.append(time.time())

# สร้าง rate limiter สำหรับแต่ละ API
twelve_data_limiter = RateLimiter(max_calls=6, period=60)  # ปลอดภัย: 6 calls/min
# massive_limiter = RateLimiter(max_calls=60, period=60)  # 60 calls/min


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Config ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8336478185:AAF_OO9dQj4vjCictaD-aWoWWUGdi6vv_lY")
TWELVE_DATA_KEY = os.environ.get("TWELVE_DATA_KEY", "")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")
ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "NM9JUC6IIMTZCQIA")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
# MASSIVE_API_KEY = os.environ.get("MASSIVE_API_KEY", "0PYpBi0FWtRGox1nWfHkotKSBhTepRNU")
FMP_API_KEY = os.environ.get("FMP_API_KEY", "hPQqCSKAkUAjTiV2GUgttI7f5l5PC3oi")  # เพิ่มบรรทัดนี้


# --- Portfolio Configuration ---
PORTFOLIO = {
    "tech": {
        "name": "🖥️ Technology",
        "stocks": ["NVDA", "AVGO", "GOOGL", "META", "MSFT"]
    },
    "streaming": {
        "name": "🎬 Streaming & Media",
        "stocks": ["NFLX"]
    },
    "ecommerce": {
        "name": "🛒 E-Commerce",
        "stocks": ["AMZN"]
    },
    "space": {
        "name": "🚀 Space Tech",
        "stocks": ["RKLB"]
    },
    "finance": {
        "name": "💳 Finance",
        "stocks": ["V"]
    },
    "etf": {
        "name": "📈 ETF",
        "stocks": ["IVV"]
    }
}

# Flatten portfolio for quick access
ALL_STOCKS = []
for category in PORTFOLIO.values():
    ALL_STOCKS.extend(category["stocks"])
 
# Cache สำหรับข้อมูลที่อัพเดทเร็ว (Quote, Technical)
quote_cache = {}
CACHE_DURATION_QUOTE = 60  # 1 นาที

fundamental_cache = {}
CACHE_DURATION_FUNDAMENTAL = 3600  # 1 ชั่วโมง

def get_cached_data(cache_dict, key, duration):
    """ดึงข้อมูลจาก cache ถ้ายังไม่หมดอายุ"""
    if key in cache_dict:
        data, timestamp = cache_dict[key]
        if datetime.now() - timestamp < timedelta(seconds=duration):
            logger.info(f"✅ Using cached data for {key}")
            return data
    return None

def set_cached_data(cache_dict, key, data):
    """เก็บข้อมูลใน cache"""
    cache_dict[key] = (data, datetime.now()) 
 
def quick_api_call(url, params=None, timeout=3):
    """เรียก API แบบรวดเร็ว พร้อม timeout สั้น"""
    try:
        response = requests.get(url, params=params, timeout=timeout)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None
        
def get_quote(symbol):
    """ดึงราคาปัจจุบัน"""
    try:
        twelve_data_limiter.wait_if_needed()  # เพิ่มบรรทัดนี้
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
        twelve_data_limiter.wait_if_needed()
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
        twelve_data_limiter.wait_if_needed()
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
        twelve_data_limiter.wait_if_needed()
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
        twelve_data_limiter.wait_if_needed()
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

# ========================================
# ฟังก์ชันใหม่: ดึงข้อมูลจาก Massive.com
# ========================================

 

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



def get_fundamental_data(symbol):
    """ดึงข้อมูล Fundamental จาก Financial Modeling Prep"""
    try:
        # ตรวจสอบ cache ก่อน
        cache_key = f"fmp_fund_{symbol}"
        cached = get_cached_data(fundamental_cache, cache_key, CACHE_DURATION_FUNDAMENTAL)
        if cached:
            return cached
        
        # เรียก API สำหรับ Key Metrics
        url = f"https://financialmodelingprep.com/api/v3/key-metrics/{symbol}"
        params = {"apikey": FMP_API_KEY, "limit": 1}
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"⚠️ FMP API error {response.status_code}")
            return None
        
        metrics_data = response.json()
        
        if not metrics_data or len(metrics_data) == 0:
            logger.warning(f"⚠️ No fundamental data for {symbol}")
            return None
        
        metrics = metrics_data[0]
        
        # เรียก API สำหรับ Financial Ratios
        ratios_url = f"https://financialmodelingprep.com/api/v3/ratios/{symbol}"
        ratios_response = requests.get(ratios_url, params=params, timeout=10)
        
        ratios = {}
        if ratios_response.status_code == 200:
            ratios_data = ratios_response.json()
            if ratios_data and len(ratios_data) > 0:
                ratios = ratios_data[0]
        
        # แปลงข้อมูลให้ตรงกับโครงสร้างเดิม
        result = {
            'pe_ratio': metrics.get('peRatio'),
            'pb_ratio': metrics.get('pbRatio'),
            'debt_to_equity': ratios.get('debtEquityRatio'),
            'eps': metrics.get('netIncomePerShare'),
            'roe': metrics.get('roe'),
            'profit_margin': ratios.get('netProfitMargin'),
            'operating_margin': ratios.get('operatingProfitMargin'),
            'dividend_yield': metrics.get('dividendYield'),
            'beta': metrics.get('beta'),
            'revenue_per_share': metrics.get('revenuePerShare'),
            'quarterly_earnings_growth': metrics.get('earningsYield'),
            'quarterly_revenue_growth': metrics.get('revenuePerShare'),
            'book_value': metrics.get('bookValuePerShare'),
            'ebitda': metrics.get('enterpriseValue'),
            'pe_ratio_forward': metrics.get('peRatio'),
            'peg_ratio': metrics.get('pegRatio'),
            'market_cap': metrics.get('marketCap')
        }
        
        # บันทึกลง cache
        set_cached_data(fundamental_cache, cache_key, result)
        
        logger.info(f"✅ FMP fundamental data for {symbol}: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error fetching FMP fundamental data: {e}")
        return None

def get_cash_flow_data(symbol):
    """ดึงข้อมูล Cash Flow จาก Alpha Vantage"""
    try:
        if not ALPHA_VANTAGE_KEY or ALPHA_VANTAGE_KEY == "":
            return None
            
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "CASH_FLOW",
            "symbol": symbol,
            "apikey": ALPHA_VANTAGE_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if not data or 'annualReports' not in data or len(data['annualReports']) == 0:
            logger.warning(f"⚠️ No cash flow data for {symbol}")
            return None
        
        # ใช้ข้อมูลล่าสุด
        latest = data['annualReports'][0]
        
        operating_cf = float(latest.get('operatingCashflow', 0)) if latest.get('operatingCashflow') not in ['None', None] else None
        capex = float(latest.get('capitalExpenditures', 0)) if latest.get('capitalExpenditures') not in ['None', None] else None
        
        # คำนวณ Free Cash Flow
        free_cf = None
        if operating_cf and capex:
            free_cf = operating_cf - abs(capex)
        
        return {
            'operating_cashflow': operating_cf,
            'capital_expenditures': capex,
            'free_cashflow': free_cf
        }
    except Exception as e:
        logger.error(f"❌ Error fetching cash flow: {e}")
        return None

def get_earnings_data(symbol):
    """ดึงข้อมูล Earnings จาก Alpha Vantage"""
    try:
        if not ALPHA_VANTAGE_KEY or ALPHA_VANTAGE_KEY == "":
            return None
            
        url = "https://www.alphavantage.co/query"
        params = {
            "function": "EARNINGS",
            "symbol": symbol,
            "apikey": ALPHA_VANTAGE_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if not data or 'annualEarnings' not in data or len(data['annualEarnings']) < 2:
            return None
        
        # เปรียบเทียบ 2 ปีล่าสุด
        current_year = data['annualEarnings'][0]
        previous_year = data['annualEarnings'][1]
        
        current_eps = float(current_year.get('reportedEPS', 0)) if current_year.get('reportedEPS') not in ['None', None] else 0
        previous_eps = float(previous_year.get('reportedEPS', 0)) if previous_year.get('reportedEPS') not in ['None', None] else 0
        
        # คำนวณ Growth
        earnings_growth = None
        if previous_eps != 0:
            earnings_growth = ((current_eps - previous_eps) / abs(previous_eps)) * 100
        
        return {
            'current_eps': current_eps,
            'previous_eps': previous_eps,
            'earnings_growth_yoy': earnings_growth
        }
    except Exception as e:
        logger.error(f"❌ Error fetching earnings: {e}")
        return None
#----------------

 



def get_stock_analysis(symbol):
    """วิเคราะห์หุ้นแบบครบถ้วน - PARALLEL API CALLS"""
    try:
        if not TWELVE_DATA_KEY or TWELVE_DATA_KEY == "":
            return "no_key"
        
        logger.info(f"🔄 Analyzing {symbol}...")
        
        # ========================================
        # PARALLEL API CALLS - เรียก API พร้อมกัน
        # ========================================
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        
        start_time = time.time()
        results = {}
        def fetch_quote():
            return get_quote(symbol)
 
        
        # สร้าง tasks สำหรับดึงข้อมูลแบบ parallel
        tasks = {
            'quote': fetch_quote,
            'rsi': lambda: get_rsi(symbol),
            'macd': lambda: get_macd(symbol),
            'ema_20': lambda: get_ema(symbol, 20),
            'ema_50': lambda: get_ema(symbol, 50),
            'ema_200': lambda: get_ema(symbol, 200),
            'bbands': lambda: get_bbands(symbol),
            'fundamental': lambda: get_fundamental_data(symbol),
            'earnings': lambda: get_earnings_data(symbol),
            'recommendations': lambda: get_analyst_recommendations(symbol),
            'price_target': lambda: get_price_target(symbol)
        }
        
        # เรียก API แบบ parallel (max 5 threads พร้อมกัน)
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_task = {executor.submit(func): name for name, func in tasks.items()}
            
            for future in as_completed(future_to_task):
                task_name = future_to_task[future]
                try:
                    results[task_name] = future.result()
                    logger.info(f"✅ {task_name} completed")
                except Exception as e:
                    results[task_name] = None
                    logger.warning(f"⚠️ {task_name} failed: {e}")
        
        elapsed = time.time() - start_time
        logger.info(f"⏱️ All API calls completed in {elapsed:.2f}s")
        
        # ========================================
        # Extract results
        # ========================================
        quote = results.get('quote')
        if not quote:
            return None
        
        rsi = results.get('rsi')
        macd_result = results.get('macd')
        macd, macd_signal = macd_result if macd_result else (None, None)
        ema_20 = results.get('ema_20')
        ema_50 = results.get('ema_50')
        ema_200 = results.get('ema_200')
        bbands_result = results.get('bbands')
        bb_lower, bb_upper = bbands_result if bbands_result else (None, None)
        fundamental = results.get('fundamental')
        earnings = results.get('earnings')
        recommendations = results.get('recommendations')
        price_target = results.get('price_target')
        
        # คำนวณข้อมูลพื้นฐาน
        current = float(quote['close'])
        prev_close = float(quote.get('previous_close', current))
        change = current - prev_close
        change_pct = (change / prev_close) * 100
        high = float(quote.get('high', current))
        low = float(quote.get('low', current))
        open_price = float(quote.get('open', current))
        
        # สร้างรายงาน
        report = f"📊 **{symbol.upper()} Analysis**\n\n"
        
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
            
            upside_pct = ((target_mean - current) / current) * 100
            
            report += f"• ราคาเป้าหมาย: ${target_mean:.2f}"
            
            if target_high and target_low:
                report += f" (${target_low:.2f}-${target_high:.2f})\n"
            else:
                report += f"\n"
            
            if num_analysts > 0:
                report += f"• นักวิเคราะห์: {num_analysts} คน\n"
            
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



        # ============ Fundamental Analysis ============
        if fundamental:
            report += f"📊 **Fundamental Analysis:**\n"
            
            # Market Cap
            if fundamental.get('market_cap'):
                market_cap_b = fundamental['market_cap'] / 1_000_000_000
                report += f"• Market Cap: ${market_cap_b:.2f}B\n"
            
            # Valuation Metrics
            if fundamental.get('pe_ratio'):
                pe = fundamental['pe_ratio']
                report += f"• P/E Ratio: {pe:.2f}"
                if pe < 15:
                    report += " ⭐⭐⭐ (ถูกมาก)\n"
                elif pe < 25:
                    report += " ⭐⭐ (ยุติธรรม)\n"
                elif pe < 35:
                    report += " ⭐ (สูง)\n"
                else:
                    report += " ⚠️ (แพงเกิน)\n"
            
            if fundamental.get('pe_ratio_forward'):
                report += f"• Forward P/E: {fundamental['pe_ratio_forward']:.2f}\n"
            
            if fundamental.get('peg_ratio'):
                peg = fundamental['peg_ratio']
                report += f"• PEG Ratio: {peg:.2f}"
                if peg < 1:
                    report += " ⭐⭐⭐ (ดีมาก)\n"
                elif peg < 2:
                    report += " ⭐⭐ (ดี)\n"
                else:
                    report += " ⚠️\n"
            
            if fundamental.get('pb_ratio'):
                pb = fundamental['pb_ratio']
                report += f"• P/B Ratio: {pb:.2f}"
                if pb < 1.5:
                    report += " ⭐⭐⭐\n"
                elif pb < 3:
                    report += " ⭐⭐\n"
                else:
                    report += " ⭐\n"
            
            if fundamental.get('eps'):
                report += f"• EPS: ${fundamental['eps']:.2f}\n"
            
            # Profitability
            if fundamental.get('roe'):
                roe = fundamental['roe']
                if roe < 1:  # ถ้าเป็นทศนิยม (0.15 = 15%)
                    roe = roe * 100
                report += f"• ROE: {roe:.1f}%"
                if roe >= 15:
                    report += " 💪 (แข็งแกร่ง)\n"
                elif roe >= 10:
                    report += " 👍 (ดี)\n"
                else:
                    report += " ⚠️ (อ่อนแอ)\n"
            
            if fundamental.get('profit_margin'):
                margin = fundamental['profit_margin']
                if margin < 1:  # ถ้าเป็นทศนิยม
                    margin = margin * 100
                report += f"• Profit Margin: {margin:.1f}%"
                if margin >= 20:
                    report += " 💪\n"
                elif margin >= 10:
                    report += " 👍\n"
                else:
                    report += "\n"
            
            if fundamental.get('operating_margin'):
                op_margin = fundamental['operating_margin']
                if op_margin < 1:
                    op_margin = op_margin * 100
                report += f"• Operating Margin: {op_margin:.1f}%\n"
            
            # Financial Health
            if fundamental.get('debt_to_equity'):
                de = fundamental['debt_to_equity']
                report += f"• Debt/Equity: {de:.2f}"
                if de < 0.5:
                    report += " 💚 (ปลอดหนี้)\n"
                elif de < 1.0:
                    report += " 🟡 (พอใช้)\n"
                else:
                    report += " 🔴 (หนี้สูง)\n"
            
            # Growth
            if fundamental.get('quarterly_earnings_growth'):
                qeg = fundamental['quarterly_earnings_growth']
                if qeg < 1:
                    qeg = qeg * 100
                report += f"• Quarterly Earnings Growth: {qeg:+.1f}%"
                if qeg >= 20:
                    report += " 🚀\n"
                elif qeg >= 10:
                    report += " 📈\n"
                elif qeg >= 0:
                    report += "\n"
                else:
                    report += " 📉\n"
            
            if fundamental.get('quarterly_revenue_growth'):
                qrg = fundamental['quarterly_revenue_growth']
                if qrg < 1:
                    qrg = qrg * 100
                report += f"• Quarterly Revenue Growth: {qrg:+.1f}%\n"
            
            # Others
            if fundamental.get('dividend_yield'):
                div = fundamental['dividend_yield']
                if div < 1:
                    div = div * 100
                if div > 0:
                    report += f"• Dividend Yield: {div:.2f}%\n"
            
            if fundamental.get('beta'):
                beta = fundamental['beta']
                report += f"• Beta: {beta:.2f}"
                if beta < 1:
                    report += " (ความผันผวนต่ำ)\n"
                elif beta > 1.5:
                    report += " (ความผันผวนสูง)\n"
                else:
                    report += "\n"
            
            report += "\n"
      
          
        # ============ Cash Flow Analysis ============
        if cash_flow:
            report += f"💰 **Cash Flow Analysis:**\n"
            
            if cash_flow.get('operating_cashflow'):
                ocf = cash_flow['operating_cashflow'] / 1_000_000_000  # Convert to billions
                report += f"• Operating Cash Flow: ${ocf:.2f}B"
                if ocf > 5:
                    report += " 💪\n"
                elif ocf > 1:
                    report += " 👍\n"
                elif ocf > 0:
                    report += " ✅\n"
                else:
                    report += " ⚠️ (เป็นลบ)\n"
            
            if cash_flow.get('capital_expenditures'):
                capex = abs(cash_flow['capital_expenditures']) / 1_000_000_000
                report += f"• Capital Expenditures: ${capex:.2f}B\n"
            
            if cash_flow.get('free_cashflow'):
                fcf = cash_flow['free_cashflow'] / 1_000_000_000
                report += f"• Free Cash Flow: ${fcf:.2f}B"
                if fcf > 5:
                    report += " 💪 (แข็งแกร่ง)\n"
                elif fcf > 1:
                    report += " 👍 (ดี)\n"
                elif fcf > 0:
                    report += " ✅\n"
                else:
                    report += " ⚠️ (เป็นลบ)\n"
            
            report += "\n"
        

        # ============ Earnings Growth ============
        if earnings and earnings.get('earnings_growth_yoy') is not None:
            growth = earnings['earnings_growth_yoy']
            report += f"📈 **Earnings Growth (YoY):** {growth:+.1f}%"
            if growth >= 20:
                report += " 🚀 (เติบโตสูง)\n"
            elif growth >= 10:
                report += " 📈 (เติบโตดี)\n"
            elif growth >= 0:
                report += " ➡️ (เติบโตช้า)\n"
            else:
                report += " 📉 (ติดลบ)\n"
            
            if earnings.get('current_eps') and earnings.get('previous_eps'):
                report += f"• Current EPS: ${earnings['current_eps']:.2f}\n"
                report += f"• Previous EPS: ${earnings['previous_eps']:.2f}\n"
            
            if earnings.get('revenue'):
                revenue_b = earnings['revenue'] / 1_000_000_000
                report += f"• Revenue: ${revenue_b:.2f}B\n"
            
            report += "\n"
    #-------------------
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
        
        # ดึงข้อมูลเทคนิคคอล - ถ้า error ให้เป็น None
        try:
            rsi = get_rsi(symbol)
        except:
            rsi = None
            logger.warning(f"⚠️ Cannot get RSI for {symbol}")
            
        try:
            macd, macd_signal = get_macd(symbol)
        except:
            macd, macd_signal = None, None
            logger.warning(f"⚠️ Cannot get MACD for {symbol}")
            
        try:
            ema_20 = get_ema(symbol, 20)
        except:
            ema_20 = None
            logger.warning(f"⚠️ Cannot get EMA20 for {symbol}")
            
        try:
            ema_50 = get_ema(symbol, 50)
        except:
            ema_50 = None
            logger.warning(f"⚠️ Cannot get EMA50 for {symbol}")
        
        # ดึงข้อมูล Fundamental
        try:
            price_target = get_price_target(symbol)
        except:
            price_target = None
            logger.warning(f"⚠️ Cannot get price target for {symbol}")
            
        try:
            fundamental = get_fundamental_data(symbol)
        except:
            fundamental = None
            logger.warning(f"⚠️ Cannot get fundamental data for {symbol}")
            
        try:
            earnings = get_earnings_data(symbol)
        except:
            earnings = None
            logger.warning(f"⚠️ Cannot get earnings for {symbol}")
        
        # คะแนนการวิเคราะห์
        score = 0
        signals = []
        
        # 1. Valuation (น้ำหนัก 30% ลดลงจาก 40%)
        if price_target and price_target.get('target_mean'):
            target_mean = price_target['target_mean']
            upside_pct = ((target_mean - current) / current) * 100
            
           

            if upside_pct >= 20:
                score += 30  # ลดลงจาก 40
                signals.append(f"💎 Valuation: +{upside_pct:.1f}% (ถูกมาก)")
            elif upside_pct >= 10:
                score += 20  # ลดลงจาก 25
                signals.append(f"💎 Valuation: +{upside_pct:.1f}% (น่าสนใจ)")
            elif upside_pct >= 0:
                score += 8  # ลดลงจาก 10
                signals.append(f"💎 Valuation: +{upside_pct:.1f}% (ยุติธรรม)")
            elif upside_pct >= -10:
                score -= 10
                signals.append(f"⚠️ Valuation: {upside_pct:.1f}% (แพง)")
            else:
                score -= 25  # ลดลงจาก 30
                signals.append(f"🚨 Valuation: {upside_pct:.1f}% (แพงเกิน)")


# 1.5 Fundamental Score (น้ำหนัก 20%)
        if fundamental:
            # P/E Ratio (10 คะแนน)
            if fundamental.get('pe_ratio'):
                pe = fundamental['pe_ratio']
                if pe < 15:
                    score += 10
                    signals.append(f"📊 P/E: {pe:.1f} (ถูก)")
                elif pe < 25:
                    score += 5
                    signals.append(f"📊 P/E: {pe:.1f} (ปกติ)")
                elif pe > 35:
                    score -= 10
                    signals.append(f"📊 P/E: {pe:.1f} (แพง)")
            
            # PEG Ratio (5 คะแนน)
            if fundamental.get('peg_ratio'):
                peg = fundamental['peg_ratio']
                if peg < 1:
                    score += 5
                    signals.append(f"💎 PEG: {peg:.2f} (ดีมาก)")
                elif peg > 2:
                    score -= 5
                    signals.append(f"⚠️ PEG: {peg:.2f}")
            
            # Debt/Equity (5 คะแนน)
            if fundamental.get('debt_to_equity'):
                de = fundamental['debt_to_equity']
                if de < 0.5:
                    score += 5
                    signals.append(f"💰 D/E: {de:.2f} (แข็งแกร่ง)")
                elif de > 1.5:
                    score -= 5
                    signals.append(f"⚠️ D/E: {de:.2f} (หนี้สูง)")
            
            # ROE (5 คะแนน)
            if fundamental.get('roe'):
                roe = fundamental['roe'] * 100
                if roe >= 15:
                    score += 5
                    signals.append(f"💪 ROE: {roe:.1f}%")
                elif roe < 10:
                    score -= 5
                    signals.append(f"⚠️ ROE: {roe:.1f}%")
            
            # Profit Margin (5 คะแนน)
            if fundamental.get('profit_margin'):
                margin = fundamental['profit_margin'] * 100
                if margin >= 20:
                    score += 5
                    signals.append(f"💰 Margin: {margin:.1f}%")
                elif margin < 5:
                    score -= 5
                    signals.append(f"⚠️ Margin: {margin:.1f}%")
        
        # 1.6 Earnings Growth (10 คะแนน)
        if earnings and earnings.get('earnings_growth_yoy') is not None:
            growth = earnings['earnings_growth_yoy']
            if growth >= 20:
                score += 10
                signals.append(f"🚀 Growth: +{growth:.1f}%")
            elif growth >= 10:
                score += 5
                signals.append(f"📈 Growth: +{growth:.1f}%")
            elif growth < 0:
                score -= 10
                signals.append(f"📉 Growth: {growth:.1f}%")



        # 2. RSI (น้ำหนัก 10% ลดลงจาก 20%)
        if rsi:
            if rsi <= 30:
                score += 10  # ลดลงจาก 20
                signals.append(f"📈 RSI: {rsi:.1f} (Oversold)")
            elif rsi <= 40:
                score += 5  # ลดลงจาก 10
                signals.append(f"📈 RSI: {rsi:.1f} (ต่ำ)")
            elif rsi >= 70:
                score -= 10  # ลดลงจาก 20
                signals.append(f"📉 RSI: {rsi:.1f} (Overbought)")
            elif rsi >= 60:
                score -= 5  # ลดลงจาก 10
                signals.append(f"📉 RSI: {rsi:.1f} (สูง)")
            else:
                signals.append(f"➡️ RSI: {rsi:.1f} (กลาง)")
        
        # 3. MACD (น้ำหนัก 10% ลดลงจาก 20%)
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                score += 10  # ลดลงจาก 20
                signals.append("📊 MACD: Bullish")
            else:
                score -= 10  # ลดลงจาก 20
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

# --- NEW: Menu-based Quick Access Handlers ---

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """แสดงเมนูหลัก - เลือกหมวดหมู่หุ้น"""
    keyboard = []
    
    # สร้างปุ่มตามหมวดหมู่
    for cat_id, cat_data in PORTFOLIO.items():
        keyboard.append([
            InlineKeyboardButton(
                cat_data["name"], 
                callback_data=f"cat_{cat_id}"
            )
        ])
    
    # เพิ่มปุ่มวิเคราะห์ทั้งหมด
    keyboard.append([
        InlineKeyboardButton("📊 วิเคราะห์ทั้งหมด", callback_data="analyze_all")
    ])
    
    # เพิ่มปุ่ม Crypto
    keyboard.append([
        InlineKeyboardButton("🪙 Bitcoin Analysis", callback_data="btc_full"),
        InlineKeyboardButton("⚡ BTC Quick", callback_data="btc_quick")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        "📊 **Quick Access Menu**\n\n"
        "เลือกหมวดหมู่หุ้นที่ต้องการวิเคราะห์:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def show_category_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: str):
    """แสดงรายการหุ้นในหมวดหมู่"""
    query = update.callback_query
    await query.answer()
    
    if category_id not in PORTFOLIO:
        await query.edit_message_text("❌ ไม่พบหมวดหมู่นี้")
        return
    
    category = PORTFOLIO[category_id]
    keyboard = []
    
    # สร้างปุ่มสำหรับแต่ละหุ้น (2 ปุ่มต่อแถว)
    stocks = category["stocks"]
    for i in range(0, len(stocks), 2):
        row = []
        for stock in stocks[i:i+2]:
            row.append(
                InlineKeyboardButton(
                    f"📈 {stock}",
                    callback_data=f"stock_{stock}"
                )
            )
        keyboard.append(row)
    
    # ปุ่มวิเคราะห์หมวดหมู่นี้ทั้งหมด
    keyboard.append([
        InlineKeyboardButton(
            f"📊 วิเคราะห์ {category['name']} ทั้งหมด",
            callback_data=f"cat_analyze_{category_id}"
        )
    ])
    
    # ปุ่มกลับ
    keyboard.append([
        InlineKeyboardButton("◀️ กลับเมนูหลัก", callback_data="back_main")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"{category['name']}\n\nเลือกหุ้นที่ต้องการวิเคราะห์:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def analyze_single_stock(update: Update, context: ContextTypes.DEFAULT_TYPE, symbol: str):
    """วิเคราะห์หุ้นเดียว"""
    query = update.callback_query
    await query.answer()
    
    processing = await query.edit_message_text(
        f"🔍 กำลังวิเคราะห์ {symbol}...\n⏳ กำลังดึงข้อมูล..."
    )
    
    analysis = get_stock_analysis(symbol)
    
    # สร้างปุ่มกลับ
    keyboard = [[
        InlineKeyboardButton("◀️ กลับ", callback_data="back_main")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if analysis == "no_key":
        await query.edit_message_text(
            "⚠️ **ไม่พบ API Key**\n\n"
            "กรุณาตั้งค่า TWELVE_DATA_KEY ใน Environment",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif analysis:
        if len(analysis) > 4000:
            mid_point = analysis.rfind('\n\n', 0, 2000)
            if mid_point == -1:
                mid_point = 2000
            
            part1 = analysis[:mid_point]
            part2 = analysis[mid_point:]
            
            await query.edit_message_text(part1, parse_mode='Markdown')
            await query.message.reply_text(
                part2,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                analysis,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    else:
        await query.edit_message_text(
            f"❌ ไม่พบข้อมูลหุ้น {symbol}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def analyze_category(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: str):
    """วิเคราะห์หุ้นทั้งหมดในหมวดหมู่"""
    query = update.callback_query
    await query.answer()
    
    if category_id not in PORTFOLIO:
        await query.edit_message_text("❌ ไม่พบหมวดหมู่นี้")
        return
    
    category = PORTFOLIO[category_id]
    stocks = category["stocks"]
    
    processing = await query.edit_message_text(
        f"🔍 กำลังวิเคราะห์ {category['name']} ({len(stocks)} หุ้น)...\n"
        f"⏳ กรุณารอสักครู่..."
    )
    
    results = []
    for symbol in stocks:
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
    
    # สร้างรายงาน
    report = f"📊 **{category['name']} Analysis**\n\n"
    
    for r in sorted(results, key=lambda x: x['score'], reverse=True):
        report += f"{r['emoji']} **{r['symbol']}** - ${r['price']:.2f}\n"
        report += f"   {r['recommendation']} (Score: {r['score']})\n\n"
    
    report += f"⏰ อัพเดท: {datetime.now().strftime('%H:%M:%S')}"
    
    # ปุ่มกลับ
    keyboard = [[
        InlineKeyboardButton("◀️ กลับเมนูหลัก", callback_data="back_main")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        report,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """จัดการ callback จากปุ่ม"""
    query = update.callback_query
    
    # แยก callback data
    if query.data == "back_main":
        await show_main_menu(update, context)
    
    elif query.data == "analyze_all":
        await quick_analysis(update, context)
    
    elif query.data == "btc_full":
        await btc_alert_callback(update, context)
    
    elif query.data == "btc_quick":
        await btc_price_callback(update, context)
    
    elif query.data.startswith("cat_analyze_"):
        category_id = query.data.replace("cat_analyze_", "")
        await analyze_category(update, context, category_id)
    
    elif query.data.startswith("cat_"):
        category_id = query.data.replace("cat_", "")
        await show_category_stocks(update, context, category_id)
    
    elif query.data.startswith("stock_"):
        symbol = query.data.replace("stock_", "")
        await analyze_single_stock(update, context, symbol)

# Bitcoin handlers for callback
async def btc_alert_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bitcoin analysis via callback"""
    query = update.callback_query
    await query.answer()
    
    processing = await query.edit_message_text(
        "🔍 กำลังวิเคราะห์ Bitcoin...\n"
        "⏳ กำลังดึงข้อมูลจาก Bitkub..."
    )
    
    try:
        bitkub_url = "https://api.bitkub.com/api/market/ticker"
        params = {"sym": "THB_BTC"}
        
        response = requests.get(bitkub_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if 'THB_BTC' not in data:
            raise Exception("No THB_BTC data")
        
        btc_data = data['THB_BTC']
        price_thb = float(btc_data['last'])
        high_thb = float(btc_data['high24hr'])
        low_thb = float(btc_data['low24hr'])
        change_pct = float(btc_data.get('percentChange', 0))
        
        if change_pct == 0 and high_thb > 0:
            avg_price = (high_thb + low_thb) / 2
            change_pct = ((price_thb - avg_price) / avg_price) * 100
        
        emoji = "🟢" if change_pct >= 0 else "🔴"
        
        report = "🪙 **Bitcoin Analysis**\n\n"
        report += f"💰 **ราคา:** ฿{price_thb:,.2f}\n"
        report += f"{emoji} **24hr:** {change_pct:+.2f}%\n"
        report += f"📊 **ช่วง:** ฿{low_thb:,.2f} - ฿{high_thb:,.2f}\n\n"
        report += f"⏰ อัพเดท: {datetime.now().strftime('%H:%M:%S')}"
        
        keyboard = [[
            InlineKeyboardButton("◀️ กลับ", callback_data="back_main")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            report,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        keyboard = [[
            InlineKeyboardButton("◀️ กลับ", callback_data="back_main")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "❌ ไม่สามารถดึงข้อมูล Bitcoin ได้",
            reply_markup=reply_markup
        )

async def btc_price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick BTC price via callback"""
    await btc_alert_callback(update, context)

# --- Original Handlers (คงเดิม) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """🤖 **ยินดีต้อนรับสู่ Stock Analysis Bot!** 📈

💡 **วิธีใช้งาน:**
• /menu - เมนูเลือกหุ้นแบบรวดเร็ว ⚡ (แนะนำ!)
• พิมพ์ชื่อหุ้น เช่น: NVDA, NFLX, AMZN
• /help - ดูคำแนะนำ
• /popular - ดูหุ้นยอดนิยม
• /a - วิเคราะห์ทั้งหมด
• /btc - วิเคราะห์ BTC แบบละเอียด 🪙
• /b - ดูราคา BTC แบบรวดเร็ว ⚡

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
/menu - เมนูเลือกหุ้นแบบรวดเร็ว
/popular - ดูหุ้นยอดนิยม

**คำสั่ง Crypto:**
/btc - วิเคราะห์ Bitcoin แบบครบวงจร
/b หรือ /btcprice - ดูราคา BTC แบบรวดเร็ว

⚠️ รองรับหุ้นอเมริกา และบางหุ้นนานาชาติ
⚠️ ข้อมูลเพื่อการศึกษาเท่านั้น"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def popular_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    popular = """📈 หุ้นยอดนิยม

เทคโนโลยี: AAPL, MSFT, GOOGL, META, NVDA, TSLA, AMZN, AVGO

การเงิน: JPM, BAC, V, MA, GS, MS

พลังงาน: XOM, CVX, COP

อุปโภคบริโภค: WMT, KO, PG, MCD, NKE

สุขภาพ: JNJ, UNH, PFE, ABBV

💡 Tip: ใช้ /menu เพื่อเข้าถึงหุ้นในพอร์ตอย่างรวดเร็ว!"""
    await update.message.reply_text(popular, parse_mode='Markdown')

async def analyze_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: 
        return
    
    user_input = update.message.text.strip().upper()
    
    if len(user_input) < 1 or len(user_input) > 6 or not user_input.isalpha(): 
        return
    
    processing = await update.message.reply_text(
        f"🔍 กำลังวิเคราะห์ {user_input}...\n"
        f"⏳ กำลังดึงข้อมูล RSI, MACD, EMA, Bollinger Bands, Valuation..."
    )
    analysis = get_stock_analysis(user_input)
    
    if analysis == "no_key":
        await processing.edit_text(
            "⚠️ **ไม่พบ API Key**\n\n"
            "กรุณาตั้งค่า TWELVE_DATA_KEY ใน Environment\n"
            "รับ Free API Key: https://twelvedata.com/apikey", 
            parse_mode='Markdown'
        )
    elif analysis:
        if len(analysis) > 4000:
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
    """วิเคราะห์ด่วนหุ้นทั้งหมดในพอร์ต"""
    
    # จัดการทั้ง message และ callback query
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        processing = await query.edit_message_text(
            f"🔍 กำลังวิเคราะห์ {len(ALL_STOCKS)} หุ้นในพอร์ต...\n"
            f"⏳ กรุณารอสักครู่..."
        )
    else:
        processing = await update.message.reply_text(
            f"🔍 กำลังวิเคราะห์ {len(ALL_STOCKS)} หุ้นในพอร์ต...\n"
            f"⏳ กรุณารอสักครู่..."
        )
    
    results = []
    for symbol in ALL_STOCKS:
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
    
    report += f"⏰ อัพเดท: {datetime.now().strftime('%H:%M:%S')}"
    
    # ปุ่มกลับ (ถ้าเป็น callback)
    if update.callback_query:
        keyboard = [[
            InlineKeyboardButton("◀️ กลับเมนูหลัก", callback_data="back_main")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await processing.edit_text(report, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await processing.edit_text(report, parse_mode='Markdown')

async def btc_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """BTC analysis command"""
    processing = await update.message.reply_text(
        "🔍 กำลังวิเคราะห์ Bitcoin...\n"
        "⏳ กำลังดึงข้อมูลจาก Bitkub..."
    )
    
    try:
        bitkub_url = "https://api.bitkub.com/api/market/ticker"
        params = {"sym": "THB_BTC"}
        
        response = requests.get(bitkub_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if 'THB_BTC' not in data:
            raise Exception("No THB_BTC data")
        
        btc_data = data['THB_BTC']
        price_thb = float(btc_data['last'])
        high_thb = float(btc_data['high24hr'])
        low_thb = float(btc_data['low24hr'])
        change_pct = float(btc_data.get('percentChange', 0))
        
        if change_pct == 0 and high_thb > 0:
            avg_price = (high_thb + low_thb) / 2
            change_pct = ((price_thb - avg_price) / avg_price) * 100
        
        emoji = "🟢" if change_pct >= 0 else "🔴"
        
        report = "🪙 **Bitcoin Analysis**\n\n"
        report += f"💰 **ราคา:** ฿{price_thb:,.2f}\n"
        report += f"{emoji} **24hr:** {change_pct:+.2f}%\n"
        report += f"📊 **ช่วง:** ฿{low_thb:,.2f} - ฿{high_thb:,.2f}\n\n"
        report += f"⏰ อัพเดท: {datetime.now().strftime('%H:%M:%S')}"
        
        await processing.edit_text(report, parse_mode='Markdown')
        
    except Exception as e:
        await processing.edit_text("❌ ไม่สามารถดึงข้อมูล Bitcoin ได้")

async def btc_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick BTC price"""
    await btc_alert(update, context)

async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /health command"""
    await update.message.reply_text("✅ Bot is running!")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# --- Main ---

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("popular", popular_stocks))
    application.add_handler(CommandHandler("menu", show_main_menu))  # NEW
    application.add_handler(CommandHandler("m", show_main_menu))  # Shortcut
    application.add_handler(CommandHandler("a", quick_analysis))
    application.add_handler(CommandHandler("btc", btc_alert))
    application.add_handler(CommandHandler("btcprice", btc_price))
    application.add_handler(CommandHandler("b", btc_price))
    application.add_handler(CommandHandler("health", health_check))
    
    # Callback handler for buttons
    application.add_handler(CallbackQueryHandler(button_callback))  # NEW
    
    # Message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_stock))
    
    # Error handler
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
