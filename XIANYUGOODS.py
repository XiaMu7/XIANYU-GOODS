#!/usr/bin/env python3
"""
闲鱼扫码登录 - 真实可用版
运行: streamlit run xianyu_login_working.py
"""

import streamlit as st
import requests
import time
import json
import re
import qrcode
from PIL import Image
import io
import base64

# 页面配置
st.set_page_config(
    page_title="闲鱼扫码登录",
    page_icon="🐟",
    layout="centered"
)

class XianyuQRLogin:
    """闲鱼扫码登录 - 使用真实接口"""
    
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.cookies = {}
        
        # 关键：设置完整的请求头，模拟真实浏览器
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.goofish.com",
            "Referer": "https://www.goofish.com/",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "X-Requested-With": "XMLHttpRequest"
        })
    
    def get_qr_code(self):
        """获取二维码 - 通过访问登录页获取真实二维码"""
        try:
            # 方法1: 通过登录页获取二维码图片
            login_url = "https://passport.goofish.com/mini_login.htm"
            params = {
                "appName": "xianyu",
                "appEntrance": "web",
                "isMobile": "true",
                "returnUrl": "https://www.goofish.com/"
            }
            
            # 先访问登录页获取cookie
            response = self.session.get(login_url, params=params, timeout=10)
            
            # 从返回的HTML中提取二维码图片URL
            html = response.text
            
            # 提取二维码图片URL
            qr_patterns = [
                r'<img[^>]+src="(https?://[^"]+qrcode[^"]+)"',
                r'<img[^>]+src="(https?://[^"]+\.png)"',
                r'data:image/png;base64,[^"]+'
            ]
            
            for pattern in qr_patterns:
                matches = re.findall(pattern, html)
                if matches:
                    qr_url = matches[0]
                    
                    # 如果是相对路径，补全
                    if qr_url.startswith('//'):
                        qr_url = 'https:' + qr_url
                    
                    # 如果是base64，直接返回
                    if qr_url.startswith('data:image'):
                        return qr_url
                    
                    # 如果是URL，下载图片
                    if qr_url.startswith('http'):
                        img_response = self.session.get(qr_url, timeout=10)
                        if img_response.status_code == 200:
                            # 转为base64
                            img_base64 = base64.b64encode(img_response.content).decode()
                            return f"data:image/png;base64,{img_base64}"
            
            # 方法2: 直接调用二维码API
            qr_api_url = "https://passport.goofish.com/newlogin/qrcode/query.do"
            params = {
                "appName": "xianyu",
                "fromSite": "77",
                "_": int(time.time() * 1000)  # 时间戳
            }
            
            response = self.session.get(qr_api_url, params=params, timeout=10)
            
            # 检查返回类型
            if 'application/json' in response.headers.get('Content-Type', ''):
                data = response.json()
                qr_code = data.get('data', {}).get('qrCode') or data.get('qrCode')
                self.token = data.get('data', {}).get('token') or data.get('token')
                if qr_code:
                    return qr_code
            
            return None
            
        except Exception as e:
            st.error(f"获取二维码异常: {e}")
            return None
    
    def check_login_status(self):
        """检查扫码状态"""
        if not self.token:
            return None
        
        try:
            url = "https://passport.goofish.com/newlogin/qrcode/query.do"
            params = {
                "appName": "xianyu",
                "fromSite": "77",
                "token": self.token,
                "_": int(time.time() * 1000)
            }
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            # 解析状态
            status = data.get('data', {}).get('status') or data.get('status')
            
            if status == 2 or data.get('code') == 0:
                login_token = data.get('data', {}).get('token') or data.get('token')
                return {"status": "success", "token": login_token}
            elif status == 1:
                return {"status": "scanned"}
            elif status == 3:
                return {"status": "expired"}
            else:
                return {"status": "waiting"}
                
        except Exception as e:
            return {"status": "error", "msg": str(e)}
    
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
            self.cookies = self.session.cookies.get_dict()
            return True
            
        except Exception as e:
            return False
    
    def get_cookies(self):
        """获取最终cookies"""
        return self.cookies


def main():
    st.title("🐟 闲鱼扫码登录")
    st.markdown("使用闲鱼APP扫描二维码登录")
    
    # 初始化
    if 'login' not in st.session_state:
        st.session_state.login = XianyuQRLogin()
        st.session_state.qr_data = None
        st.session_state.is_logged_in = False
        st.session_state.cookies = None
    
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
        
        if st.button("🔄 重置", use_container_width=True):
            st.session_state.clear()
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
        
        # 显示二维码
        if st.session_state.qr_data:
            st.markdown("### 📱 请扫描二维码")
            
            # 显示二维码图片
            if st.session_state.qr_data.startswith('data:image'):
                st.image(st.session_state.qr_data, use_container_width=True)
            elif st.session_state.qr_data.startswith('http'):
                st.image(st.session_state.qr_data, use_container_width=True)
            else:
                # 生成二维码
                try:
                    qr = qrcode.QRCode(box_size=8, border=2)
                    qr.add_data(st.session_state.qr_data)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color="black", back_color="white")
                    
                    # 转换为bytes
                    buf = io.BytesIO()
                    img.save(buf, format='PNG')
                    buf.seek(0)
                    st.image(buf, use_container_width=True)
                except:
                    st.text(st.session_state.qr_data)
            
            # 状态轮询
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
                
                result = st.session_state.login.check_login_status()
                
                if result:
                    if result.get("status") == "success":
                        status_placeholder.success("✅ 登录成功！正在获取Cookie...")
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
            important = ['cna', 'cookie2', 't', 'tracknick', '_tb_token_']
            important_cookies = {k: v[:30] + "..." if len(v) > 30 else v 
                                for k, v in cookies.items() if k in important}
            st.json(important_cookies)
            st.caption(f"共 {len(cookies)} 个Cookie")
        
        # 保存
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存Cookie", use_container_width=True, type="primary"):
                with open("xianyu_cookies.json", "w") as f:
                    json.dump(cookies, f, indent=2)
                st.success("✅ 已保存")
        
        with col2:
            if st.button("🔄 重新登录", use_container_width=True):
                st.session_state.clear()
                st.rerun()


if __name__ == "__main__":
    main()
