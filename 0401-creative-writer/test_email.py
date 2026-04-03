import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# QQ邮箱配置
EMAIL_ADDRESS = "---@qq.com"
EMAIL_AUTH_CODE = "----jxkhaje"
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465

def send_test_email():
    """发送测试邮件"""
    try:
        # 创建邮件对象
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = EMAIL_ADDRESS
        msg['Subject'] = f"📧 测试邮件 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # 邮件正文
        html_content = """
        <h2>✅ 邮件发送成功！</h2>
        <p>这是一封测试邮件，用于验证QQ邮箱SMTP配置是否正确。</p>
        <hr>
        <p><strong>发送时间：</strong>{}</p>
        <p><strong>发件人：</strong>{}</p>
        <p><strong>收件人：</strong>{}</p>
        <hr>
        <p style="color: green;">如果您收到这封邮件，说明邮件配置正确！🎉</p>
        """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), EMAIL_ADDRESS, EMAIL_ADDRESS)
        
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        
        # 连接SMTP服务器并发送
        print("正在连接SMTP服务器...")
        print(f"服务器: {SMTP_SERVER}")
        print(f"端口: {SMTP_PORT}")
        
        # 尝试使用 SMTP_SSL
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.set_debuglevel(1)  # 开启调试模式
        
        print("正在登录...")
        server.login(EMAIL_ADDRESS, EMAIL_AUTH_CODE)
        print("登录成功！")
        
        print("正在发送邮件...")
        server.send_message(msg)
        print("✅ 邮件发送成功！")
        print(f"请检查邮箱：{EMAIL_ADDRESS}")
        
        server.quit()
        return True
            
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ 认证失败：{e}")
        print("请检查：")
        print("1. 授权码是否正确（不是邮箱密码）")
        print("2. QQ邮箱是否开启了POP3/SMTP服务")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP错误：{e}")
        print(f"错误代码：{e.smtp_code}")
        print(f"错误信息：{e.smtp_error}")
        return False
    except Exception as e:
        print(f"❌ 发送失败：{e}")
        print(f"错误类型：{type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 50)
    print("QQ邮件测试程序")
    print("=" * 50)
    print(f"邮箱：{EMAIL_ADDRESS}")
    print(f"SMTP：{SMTP_SERVER}:{SMTP_PORT}")
    print(f"授权码：{'*' * len(EMAIL_AUTH_CODE)}")
    print("=" * 50)
    
    success = send_test_email()
    
    print("=" * 50)
    if success:
        print("测试完成！请检查邮箱收件箱（可能在垃圾邮件中）")
    else:
        print("测试失败，请检查配置")
    print("=" * 50)