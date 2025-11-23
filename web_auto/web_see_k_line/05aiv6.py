# 05aiv5.py
# 在v5的基础上，优化频发邮件的问题
# 05aiv6.py

# 优化版：增加震荡行情判断，减少误报
# ==========================  震荡过滤优化版  ==========================
import base64
from dotenv import load_dotenv
import os
import time
import json
from datetime import datetime, timedelta
from io import BytesIO
from PIL import ImageGrab
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr


# ================= 配置区域 =================
load_dotenv()

MODELSCOPE_ACCESS_TOKEN = os.getenv("MODELSCOPE_ACCESS_TOKEN")

client = OpenAI(
    api_key=MODELSCOPE_ACCESS_TOKEN,
    base_url="https://api-inference.modelscope.cn/v1/"
)

MAIL_HOST = "smtp.qq.com"
MAIL_PORT = 465
MAIL_USER = os.getenv("MAIL_USER")
MAIL_PASS = os.getenv("MAIL_PASS")
MAIL_RECEIVER = os.getenv("MAIL_RECEIVER")

# 基础配置
SCREEN_BBOX = (85, 145, 1137, 722)
LOOP_INTERVAL = 150  # 2.5分钟

# 历史数据存储
HISTORY_MEMORY = []
SIGNAL_HISTORY = []

# 震荡行情过滤配置
MIN_SIGNAL_INTERVAL = 60  # 相同方向信号最小间隔时间(秒)
MIN_PRICE_CHANGE_PERCENT = 0.3  # 最小价格变动百分比，过滤小幅波动
VOLUME_THRESHOLD = 1.8  # 提高成交量阈值，从1.5提高到1.8
MACD_ABS_THRESHOLD = 0.5  # MACD绝对值阈值，避免在0轴附近的轻微交叉
TREND_CONFIRM_LENGTH = 3  # 趋势确认所需的连续同向信号数量

