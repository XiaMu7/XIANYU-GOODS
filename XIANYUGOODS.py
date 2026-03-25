#!/usr/bin/env python3
"""
闲鱼扫码登录 - Streamlit + Selenium 版
运行: streamlit run xianyu_login_selenium.py
"""

import streamlit as st
import time
import json
import os
import base64
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import threading
import tempfile

# 页面配置
st.set_page_config(
    page_title="闲鱼扫码登录",
    page_icon="🐟",
    layout="centered"
)

class XianyuSeleniumLogin:
    """使用Selenium获取闲鱼二维码"""
    
    def __init__(self):
        self.driver = None
        self.qr_image_base64 = None
        self.qr_url = None
        self.cookies = {}
        self.is_logged_in = False
        
    def setup_driver(self):
        """配置Chrome驱动"""
        chrome_options = Options()
        
        # 无头模式（后台运行，不显示浏览器窗口）
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # 模拟真实浏览器
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 用户代理
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 创建驱动
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # 隐藏webdriver特征
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        
        return self.driver
    
    def get_qr_code(self):
        """获取二维码"""
        try:
            # 启动浏览器
            if not self.driver:
                self.setup_driver()
            
            # 访问登录页
            login_url = "https://passport.goofish.com/mini_login.htm?appName=xianyu&appEntrance=web&isMobile=true"
            self.driver.get(login_url)
            
            # 等待页面加载
            time.sleep(3)
            
            # 查找二维码元素
            qr_selectors = [
                "img[class*='qrcode']",
                "img[alt*='二维码']",
                "img[src*='qrcode']",
                "div[class*='qr'] img",
                ".qr-code img",
                "#qrcode img",
                "canvas[id*='qrcode']"
            ]
            
            qr_element = None
            for selector in qr_selectors:
                try:
                    qr_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if qr_element:
                        print(f"找到二维码: {selector}")
                        break
                except:
                    continue
            
            if qr_element:
                # 获取二维码图片
                qr_src = qr_element.get_attribute('src')
                if qr_src:
                    if qr_src.startswith('data:image'):
                        self.qr_image_base64 = qr_src
                    else:
                        self.qr_url = qr_src
                
                # 保存截图备用
                screenshot = self.driver.find_element(By.TAG_NAME, 'body').screenshot_as_png
                with open('qrcode_screenshot.png', 'wb') as f:
                    f.write(screenshot)
                
                return True
            
            # 如果找不到图片元素，尝试截图整个登录区域
            return self._capture_qr_from_screen()
            
        except Exception as e:
            print(f"获取二维码失败: {e}")
            return False
    
    def _capture_qr_from_screen(self):
        """从屏幕截图中裁剪二维码区域"""
        try:
            from PIL import Image
            import io
            
            # 截取整个页面
            screenshot = self.driver.get_screenshot_as_png()
            img = Image.open(io.BytesIO(screenshot))
            
            # 保存完整截图供用户手动查看
            img.save("full_page.png")
            self.qr_image_base64 = "full_page.png"  # 标记为文件路径
            
            return True
        except Exception as e:
            print(f"截图失败: {e}")
            return False
    
    def wait_for_login(self, timeout=120):
        """等待用户扫码登录"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 检查当前URL
            current_url = self.driver.current_url
            
            # 如果跳转到闲鱼主页，说明登录成功
            if "goofish.com" in current_url and "login" not in current_url and "passport" not in current_url:
                self.is_logged_in = True
                # 获取cookies
                for cookie in self.driver.get_cookies():
                    self.cookies[cookie['name']] = cookie['value']
                return True
            
            # 检查页面是否有成功提示
            try:
                success_text = self.driver.find_elements(By.XPATH, "//*[contains(text(), '登录成功') or contains(text(), '跳转中')]")
                if success_text:
                    time.sleep(2)
                    self.is_logged_in = True
                    for cookie in self.driver.get_cookies():
                        self.cookies[cookie['name']] = cookie['value']
                    return True
            except:
                pass
            
            # 显示等待状态
            elapsed = int(time.time() - start_time)
            yield elapsed, timeout
            
            time.sleep(2)
        
        return False
    
    def cleanup(self):
        """清理资源"""
        if self.driver:
            self.driver.quit()
            self.driver = None


def main():
    st.title("🐟 闲鱼扫码登录")
    st.markdown("使用闲鱼APP扫描二维码登录")
    
    # 侧边栏
    with st.sidebar:
        st.header("📱 使用说明")
        st.markdown("""
        1. 点击下方按钮启动浏览器
        2. 等待二维码生成（约5-10秒）
        3. 使用闲鱼APP扫描二维码
        4. 在手机上确认登录
        5. 自动获取Cookie
        """)
        
        st.header("⚠️ 注意事项")
        st.warning("""
        - **首次运行需要安装Chrome浏览器和ChromeDriver**
        - ChromeDriver下载: https://chromedriver.chromium.org/
        - 安装命令: `pip install selenium pillow`
        - 二维码有效时间约2分钟
        """)
        
        st.header("🔧 环境检查")
        
        # 检查selenium
        try:
            import selenium
            st.success("✅ selenium 已安装")
        except:
            st.error("❌ selenium 未安装")
        
        # 检查PIL
        try:
            from PIL import Image
            st.success("✅ Pillow 已安装")
        except:
            st.error("❌ Pillow 未安装")
    
    # 主界面
    if 'login_instance' not in st.session_state:
        st.session_state.login_instance = None
        st.session_state.qr_display = None
        st.session_state.is_logged_in = False
        st.session_state.status = None
    
    # 开始登录按钮
    if not st.session_state.is_logged_in:
        if st.button("🚀 开始扫码登录", type="primary", use_container_width=True):
            
            with st.spinner("正在启动浏览器，请稍候..."):
                login = XianyuSeleniumLogin()
                st.session_state.login_instance = login
                
                if login.get_qr_code():
                    st.success("✅ 浏览器启动成功，正在获取二维码...")
                    
                    # 显示二维码
                    st.markdown("### 📱 请扫描下方二维码")
                    
                    if login.qr_image_base64:
                        if login.qr_image_base64.startswith('data:image'):
                            st.image(login.qr_image_base64, use_container_width=True)
                        else:
                            # 文件路径
                            st.image("full_page.png", caption="请查看截图中的二维码", use_container_width=True)
                            with open("full_page.png", "rb") as f:
                                st.download_button(
                                    label="📥 下载二维码图片",
                                    data=f,
                                    file_name="qrcode.png",
                                    mime="image/png"
                                )
                    elif login.qr_url:
                        st.image(login.qr_url, use_container_width=True)
                    
                    # 状态轮询
                    status_placeholder = st.empty()
                    progress_bar = st.progress(0)
                    
                    st.info("⏳ 等待扫码，请在手机上确认登录...")
                    
                    # 等待登录
                    generator = login.wait_for_login()
                    start_time = time.time()
                    
                    for elapsed, timeout in generator:
                        progress = elapsed / timeout
                        progress_bar.progress(min(progress, 1.0))
                        remaining = timeout - elapsed
                        status_placeholder.info(f"⏳ 等待扫码中... 剩余 {remaining} 秒")
                        
                        if login.is_logged_in:
                            break
                    
                    if login.is_logged_in:
                        status_placeholder.success("✅ 登录成功！")
                        st.session_state.is_logged_in = True
                        st.session_state.cookies = login.cookies
                        st.balloons()
                        st.rerun()
                    else:
                        status_placeholder.error("❌ 登录超时，请重试")
                        login.cleanup()
                        st.session_state.login_instance = None
                else:
                    st.error("❌ 获取二维码失败")
                    st.info("""
                    **可能的原因：**
                    1. ChromeDriver未安装或版本不匹配
                    2. Chrome浏览器未安装
                    3. 网络连接问题
                    
                    **解决方案：**
                    1. 确认Chrome浏览器已安装
                    2. 下载对应版本的ChromeDriver: 
                       https://chromedriver.chromium.org/
                    3. 将chromedriver.exe放在系统PATH或脚本目录
                    """)
    
    # 登录成功后的显示
    if st.session_state.is_logged_in:
        st.success("### ✅ 登录成功！")
        
        # 显示Cookie
        with st.expander("📦 Cookie信息", expanded=True):
            cookies = st.session_state.get('cookies', {})
            if cookies:
                important = ['cna', 'cookie2', 't', 'tracknick', '_tb_token_']
                important_cookies = {k: v for k, v in cookies.items() if k in important}
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
                if st.session_state.login_instance:
                    st.session_state.login_instance.cleanup()
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
