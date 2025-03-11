import os
import base64
import email
import imaplib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
import threading
import time
import google.generativeai as genai
import warnings
import logging
import absl.logging

# 设置环境变量以抑制警告
os.environ['TK_SILENCE_DEPRECATION'] = '1'

# 抑制所有警告
warnings.filterwarnings('ignore')

# 初始化 absl 日志
absl.logging.set_verbosity(absl.logging.ERROR)
absl.logging.use_absl_handler()

# 抑制 libpng 警告
logging.getLogger('PIL').setLevel(logging.ERROR)

class AutoEmailProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title("自动邮件处理应用")
        self.root.geometry("800x600")
        
        # 邮箱配置
        self.email_address = ""
        self.email_password = ""
        self.imap_server = "imap.gmail.com"  # 默认使用 Gmail
        self.smtp_server = "smtp.gmail.com"
        self.imap_port = 993
        self.smtp_port = 587
        
        # 处理配置
        self.processing = False
        self.check_interval = 60  # 默认每60秒检查一次
        
        # Gemini API 配置
        self.api_key = ""  # 需要填入你的 Gemini API 密钥
        
        # 首先设置UI
        self.setup_ui()
        
        # 然后配置 Gemini
        self.configure_gemini()
    
    def configure_gemini(self):
        if not self.api_key:
            self.log("未设置 Gemini API 密钥")
            return
            
        try:
            genai.configure(api_key=self.api_key,transport='rest')
            
            # 设置生成参数
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 1024,
            }
            
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                },
            ]
            
            self.model = genai.GenerativeModel(
                model_name='gemini-2.0-flash',
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            self.log("Gemini API 配置成功")
            
        except Exception as e:
            self.log(f"Gemini API 配置失败: {str(e)}")
            messagebox.showerror("API 错误", f"Gemini API 配置失败: {str(e)}")
    
    def setup_ui(self):
        # 创建菜单栏
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="邮箱配置", command=self.configure_email)
        settings_menu.add_command(label="API配置", command=self.configure_api)
        settings_menu.add_separator()
        settings_menu.add_command(label="退出", command=self.root.quit)
        
        # 主框架
        main_frame = tk.Frame(self.root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 控制区域
        control_frame = tk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)
        
        self.start_button = tk.Button(control_frame, text="开始处理", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(control_frame, text="停止处理", command=self.stop_processing, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 日志区域
        log_frame = tk.LabelFrame(main_frame, text="处理日志")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 规则区域
        rules_frame = tk.LabelFrame(main_frame, text="处理规则")
        rules_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.rules_text = scrolledtext.ScrolledText(rules_frame, wrap=tk.WORD, height=5)
        self.rules_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.rules_text.insert(tk.END, "请在这里输入邮件处理规则，例如：\n1. 如果邮件包含'发票'关键词，自动回复'已收到发票，谢谢'\n2. 将所有来自特定域名的邮件分类到'工作'文件夹")
        
        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def log(self, message):
        self.log_text.insert(tk.END, f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_text.see(tk.END)
    
    def configure_email(self):
        self.email_address = simpledialog.askstring("邮箱配置", "请输入邮箱地址:", initialvalue=self.email_address)
        if self.email_address:
            self.email_password = simpledialog.askstring("邮箱配置", "请输入邮箱密码:", show='*')
            self.imap_server = simpledialog.askstring("邮箱配置", "IMAP服务器:", initialvalue=self.imap_server)
            self.smtp_server = simpledialog.askstring("邮箱配置", "SMTP服务器:", initialvalue=self.smtp_server)
            self.log(f"邮箱配置已更新: {self.email_address}")
    
    def configure_api(self):
        self.api_key = simpledialog.askstring("API配置", "请输入Gemini API密钥:", initialvalue=self.api_key)
        if self.api_key:
            self.configure_gemini()
            self.log("Gemini API配置已更新")
    
    def start_processing(self):
        if not self.email_address or not self.email_password or not self.api_key:
            messagebox.showerror("配置错误", "请先完成邮箱和API配置")
            return
        
        self.processing = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("正在处理邮件...")
        
        # 启动处理线程
        self.process_thread = threading.Thread(target=self.email_processing_loop)
        self.process_thread.daemon = True
        self.process_thread.start()
        
        self.log("邮件自动处理已启动")
    
    def stop_processing(self):
        self.processing = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("就绪")
        self.log("邮件自动处理已停止")
    
    def email_processing_loop(self):
        while self.processing:
            try:
                self.process_emails()
            except Exception as e:
                self.log(f"处理邮件时出错: {str(e)}")
            
            # 等待下一次检查
            for _ in range(self.check_interval):
                if not self.processing:
                    break
                time.sleep(1)
    
    def process_emails(self):
        try:
            # 连接到IMAP服务器
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.email_password)
        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            if "AUTHENTICATIONFAILED" in error_msg:
                self.log("认证失败！如果你使用的是Gmail，请注意：")
                self.log("1. 需要开启两步验证")
                self.log("2. 使用App专用密码而不是普通密码")
                self.log("3. 访问 https://myaccount.google.com/apppasswords 生成App专用密码")
                self.stop_processing()
                return
            else:
                self.log(f"IMAP连接错误: {str(e)}")
                return
        
        try:
            mail.select('inbox')
            
            # 搜索未读邮件
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                self.log("无法获取未读邮件")
                mail.logout()
                return
            
            message_ids = messages[0].split()
            if not message_ids:
                self.log("没有新邮件")
                mail.logout()
                return
            
            self.log(f"发现 {len(message_ids)} 封未读邮件")
            
            # 获取处理规则
            rules = self.rules_text.get("1.0", tk.END).strip()
            
            # 处理每封邮件
            for msg_id in message_ids:
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                if status != 'OK':
                    continue
                    
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                subject = email_message['Subject']
                from_addr = email.utils.parseaddr(email_message['From'])[1]
                
                self.log(f"处理邮件: {subject} (来自 {from_addr})")
                
                # 提取邮件内容
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        content_type = part.get_content_type()
                        if content_type == "text/plain":
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = email_message.get_payload(decode=True).decode()
                
                # 使用Gemini API分析邮件
                if self.api_key:
                    try:
                        prompt = f"""
                        分析以下邮件并根据规则处理:
                        
                        发件人: {from_addr}
                        主题: {subject}
                        内容: {body[:500]}...
                        
                        处理规则:
                        {rules}
                        
                        请提供:
                        1. 这封邮件的简要总结
                        2. 根据规则应该如何处理
                        3. 如果需要回复，提供回复内容
                        """
                        
                        response = self.model.generate_content(prompt)
                        analysis = response.text
                        
                        self.log(f"AI分析结果: {analysis[:100]}...")
                        
                        # 检查是否需要自动回复
                        if "需要回复" in analysis or "回复内容" in analysis:
                            # 提取回复内容
                            reply_content = ""
                            if "回复内容:" in analysis:
                                reply_content = analysis.split("回复内容:")[1].strip()
                            elif "回复内容：" in analysis:
                                reply_content = analysis.split("回复内容：")[1].strip()
                            
                            if reply_content:
                                self.send_reply(from_addr, f"Re: {subject}", reply_content)
                    
                    except Exception as e:
                        self.log(f"AI处理失败: {str(e)}")
        
            mail.logout()
        except Exception as e:
            self.log(f"处理邮件时出错: {str(e)}")
    
    def send_reply(self, to_addr, subject, content):
        try:
            # 创建邮件
            msg = MIMEMultipart()
            msg['From'] = self.email_address
            msg['To'] = to_addr
            msg['Subject'] = subject
            
            msg.attach(MIMEText(content, 'plain'))
            
            # 发送邮件
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_address, self.email_password)
            server.send_message(msg)
            server.quit()
            
            self.log(f"已回复邮件给 {to_addr}")
        except Exception as e:
            self.log(f"发送回复失败: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoEmailProcessor(root)
    root.mainloop()
