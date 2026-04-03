# Creative Chat System

AI创意聊天系统，支持长期记忆和邮件报告功能。

## 文件说明

| 文件 | 说明 |
|------|------|
| `creative_chat_v5.py` | 基础版本，使用 v5 数据库 |
| `creative_chat_enhanced.py` | 增强版本，使用 v7 数据库，支持定时邮件报告 |
| `send_email_report.py` | 独立的邮件报告发送模块 |
| `test_email.py` | 邮件发送测试工具 |

## 核心功能

- **AI对话**：调用 DeepSeek API 进行智能对话
- **长期记忆**：自动归纳对话要点，跨会话保持上下文
- **短期记忆**：保留最近6条对话记录
- **邮件报告**：可配置每日/定时发送聊天记录报告（QQ邮箱SMTP）

## 配置

系统首次运行时会自动初始化数据库（SQLite），默认配置：

- AI API: DeepSeek (`deepseek-chat`)
- AI URL: `https://api.deepseek.com/v1`
- 邮件: QQ邮箱 SMTP (465端口)

## 依赖

```
flask
openai
requests
```

## 运行

```bash
pip install flask openai requests
python creative_chat_enhanced.py
```

服务启动后访问 `http://localhost:5000`
