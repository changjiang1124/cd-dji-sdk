#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件通知模块

功能说明：
- 提供统一的邮件发送接口
- 支持多种邮件类型（成功、警告、错误）
- 自动从环境变量读取SMTP配置
- 支持HTML和纯文本格式

使用示例：
    from email_notifier import EmailNotifier
    
    notifier = EmailNotifier()
    notifier.send_success("同步完成", "媒体文件同步成功完成")
    notifier.send_error("同步失败", "网络连接异常")
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class EmailNotifier:
    """
    邮件通知器类
    
    负责发送各种类型的通知邮件，包括成功、警告、错误等状态通知
    """
    
    def __init__(self):
        """
        初始化邮件通知器
        
        从环境变量中读取SMTP配置信息
        """
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.smtp_recipient = os.getenv('SMTP_RECIPIENT')
        
        # 验证必要的配置项
        if not all([self.smtp_server, self.smtp_user, self.smtp_password, self.smtp_recipient]):
            raise ValueError("缺少必要的SMTP配置信息，请检查.env文件")
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
    
    def _create_message(self, subject: str, body: str, is_html: bool = False) -> MIMEMultipart:
        """
        创建邮件消息对象
        
        参数:
            subject: 邮件主题
            body: 邮件正文
            is_html: 是否为HTML格式
            
        返回:
            MIMEMultipart: 邮件消息对象
        """
        msg = MIMEMultipart()
        # 修复邮件头格式，避免编码问题
        msg['From'] = f"Edge Server <{self.smtp_user}>"
        msg['To'] = self.smtp_recipient
        msg['Subject'] = Header(subject, 'utf-8').encode()
        
        # 添加时间戳到邮件正文
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body_with_timestamp = f"时间: {timestamp}\n\n{body}"
        
        # 设置邮件正文
        if is_html:
            msg.attach(MIMEText(body_with_timestamp, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(body_with_timestamp, 'plain', 'utf-8'))
        
        return msg
    
    def _send_email(self, msg: MIMEMultipart) -> bool:
        """
        发送邮件
        
        参数:
            msg: 邮件消息对象
            
        返回:
            bool: 发送是否成功
        """
        try:
            # 根据端口选择连接方式
            if self.smtp_port == 465:
                # 端口 465 使用 SSL
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                # 其他端口使用 STARTTLS
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()  # 启用TLS加密
            
            server.login(self.smtp_user, self.smtp_password)
            
            # 发送邮件
            text = msg.as_string()
            server.sendmail(self.smtp_user, [self.smtp_recipient], text)
            server.quit()
            
            self.logger.info(f"邮件发送成功: {msg['Subject']}")
            return True
            
        except Exception as e:
            self.logger.error(f"邮件发送失败: {str(e)}")
            return False
    
    def send_success(self, subject: str, message: str, details: Optional[str] = None) -> bool:
        """
        发送成功通知邮件
        
        参数:
            subject: 邮件主题
            message: 主要消息内容
            details: 详细信息（可选）
            
        返回:
            bool: 发送是否成功
        """
        full_subject = f"✅ [成功] {subject}"
        
        body = f"操作成功完成！\n\n{message}"
        if details:
            body += f"\n\n详细信息:\n{details}"
        
        msg = self._create_message(full_subject, body)
        return self._send_email(msg)
    
    def send_warning(self, subject: str, message: str, details: Optional[str] = None) -> bool:
        """
        发送警告通知邮件
        
        参数:
            subject: 邮件主题
            message: 主要消息内容
            details: 详细信息（可选）
            
        返回:
            bool: 发送是否成功
        """
        full_subject = f"⚠️ [警告] {subject}"
        
        body = f"检测到需要注意的情况：\n\n{message}"
        if details:
            body += f"\n\n详细信息:\n{details}"
        
        msg = self._create_message(full_subject, body)
        return self._send_email(msg)
    
    def send_error(self, subject: str, message: str, error_details: Optional[str] = None) -> bool:
        """
        发送错误通知邮件
        
        参数:
            subject: 邮件主题
            message: 主要消息内容
            error_details: 错误详细信息（可选）
            
        返回:
            bool: 发送是否成功
        """
        full_subject = f"❌ [错误] {subject}"
        
        body = f"发生错误，需要立即处理：\n\n{message}"
        if error_details:
            body += f"\n\n错误详情:\n{error_details}"
        
        msg = self._create_message(full_subject, body)
        return self._send_email(msg)
    
    def send_info(self, subject: str, message: str, details: Optional[str] = None) -> bool:
        """
        发送信息通知邮件
        
        参数:
            subject: 邮件主题
            message: 主要消息内容
            details: 详细信息（可选）
            
        返回:
            bool: 发送是否成功
        """
        full_subject = f"ℹ️ [信息] {subject}"
        
        body = f"系统信息通知：\n\n{message}"
        if details:
            body += f"\n\n详细信息:\n{details}"
        
        msg = self._create_message(full_subject, body)
        return self._send_email(msg)
    
    def send_custom(self, subject: str, body: str, is_html: bool = False) -> bool:
        """
        发送自定义邮件
        
        参数:
            subject: 邮件主题
            body: 邮件正文
            is_html: 是否为HTML格式
            
        返回:
            bool: 发送是否成功
        """
        msg = self._create_message(subject, body, is_html)
        return self._send_email(msg)
    
    def send_batch_notification(self, notifications: List[dict]) -> dict:
        """
        批量发送通知邮件
        
        参数:
            notifications: 通知列表，每个元素包含type, subject, message, details等字段
            
        返回:
            dict: 发送结果统计
        """
        results = {'success': 0, 'failed': 0, 'total': len(notifications)}
        
        for notification in notifications:
            notification_type = notification.get('type', 'info')
            subject = notification.get('subject', '无主题')
            message = notification.get('message', '无内容')
            details = notification.get('details')
            
            # 根据类型调用相应的发送方法
            if notification_type == 'success':
                success = self.send_success(subject, message, details)
            elif notification_type == 'warning':
                success = self.send_warning(subject, message, details)
            elif notification_type == 'error':
                success = self.send_error(subject, message, details)
            else:
                success = self.send_info(subject, message, details)
            
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
        
        return results


# 创建全局实例，方便其他模块直接导入使用
try:
    email_notifier = EmailNotifier()
except ValueError as e:
    # 如果配置不完整，创建一个空的实例
    email_notifier = None
    print(f"邮件通知器初始化失败: {e}")


if __name__ == "__main__":
    """
    测试邮件通知功能
    """
    import sys
    
    if email_notifier is None:
        print("邮件通知器未正确初始化，请检查.env配置")
        sys.exit(1)
    
    # 测试各种类型的通知
    print("测试邮件通知功能...")
    
    # 测试成功通知
    success = email_notifier.send_success(
        "测试成功通知", 
        "这是一个测试成功通知", 
        "所有功能正常运行"
    )
    print(f"成功通知发送: {'成功' if success else '失败'}")
    
    # 测试警告通知
    success = email_notifier.send_warning(
        "测试警告通知", 
        "这是一个测试警告通知", 
        "磁盘空间使用率较高"
    )
    print(f"警告通知发送: {'成功' if success else '失败'}")
    
    # 测试错误通知
    success = email_notifier.send_error(
        "测试错误通知", 
        "这是一个测试错误通知", 
        "网络连接超时"
    )
    print(f"错误通知发送: {'成功' if success else '失败'}")
    
    # 测试信息通知
    success = email_notifier.send_info(
        "测试信息通知", 
        "这是一个测试信息通知", 
        "系统状态正常"
    )
    print(f"信息通知发送: {'成功' if success else '失败'}")
    
    print("邮件通知测试完成")