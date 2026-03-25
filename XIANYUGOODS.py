#!/usr/bin/env python3
"""
闲鱼扫码登录 - 完整浏览器模拟版
运行: streamlit run xianyu_login.py
"""

import streamlit as st
import requests
import time
import json
import re
import base64
from datetime import datetime

# 页面配置
st.set_page_config(
    page_title="闲鱼扫码登录",
    page_icon="🐟",
    layout="centered"
)

# 自定义CSS
st.markdown("""
<style>
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
    .success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .info { background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
    .warning { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
</style>
""", unsafe_allow_html=True)

class XianyuQRLogin:
    """闲鱼扫码登录类 - 完整浏览器模拟"""
    
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://passport.goofish.com"
        self.token = None
        self.qr_code_url = None
        self.cookies = {}
        
        # 完整的浏览器请求头（关键！）
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
        """初始化会话 - 先访问首页获取cookie"""
        try:
            # 1. 先访问闲鱼首页建立会话
            print("正在初始化会话...")
            resp = self.session.get("https://www.goofish.com/", timeout=10)
            
            # 2. 访问登录页
            login_page_url = "https://passport.goofish.com/mini_login.htm?appName=xianyu&appEntrance=web&isMobile=true"
            resp = self.session.get(login_page_url, timeout=10)
            
            # 从返回的HTML中提取二维码接口需要的参数
            html = resp.text
            
            # 提取token或sessionId
            token_match = re.search(r'token["\']?\s*[:=]\s*["\']([^"\']+)["\']', html)
            if token_match:
                self.token = token_match.group(1)
                print(f"找到token: {self.token[:20]}...")
            
            # 提取其他可能需要的参数
            csrf_match = re.search(r'csrf["\']?\s*[:=]\s*["\']([^"\']+)["\']', html)
            if csrf_match:
                self.session.headers.update({"_csrf": csrf_match.group(1)})
            
            return True
            
        except Exception as e:
            print(f"初始化会话失败: {e}")
            return False
    
    def get_qr_code(self):
        """获取登录二维码 - 使用正确的接口"""
        
        # 先初始化会话
        if not self.init_session():
            return None, None
        
        try:
            # 方法1: 尝试正确的二维码接口
            url = "https://passport.goofish.com/newlogin/qrcode/query.do"
            params = {
                "appName": "xianyu",
                "fromSite": "77"
            }
            
            # 添加必要的cookie和header
            self.session.headers.update({
                "Accept": "application/json, text/plain, */*",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://passport.goofish.com/mini_login.htm"
            })
            
            response = self.session.get(url, params=params, timeout=10)
            
            # 检查返回内容
            content_type = response.headers.get('Content-Type', '')
            
            if 'application/json' in content_type:
                # 返回JSON，正常解析
                data = response.json()
                qr_content = self._extract_qr_from_json(data)
                token = self._extract_token_from_json(data)
                
                if qr_content:
                    return qr_content, token
            
            # 方法2: 从HTML中提取二维码图片URL
            elif 'text/html' in content_type:
                return self._get_qr_from_html_page()
            
            return None, None
            
        except Exception as e:
            st.error(f"获取二维码错误: {str(e)}")
            return None, None
    
    def _get_qr_from_html_page(self):
        """从HTML登录页直接获取二维码图片"""
        try:
            # 访问登录页，直接获取二维码图片
            login_url = "https://passport.goofish.com/mini_login.htm"
            params = {
                "appName": "xianyu",
                "appEntrance": "web",
                "isMobile": "true",
                "returnUrl": "https://www.goofish.com/"
            }
            
            self.session.headers.update({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Referer": "https://www.goofish.com/"
            })
            
            response = self.session.get(login_url, params=params, timeout=10)
            html = response.text
            
            # 提取二维码图片URL
            # 常见的二维码图片URL模式
            patterns = [
                r'<img[^>]+src=["\'](https?://[^"\']+qrcode[^"\']+)["\']',
                r'<img[^>]+src=["\'](https?://[^"\']+\.png)["\']',
                r'qrcode["\']?\s*[:=]\s*["\'](https?://[^"\']+)["\']',
                r'data:image/png;base64,[^"\']+'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    qr_url = matches[0]
                    # 补全URL
                    if qr_url.startswith('//'):
                        qr_url = 'https:' + qr_url
                    return qr_url, None
            
            # 如果没找到，保存HTML供调试
            with open("debug_login_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            st.info("已保存登录页HTML到 debug_login_page.html，请查看")
            
            return None, None
            
        except Exception as e:
            st.error(f"从HTML获取二维码失败: {e}")
            return None, None
    
    def _extract_qr_from_json(self, data):
        """从JSON中提取二维码"""
        if isinstance(data, dict):
            # 直接字段
            for key in ['qrCode', 'qrcode', 'code', 'content', 'url', 'image']:
                if key in data:
                    return data[key]
            # 嵌套查找
            if 'data' in data and isinstance(data['data'], dict):
                for key in ['qrCode', 'qrcode', 'code', 'content', 'url']:
                    if key in data['data']:
                        return data['data'][key]
        return None
    
    def _extract_token_from_json(self, data):
        """从JSON中提取token"""
        if isinstance(data, dict):
            for key in ['token', 'qrId', 'id', 'ticket']:
                if key in data:
                    return data[key]
            if 'data' in data and isinstance(data['data'], dict):
                for key in ['token', 'qrId', 'id']:
                    if key in data['data']:
                        return data['data'][key]
        return None
    
    def check_login_status(self):
        """检查登录状态"""
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
            
            if response.status_code != 200:
                return {"status": "error"}
            
            try:
                data = response.json()
            except:
                return {"status": "waiting"}
            
            # 判断状态
            if data.get('success') or data.get('code') == 0:
                login_token = data.get('token') or data.get('data', {}).get('token')
                return {"status": "success", "token": login_token}
            
            status = data.get('status') or data.get('data', {}).get('status')
            
            if status == 1 or status == 'SCANED':
                return {"status": "scanned"}
            elif status == 3 or status == 'EXPIRED':
                return {"status": "expired"}
            else:
                return {"status": "waiting"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
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


def main():
    st.title("🐟 闲鱼扫码登录")
    st.markdown("使用闲鱼APP扫描二维码登录")
    
    # 初始化
    if 'login' not in st.session_state:
        st.session_state.login = XianyuQRLogin()
        st.session_state.qr_data = None
        st.session_state.is_logged_in = False
        st.session_state.status = None
    
    # 侧边栏说明
    with st.sidebar:
        st.header("📱 使用说明")
        st.markdown("""
        1. 点击下方按钮获取二维码
        2. 打开闲鱼APP
        3. 点击右上角"扫一扫"
        4. 扫描二维码
        5. 在手机上确认登录
        """)
        
        st.header("⚠️ 注意事项")
        st.info("""
        - 二维码有效期约2分钟
        - 过期后需重新获取
        - 请确保网络畅通
        """)
        
        if st.button("🔄 重新获取", use_container_width=True):
            st.session_state.qr_data = None
            st.session_state.is_logged_in = False
            st.rerun()
    
    # 主界面
    if not st.session_state.is_logged_in:
        # 获取二维码按钮
        if not st.session_state.qr_data:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📱 获取登录二维码", type="primary", use_container_width=True):
                    with st.spinner("正在获取二维码..."):
                        qr_data, token = st.session_state.login.get_qr_code()
                        
                        if qr_data:
                            st.session_state.qr_data = qr_data
                            if token:
                                st.session_state.login.token = token
                            st.success("✅ 二维码获取成功！")
                            st.rerun()
                        else:
                            st.error("❌ 获取二维码失败")
                            st.info("""
                            **可能的原因：**
                            1. 闲鱼接口限制，需要先登录网页版
                            2. IP被限制访问
                            3. 网络代理问题
                            
                            **建议尝试：**
                            1. 在浏览器中先登录 https://www.goofish.com
                            2. 更换网络环境（如使用手机热点）
                            3. 等待几分钟后重试
                            """)
        
        # 显示二维码
        if st.session_state.qr_data:
            st.markdown('<div class="qr-container">', unsafe_allow_html=True)
            
            qr_data = st.session_state.qr_data
            
            # 显示二维码
            if qr_data.startswith('http'):
                st.image(qr_data, use_container_width=True)
                st.caption("👆 使用闲鱼APP扫描上方二维码")
            elif qr_data.startswith('data:image'):
                try:
                    img_data = re.sub('^data:image/.+;base64,', '', qr_data)
                    st.image(base64.b64decode(img_data), use_container_width=True)
                except:
                    st.text("二维码数据: " + qr_data[:100])
            else:
                st.text("二维码数据: " + qr_data[:100])
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # 状态轮询
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            max_wait = 120
            start_time = time.time()
            
            while time.time() - start_time < max_wait and not st.session_state.is_logged_in:
                elapsed = int(time.time() - start_time)
                remaining = max_wait - elapsed
                
                progress_bar.progress(elapsed / max_wait)
                
                result = st.session_state.login.check_login_status()
                
                if result:
                    if result.get("status") == "success":
                        login_token = result.get("token")
                        if login_token:
                            st.session_state.login.confirm_login(login_token)
                        st.session_state.is_logged_in = True
                        status_placeholder.markdown(
                            '<div class="status-box success">✅ 登录成功！</div>',
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
                            '<div class="status-box warning">⏰ 二维码已过期，请重新获取</div>',
                            unsafe_allow_html=True
                        )
                        break
                    else:
                        status_placeholder.markdown(
                            f'<div class="status-box info">⏳ 等待扫码... {remaining}秒</div>',
                            unsafe_allow_html=True
                        )
                
                time.sleep(2)
    
    # 登录成功
    if st.session_state.is_logged_in:
        st.balloons()
        st.success("### ✅ 登录成功！")
        
        with st.expander("📦 Cookie信息", expanded=True):
            cookies = st.session_state.login.cookies
            if cookies:
                st.json({k: v for k, v in list(cookies.items())[:10]})
        
        if st.button("💾 保存Cookie", use_container_width=True, type="primary"):
            with open("xianyu_cookies.json", "w") as f:
                json.dump(cookies, f, indent=2)
            st.success("已保存到 xianyu_cookies.json")


if __name__ == "__main__":
    main()
