import os
import telebot
import yfinance as yf
import pandas as pd
from datetime import datetime

# ตั้งค่า Bot Token (ได้จาก @BotFather)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
bot = telebot.TeleBot(BOT_TOKEN)

def calculate_rsi(data, period=14):
    """คำนวณ RSI"""
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def calculate_macd(data):
    """คำนวณ MACD"""
    exp1 = data['Close'].ewm(span=12, adjust=False).mean()
    exp2 = data['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd.iloc[-1], signal.iloc[-1]

def calculate_ema(data, period):
    """คำนวณ EMA"""
    return data['Close'].ewm(span=period, adjust=False).mean().iloc[-1]

def calculate_bollinger(data, period=20):
    """คำนวณ Bollinger Bands"""
    sma = data['Close'].rolling(window=period).mean()
    std = data['Close'].rolling(window=period).std()
    upper = sma + (std * 2)
    lower = sma - (std * 2)
    return lower.iloc[-1], upper.iloc[-1]

def get_stock_analysis(symbol):
    """วิเคราะห์หุ้นและส่งกลับข้อมูล"""
    try:
        # ดึงข้อมูลหุ้น
        stock = yf.Ticker(symbol)
        data = stock.history(period="6mo")
        
        if data.empty:
            return "❌ ไม่พบข้อมูลหุ้น กรุณาตรวจสอบสัญลักษณ์หุ้น"
        
        # ข้อมูลปัจจุบัน
        current_price = data['Close'].iloc[-1]
        prev_close = data['Close'].iloc[-2]
        change = current_price - prev_close
        change_percent = (change / prev_close) * 100
        
        # คำนวณตัวชี้วัด
        rsi = calculate_rsi(data)
        macd, signal = calculate_macd(data)
        ema20 = calculate_ema(data, 20)
        ema50 = calculate_ema(data, 50)
        ema200 = calculate_ema(data, 200)
        bb_lower, bb_upper = calculate_bollinger(data)
        
        # วิเคราะห์สัญญาณ
        trend_icon = "📈" if change > 0 else "📉"
        rsi_signal = "🟢" if rsi < 30 else "🔴" if rsi > 70 else "🟡"
        rsi_text = "กลาง" if 30 <= rsi <= 70 else "oversold" if rsi < 30 else "overbought"
        
        macd_signal = "🟢 สัญญาณซื้อ" if macd > signal else "🔴 สัญญาณขาย"
        
        ema_trend = "🟢" if current_price > ema20 > ema50 else "🔴"
        ema_long = "🟢 โกลเด้นครอส" if ema50 > ema200 else "🔴 เดธครอส"
        
        obv_trend = "🟢 เพิ่มขึ้น" if change > 0 else "🔴 ลดลง"
        
        # สร้างข้อความ
        message = f"""📊 {symbol.upper()}
{'─' * 35}
💰 ราคา: ${current_price:.2f} {trend_icon}
📊 เปลี่ยนแปลง: {change:+.2f} ({change_percent:+.2f}%)

📈 ตัวชี้วัดทางเทคนิค:
{'─' * 35}
🔸 RSI: {rsi:.2f} {rsi_signal} ({rsi_text})
🔸 MACD: {macd_signal}
🔸 ผัยผวน: {ema_trend} ราคาเฉลี่ย 5 วัน: ${ema20:.2f}
🔸 โบลลิงเจอร์ (20): ${bb_lower:.2f} - ${bb_upper:.2f} 🟡
🔸 EMA 20/50: {ema_trend}
🔸 EMA 50/200: {ema_long}
🔸 OBV ล่าสุด: {obv_trend}

📌 แนวรับ: ${bb_lower:.2f} | แนวต้าน: ${bb_upper:.2f}

⏰ อัพเดท: {datetime.now().strftime('%d/%m/%Y %H:%M')}

*เพื่อเป็นข้อมูล ไม่ใช่คำแนะนำการลงทุน**
"""
        return message
        
    except Exception as e:
        return f"❌ เกิดข้อผิดพลาด: {str(e)}"

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """ข้อความต้อนรับ"""
    welcome_text = """
🤖 ยินดีต้อนรับสู่ Stock Bot!

📋 คำสั่งที่ใช้ได้:
• /stock [symbol] - ดูข้อมูลหุ้น
  ตัวอย่าง: /stock AVGO
  
• /help - แสดงคำสั่ง

💡 หรือพิมพ์ชื่อหุ้นโดยตรง เช่น: AVGO, AAPL, TSLA
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['stock'])
def stock_command(message):
    """คำสั่ง /stock"""
    try:
        symbol = message.text.split()[1].upper()
        bot.reply_to(message, "⏳ กำลังดึงข้อมูล...")
        result = get_stock_analysis(symbol)
        bot.reply_to(message, result)
    except IndexError:
        bot.reply_to(message, "❌ กรุณาระบุสัญลักษณ์หุ้น\nตัวอย่าง: /stock AVGO")

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """รับข้อความทั่วไป"""
    text = message.text.strip().upper()
    
    # ตรวจสอบว่าเป็นสัญลักษณ์หุ้นหรือไม่ (2-5 ตัวอักษร)
    if len(text) >= 2 and len(text) <= 5 and text.isalpha():
        bot.reply_to(message, "⏳ กำลังดึงข้อมูล...")
        result = get_stock_analysis(text)
        bot.reply_to(message, result)
    else:
        bot.reply_to(message, "💡 พิมพ์สัญลักษณ์หุ้น เช่น AVGO, AAPL\nหรือใช้คำสั่ง /help")

# เริ่มต้น Bot
if __name__ == "__main__":
    print("🤖 Bot กำลังทำงาน...")
    bot.infinity_polling()
