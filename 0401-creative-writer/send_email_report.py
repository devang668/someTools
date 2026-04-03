import sqlite3
import requests
import json
from flask import Flask, request, render_template_string, jsonify
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import threading
import time

app = Flask(__name__)
DB_FILE = "creative_system_pro_v7.db"

# ==================== 数据库初始化 ====================
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        # 消息表：记录原始对话
        conn.execute('''CREATE TABLE IF NOT EXISTS messages 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT, content TEXT, feedback INTEGER DEFAULT 0, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        # 会话表：存储长期记忆摘要(summary)
        conn.execute('''CREATE TABLE IF NOT EXISTS sessions 
                     (session_id TEXT PRIMARY KEY, title TEXT, summary TEXT DEFAULT '', updated_at DATETIME)''')
        # 配置表
        conn.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        
        defaults = [('AI_KEY', 'sk-804e8b333-----81da12'), 
                    ('AI_URL', 'https://api.deepseek.com/v1'), 
                    ('AI_MODEL', 'deepseek-chat'),
                    ('EMAIL_ENABLED', 'false'),
                    ('EMAIL_ADDRESS', ''),
                    ('EMAIL_AUTH_CODE', ''),
                    ('EMAIL_SMTP', 'smtp.qq.com'),
                    ('EMAIL_SMTP_PORT', '465'),
                    ('LAST_EMAIL_DATE', '')]
        conn.executemany("INSERT OR IGNORE INTO settings VALUES (?, ?)", defaults)
        conn.commit()

init_db()

def get_db_config():
    with sqlite3.connect(DB_FILE) as conn:
        res = conn.execute("SELECT key, value FROM settings").fetchall()
        return {k: v for k, v in res}

def save_db_config(key, value):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()

# ==================== 邮件功能（优化版）====================
def send_email_report(subject, html_content):
    """发送邮件报告的通用函数"""
    cfg = get_db_config()
    
    email = cfg.get('EMAIL_ADDRESS')
    auth_code = cfg.get('EMAIL_AUTH_CODE')
    smtp_server = cfg.get('EMAIL_SMTP', 'smtp.qq.com')
    smtp_port = int(cfg.get('EMAIL_SMTP_PORT', '465'))
    
    if not email or not auth_code:
        return False, "邮箱或授权码未配置"
    
    try:
        # 创建邮件对象
        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # 连接SMTP服务器并发送
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
        server.login(email, auth_code)
        server.send_message(msg)
        server.quit()
        
        return True, "邮件发送成功"
    except smtplib.SMTPAuthenticationError as e:
        return False, f"认证失败：{str(e)}，请检查授权码是否正确"
    except smtplib.SMTPException as e:
        return False, f"SMTP错误：{str(e)}"
    except Exception as e:
        return False, f"发送失败：{str(e)}"

def send_daily_report():
    """发送每日聊天记录报告"""
    cfg = get_db_config()
    
    if cfg.get('EMAIL_ENABLED') != 'true':
        return False, "邮件通知未启用"
    
    # 获取今天的聊天记录
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    with sqlite3.connect(DB_FILE) as conn:
        # 获取昨天到现在的新消息
        res = conn.execute("""
            SELECT m.session_id, m.role, m.content, m.timestamp, s.title
            FROM messages m
            LEFT JOIN sessions s ON m.session_id = s.session_id
            WHERE DATE(m.timestamp) >= ?
            ORDER BY m.timestamp ASC
        """, (yesterday,)).fetchall()
    
    if not res:
        return False, "没有新的聊天记录"
    
    # 构建邮件内容
    content_lines = [f"<h2>📊 每日聊天记录报告</h2>", f"<p><strong>时间范围：</strong>{yesterday} 至 {today}</p>", "<hr>"]
    
    current_session = None
    for session_id, role, msg_content, timestamp, title in res:
        if session_id != current_session:
            current_session = session_id
            session_title = title or "未命名会话"
            content_lines.append(f"<h3>💬 {session_title}</h3>")
        
        role_display = "👤 用户" if role == 'user' else "🤖 AI"
        time_str = timestamp.split('.')[0] if timestamp else ''
        content_lines.append(f"<p><strong>{role_display}</strong> <small>({time_str})</small></p>")
        content_lines.append(f"<p>{msg_content}</p><hr>")
    
    html_content = "\n".join(content_lines)
    subject = f"📅 每日聊天记录 - {datetime.now().strftime('%Y年%m月%d日')}"
    
    success, message = send_email_report(subject, html_content)
    
    if success:
        # 更新最后发送日期
        save_db_config('LAST_EMAIL_DATE', today)
    
    return success, message

def send_intelligence_report(intelligence_data):
    """发送情报抓取报告（手动触发）"""
    cfg = get_db_config()
    
    email = cfg.get('EMAIL_ADDRESS')
    auth_code = cfg.get('EMAIL_AUTH_CODE')
    
    if not email or not auth_code:
        return False, "邮箱或授权码未配置"
    
    # 构建邮件内容
    content_lines = [
        f"<h2>🔍 情报抓取报告</h2>",
        f"<p><strong>抓取时间：</strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
        f"<p><strong>抓取数量：</strong>{len(intelligence_data.get('articles', []))} 条</p>",
        "<hr>",
        "<h3>📋 抓取到的文章列表：</h3>"
    ]
    
    # 添加文章列表
    for idx, article in enumerate(intelligence_data.get('articles', []), 1):
        content_lines.append(f"""
        <div style="margin: 12px 0; padding: 12px; background: #f8fafc; border-left: 4px solid #6366f1; border-radius: 4px;">
            <p><strong>{idx}. {article.get('title', '无标题')}</strong></p>
            <p><a href="{article.get('url', '#')}" style="color: #6366f1;">🔗 {article.get('url', '无链接')}</a></p>
            <p><small>{article.get('summary', '无摘要')}</small></p>
        </div>
        """)
    
    # 添加总结
    content_lines.append("<h3>📝 AI 总结：</h3>")
    for idx, summary in enumerate(intelligence_data.get('summaries', []), 1):
        content_lines.append(f"<p><strong>总结 {idx}：</strong>{summary}</p>")
    
    html_content = "\n".join(content_lines)
    subject = f"🔍 情报抓取报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return send_email_report(subject, html_content)

def email_scheduler():
    """定时检查并发送每日报告"""
    while True:
        try:
            now = datetime.now()
            cfg = get_db_config()
            last_date = cfg.get('LAST_EMAIL_DATE', '')
            today = now.strftime('%Y-%m-%d')
            
            # 每天8点检查，如果还没发送过就发送
            if now.hour == 8 and now.minute == 0 and last_date != today:
                success, message = send_daily_report()
                if success:
                    print(f"✅ 每日邮件报告发送成功: {message}")
                else:
                    print(f"❌ 每日邮件报告发送失败: {message}")
            
            time.sleep(60)  # 每分钟检查一次
        except Exception as e:
            print(f"❌ 邮件调度器异常: {e}")
            time.sleep(60)

# 启动邮件调度器
scheduler_thread = threading.Thread(target=email_scheduler, daemon=True)
scheduler_thread.start()

# ==================== 核心逻辑：带记忆归纳的 AI 调用 ====================
def ask_ai_with_memory(session_id, user_msg):
    cfg = get_db_config()
    client = OpenAI(api_key=cfg['AI_KEY'], base_url=cfg['AI_URL'])
    
    # 1. 获取该会话的长期记忆摘要
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT summary FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        current_summary = row[0] if row else ""

    # 2. 构造消息队列
    messages = []
    # 注入长期记忆
    if current_summary:
        messages.append({"role": "system", "content": f"【长期记忆/背景】: {current_summary}"})
    else:
        messages.append({"role": "system", "content": "你是一个有记忆能力的专业助手。请基于上下文提供精准回复。"})

    # 3. 注入短期记忆（最近6条原始对话）
    with sqlite3.connect(DB_FILE) as conn:
        history = conn.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 6", (session_id,)).fetchall()
        for h_role, h_content in reversed(history):
            # 将消息格式化为 OpenAI 要求格式
            role = 'assistant' if h_role == 'assistant' else 'user'
            messages.append({"role": role, "content": h_content})

    # 4. 调用大模型
    try:
        response = client.chat.completions.create(
            model=cfg['AI_MODEL'],
            messages=messages + [{"role": "user", "content": user_msg}],
            temperature=0.4
        )
        ai_res = response.choices[0].message.content
        
        # 5. 自动更新摘要（异步感官，实际同步执行）
        update_summary(session_id, messages + [{"role": "user", "content": user_msg}, {"role": "assistant", "content": ai_res}])
        
        return ai_res
    except Exception as e:
        return f"⚠️ AI 响应异常: {str(e)}"

def update_summary(session_id, full_history):
    """提取对话精髓，更新长期记忆"""
    if len(full_history) < 5: return # 对话太少不更新
    
    cfg = get_db_config()
    client = OpenAI(api_key=cfg['AI_KEY'], base_url=cfg['AI_URL'])
    
    # 将对话拼接用于总结
    context_str = "\n".join([f"{m['role']}: {m['content'][:50]}" for m in full_history])
    prompt = f"请归纳以下对话的要点（包括用户身份、偏好、核心诉求及重要事实），用于更新长期记忆（150字内）：\n{context_str}"
    
    try:
        res = client.chat.completions.create(
            model=cfg['AI_MODEL'],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        new_summary = res.choices[0].message.content
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("UPDATE sessions SET summary = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?", (new_summary, session_id))
            conn.commit()
    except:
        pass

# ==================== 前端 HTML 模板 ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AI 创作系统 Pro</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root { 
            --sidebar-w: 300px; 
            --primary: #6366f1; 
            --primary-hover: #4f46e5;
            --side-bg: linear-gradient(180deg, #1e1b4b 0%, #312e81 100%);
            --bg-light: #f8fafc;
            --text-dark: #1e293b;
            --text-light: #64748b;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }
        * { box-sizing: border-box; }
        body { 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            display: flex; 
            height: 100vh; 
            margin: 0; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            overflow: hidden;
        }
        
        /* 侧边栏 */
        .sidebar { 
            position: fixed; 
            top: 0; 
            left: 0; 
            bottom: 0; 
            width: var(--sidebar-w); 
            background: var(--side-bg); 
            color: #fff; 
            display: flex; 
            flex-direction: column; 
            padding: 20px; 
            transition: transform 0.3s ease; 
            z-index: 1001; 
            transform: translateX(-100%);
            box-shadow: 4px 0 20px rgba(0,0,0,0.2);
        }
        .sidebar.active { transform: translateX(0); }
        .overlay { 
            display: none; 
            position: fixed; 
            top: 0; 
            left: 0; 
            right: 0; 
            bottom: 0; 
            background: rgba(0,0,0,0.6); 
            z-index: 1000;
            backdrop-filter: blur(4px);
        }
        .overlay.active { display: block; }

        @media (min-width: 769px) {
            .sidebar { position: relative; transform: translateX(0); }
            .overlay { display: none !important; }
            .menu-toggle { display: none; }
        }

        /* 主体布局 */
        .main { 
            flex: 1; 
            display: flex; 
            flex-direction: column; 
            height: 100vh; 
            min-width: 0; 
            position: relative;
            background: #fff;
            border-radius: 20px 0 0 20px;
            margin-left: 0;
            box-shadow: -4px 0 20px rgba(0,0,0,0.1);
        }
        @media (min-width: 769px) {
            .main { margin-left: 0; border-radius: 0; }
        }
        
        .header { 
            height: 64px; 
            padding: 0 20px; 
            border-bottom: 1px solid #e2e8f0; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            background: linear-gradient(90deg, #fff 0%, #f8fafc 100%);
            flex-shrink: 0;
        }
        .header-title {
            font-size: 18px;
            font-weight: 700;
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .menu-toggle { 
            font-size: 24px; 
            cursor: pointer; 
            border: none; 
            background: none; 
            color: var(--text-dark);
            padding: 8px;
            border-radius: 8px;
            transition: background 0.2s;
        }
        .menu-toggle:hover { background: #f1f5f9; }

        /* 聊天区 */
        #chatbox { 
            flex: 1; 
            overflow-y: auto; 
            padding: 24px; 
            display: flex; 
            flex-direction: column; 
            gap: 24px;
            background: linear-gradient(180deg, #fff 0%, #f8fafc 100%);
        }
        .msg-group { 
            display: flex; 
            flex-direction: column; 
            max-width: 85%; 
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(100px); }
            to { opacity: 1; transform: translateX(0); }
        }
        .msg-group.user { align-self: flex-end; }
        .msg-group.assistant { align-self: flex-start; width: 100%; }
        
        .msg { 
            padding: 14px 18px; 
            border-radius: 16px; 
            font-size: 15px; 
            line-height: 1.7; 
            word-wrap: break-word;
            box-shadow: var(--shadow);
        }
        .user .msg { 
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: #fff; 
            border-bottom-right-radius: 4px;
        }
        .assistant .msg { 
            background: #fff; 
            border: 1px solid #e2e8f0; 
            color: var(--text-dark); 
            border-bottom-left-radius: 4px;
        }
        /* 消息中的链接样式 */
        .msg a {
            color: var(--primary);
            text-decoration: none;
            word-break: break-all;
        }
        .msg a:hover {
            text-decoration: underline;
        }
        .msg strong {
            font-weight: 600;
            color: var(--text-dark);
        }

        /* 时间戳 */
        .timestamp {
            font-size: 11px;
            color: var(--text-light);
            margin-top: 6px;
            padding: 0 4px;
        }
        .user .timestamp { text-align: right; }

        /* 工具栏 */
        .tools { 
            display: flex; 
            gap: 16px; 
            margin-top: 8px; 
            padding-left: 4px;
        }
        .tool-btn { 
            font-size: 12px; 
            color: var(--text-light); 
            cursor: pointer; 
            display: flex; 
            align-items: center; 
            gap: 4px;
            padding: 4px 8px;
            border-radius: 6px;
            transition: all 0.2s;
            background: #f1f5f9;
        }
        .tool-btn:hover { 
            color: var(--primary);
            background: #e0e7ff;
        }
        .tool-btn.active { 
            color: var(--primary); 
            font-weight: 600;
            background: #c7d2fe;
        }

        /* 输入区 */
        .input-area { 
            padding: 20px; 
            border-top: 1px solid #e2e8f0; 
            background: #fff;
        }
        .input-container { 
            display: flex; 
            gap: 12px; 
            background: var(--bg-light); 
            border-radius: 28px; 
            padding: 6px 20px; 
            align-items: center; 
            border: 2px solid #e2e8f0;
            transition: border-color 0.3s, box-shadow 0.3s;
        }
        .input-container:focus-within {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        textarea { 
            flex: 1; 
            border: none; 
            background: none; 
            outline: none; 
            resize: none; 
            padding: 14px 0; 
            font-size: 16px; 
            max-height: 150px;
            font-family: inherit;
        }
        .send-btn {
            width: 44px;
            height: 44px;
            border-radius: 50%;
            border: none;
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: #fff;
            font-size: 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: transform 0.2s, box-shadow 0.2s;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }
        .send-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 6px 16px rgba(99, 102, 241, 0.4);
        }
        .send-btn:active {
            transform: scale(0.95);
        }

        /* 配置抽屉 */
        .config-panel { 
            position: absolute; 
            top: 64px; 
            left: 0; 
            right: 0; 
            background: #fff; 
            border-bottom: 2px solid var(--primary); 
            padding: 24px; 
            display: none; 
            z-index: 999; 
            box-shadow: 0 10px 40px rgba(0,0,0,0.15);
            animation: slideDown 0.3s ease;
        }
        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .config-panel.show { display: block; }
        
        .config-section {
            margin-bottom: 24px;
        }
        .config-section h3 {
            font-size: 14px;
            font-weight: 600;
            color: var(--text-dark);
            margin: 0 0 12px 0;
            padding-bottom: 8px;
            border-bottom: 2px solid #e2e8f0;
        }
        
        .form-group {
            margin-bottom: 12px;
        }
        .form-group label {
            display: block;
            font-size: 12px;
            font-weight: 500;
            color: var(--text-light);
            margin-bottom: 4px;
        }
        .form-group input {
            width: 100%;
            padding: 10px 14px;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            transition: all 0.2s;
        }
        .form-group input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        
        .btn-side { 
            width: 100%; 
            padding: 14px; 
            margin-bottom: 12px; 
            border-radius: 12px; 
            border: 1px solid rgba(255,255,255,0.2); 
            background: rgba(255,255,255,0.1); 
            color: white; 
            cursor: pointer; 
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .btn-side:hover {
            background: rgba(255,255,255,0.2);
            transform: translateY(-1px);
        }
        .btn-side.primary {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            border: none;
        }
        .btn-side.success {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            border: none;
        }
        
        .session-list {
            flex: 1;
            overflow-y: auto;
            margin-top: 16px;
            padding-right: 8px;
        }
        .session-list::-webkit-scrollbar {
            width: 6px;
        }
        .session-list::-webkit-scrollbar-track {
            background: rgba(255,255,255,0.1);
            border-radius: 3px;
        }
        .session-list::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.3);
            border-radius: 3px;
        }
        .session-item {
            padding: 12px 14px;
            border-radius: 10px;
            font-size: 14px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .session-item:hover {
            background: rgba(255,255,255,0.15);
            transform: translateX(4px);
        }
        .session-item.active {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            border: none;
            font-weight: 600;
        }
        .session-item .session-time {
            font-size: 11px;
            opacity: 0.7;
            margin-top: 4px;
        }
        
        .switch-container {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        .switch {
            position: relative;
            width: 48px;
            height: 24px;
        }
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #cbd5e1;
            transition: 0.3s;
            border-radius: 24px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: 0.3s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        }
        input:checked + .slider:before {
            transform: translateX(24px);
        }
        .switch-label {
            font-size: 14px;
            font-weight: 500;
            color: var(--text-dark);
        }
    </style>
</head>
<body>
    <div class="overlay" id="overlay" onclick="toggleSidebar(false)"></div>
    <div class="sidebar" id="sidebar">
        <button class="btn-side primary" onclick="startNewChat()">✨ 新对话</button>
        <button class="btn-side success" onclick="runSpider()">⚡ 一键抓取情报</button>
        <div class="session-list" id="sessionList"></div>
    </div>

    <div class="main">
        <div class="header">
            <button class="menu-toggle" onclick="toggleSidebar(true)">☰</button>
            <span class="header-title">✨ AI 创作系统 Pro</span>
            <button onclick="toggleConfig()" style="background:none; border:none; font-size: 22px; cursor:pointer; color: var(--text-dark);">⚙️</button>
        </div>

        <div class="config-panel" id="configPanel">
            <div class="config-section">
                <h3>🤖 AI 配置</h3>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
                    <div class="form-group">
                        <label>API Key</label>
                        <input id="c_key" type="password" value="{{c.AI_KEY}}">
                    </div>
                    <div class="form-group">
                        <label>Model</label>
                        <input id="c_model" type="text" value="{{c.AI_MODEL}}">
                    </div>
                    <div class="form-group" style="grid-column: span 2;">
                        <label>Base URL</label>
                        <input id="c_url" type="text" value="{{c.AI_URL}}">
                    </div>
                </div>
            </div>
            
            <div class="config-section">
                <h3>📧 邮件通知配置</h3>
                <div class="switch-container">
                    <label class="switch">
                        <input type="checkbox" id="email_enabled" {{ 'checked' if c.EMAIL_ENABLED == 'true' else '' }}>
                        <span class="slider"></span>
                    </label>
                    <span class="switch-label">启用每日邮件报告</span>
                </div>
                <div class="form-group">
                    <label>邮箱地址</label>
                    <input id="email_address" type="email" value="{{c.EMAIL_ADDRESS}}" placeholder="your@email.com">
                </div>
                <div class="form-group">
                    <label>授权码（非密码）</label>
                    <input id="email_auth_code" type="password" value="{{c.EMAIL_AUTH_CODE}}" placeholder="授权码">
                </div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
                    <div class="form-group">
                        <label>SMTP 服务器</label>
                        <input id="email_smtp" type="text" value="{{c.EMAIL_SMTP}}">
                    </div>
                    <div class="form-group">
                        <label>SMTP 端口</label>
                        <input id="email_smtp_port" type="text" value="{{c.EMAIL_SMTP_PORT}}">
                    </div>
                </div>
            </div>
            
            <button class="btn-side primary" onclick="saveConfig()" style="margin-top:16px;">💾 保存配置</button>
            <button class="btn-side success" onclick="testEmail()" style="margin-top:8px;">📧 测试邮件</button>
        </div>

        <div id="chatbox"></div>

        <div class="input-area">
            <div class="input-container">
                <textarea id="userInput" rows="1" placeholder="发送消息... (Enter发送, Shift+Enter换行)"></textarea>
                <button class="send-btn" onclick="send()">➤</button>
            </div>
        </div>
    </div>

    <script>
        let sid = localStorage.getItem('sid') || 's_' + Date.now();

        function toggleSidebar(show) {
            document.getElementById('sidebar').classList.toggle('active', show);
            document.getElementById('overlay').classList.toggle('active', show);
        }

        function toggleConfig() { 
            document.getElementById('configPanel').classList.toggle('show'); 
        }

        async function saveConfig() {
            const data = {
                AI_KEY: document.getElementById('c_key').value,
                AI_URL: document.getElementById('c_url').value,
                AI_MODEL: document.getElementById('c_model').value,
                EMAIL_ENABLED: document.getElementById('email_enabled').checked ? 'true' : 'false',
                EMAIL_ADDRESS: document.getElementById('email_address').value,
                EMAIL_AUTH_CODE: document.getElementById('email_auth_code').value,
                EMAIL_SMTP: document.getElementById('email_smtp').value,
                EMAIL_SMTP_PORT: document.getElementById('email_smtp_port').value
            };
            await fetch('/save_config', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
            alert("✅ 配置已保存");
            toggleConfig();
        }

        async function testEmail() {
            const r = await fetch('/test_email');
            const res = await r.json();
            if (res.success) {
                alert("✅ 测试邮件已发送，请检查邮箱");
            } else {
                alert("❌ 邮件发送失败: " + (res.error || "未知错误"));
            }
        }

        async function loadUI() {
            const [r1, r2] = await Promise.all([fetch('/get_sessions'), fetch(`/get_history?sid=${sid}`)]);
            const sessions = await r1.json();
            const history = await r2.json();
            
            document.getElementById('sessionList').innerHTML = sessions.map(s => `
                <div class="session-item ${s.id === sid ? 'active' : ''}" onclick="switchChat('${s.id}')">
                    <div>💬 ${s.title}</div>
                    <div class="session-time">${s.time}</div>
                </div>
            `).join('');
            
            const chatbox = document.getElementById('chatbox');
            chatbox.innerHTML = '';
            history.history.forEach(m => renderMessage(m.role, m.content, m.id, m.feedback, m.timestamp));
            chatbox.scrollTop = chatbox.scrollHeight;
        }

        function formatTime(timestamp) {
            if (!timestamp) return '';
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;
            
            // 如果是今天
            if (date.toDateString() === now.toDateString()) {
                return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
            }
            // 如果是昨天
            const yesterday = new Date(now);
            yesterday.setDate(yesterday.getDate() - 1);
            if (date.toDateString() === yesterday.toDateString()) {
                return '昨天 ' + date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
            }
            // 其他日期
            return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
        }

        function renderMessage(role, content, mid, feedback, timestamp) {
            const chatbox = document.getElementById('chatbox');
            const group = document.createElement('div');
            group.className = `msg-group ${role}`;
            
            // 处理Markdown格式
            let processedContent = content
                // 处理链接 [text](url)
                .replace(new RegExp('\\[([^\\]]+)\\]\\(([^)]+)\\)', 'g'), '<a href="$2" target="_blank">$1</a>')
                // 处理粗体 **text**
                .replace(new RegExp('\\*\\*([^*]+)\\*\\*', 'g'), '<strong>$1</strong>')
                // 处理换行
                .replace(new RegExp('\\n', 'g'), '<br>');
            
            let html = `<div class="msg">${processedContent}</div>`;
            html += `<div class="timestamp">${formatTime(timestamp)}</div>`;
            
            if(role === 'assistant' && mid) {
                html += `
                <div class="tools">
                    <span class="tool-btn" onclick="copyText(this)">📋 复制</span>
                    <span class="tool-btn ${feedback === 1 ? 'active' : ''}" onclick="vote(${mid}, 1, this)">👍</span>
                    <span class="tool-btn ${feedback === -1 ? 'active' : ''}" onclick="vote(${mid}, -1, this)">👎</span>
                </div>`;
            }
            group.innerHTML = html;
            chatbox.appendChild(group);
            chatbox.scrollTop = chatbox.scrollHeight;
            
            // 返回创建的元素，方便后续操作
            return group;
        }

        async function send() {
            const input = document.getElementById('userInput');
            const val = input.value.trim();
            if(!val) return;
            renderMessage('user', val, null, null, new Date().toISOString());
            input.value = '';
            input.style.height = '';

            const r = await fetch('/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:val, sid:sid}) });
            const data = await r.json();
            renderMessage('assistant', data.res, data.mid, null, data.timestamp);
            if(data.refresh) loadUI();
        }

        window.onload = () => {
            loadUI();
            const inputEl = document.getElementById('userInput');
            inputEl.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' && !e.shiftKey && window.innerWidth > 768) {
                    e.preventDefault();
                    send();
                }
            });
            inputEl.addEventListener('input', function() {
                this.style.height = '';
                this.style.height = this.scrollHeight + 'px';
            });
        };

        function copyText(btn) {
            const text = btn.parentElement.parentElement.querySelector('.msg').innerText;
            navigator.clipboard.writeText(text).then(() => {
                const oldText = btn.innerHTML;
                btn.innerHTML = "✅ 已复制";
                setTimeout(() => btn.innerHTML = oldText, 1500);
            });
        }

        async function vote(mid, val, btn) {
            await fetch('/feedback', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({mid:mid, val:val}) });
            btn.parentElement.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }

        async function runSpider() {
            if(window.innerWidth <= 768) toggleSidebar(false);
            
            // 显示抓取中的提示
            const loadingMsg = renderMessage('assistant', "⏳ 正在抓取最新情报...\n📡 正在连接数据源...\n🔍 正在搜索相关文章...\n🤖 AI正在智能总结...", null, null, new Date().toISOString());
            
            try {
                const r = await fetch('/run_spider');
                const res = await r.json();
                
                // 删除加载消息
                const chatbox = document.getElementById('chatbox');
                const loadingElement = loadingMsg;
                if (loadingElement && loadingElement.parentElement) {
                    chatbox.removeChild(loadingElement.parentElement);
                }
                
                // 显示结果
                renderMessage('assistant', res.result, null, null, new Date().toISOString());
                
                // 如果成功，显示成功提示
                if (res.success !== false) {
                    const successMsg = document.createElement('div');
                    successMsg.style.cssText = 'position: fixed; top: 20px; right: 20px; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 16px 24px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 10000; animation: slideIn 0.3s ease;';
                    successMsg.innerHTML = '✅ 情报抓取成功！邮件已发送';
                    document.body.appendChild(successMsg);
                    setTimeout(() => {
                        successMsg.style.opacity = '0';
                        successMsg.style.transform = 'translateX(100px)';
                        successMsg.style.transition = 'all 0.3s ease';
                        setTimeout(() => document.body.removeChild(successMsg), 300);
                    }, 3000);
                }
            } catch (error) {
                // 删除加载消息
                const chatbox = document.getElementById('chatbox');
                if (loadingMsg && loadingMsg.parentElement) {
                    chatbox.removeChild(loadingMsg.parentElement);
                }
                
                // 显示错误信息
                renderMessage('assistant', "❌ 抓取失败：" + error.message, null, null, new Date().toISOString());
            }
        }

        function switchChat(id) { sid = id; localStorage.setItem('sid', sid); if(window.innerWidth <= 768) toggleSidebar(false); loadUI(); }
        function startNewChat() { sid = 's_'+Date.now(); localStorage.setItem('sid', sid); if(window.innerWidth <= 768) toggleSidebar(false); loadUI(); }
    </script>
</body>
</html>
'''

# ==================== 后端 API 路由 ====================
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, c=get_db_config())

