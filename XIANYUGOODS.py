#!/usr/bin/env python3
"""
闲鱼扫码登录 - 使用正确接口版
运行: streamlit run xianyu_login_fixed.py
"""

import streamlit as st
import requests
import time
import json
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
    """闲鱼扫码登录 - 使用正确的接口"""
    
    def __init__(self):
        self.session = requests.Session()
        self.token = None
        self.cookies = {}
        
        # 关键：模拟浏览器环境
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.goofish.com",
            "Referer": "https://www.goofish.com/",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        })
    
    def get_qr_code(self):
        """获取二维码 - 使用正确的参数"""
        try:
            # 先访问主页获取必要的cookie
            self.session.get("https://www.goofish.com/")
            
            # 获取二维码
            url = "https://passport.goofish.com/newlogin/qrcode/query.do"
            params = {
                "appName": "xianyu",
                "fromSite": "77",
                "_input_charset": "utf-8"
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            # 打印调试信息
            st.text(f"响应状态: {response.status_code}")
            st.text(f"Content-Type: {response.headers.get('Content-Type')}")
            
            # 尝试解析JSON
            try:
                data = response.json()
                st.json(data)  # 显示返回数据，帮助调试
                
                # 提取二维码
                qr_code = data.get("data", {}).get("qrCode") or data.get("qrCode")
                self.token = data.get("data", {}).get("token") or data.get("token")
                
                if qr_code:
                    return qr_code
                else:
                    st.error("未找到二维码数据")
                    return None
                    
            except Exception as e:
                st.error(f"JSON解析失败: {e}")
                st.text(f"原始响应: {response.text[:500]}")
                return None
                
        except Exception as e:
            st.error(f"请求失败: {e}")
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
            data = response.json()
            
            # 返回状态
            return {
                "code": data.get("code"),
                "data": data.get("data", {}),
                "raw": data
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_cookies(self):
        """获取最终cookies"""
        return self.session.cookies.get_dict()


def generate_qr_image(qr_data):
    """生成二维码图片"""
    qr = qrcode.QRCode(
        version=1,
        box_size=8,
        border=2
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    return img


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
        2. 打开闲鱼APP扫码
        3. 在手机上确认登录
        4. 自动获取Cookie
        """)
        
        if st.button("🔄 重置", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # 主界面
    if not st.session_state.is_logged_in:
        # 获取二维码按钮
        if not st.session_state.qr_data:
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
                        **调试信息：**
                        请查看上方显示的API返回数据，可能的原因：
                        1. 接口需要额外的token参数
                        2. IP被限制
                        3. 需要先访问其他页面
                        """)
        
        # 显示二维码
        if st.session_state.qr_data:
            st.markdown("### 📱 请扫描二维码")
            
            # 生成并显示二维码
            img = generate_qr_image(st.session_state.qr_data)
            st.image(img, use_container_width=True)
            
            # 显示二维码文本
            with st.expander("查看二维码文本"):
                st.code(st.session_state.qr_data)
            
            # 状态轮询
            status_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            st.info("⏳ 等待扫码，请在手机上确认登录...")
            
            max_wait = 120
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                elapsed = int(time.time() - start_time)
                progress = elapsed / max_wait
                progress_bar.progress(min(progress, 1.0))
                
                status_placeholder.text(f"等待中... {max_wait - elapsed}秒")
                
                result = st.session_state.login.check_status()
                
                if result and result.get("code") == 0:
                    status_placeholder.success("✅ 登录成功！正在获取Cookie...")
                    st.session_state.cookies = st.session_state.login.get_cookies()
                    st.session_state.is_logged_in = True
                    time.sleep(1)
                    st.rerun()
                    break
                elif result and result.get("data", {}).get("status") == 1:
                    status_placeholder.info("📱 已扫码！请在手机上确认...")
                elif result and result.get("data", {}).get("status") == 3:
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
            # 只显示关键Cookie
            important = ['cna', 'cookie2', 't', 'tracknick', '_tb_token_']
            important_cookies = {k: v for k, v in cookies.items() if k in important}
            st.json(important_cookies)
            st.caption(f"共 {len(cookies)} 个Cookie")
        
        # 保存Cookie
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存Cookie到文件", use_container_width=True, type="primary"):
                with open("xianyu_cookies.json", "w") as f:
                    json.dump(cookies, f, indent=2)
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

# 发起请求
response = session.get('https://www.goofish.com/')
print(f"状态码: {response.status_code}")
            """, language="python")


if __name__ == "__main__":
    main()
