#!/usr/bin/env python3
"""
闲鱼扫码登录 - Streamlit Web版
运行: streamlit run xianyu_login_streamlit.py
"""

import streamlit as st
import requests
import time
import json
import qrcode
from PIL import Image
import io
import base64
from datetime import datetime, timedelta
import threading

# 页面配置
st.set_page_config(
    page_title="闲鱼扫码登录",
    page_icon="🐟",
    layout="centered"
)

# 自定义CSS
st.markdown("""
<style>
    .login-container {
        max-width: 500px;
        margin: 0 auto;
        padding: 20px;
    }
    .qr-container {
        display: flex;
        justify-content: center;
        margin: 20px 0;
    }
    .status-box {
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .success {
        background-color: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
    }
    .info {
        background-color: #d1ecf1;
        color: #0c5460;
        border: 1px solid #bee5eb;
    }
    .warning {
        background-color: #fff3cd;
        color: #856404;
        border: 1px solid #ffeeba;
    }
    .error {
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
    }
</style>
""", unsafe_allow_html=True)

class XianyuQRLogin:
    """闲鱼扫码登录类"""
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://passport.goofish.com"
        self.token = None
        self.is_logged_in = False
        self.qr_data = None
        self.cookies = {}
        
        # 设置请求头
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.goofish.com/",
            "Origin": "https://www.goofish.com"
        })
    
    def get_qr_code(self):
        """获取登录二维码"""
        try:
            url = f"{self.base_url}/newlogin/qrcode/query.do"
            params = {
                "appName": "xianyu",
                "fromSite": "77"
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return None, None
            
            # 尝试解析JSON
            try:
                data = response.json()
            except:
                # 如果返回的不是JSON，尝试从HTML中提取
                return self._extract_qr_from_html(response.text)
            
            # 查找二维码和token
            qr_content = self._find_qr_content(data)
            token = self._find_token(data)
            
            if qr_content:
                self.token = token
                return qr_content, token
            
            return None, None
            
        except Exception as e:
            st.error(f"获取二维码失败: {e}")
            return None, None
    
    def _extract_qr_from_html(self, html):
        """从HTML中提取二维码信息"""
        import re
        
        # 尝试提取二维码图片URL
        qr_patterns = [
            r'<img[^>]+src=["\']([^"\']+qrcode[^"\']+)["\']',
            r'<img[^>]+src=["\']([^"\']+\.png)["\']',
            r'qrCode["\']?\s*:\s*["\']([^"\']+)["\']',
        ]
        
        for pattern in qr_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                qr_url = match.group(1)
                if not qr_url.startswith('http'):
                    qr_url = 'https:' + qr_url if qr_url.startswith('//') else qr_url
                return qr_url, None
        
        return None, None
    
    def _find_qr_content(self, data, depth=0):
        """递归查找二维码内容"""
        if depth > 5:
            return None
        
        if isinstance(data, dict):
            for key, value in data.items():
                if 'qr' in key.lower() or 'code' in key.lower():
                    if isinstance(value, str) and len(value) > 50:
                        return value
                result = self._find_qr_content(value, depth + 1)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_qr_content(item, depth + 1)
                if result:
                    return result
        
        return None
    
    def _find_token(self, data):
        """查找token"""
        if isinstance(data, dict):
            for key, value in data.items():
                if 'token' in key.lower() or 'qr' in key.lower():
                    if isinstance(value, str) and len(value) > 10:
                        return value
                result = self._find_token(value)
                if result:
                    return result
        return None
    
    def check_login_status(self):
        """检查登录状态"""
        if not self.token:
            return None
        
        try:
            url = f"{self.base_url}/newlogin/qrcode/query.do"
            params = {
                "appName": "xianyu",
                "fromSite": "77",
                "token": self.token
            }
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            # 根据状态码判断
            status = data.get("data", {}).get("status") or data.get("status")
            
            if status == 2 or data.get("success") or data.get("code") == "0":
                login_token = data.get("data", {}).get("token") or data.get("token")
                return {"status": "success", "token": login_token}
            elif status == 1:
                return {"status": "scanned"}
            elif status == 3 or data.get("expired"):
                return {"status": "expired"}
            else:
                return {"status": "waiting"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def confirm_login(self, login_token):
        """确认登录"""
        try:
            url = f"{self.base_url}/login_token/login.do"
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
            st.error(f"确认登录失败: {e}")
            return False
    
    def get_final_cookies(self):
        """获取最终cookie"""
        try:
            response = self.session.get("https://www.goofish.com/", timeout=10)
            self.cookies = self.session.cookies.get_dict()
            return self.cookies
        except:
            return self.cookies


def generate_qr_image(qr_data):
    """生成二维码图片"""
    try:
        if qr_data.startswith('http'):
            # 如果是URL，生成二维码
            qr = qrcode.QRCode(box_size=4, border=2)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            return img
        elif qr_data.startswith('data:image'):
            # 如果是base64，直接解码
            import base64
            import re
            img_data = re.sub('^data:image/.+;base64,', '', qr_data)
            img_bytes = base64.b64decode(img_data)
            img = Image.open(io.BytesIO(img_bytes))
            return img
        else:
            # 尝试作为URL处理
            qr = qrcode.QRCode(box_size=4, border=2)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            return img
    except Exception as e:
        st.error(f"生成二维码失败: {e}")
        return None


def main():
    """主函数"""
    st.title("🐟 闲鱼扫码登录")
    st.markdown("使用闲鱼APP扫描二维码登录")
    
    # 初始化session state
    if 'login_instance' not in st.session_state:
        st.session_state.login_instance = XianyuQRLogin()
        st.session_state.is_logged_in = False
        st.session_state.qr_data = None
        st.session_state.token = None
        st.session_state.status = None
        st.session_state.stop_polling = False
    
    # 侧边栏
    with st.sidebar:
        st.header("📱 使用说明")
        st.markdown("""
        1. 点击下方按钮获取二维码
        2. 打开闲鱼APP
        3. 点击右上角"扫一扫"
        4. 扫描二维码
        5. 在手机上确认登录
        """)
        
        st.header("⚙️ 设置")
        auto_refresh = st.checkbox("自动刷新过期二维码", value=True)
        
        if st.button("🔄 重新获取二维码"):
            st.session_state.qr_data = None
            st.session_state.token = None
            st.session_state.is_logged_in = False
            st.rerun()
    
    # 主内容区
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # 获取二维码按钮
        if not st.session_state.qr_data and not st.session_state.is_logged_in:
            if st.button("📱 获取登录二维码", type="primary", use_container_width=True):
                with st.spinner("正在获取二维码..."):
                    qr_data, token = st.session_state.login_instance.get_qr_code()
                    if qr_data:
                        st.session_state.qr_data = qr_data
                        st.session_state.token = token
                        st.success("✓ 二维码获取成功！")
                        st.rerun()
                    else:
                        st.error("获取二维码失败，请重试")
        
        # 显示二维码
        if st.session_state.qr_data and not st.session_state.is_logged_in:
            st.markdown('<div class="qr-container">', unsafe_allow_html=True)
            
            img = generate_qr_image(st.session_state.qr_data)
            if img:
                st.image(img, caption="请使用闲鱼APP扫码", use_container_width=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # 状态显示区域
            status_placeholder = st.empty()
            
            # 开始轮询
            if not st.session_state.stop_polling:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                max_wait = 120
                start_time = time.time()
                
                while time.time() - start_time < max_wait and not st.session_state.is_logged_in:
                    elapsed = int(time.time() - start_time)
                    remaining = max_wait - elapsed
                    
                    # 更新进度条
                    progress = elapsed / max_wait
                    progress_bar.progress(progress)
                    
                    # 检查登录状态
                    result = st.session_state.login_instance.check_login_status()
                    
                    if result:
                        if result.get("status") == "success":
                            # 登录成功
                            login_token = result.get("token")
                            if login_token:
                                st.session_state.login_instance.confirm_login(login_token)
                            
                            st.session_state.login_instance.get_final_cookies()
                            st.session_state.is_logged_in = True
                            st.session_state.stop_polling = True
                            
                            status_placeholder.markdown(
                                '<div class="status-box success">✅ 登录成功！正在获取Cookie...</div>',
                                unsafe_allow_html=True
                            )
                            break
                            
                        elif result.get("status") == "scanned":
                            status_placeholder.markdown(
                                '<div class="status-box info">📱 已扫码！请在手机上确认登录...</div>',
                                unsafe_allow_html=True
                            )
                            status_text.text(f"等待确认... {remaining}秒")
                            
                        elif result.get("status") == "expired":
                            status_placeholder.markdown(
                                '<div class="status-box warning">⏰ 二维码已过期</div>',
                                unsafe_allow_html=True
                            )
                            if auto_refresh:
                                status_text.text("正在刷新二维码...")
                                time.sleep(1)
                                qr_data, token = st.session_state.login_instance.get_qr_code()
                                if qr_data:
                                    st.session_state.qr_data = qr_data
                                    st.session_state.token = token
                                    start_time = time.time()
                                    st.rerun()
                            break
                            
                        else:
                            status_text.text(f"等待扫码... {remaining}秒")
                    
                    time.sleep(2)
                
                if not st.session_state.is_logged_in:
                    status_placeholder.markdown(
                        '<div class="status-box error">⏰ 超时，请重新获取二维码</div>',
                        unsafe_allow_html=True
                    )
    
    # 登录成功后的显示
    if st.session_state.is_logged_in:
        st.success("### ✅ 登录成功！")
        
        # 显示Cookie信息
        with st.expander("查看Cookie详情"):
            cookies = st.session_state.login_instance.cookies
            if cookies:
                st.json(cookies)
        
        # 保存Cookie按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存Cookie到文件", use_container_width=True):
                with open("xianyu_cookies.json", "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2, ensure_ascii=False)
                st.success("已保存到 xianyu_cookies.json")
        
        with col2:
            if st.button("🔄 重新登录", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        
        # 使用示例
        with st.expander("📖 使用示例"):
            st.code("""
import requests
import json

# 加载cookie
with open('xianyu_cookies.json', 'r') as f:
    cookies = json.load(f)

# 使用cookie发起请求
session = requests.Session()
session.cookies.update(cookies)

# 访问需要登录的页面
response = session.get('https://www.goofish.com/')
print(response.status_code)
            """, language="python")


if __name__ == "__main__":
    main()