# 分析计数和配置
ANALYSIS_COUNT = 0  # 分析次数计数器
# 启动信息使用用户示例中的格式
print(json.dumps({"timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "message": "图表监控系统启动"}, ensure_ascii=False))


# ================= 工具函数 =================
def calculate_price_change_percent(current_price, history_data):
    """计算价格变化百分比，用于判断是否有实质性变动"""
    if not history_data or len(history_data) < 3:
        return 0
    
    # 从历史记录中提取价格数据
    prices = []
    for record in history_data:
        try:
            # 解析历史记录中的价格
            price_str = record.split('价:')[1].split(' DIF')[0]
            prices.append(float(price_str))
        except:
            continue
    
    if not prices or len(prices) < 3:
        return 0
    
    # 计算与前几期价格的平均变化百分比
    avg_change = 0
    count = 0
    for i in range(1, min(4, len(prices))):
        if prices[i-1] > 0:
            change_pct = abs((current_price - prices[i-1]) / prices[i-1] * 100)
            avg_change += change_pct
            count += 1
    
    return avg_change / count if count > 0 else 0

def is_recent_signal_exists(signal_type, min_interval=MIN_SIGNAL_INTERVAL):
    """检查最近是否已经发送过相同类型的信号"""
    current_time = datetime.now()
    
    for timestamp, signal in SIGNAL_HISTORY:
        time_diff = (current_time - timestamp).total_seconds()
        if signal == signal_type and time_diff < min_interval:
            return True
    
    return False

def is_market_trending(history_data, trend_length=TREND_CONFIRM_LENGTH):
    """判断市场是否处于趋势中，而非震荡"""
    if len(history_data) < trend_length:
        return False
    
    # 提取最近的信号数据
    recent_signals = []
    for record in history_data[-trend_length:]:
        try:
            signal_part = record.split('信号:')[1]
            if '金叉' in signal_part:
                recent_signals.append(1)  # 金叉为1
            elif '死叉' in signal_part:
                recent_signals.append(-1)  # 死叉为-1
        except:
            continue
    
    # 如果最近的趋势确认周期内有连续同向信号，则认为有趋势
    if len(recent_signals) >= trend_length:
        # 检查是否有足够的同向信号
        positive_count = recent_signals.count(1)
        negative_count = recent_signals.count(-1)
        
        # 如果超过70%的信号是同向的，则认为有趋势
        if positive_count >= trend_length * 0.7 or negative_count >= trend_length * 0.7:
            return True
    
    return False

def send_email_alert(signal_type, price, volume_analysis, rationale, macd_data):
    try:
        content = f"""
【高盈亏比信号】{datetime.now().strftime('%H:%M')}
----------------------------------------
信号类型: {signal_type}
价格: {price}
成交量: {volume_analysis}
MACD: {macd_data}
原因:
{rationale}

        """
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = formataddr(["AI 量化监控", MAIL_USER])
        msg['To'] = formataddr(["交易员", MAIL_RECEIVER])
        msg['Subject'] = f"{signal_type} | {price} | 高盈亏比"

        with smtplib.SMTP_SSL(MAIL_HOST, MAIL_PORT) as server:
            server.login(MAIL_USER, MAIL_PASS)
            server.sendmail(MAIL_USER, [MAIL_RECEIVER], msg.as_string())
        print(f"邮件已发送: {signal_type} @ {price}")
    except Exception as e:
        print("邮件失败:", e)


def capture_screen_to_base64(bbox):
    try:
        screenshot = ImageGrab.grab(bbox=bbox)
        buffer = BytesIO()
        screenshot.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except:
        return None


def clean_json_string(content):
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()


# ================= 核心分析 =================
def analyze_chart():
    global HISTORY_MEMORY, SIGNAL_HISTORY, ANALYSIS_COUNT
    ANALYSIS_COUNT += 1  # 增加分析次数计数

    img_b64 = capture_screen_to_base64(SCREEN_BBOX)
    if not img_b64:
        print("截图失败")
        return

    history_str = "\n".join(HISTORY_MEMORY[-5:]) if HISTORY_MEMORY else "无"  # 增加历史记录数量

    system_prompt = f"""
你是专业交易分析师，请基于图像读取数据并进行深度分析：
1. 最新价格
2. MACD DIF、DEA 数值和柱状图高度
3. 成交量对比前 3 根的倍率
4. 判断金叉死叉（请谨慎判断，避免在0轴附近的轻微交叉被误判）
5. 评估当前市场是趋势行情还是震荡行情

历史参考:
{history_str}

请特别注意：
- 只有明确的、具有显著特征的金叉/死叉才标注为对应信号
- 在MACD指标值接近0轴时的轻微交叉应标注为"无"
- 请提供更详细的rationale解释信号原因

返回 JSON：
{{
    "current_price": 数字,
    "macd_dif": 数字,
    "macd_dea": 数字,
    "volume_ratio": 数字,
    "signal": "金叉/死叉/无",
    "rationale": "25字以内理由",
    "market_summary": "15字总结",
    "is_trending": true/false,  # 是否处于趋势行情
    "confidence_score": 数字   # 信号可信度(0-10)
}}
"""

    user_prompt = "请基于截图分析行情，只返回 JSON。请特别注意在震荡行情中谨慎判断金叉死叉信号。"
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_b64}"
                    }
                },
                {
                    "type": "text",
                    "text": user_prompt
                }
            ]
        }
    ]

    try:
        response = client.chat.completions.create(
            model="Qwen/Qwen3-VL-235B-A22B-Instruct",
            messages=messages,
            temperature=0,
            stream=False
        )

        raw = response.choices[0].message.content
        # 不再显示原始响应文本，只保留JSON输出
        pass

        result = json.loads(clean_json_string(raw))

        price = float(result["current_price"])
        dif = float(result["macd_dif"])
        dea = float(result["macd_dea"])
        vol = float(result["volume_ratio"])
        signal = result["signal"]
        rationale = result["rationale"]
        
        # 提取AI判断的趋势信息和置信度
        is_trending = result.get("is_trending", False)
        confidence_score = result.get("confidence_score", 5)

        # 记录当前数据
        current_record = f"{datetime.now().strftime('%H:%M:%S')} 价:{price} DIF:{dif} DEA:{dea} 量比:{vol} 信号:{signal} 置信度:{confidence_score}"
        HISTORY_MEMORY.append(current_record)
        
        # 限制历史记录长度，避免内存占用过大
        if len(HISTORY_MEMORY) > 50:
            HISTORY_MEMORY = HISTORY_MEMORY[-50:]

        # 计算价格变化百分比
        price_change_pct = calculate_price_change_percent(price, HISTORY_MEMORY)
        
        # 检查是否处于趋势行情（AI判断 + 历史数据分析）
        market_trending = is_trending or is_market_trending(HISTORY_MEMORY)
        
        # 综合判断是否发送信号
        should_send = False
        
        # 基础条件：信号类型和成交量
        if signal in ("金叉", "死叉") and vol >= VOLUME_THRESHOLD:
            # 1. 检查MACD值是否足够强（避免0轴附近的轻微交叉）
            macd_strong = abs(dif - dea) > MACD_ABS_THRESHOLD
            
            # 2. 检查价格是否有实质性变动
            price_moved = price_change_pct >= MIN_PRICE_CHANGE_PERCENT
            
            # 3. 检查信号置信度
            confidence_high = confidence_score >= 7
            
            # 4. 检查是否处于趋势行情或有足够强的信号
            strong_signal = market_trending or confidence_high or macd_strong
            
            # 5. 检查是否最近发送过相同类型的信号
            no_recent_signal = not is_recent_signal_exists(signal)
            
            # 综合决策：如果是震荡行情，需要更严格的条件
            if not market_trending:
                # 震荡行情下，只在信号极强时发送
                should_send = macd_strong and price_moved and confidence_high and no_recent_signal
            else:
                # 趋势行情下，可以适当放宽条件
                should_send = (macd_strong or price_moved or confidence_high) and no_recent_signal
        
        # 构建分析结果JSON对象，使用用户指定的字段名
        analysis_result = {
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "signal": signal,
            "current_price": price,
            "macd_dif": dif,
            "macd_dea": dea,
            "volume_ratio": vol,
            "rationale": rationale if 'rationale' in locals() else "",
            "market_summary": result.get("market_summary", ""),
            "is_trending": market_trending,
            "confidence_score": confidence_score
        }
        print(json.dumps(analysis_result, ensure_ascii=False))
        
        # 如果满足所有条件，发送邮件提醒
        if should_send:
            send_email_alert(signal, price, vol, rationale, f"DIF={dif}, DEA={dea}")
            # 记录发送的信号
            SIGNAL_HISTORY.append((datetime.now(), signal))
            # 清理旧的信号历史
            if len(SIGNAL_HISTORY) > 10:
                SIGNAL_HISTORY = SIGNAL_HISTORY[-10:]

    except Exception as e:
        # 错误情况下也输出JSON格式
        error_result = {
            "error": str(e),
            "analysis_count": ANALYSIS_COUNT,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "status": "error"
        }
        if 'raw' in locals():
            error_result["raw_response"] = raw
        print(json.dumps(error_result, ensure_ascii=False))


# ================= 主循环 =================
if __name__ == "__main__":
    time.sleep(7)
    analyze_chart()

    while True:
        analyze_chart()
        # 倒计时功能，使用更清晰的格式输出
        for i in range(LOOP_INTERVAL):
            remaining_time = LOOP_INTERVAL - i
            # 在同一行更新倒计时，使用回车符而不是换行符
            print(f"倒计时: {remaining_time}秒", end='\r')
            time.sleep(1)
        # 倒计时结束后输出一个换行，避免与下一次输出重叠
        print()