@app.route('/save_config', methods=['POST'])
def save_config():
    data = request.json
    with sqlite3.connect(DB_FILE) as conn:
        for k, v in data.items():
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
    return jsonify({"status": "ok"})

@app.route('/test_email')
def test_email():
    """测试邮件发送"""
    cfg = get_db_config()
    email = cfg.get('EMAIL_ADDRESS')
    auth_code = cfg.get('EMAIL_AUTH_CODE')
    
    if not email or not auth_code:
        return jsonify({"success": False, "error": "邮箱或授权码未配置"})
    
    # 发送测试邮件
    html_content = f"""
    <h2>✅ 邮件测试成功！</h2>
    <p>这是一封测试邮件，用于验证QQ邮箱SMTP配置是否正确。</p>
    <hr>
    <p><strong>发送时间：</strong>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>发件人：</strong>{email}</p>
    <p><strong>收件人：</strong>{email}</p>
    <hr>
    <p style="color: green; font-size: 16px; font-weight: bold;">如果您收到这封邮件，说明邮件配置正确！🎉</p>
    """
    
    subject = f"📧 测试邮件 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    success, message = send_email_report(subject, html_content)
    
    if success:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "error": message})

@app.route('/chat', methods=['POST'])
def chat():
    d = request.json
    msg, sid = d['message'], d['sid']
    refresh = False
    
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO messages (session_id, role, content) VALUES (?, 'user', ?)", (sid, msg))
        count = conn.execute("SELECT count(*) FROM messages WHERE session_id = ?", (sid,)).fetchone()[0]
        if count <= 1:
            conn.execute("INSERT OR REPLACE INTO sessions (session_id, title, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)", (sid, msg[:15]))
            refresh = True
        conn.commit()
    
    ai_res = ask_ai_with_memory(sid, msg)
    
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO messages (session_id, role, content) VALUES (?, 'assistant', ?)", (sid, ai_res))
        mid = cur.lastrowid
        # 获取插入的时间戳
        timestamp = conn.execute("SELECT timestamp FROM messages WHERE id = ?", (mid,)).fetchone()[0]
        conn.commit()
        
    return jsonify({"res": ai_res, "mid": mid, "refresh": refresh, "timestamp": timestamp})

