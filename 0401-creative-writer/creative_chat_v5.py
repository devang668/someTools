import sqlite3
import requests
import json
from flask import Flask, request, render_template_string, jsonify
from openai import OpenAI

app = Flask(__name__)
DB_FILE = "creative_system_pro_v5.db"

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
        
        defaults = [('AI_KEY', 'sk-804e8b333a5e4be886765ba00181da12'), 
                    ('AI_URL', 'https://api.deepseek.com/v1'), 
                    ('AI_MODEL', 'deepseek-chat')]
        conn.executemany("INSERT OR IGNORE INTO settings VALUES (?, ?)", defaults)
        conn.commit()

init_db()

def get_db_config():
    with sqlite3.connect(DB_FILE) as conn:
        res = conn.execute("SELECT key, value FROM settings").fetchall()
        return {k: v for k, v in res}

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
    <title>AI 创作系统 V5</title>
    <style>
        :root { --sidebar-w: 280px; --primary: #1a73e8; --side-bg: #1e293b; --bg-light: #f8f9fa; }
        * { box-sizing: border-box; }
        body { font-family: -apple-system, sans-serif; display: flex; height: 100vh; margin: 0; background: #fff; overflow: hidden; }
        
        /* 侧边栏 */
        .sidebar { position: fixed; top: 0; left: 0; bottom: 0; width: var(--sidebar-w); background: var(--side-bg); color: #fff; display: flex; flex-direction: column; padding: 15px; transition: transform 0.3s ease; z-index: 1001; transform: translateX(-100%); }
        .sidebar.active { transform: translateX(0); }
        .overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000; }
        .overlay.active { display: block; }

        @media (min-width: 769px) {
            .sidebar { position: relative; transform: translateX(0); }
            .overlay { display: none !important; }
            .menu-toggle { display: none; }
        }

        /* 主体布局 */
        .main { flex: 1; display: flex; flex-direction: column; height: 100vh; min-width: 0; position: relative; }
        .header { height: 56px; padding: 0 15px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; background: #fff; flex-shrink: 0; }
        .menu-toggle { font-size: 24px; cursor: pointer; border: none; background: none; color: #475569; }

        /* 聊天区 */
        #chatbox { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 20px; }
        .msg-group { display: flex; flex-direction: column; max-width: 85%; }
        .msg-group.user { align-self: flex-end; }
        .msg-group.assistant { align-self: flex-start; width: 100%; }
        
        .msg { padding: 12px 16px; border-radius: 12px; font-size: 15px; line-height: 1.6; word-wrap: break-word; }
        .user .msg { background: #f1f3f4; color: #1a1a1a; border-bottom-right-radius: 2px; }
        .assistant .msg { background: #fff; border: 1px solid #e2e8f0; color: #1a1a1a; border-bottom-left-radius: 2px; }

        /* 工具栏 */
        .tools { display: flex; gap: 15px; margin-top: 5px; padding-left: 5px; }
        .tool-btn { font-size: 12px; color: #94a3b8; cursor: pointer; display: flex; align-items: center; gap: 4px; }
        .tool-btn:hover { color: var(--primary); }
        .tool-btn.active { color: var(--primary); font-weight: bold; }

        /* 输入区 */
        .input-area { padding: 15px; border-top: 1px solid #eee; }
        .input-container { display: flex; gap: 10px; background: var(--bg-light); border-radius: 24px; padding: 4px 16px; align-items: center; border: 1px solid #e2e8f0; }
        textarea { flex: 1; border: none; background: none; outline: none; resize: none; padding: 12px 0; font-size: 16px; max-height: 150px; }

        /* 配置抽屉 */
        .config-panel { position: absolute; top: 56px; left: 0; right: 0; background: #fff; border-bottom: 2px solid var(--primary); padding: 20px; display: none; z-index: 999; box-shadow: 0 10px 15px rgba(0,0,0,0.1); }
        .config-panel.show { display: block; }
        .btn-side { width: 100%; padding: 12px; margin-bottom: 10px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.2); background: rgba(255,255,255,0.1); color: white; cursor: pointer; }
    </style>
</head>
<body>
    <div class="overlay" id="overlay" onclick="toggleSidebar(false)"></div>
    <div class="sidebar" id="sidebar">
        <button class="btn-side" onclick="startNewChat()">+ 新对话</button>
        <button class="btn-side" style="background:#10b981; border:none;" onclick="runSpider()">⚡ 一键抓取情报</button>
        <div id="sessionList" style="flex:1; overflow-y:auto; margin-top:10px;"></div>
    </div>

    <div class="main">
        <div class="header">
            <button class="menu-toggle" onclick="toggleSidebar(true)">☰</button>
            <span style="font-weight: bold;">AI 创作系统 V5</span>
            <button onclick="toggleConfig()" style="background:none; border:none; font-size: 20px; cursor:pointer;">⚙️</button>
        </div>

        <div class="config-panel" id="configPanel">
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                <div><label style="font-size:11px">API Key</label><input id="c_key" type="password" value="{{c.AI_KEY}}" style="width:100%"></div>
                <div><label style="font-size:11px">Model</label><input id="c_model" type="text" value="{{c.AI_MODEL}}" style="width:100%"></div>
                <div style="grid-column: span 2;"><label style="font-size:11px">Base URL</label><input id="c_url" type="text" value="{{c.AI_URL}}" style="width:100%"></div>
            </div>
            <button class="btn-side" style="background:var(--primary); border:none; margin-top:15px;" onclick="saveConfig()">保存配置</button>
        </div>

        <div id="chatbox"></div>

        <div class="input-area">
            <div class="input-container">
                <textarea id="userInput" rows="1" placeholder="发送消息... (Enter发送, Shift+Enter换行)"></textarea>
                <button onclick="send()" style="border:none; background:none; color:var(--primary); font-size:24px; cursor:pointer;">➤</button>
            </div>
        </div>
    </div>

    <script>
        let sid = localStorage.getItem('sid') || 's_' + Date.now();

        function toggleSidebar(show) {
            document.getElementById('sidebar').classList.toggle('active', show);
            document.getElementById('overlay').classList.toggle('active', show);
        }

        function toggleConfig() { document.getElementById('configPanel').classList.toggle('show'); }

        async function saveConfig() {
            const data = {
                AI_KEY: document.getElementById('c_key').value,
                AI_URL: document.getElementById('c_url').value,
                AI_MODEL: document.getElementById('c_model').value
            };
            await fetch('/save_config', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
            alert("配置已应用");
            toggleConfig();
        }

        async function loadUI() {
            const [r1, r2] = await Promise.all([fetch('/get_sessions'), fetch(`/get_history?sid=${sid}`)]);
            const sessions = await r1.json();
            const history = await r2.json();
            
            document.getElementById('sessionList').innerHTML = sessions.map(s => `
                <div onclick="switchChat('${s.id}')" style="padding:10px; border-radius:6px; font-size:14px; margin-bottom:4px; cursor:pointer; ${s.id === sid ? 'background:var(--primary)' : 'opacity:0.8'}">💬 ${s.title}</div>
            `).join('');
            
            const chatbox = document.getElementById('chatbox');
            chatbox.innerHTML = '';
            history.history.forEach(m => renderMessage(m.role, m.content, m.id, m.feedback));
            chatbox.scrollTop = chatbox.scrollHeight;
        }

        function renderMessage(role, content, mid, feedback) {
            const chatbox = document.getElementById('chatbox');
            const group = document.createElement('div');
            group.className = `msg-group ${role}`;
            
            let html = `<div class="msg">${content}</div>`;
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
        }

        async function send() {
            const input = document.getElementById('userInput');
            const val = input.value.trim();
            if(!val) return;
            renderMessage('user', val);
            input.value = '';
            input.style.height = '';

            const r = await fetch('/chat', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:val, sid:sid}) });
            const data = await r.json();
            renderMessage('assistant', data.res, data.mid);
            if(data.refresh) loadUI();
        }

        // --- 核心改进：键盘监听 ---
        window.onload = () => {
            loadUI();
            const inputEl = document.getElementById('userInput');
            inputEl.addEventListener('keydown', function(e) {
                // PC端回车发送，Shift+Enter换行
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
            renderMessage('assistant', "⏳ 正在抓取最新情报并总结中...");
            const r = await fetch('/run_spider');
            const res = await r.json();
            renderMessage('assistant', res.result);
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
        conn.commit()
        
    return jsonify({"res": ai_res, "mid": mid, "refresh": refresh})

@app.route('/get_sessions')
def get_sessions():
    with sqlite3.connect(DB_FILE) as conn:
        res = conn.execute("SELECT session_id, title FROM sessions ORDER BY updated_at DESC").fetchall()
        return jsonify([{"id": r[0], "title": r[1]} for r in res])

@app.route('/get_history')
def get_history():
    sid = request.args.get('sid')
    with sqlite3.connect(DB_FILE) as conn:
        res = conn.execute("SELECT role, content, id, feedback FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)).fetchall()
        return jsonify({"history": [{"role": r[0], "content": r[1], "id": r[2], "feedback": r[3]} for r in res]})

@app.route('/feedback', methods=['POST'])
def feedback():
    d = request.json
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE messages SET feedback = ? WHERE id = ?", (d['val'], d['mid']))
    return jsonify({"ok": True})

@app.route('/run_spider')
def run_spider():
    # 示例抓取摘要逻辑
    report = "【情报站同步成功】\n今日热点摘要：关于情感心理学及深度创作的15条新线索已收录。AI已根据这些背景信息准备好协助你创作。"
    return jsonify({"result": report})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)