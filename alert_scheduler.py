import asyncio
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import pytz

logger = logging.getLogger(__name__)

# Watchlist หุ้นที่ต้องติดตาม
WATCHLIST = ["NVDA", "NFLX", "AMZN", "GOOGL", "RKLB", "V", "MSFT", "IVV", "AVGO", "META"]

class AlertScheduler:
    def __init__(self, bot_application):
        self.app = bot_application
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Bangkok'))
        self.last_alerts = {}  # เก็บ alerts ที่ส่งไปแล้ว เพื่อไม่ส่งซ้ำ
        
    def start(self):
        """เริ่มต้น Scheduler"""
        
        # 1. ตรวจสอบ Technical Signals ทุก 15 นาที (เฉพาะเวลาตลาดเปิด)
        self.scheduler.add_job(
            self.check_technical_signals,
            trigger=IntervalTrigger(minutes=15),
            id='technical_signals',
            name='Check Technical Signals',
            replace_existing=True
        )
        
        # 2. ตรวจสอบ Support/Resistance ทุก 10 นาที
        self.scheduler.add_job(
            self.check_support_resistance,
            trigger=IntervalTrigger(minutes=10),
            id='support_resistance',
            name='Check Support/Resistance',
            replace_existing=True
        )
        
        # 3. ตรวจสอบ Market Sentiment ทุกชั่วโมง
        self.scheduler.add_job(
            self.check_market_sentiment,
            trigger=IntervalTrigger(hours=1),
            id='market_sentiment',
            name='Check Market Sentiment',
            replace_existing=True
        )
        
        # 4. ล้างข้อมูล alerts เก่าทุกเที่ยงคืน
        self.scheduler.add_job(
            self.cleanup_old_alerts,
            trigger=CronTrigger(hour=0, minute=0),
            id='cleanup',
            name='Cleanup Old Alerts',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("✅ Alert Scheduler started successfully")
    
    async def check_technical_signals(self):
        """ตรวจสอบสัญญาณเทคนิค"""
        try:
            # เช็คว่าเป็นเวลาตลาดเปิดหรือไม่ (US Market: 21:30-04:00 ICT)
            if not self.is_market_hours():
                logger.info("⏸️ Market closed - skipping technical signals check")
                return
            
            logger.info("🔍 Checking technical signals...")
            
            for symbol in WATCHLIST:
                await self.analyze_technical_signals(symbol)
            
            logger.info("✅ Technical signals check completed")
            
        except Exception as e:
            logger.error(f"❌ Error checking technical signals: {e}")
    
    async def analyze_technical_signals(self, symbol):
        """วิเคราะห์สัญญาณเทคนิคของหุ้น"""
        try:
            from main import get_quote, get_rsi, get_macd, get_ema, get_bbands
            
            # ดึงข้อมูล
            quote = get_quote(symbol)
            if not quote or 'close' not in quote:
                return
            
            current_price = float(quote['close'])
            rsi = get_rsi(symbol)
            macd, macd_signal = get_macd(symbol)
            ema_50 = get_ema(symbol, 50)
            ema_200 = get_ema(symbol, 200)
            bb_lower, bb_upper = get_bbands(symbol)
            
            alerts = []
            
            # 1. RSI Oversold/Overbought
            if rsi:
                if rsi < 30:
                    alert = self.create_rsi_alert(symbol, rsi, current_price, "oversold")
                    alerts.append(("rsi_oversold", alert))
                elif rsi > 70:
                    alert = self.create_rsi_alert(symbol, rsi, current_price, "overbought")
                    alerts.append(("rsi_overbought", alert))
            
            # 2. MACD Crossover
            if macd is not None and macd_signal is not None:
                # ต้องเก็บค่า MACD ก่อนหน้าเพื่อตรวจสอบ crossover
                previous_macd = self.get_previous_macd(symbol)
                if previous_macd:
                    prev_macd, prev_signal = previous_macd
                    
                    # Bullish Crossover: MACD ตัดขึ้น Signal
                    if prev_macd <= prev_signal and macd > macd_signal:
                        alert = self.create_macd_alert(symbol, current_price, "bullish")
                        alerts.append(("macd_bullish", alert))
                    
                    # Bearish Crossover: MACD ตัดลง Signal
                    elif prev_macd >= prev_signal and macd < macd_signal:
                        alert = self.create_macd_alert(symbol, current_price, "bearish")
                        alerts.append(("macd_bearish", alert))
                
                # เก็บค่า MACD ปัจจุบัน
                self.save_macd_value(symbol, macd, macd_signal)
            
            # 3. Bollinger Bands
            if bb_lower and bb_upper:
                if current_price <= bb_lower:
                    alert = self.create_bb_alert(symbol, current_price, bb_lower, bb_upper, "lower")
                    alerts.append(("bb_lower", alert))
                elif current_price >= bb_upper:
                    alert = self.create_bb_alert(symbol, current_price, bb_lower, bb_upper, "upper")
                    alerts.append(("bb_upper", alert))
            
            # 4. Golden Cross / Death Cross
            if ema_50 and ema_200:
                previous_ema = self.get_previous_ema(symbol)
                if previous_ema:
                    prev_ema_50, prev_ema_200 = previous_ema
                    
                    # Golden Cross: EMA 50 ตัดขึ้น EMA 200
                    if prev_ema_50 <= prev_ema_200 and ema_50 > ema_200:
                        alert = self.create_cross_alert(symbol, current_price, "golden")
                        alerts.append(("golden_cross", alert))
                    
                    # Death Cross: EMA 50 ตัดลง EMA 200
                    elif prev_ema_50 >= prev_ema_200 and ema_50 < ema_200:
                        alert = self.create_cross_alert(symbol, current_price, "death")
                        alerts.append(("death_cross", alert))
                
                # เก็บค่า EMA ปัจจุบัน
                self.save_ema_value(symbol, ema_50, ema_200)
            
            # ส่ง alerts (ถ้ามี)
            for alert_type, alert_message in alerts:
                await self.send_alert_if_new(symbol, alert_type, alert_message)
        
        except Exception as e:
            logger.error(f"❌ Error analyzing {symbol}: {e}")
    
    async def check_support_resistance(self):
        """ตรวจสอบแนวรับ/แนวต้าน"""
        try:
            if not self.is_market_hours():
                return
            
            logger.info("🔍 Checking support/resistance...")
            
            for symbol in WATCHLIST:
                await self.analyze_support_resistance(symbol)
            
            logger.info("✅ Support/Resistance check completed")
            
        except Exception as e:
            logger.error(f"❌ Error checking support/resistance: {e}")
    
    async def analyze_support_resistance(self, symbol):
        """วิเคราะห์แนวรับ/แนวต้าน"""
        try:
            from main import get_quote, get_bbands
            
            quote = get_quote(symbol)
            if not quote or 'close' not in quote:
                return
            
            current_price = float(quote['close'])
            bb_lower, bb_upper = get_bbands(symbol)
            
            if not bb_lower or not bb_upper:
                return
            
            # คำนวณระยะห่างจากแนวรับ/แนวต้าน
            distance_to_support = ((current_price - bb_lower) / current_price) * 100
            distance_to_resistance = ((bb_upper - current_price) / current_price) * 100
            
            # แจ้งเตือนถ้าใกล้แนวรับ/แนวต้าน (ภายใน 2%)
            if distance_to_support <= 2:
                alert = self.create_support_resistance_alert(
                    symbol, current_price, bb_lower, bb_upper, 
                    distance_to_support, "support"
                )
                await self.send_alert_if_new(symbol, "near_support", alert)
            
            elif distance_to_resistance <= 2:
                alert = self.create_support_resistance_alert(
                    symbol, current_price, bb_lower, bb_upper, 
                    distance_to_resistance, "resistance"
                )
                await self.send_alert_if_new(symbol, "near_resistance", alert)
        
        except Exception as e:
            logger.error(f"❌ Error analyzing support/resistance for {symbol}: {e}")
    
    async def check_market_sentiment(self):
        """ตรวจสอบความเชื่อมั่นตลาด"""
        try:
            logger.info("🔍 Checking market sentiment...")
            
            from main import get_quote
            
            # ดึงข้อมูล S&P 500 และ VIX
            spy = get_quote("SPY")  # S&P 500 ETF
            vix = get_quote("^VIX")  # VIX Index (ถ้า API รองรับ)
            
            if spy and 'close' in spy:
                current = float(spy['close'])
                prev_close = float(spy.get('previous_close', current))
                change_pct = ((current - prev_close) / prev_close) * 100
                
                # ถ้าตลาดเปลี่ยนแปลงมากกว่า 1%
                if abs(change_pct) >= 1:
                    alert = self.create_market_sentiment_alert(change_pct, vix)
                    await self.send_alert_if_new("MARKET", "sentiment", alert)
            
            logger.info("✅ Market sentiment check completed")
            
        except Exception as e:
            logger.error(f"❌ Error checking market sentiment: {e}")
    
    # ===== Helper Methods =====
    
    def create_rsi_alert(self, symbol, rsi, price, alert_type):
        """สร้าง RSI Alert Message"""
        from main import get_bbands
        
        bb_lower, bb_upper = get_bbands(symbol)
        support = f"${bb_lower:.2f}" if bb_lower else "N/A"
        
        if alert_type == "oversold":
            emoji = "🟢"
            condition = "Oversold"
            recommendation = "พิจารณาจุดซื้อ"
        else:
            emoji = "🔴"
            condition = "Overbought"
            recommendation = "พิจารณาจุดขาย"
        
        return f"""⚡ {symbol} - สัญญาณเทคนิคสำคัญ!

{emoji} RSI = {rsi:.1f} ({condition}!)
   ราคาอาจจะปรับตัว{"ขึ้น" if alert_type == "oversold" else "ลง"}

💡 คำแนะนำ: {recommendation}
📍 ราคาปัจจุบัน: ${price:.2f}
🛡️ แนวรับ: {support}

วิเคราะห์เพิ่ม: /aiplus {symbol}"""
    
    def create_macd_alert(self, symbol, price, signal_type):
        """สร้าง MACD Alert Message"""
        if signal_type == "bullish":
            emoji = "🟢"
            trend = "กลับตัวขึ้น (Bullish)"
            action = "โอกาสซื้อ"
        else:
            emoji = "🔴"
            trend = "กลับตัวลง (Bearish)"
            action = "พิจารณาขาย/ลดน้ำหนัก"
        
        return f"""⚡ {symbol} - MACD Crossover!

{emoji} MACD {trend}
   สัญญาณเปลี่ยนแนวโน้ม

💡 คำแนะนำ: {action}
📍 ราคาปัจจุบัน: ${price:.2f}

วิเคราะห์เพิ่ม: /aiplus {symbol}"""
    
    def create_bb_alert(self, symbol, price, bb_lower, bb_upper, band_type):
        """สร้าง Bollinger Bands Alert"""
        if band_type == "lower":
            emoji = "🟢"
            message = "ทะลุแนวล่าง Bollinger Bands"
            recommendation = "โอกาสซื้อ - ราคาอาจตีกลับขึ้น"
        else:
            emoji = "🔴"
            message = "ทะลุแนวบน Bollinger Bands"
            recommendation = "ระวัง - ราคาอาจปรับฐาน"
        
        return f"""⚡ {symbol} - Bollinger Bands Signal!

{emoji} {message}

📊 Bollinger Bands:
   Upper: ${bb_upper:.2f}
   Lower: ${bb_lower:.2f}
   ราคา: ${price:.2f}

💡 {recommendation}

วิเคราะห์เพิ่ม: /aiplus {symbol}"""
    
    def create_cross_alert(self, symbol, price, cross_type):
        """สร้าง Golden/Death Cross Alert"""
        if cross_type == "golden":
            emoji = "🟢"
            name = "Golden Cross"
            description = "EMA 50 ตัดขึ้น EMA 200"
            signal = "สัญญาณขาขึ้นระยะยาว"
            action = "โอกาสซื้อระยะยาว"
        else:
            emoji = "🔴"
            name = "Death Cross"
            description = "EMA 50 ตัดลง EMA 200"
            signal = "สัญญาณขาลงระยะยาว"
            action = "พิจารณาขายหรือลดน้ำหนัก"
        
        return f"""⚡ {symbol} - {name}!

{emoji} {description}
   {signal}

📍 ราคาปัจจุบัน: ${price:.2f}
💡 คำแนะนำ: {action}

วิเคราะห์เพิ่ม: /aiplus {symbol}"""
    
    def create_support_resistance_alert(self, symbol, price, support, resistance, distance, level_type):
        """สร้าง Support/Resistance Alert"""
        if level_type == "support":
            emoji = "🛡️"
            level = support
            level_name = "แนวรับ"
            scenario1 = f"ทะลุแนวรับ → อาจลงต่อไปที่ ${support * 0.97:.2f}"
            scenario2 = f"ตีกลับ → เป้าหมาย ${resistance:.2f}"
        else:
            emoji = "🎯"
            level = resistance
            level_name = "แนวต้าน"
            scenario1 = f"ทะลุแนวต้าน → อาจขึ้นต่อไปที่ ${resistance * 1.03:.2f}"
            scenario2 = f"ตีกลับ → อาจปรับลงไปที่ ${support:.2f}"
        
        dollar_distance = abs(price - level)
        
        return f"""🎯 {symbol} ใกล้{level_name}สำคัญ!

📍 ราคาปัจจุบัน: ${price:.2f}
{emoji} {level_name}: ${level:.2f}
   ห่าง: {distance:.1f}% (${dollar_distance:.2f})

💡 ถ้า{scenario1}
💡 ถ้า{scenario2}

ติดตาม: /aiplus {symbol}"""
    
    def create_market_sentiment_alert(self, spy_change, vix_data):
        """สร้าง Market Sentiment Alert"""
        if spy_change >= 1:
            emoji = "🟢"
            sentiment = "Greed Mode"
            advice = "ตลาดร้อนแรง แต่ระวังการปรับฐาน"
        elif spy_change <= -1:
            emoji = "🔴"
            sentiment = "Fear Mode"
            advice = "นักลงทุนระมัดระวังสูง เหมาะเก็บเงินสดรอจังหวะ"
        else:
            emoji = "🟡"
            sentiment = "Neutral"
            advice = "ตลาดเคลื่อนไหวปกติ"
        
        vix_info = ""
        if vix_data and 'close' in vix_data:
            vix_current = float(vix_data['close'])
            vix_prev = float(vix_data.get('previous_close', vix_current))
            vix_change = ((vix_current - vix_prev) / vix_prev) * 100
            vix_info = f"\n📉 VIX: {vix_current:.1f} ({vix_change:+.1f}%) - ความกลัว{'เพิ่มขึ้น' if vix_change > 0 else 'ลดลง'}"
        
        return f"""📊 สรุปตลาดวันนี้

{emoji} S&P 500: {spy_change:+.1f}% ({sentiment}){vix_info}

💡 {advice}

ดูหุ้นที่น่าสนใจ: /popular"""
    
    async def send_alert_if_new(self, symbol, alert_type, message):
        """ส่ง alert ถ้ายังไม่เคยส่งในวันนี้"""
        alert_key = f"{symbol}_{alert_type}_{datetime.now().strftime('%Y-%m-%d')}"
        
        # เช็คว่าเคยส่งแล้วหรือยัง
        if alert_key in self.last_alerts:
            logger.info(f"⏭️ Skipping duplicate alert: {alert_key}")
            return
        
        # บันทึกว่าส่งแล้ว
        self.last_alerts[alert_key] = datetime.now()
        
        # ส่งข้อความไปยัง users ทั้งหมด (หรือ broadcast channel)
        await self.broadcast_alert(message)
    
    async def broadcast_alert(self, message):
        """ส่ง broadcast alert ไปยัง users"""
        try:
            # TODO: ดึง list ของ user_ids ที่ subscribe alerts
            # สำหรับตอนนี้ ให้ส่งไปยัง channel หรือ group
            
            ALERT_CHANNEL_ID = os.environ.get("ALERT_CHANNEL_ID", "")
            
            if ALERT_CHANNEL_ID:
                await self.app.bot.send_message(
                    chat_id=ALERT_CHANNEL_ID,
                    text=message,
                    parse_mode=None,
                    disable_web_page_preview=True
                )
                logger.info(f"✅ Alert sent to channel")
            else:
                logger.warning("⚠️ No ALERT_CHANNEL_ID configured")
        
        except Exception as e:
            logger.error(f"❌ Error broadcasting alert: {e}")
    
    def is_market_hours(self):
        """ตรวจสอบว่าเป็นเวลาตลาดเปิดหรือไม่"""
        # US Market: 9:30 AM - 4:00 PM EST = 21:30 - 04:00 ICT (วันถัดไป)
        now = datetime.now(pytz.timezone('Asia/Bangkok'))
        hour = now.hour
        
        # ตลาดเปิด: 21:30 - 23:59 หรือ 00:00 - 04:00
        return (21 <= hour <= 23) or (0 <= hour <= 4)
    
    def get_previous_macd(self, symbol):
        """ดึงค่า MACD ก่อนหน้า"""
        return self.last_alerts.get(f"{symbol}_macd_values")
    
    def save_macd_value(self, symbol, macd, signal):
        """บันทึกค่า MACD"""
        self.last_alerts[f"{symbol}_macd_values"] = (macd, signal)
    
    def get_previous_ema(self, symbol):
        """ดึงค่า EMA ก่อนหน้า"""
        return self.last_alerts.get(f"{symbol}_ema_values")
    
    def save_ema_value(self, symbol, ema_50, ema_200):
        """บันทึกค่า EMA"""
        self.last_alerts[f"{symbol}_ema_values"] = (ema_50, ema_200)
    
    async def cleanup_old_alerts(self):
        """ลบ alerts เก่าที่เกิน 24 ชม."""
        try:
            now = datetime.now()
            keys_to_delete = []
            
            for key, timestamp in self.last_alerts.items():
                if isinstance(timestamp, datetime):
                    if (now - timestamp).total_seconds() > 86400:  # 24 hours
                        keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.last_alerts[key]
            
            logger.info(f"🗑️ Cleaned up {len(keys_to_delete)} old alerts")
        
        except Exception as e:
            logger.error(f"❌ Error cleaning up alerts: {e}")
    
    def stop(self):
        """หยุด Scheduler"""
        self.scheduler.shutdown()
        logger.info("🛑 Alert Scheduler stopped")