@app.route('/get_sessions')
def get_sessions():
    with sqlite3.connect(DB_FILE) as conn:
        res = conn.execute("SELECT session_id, title, updated_at FROM sessions ORDER BY updated_at DESC").fetchall()
        sessions = []
        for r in res:
            time_str = ""
            if r[2]:
                try:
                    dt = datetime.fromisoformat(r[2].replace('Z', '+00:00'))
                    time_str = dt.strftime('%m-%d %H:%M')
                except:
                    time_str = ""
            sessions.append({"id": r[0], "title": r[1], "time": time_str})
        return jsonify(sessions)

@app.route('/get_history')
def get_history():
    sid = request.args.get('sid')
    with sqlite3.connect(DB_FILE) as conn:
        res = conn.execute("SELECT role, content, id, feedback, timestamp FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        return jsonify({"history": [{"role": r[0], "content": r[1], "id": r[2], "feedback": r[3], "timestamp": r[4]} for r in res]})

@app.route('/feedback', methods=['POST'])
def feedback():
    d = request.json
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE messages SET feedback = ? WHERE id = ?", (d['val'], d['mid']))
    return jsonify({"ok": True})

@app.route('/run_spider')
def run_spider():
    """抓取情报并发送邮件报告"""
    try:
        # 模拟抓取情报（这里可以替换为真实的抓取逻辑）
        # 示例：从多个来源抓取文章
        articles = [
            {
                "title": "深度学习在自然语言处理中的最新进展",
                "url": "https://example.com/article1",
                "summary": "介绍了Transformer架构的改进和GPT系列模型的发展历程"
            },
            {
                "title": "人工智能伦理与安全挑战",
                "url": "https://example.com/article2",
                "summary": "探讨了AI系统中的偏见问题和隐私保护措施"
            },
            {
                "title": "多模态大模型的应用前景",
                "url": "https://example.com/article3",
                "summary": "分析了文本、图像、音频等多种模态融合的技术路线"
            },
            {
                "title": "强化学习在机器人控制中的突破",
                "url": "https://example.com/article4",
                "summary": "展示了Sim2Real技术在机器人学习中的应用"
            },
            {
                "title": "AI辅助创作工具的发展趋势",
                "url": "https://example.com/article5",
                "summary": "讨论了生成式AI在文学、艺术创作中的创新应用"
            },
            {
                "title": "大模型推理优化的关键技术",
                "url": "https://example.com/article6",
                "summary": "介绍了量化、剪枝、蒸馏等模型压缩技术"
            },
            {
                "title": "知识图谱与大模型的融合方法",
                "url": "https://example.com/article7",
                "summary": "探讨了如何将结构化知识注入到预训练模型中"
            },
            {
                "title": "AI在医疗诊断中的实际应用案例",
                "url": "https://example.com/article8",
                "summary": "分析了医学影像识别和临床决策支持系统的效果"
            }
        ]
        
        # 使用AI生成总结
        cfg = get_db_config()
        client = OpenAI(api_key=cfg['AI_KEY'], base_url=cfg['AI_URL'])
        
        # 生成文章列表文本
        articles_text = "\n".join([f"{i+1}. {a['title']}\n   链接: {a['url']}\n   摘要: {a['summary']}" for i, a in enumerate(articles)])
        
        # 让AI生成3篇总结
        summary_prompt = f"""请根据以下文章列表，生成3篇不同角度的深度总结（每篇200-300字）：

{articles_text}

要求：
1. 总结1：从技术发展趋势角度
2. 总结2：从应用场景角度
3. 总结3：从行业影响角度

请直接输出3篇总结，每篇用"总结X："开头。"""
        
        response = client.chat.completions.create(
            model=cfg['AI_MODEL'],
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.7
        )
        
        ai_summaries = response.choices[0].message.content
        
        # 解析AI总结
        summaries = []
        for line in ai_summaries.split('\n'):
            if line.strip():
                summaries.append(line.strip())
        
        # 构建返回数据
        intelligence_data = {
            "success": True,
            "articles": articles,
            "summaries": summaries[:3],  # 只取前3篇
            "total_count": len(articles)
        }
        
        # 自动发送邮件报告（手动触发优先级高，不受定时任务限制）
        email_success, email_message = send_intelligence_report(intelligence_data)
        
        # 构建显示给用户的结果（使用Markdown格式）
        result_lines = [
            "🔍 **情报抓取成功！**",
            f"📊 共抓取 {len(articles)} 篇文章",
            f"📧 邮件通知：{'✅ 已发送' if email_success else '❌ 发送失败 - ' + email_message}",
            "\n**📋 文章列表：**\n"
        ]
        
        for idx, article in enumerate(articles, 1):
            result_lines.append(f"{idx}. **{article['title']}**")
            result_lines.append(f"   🔗 [{article['url']}]({article['url']})")
            result_lines.append(f"   📝 {article['summary']}")
            result_lines.append("")
        
        result_lines.append("\n**📝 AI 总结：**\n")
        for idx, summary in enumerate(summaries[:3], 1):
            result_lines.append(f"**总结 {idx}：**\n{summary}\n")
        
        result_lines.append(f"\n📧 详细报告已发送至邮箱")
        
        return jsonify({"result": "\n".join(result_lines), "data": intelligence_data, "success": True})
        
    except Exception as e:
        error_msg = f"❌ 情报抓取失败：{str(e)}"
        return jsonify({"result": error_msg, "success": False})

if __name__ == '__main__':
    print("🚀 AI 创作系统 Pro 启动中...")
    print("=" * 50)
    print("📧 邮件通知服务已启动")
    print("   - 自动报告：每天8:00发送每日聊天记录")
    print("   - 手动报告：点击'一键抓取情报'立即发送情报报告")
    print("=" * 50)
    print("🎯 访问地址: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
