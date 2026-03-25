#!/usr/bin/env python3
"""
闲鱼扫码登录 - Streamlit Web版 (无qrcode依赖)
运行: streamlit run xianyu_login.py
"""

import streamlit as st
import requests
import time
import json
import base64
import re
from datetime import datetime
import io

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
        padding: 20px;
        background: white;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    .status-box {
        padding: 12px;
        border-radius: 8px;
        margin: 10px 0;
        text-align: center;
        font-weight: 500;
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
    .qr-code-url {
        font-family: monospace;
        font-size: 12px;
        word-break: break-all;
        background: #f5f5f5;
        padding: 10px;
        border-radius: 5px;
        margin-top: 10px;
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
            
            with st.spinner("正在获取二维码..."):
                response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                st.error(f"请求失败: HTTP {response.status_code}")
                return None, None
            
            # 尝试解析JSON
            try:
                data = response.json()
                st.info(f"接口返回类型: JSON")
                
                # 查找二维码
                qr_content = self._find_value(data, ['qrCode', 'qrcode', 'code', 'content', 'url'])
                token = self._find_value(data, ['token', 'qrId', 'id', 't'])
                
                if qr_content:
                    self.token = token
                    return qr_content, token
                    
            except:
                # 不是JSON，可能是HTML
                st.info("返回的是HTML页面，尝试从中提取二维码...")
                qr_content = self._extract_qr_from_html(response.text)
                if qr_content:
                    return qr_content, None
            
            return None, None
            
        except Exception as e:
            st.error(f"获取二维码失败: {str(e)}")
            return None, None
    
    def _find_value(self, obj, keys, depth=0):
        """递归查找指定键的值"""
        if depth > 5:
            return None
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.lower() in [k.lower() for k in keys]:
                    if isinstance(value, str) and len(value) > 10:
                        return value
                result = self._find_value(value, keys, depth + 1)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_value(item, keys, depth + 1)
                if result:
                    return result
        
        return None
    
    def _extract_qr_from_html(self, html):
        """从HTML中提取二维码"""
        # 提取图片URL
        img_patterns = [
            r'<img[^>]+src=["\']([^"\']+qrcode[^"\']+)["\']',
            r'<img[^>]+src=["\']([^"\']+\.png)["\']',
            r'data:image/[^;]+;base64,[^"\']+',
        ]
        
        for pattern in img_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                qr_url = matches[0]
                if qr_url.startswith('//'):
                    qr_url = 'https:' + qr_url
                return qr_url
        
        # 提取JavaScript中的二维码数据
        js_pattern = r'qrCode["\']?\s*:\s*["\']([^"\']+)["\']'
        match = re.search(js_pattern, html)
        if match:
            return match.group(1)
        
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
            
            # 根据返回判断状态
            if data.get("success") or data.get("code") == "0":
                login_token = data.get("token") or data.get("data", {}).get("token")
                return {"status": "success", "token": login_token}
            
            status = data.get("status") or data.get("data", {}).get("status")
            
            if status == "SCANED" or status == 1:
                return {"status": "scanned"}
            elif status == "EXPIRED" or status == 3:
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
            return False
    
    def get_final_cookies(self):
        """获取最终cookie"""
        try:
            response = self.session.get("https://www.goofish.com/", timeout=10)
            self.cookies = self.session.cookies.get_dict()
            return self.cookies
        except:
            return self.cookies


def display_qr_data(qr_data):
    """显示二维码数据"""
    if not qr_data:
        return
    
    st.markdown('<div class="qr-container">', unsafe_allow_html=True)
    
    # 判断数据类型
    if qr_data.startswith('http'):
        # 如果是URL，显示链接和图片
        st.image(qr_data, use_container_width=True)
        st.caption("👆 使用闲鱼APP扫描上方二维码")
        
        with st.expander("查看二维码链接"):
            st.code(qr_data, language="url")
            
    elif qr_data.startswith('data:image'):
        # 如果是base64图片，直接显示
        try:
            # 提取base64数据
            img_data = re.sub('^data:image/.+;base64,', '', qr_data)
            img_bytes = base64.b64decode(img_data)
            st.image(img_bytes, use_container_width=True)
            st.caption("👆 使用闲鱼APP扫描上方二维码")
        except Exception as e:
            st.warning(f"无法显示图片: {e}")
            st.text_area("二维码数据", qr_data[:500], height=100)
            
    else:
        # 其他格式，显示文本
        st.warning("二维码数据格式未知，请手动扫码")
        st.text_area("二维码数据", qr_data, height=100)
    
    st.markdown('</div>', unsafe_allow_html=True)


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
        st.session_state.stop_polling = False
        st.session_state.login_result = None
    
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
        
        if st.button("🔄 重新获取二维码", use_container_width=True):
            st.session_state.qr_data = None
            st.session_state.token = None
            st.session_state.is_logged_in = False
            st.session_state.login_result = None
            st.rerun()
    
    # 主内容区
    if not st.session_state.is_logged_in:
        # 获取二维码按钮
        if not st.session_state.qr_data:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📱 获取登录二维码", type="primary", use_container_width=True):
                    qr_data, token = st.session_state.login_instance.get_qr_code()
                    if qr_data:
                        st.session_state.qr_data = qr_data
                        st.session_state.token = token
                        st.success("✓ 二维码获取成功！")
                        st.rerun()
                    else:
                        st.error("❌ 获取二维码失败")
                        st.info("""
                        **可能的原因：**
                        - 网络连接问题
                        - 需要先访问闲鱼首页
                        - IP被限制
                        
                        **建议：**
                        1. 检查网络连接
                        2. 稍后重试
                        3. 使用VPN或更换网络
                        """)
        
        # 显示二维码
        if st.session_state.qr_data:
            display_qr_data(st.session_state.qr_data)
            
            # 状态显示区域
            status_placeholder = st.empty()
            
            # 开始轮询
            if not st.session_state.stop_polling:
                progress_bar = st.progress(0)
                
                max_wait = 120
                start_time = time.time()
                
                while time.time() - start_time < max_wait and not st.session_state.is_logged_in:
                    elapsed = int(time.time() - start_time)
                    remaining = max_wait - elapsed
                    
                    # 更新进度条
                    progress_bar.progress(elapsed / max_wait)
                    
                    # 检查登录状态
                    result = st.session_state.login_instance.check_login_status()
                    
                    if result:
                        if result.get("status") == "success":
                            login_token = result.get("token")
                            if login_token:
                                st.session_state.login_instance.confirm_login(login_token)
                            
                            st.session_state.login_instance.get_final_cookies()
                            st.session_state.is_logged_in = True
                            st.session_state.login_result = result
                            
                            status_placeholder.markdown(
                                '<div class="status-box success">✅ 登录成功！正在获取Cookie...</div>',
                                unsafe_allow_html=True
                            )
                            time.sleep(1)
                            st.rerun()
                            break
                            
                        elif result.get("status") == "scanned":
                            status_placeholder.markdown(
                                '<div class="status-box info">📱 已扫码！请在手机上确认登录...</div>',
                                unsafe_allow_html=True
                            )
                            
                        elif result.get("status") == "expired":
                            status_placeholder.markdown(
                                '<div class="status-box warning">⏰ 二维码已过期</div>',
                                unsafe_allow_html=True
                            )
                            if auto_refresh:
                                with st.spinner("正在刷新二维码..."):
                                    time.sleep(1)
                                    qr_data, token = st.session_state.login_instance.get_qr_code()
                                    if qr_data:
                                        st.session_state.qr_data = qr_data
                                        st.session_state.token = token
                                        start_time = time.time()
                                        st.rerun()
                            break
                        else:
                            status_placeholder.markdown(
                                f'<div class="status-box info">⏳ 等待扫码... {remaining}秒</div>',
                                unsafe_allow_html=True
                            )
                    
                    time.sleep(2)
                
                if not st.session_state.is_logged_in:
                    status_placeholder.markdown(
                        '<div class="status-box error">⏰ 超时，请重新获取二维码</div>',
                        unsafe_allow_html=True
                    )
    
    # 登录成功后的显示
    if st.session_state.is_logged_in:
        st.balloons()
        st.success("### ✅ 登录成功！")
        
        # 显示Cookie信息
        with st.expander("📦 查看Cookie详情", expanded=True):
            cookies = st.session_state.login_instance.cookies
            if cookies:
                # 只显示关键cookie
                important_keys = ['cna', 'cookie2', 't', 'tracknick', '_tb_token_', 'sgcookie']
                important_cookies = {k: v for k, v in cookies.items() if k in important_keys}
                
                if important_cookies:
                    st.json(important_cookies)
                
                st.text(f"共 {len(cookies)} 个Cookie")
        
        # 保存Cookie按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存Cookie到文件", use_container_width=True, type="primary"):
                with open("xianyu_cookies.json", "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2, ensure_ascii=False)
                st.success("✅ 已保存到 xianyu_cookies.json")
        
        with col2:
            if st.button("🔄 重新登录", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
        
        # 使用示例
        with st.expander("📖 Python使用示例"):
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
