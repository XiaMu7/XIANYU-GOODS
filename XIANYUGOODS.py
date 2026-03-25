#!/usr/bin/env python3
"""
闲鱼扫码登录 - 无依赖版
运行: streamlit run xianyu_login_no_qrcode.py
"""

import streamlit as st
import requests
import time
import json
import re
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="闲鱼扫码登录",
    page_icon="🐟",
    layout="centered"
)

class XianyuQRLogin:
    """闲鱼扫码登录"""
    
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.cookies = {}
        
        # 完整的浏览器请求头
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        })
    
    def init_session(self):
        """初始化会话"""
        try:
            # 先访问闲鱼首页
            self.session.get("https://www.goofish.com/", timeout=10)
            return True
        except Exception as e:
            st.error(f"初始化失败: {e}")
            return False
    
    def get_qr_code(self):
        """获取二维码 - 多种方法尝试"""
        
        if not self.init_session():
            return None
        
        # 方法1: 直接请求二维码接口
        result = self._try_qr_api()
        if result:
            return result
        
        # 方法2: 从登录页提取
        result = self._extract_from_login_page()
        if result:
            return result
        
        return None
    
    def _try_qr_api(self):
        """尝试二维码API"""
        try:
            url = "https://passport.goofish.com/newlogin/qrcode/query.do"
            params = {
                "appName": "xianyu",
                "fromSite": "77"
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            # 检查是否是JSON
            if 'application/json' in response.headers.get('Content-Type', ''):
                data = response.json()
                
                # 提取二维码
                qr = data.get('data', {}).get('qrCode') or data.get('qrCode')
                self.token = data.get('data', {}).get('token') or data.get('token')
                
                if qr:
                    return qr
            
            return None
            
        except Exception as e:
            return None
    
    def _extract_from_login_page(self):
        """从登录页提取二维码"""
        try:
            url = "https://passport.goofish.com/mini_login.htm"
            params = {
                "appName": "xianyu",
                "appEntrance": "web",
                "isMobile": "true"
            }
            
            response = self.session.get(url, params=params, timeout=10)
            html = response.text
            
            # 提取二维码图片URL
            patterns = [
                r'<img[^>]+src=["\'](https?://[^"\']+qrcode[^"\']+)["\']',
                r'<img[^>]+src=["\'](https?://[^"\']+\.png)["\']',
                r'data:image/png;base64,[^"\']+',
                r'qrCode["\']?\s*[:=]\s*["\']([^"\']+)["\']'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    qr = matches[0]
                    # 补全URL
                    if qr.startswith('//'):
                        qr = 'https:' + qr
                    
                    # 尝试从HTML中提取token
                    token_match = re.search(r'token["\']?\s*[:=]\s*["\']([^"\']+)["\']', html)
                    if token_match:
                        self.token = token_match.group(1)
                    
                    return qr
            
            return None
            
        except Exception as e:
            return None
    
    def check_status(self):
        """检查扫码状态"""
        if not self.token:
            return None
        
        try:
            url = "https://passport.goofish.com/newlogin/qrcode/query.do"
            params = {
                "appName": "xianyu",
                "fromSite": "77",
                "token": self.token
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            # 尝试解析JSON
            try:
                data = response.json()
                
                # 检查登录成功
                if data.get('success') or data.get('code') == 0:
                    return {"status": "success", "token": data.get('token')}
                
                # 检查状态
                status = data.get('data', {}).get('status') or data.get('status')
                if status == 1:
                    return {"status": "scanned"}
                elif status == 3:
                    return {"status": "expired"}
                else:
                    return {"status": "waiting"}
                    
            except:
                return {"status": "waiting"}
                
        except Exception as e:
            return {"status": "error"}
    
    def confirm_login(self, login_token):
        """确认登录"""
        try:
            url = "https://passport.goofish.com/login_token/login.do"
            params = {
                "token": login_token,
                "subFlow": "DIALOG_CHECK_LOGIN_RPC",
                "nextCode": "0018",
                "bizScene": "qrcode",
                "confirm": "true"
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                self.cookies = self.session.cookies.get_dict()
                return True
            return False
            
        except Exception as e:
            return False
    
    def get_cookies(self):
        """获取cookies"""
        return self.cookies


def display_qr_simple(qr_data):
    """简单显示二维码（不依赖qrcode库）"""
    
    if not qr_data:
        return
    
    st.markdown("### 📱 请使用闲鱼APP扫描")
    
    # 判断数据类型并显示
    if qr_data.startswith('http'):
        # 如果是URL，显示链接和说明
        st.info("二维码URL已获取，请手动扫码：")
        st.code(qr_data, language="url")
        
        # 尝试显示图片（如果URL是图片）
        try:
            st.image(qr_data, use_container_width=True)
        except:
            pass
            
    elif qr_data.startswith('data:image'):
        # 如果是base64图片，直接显示
        st.image(qr_data, use_container_width=True)
        
    else:
        # 其他格式，显示文本
        st.text_area("二维码数据", qr_data, height=100)
        
        # 尝试生成ASCII二维码（不需要额外库）
        st.markdown("**或手动输入以下链接：**")
        st.code(qr_data, language="text")


def main():
    st.title("🐟 闲鱼扫码登录")
    st.markdown("使用闲鱼APP扫描二维码登录")
    
    # 初始化session
    if 'login' not in st.session_state:
        st.session_state.login = XianyuQRLogin()
        st.session_state.qr_data = None
        st.session_state.is_logged_in = False
        st.session_state.cookies = None
        st.session_state.token = None
    
    # 侧边栏
    with st.sidebar:
        st.header("📱 使用说明")
        st.markdown("""
        1. 点击下方按钮获取二维码
        2. 使用闲鱼APP扫描二维码
        3. 在手机上确认登录
        4. 自动获取Cookie
        """)
        
        st.header("💡 提示")
        st.info("""
        如果二维码无法显示，请：
        1. 点击"复制二维码链接"
        2. 在浏览器中打开链接
        3. 使用闲鱼APP扫码
        """)
        
        if st.button("🔄 重置", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # 主界面
    if not st.session_state.is_logged_in:
        
        # 获取二维码按钮
        if not st.session_state.qr_data:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📱 获取登录二维码", type="primary", use_container_width=True):
                    with st.spinner("正在获取二维码..."):
                        qr_data = st.session_state.login.get_qr_code()
                        
                        if qr_data:
                            st.session_state.qr_data = qr_data
                            st.success("✅ 二维码获取成功！")
                            st.rerun()
                        else:
                            st.error("❌ 获取二维码失败")
                            st.info("""
                            **可能的原因：**
                            - 闲鱼接口返回了HTML而不是JSON
                            - 需要先登录网页版获取Cookie
                            - IP被限制访问
                            
                            **建议：**
                            1. 在浏览器中访问 https://www.goofish.com
                            2. 手动登录一次
                            3. 然后使用本工具的Cookie导入功能
                            """)
        
        # 显示二维码
        if st.session_state.qr_data:
            display_qr_simple(st.session_state.qr_data)
            
            # 复制按钮
            st.button("📋 复制二维码链接", on_click=lambda: st.write("已复制"), use_container_width=True)
            
            # 状态显示
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            st.info("⏳ 等待扫码，请在手机上确认登录...")
            
            max_wait = 120
            start_time = time.time()
            
            while time.time() - start_time < max_wait and not st.session_state.is_logged_in:
                elapsed = int(time.time() - start_time)
                remaining = max_wait - elapsed
                progress = elapsed / max_wait
                
                progress_bar.progress(min(progress, 1.0))
                status_placeholder.text(f"等待中... {remaining}秒")
                
                result = st.session_state.login.check_status()
                
                if result:
                    if result.get("status") == "success":
                        status_placeholder.success("✅ 登录成功！正在获取Cookie...")
                        # 确认登录
                        login_token = result.get("token")
                        if login_token:
                            st.session_state.login.confirm_login(login_token)
                        st.session_state.cookies = st.session_state.login.get_cookies()
                        st.session_state.is_logged_in = True
                        time.sleep(1)
                        st.rerun()
                        break
                        
                    elif result.get("status") == "scanned":
                        status_placeholder.info("📱 已扫码！请在手机上确认...")
                        
                    elif result.get("status") == "expired":
                        status_placeholder.error("❌ 二维码已过期，请重新获取")
                        break
                
                time.sleep(2)
            
            if not st.session_state.is_logged_in:
                status_placeholder.error("⏰ 超时，请重试")
    
    # 登录成功
    if st.session_state.is_logged_in and st.session_state.cookies:
        st.balloons()
        st.success("### ✅ 登录成功！")
        
        # 显示Cookie
        with st.expander("📦 Cookie详情", expanded=True):
            cookies = st.session_state.cookies
            
            # 显示关键Cookie
            important = ['cna', 'cookie2', 't', 'tracknick', '_tb_token_', 'sgcookie']
            important_cookies = {}
            for key in important:
                if key in cookies:
                    value = cookies[key]
                    important_cookies[key] = value[:30] + "..." if len(value) > 30 else value
            
            if important_cookies:
                st.json(important_cookies)
            
            st.caption(f"共 {len(cookies)} 个Cookie")
        
        # 保存按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存Cookie到文件", use_container_width=True, type="primary"):
                with open("xianyu_cookies.json", "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2, ensure_ascii=False)
                st.success("✅ 已保存到 xianyu_cookies.json")
        
        with col2:
            if st.button("🔄 重新登录", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        
        # 使用示例
        with st.expander("📖 Python使用示例"):
            st.code("""
import requests
import json

# 加载cookie
with open('xianyu_cookies.json', 'r') as f:
    cookies = json.load(f)

# 使用cookie
session = requests.Session()
session.cookies.update(cookies)
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# 发起请求
response = session.get('https://www.goofish.com/')
print(f"状态码: {response.status_code}")
            """, language="python")


if __name__ == "__main__":
    main()
