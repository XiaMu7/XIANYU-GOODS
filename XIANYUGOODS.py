import streamlit as st
import requests
import json
import time
from datetime import datetime

st.set_page_config(
    page_title="闲鱼助手",
    page_icon="🐟",
    layout="centered"
)

# 自定义样式
st.markdown("""
<style>
    .cookie-box {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        font-family: monospace;
        font-size: 12px;
        word-break: break-all;
    }
    .step {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin: 15px 0;
    }
    .success {
        background-color: #d4edda;
        color: #155724;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🐟 闲鱼助手")
st.markdown("管理闲鱼商品、查询信息")

# 初始化
if 'cookies' not in st.session_state:
    st.session_state.cookies = {}
    st.session_state.is_logged_in = False

# ========== 侧边栏：Cookie管理 ==========
with st.sidebar:
    st.header("🔐 登录设置")
    
    if st.session_state.is_logged_in:
        st.success("✅ 已登录")
        if st.button("🔄 重新登录", use_container_width=True):
            st.session_state.cookies = {}
            st.session_state.is_logged_in = False
            st.rerun()
    else:
        st.warning("⚠️ 未登录")
    
    st.markdown("---")
    st.header("📖 如何获取Cookie")
    
    with st.expander("点击查看详细教程", expanded=True):
        st.markdown("""
        ### 只需1分钟：
        
        **步骤1：登录闲鱼**
        
        打开浏览器访问 [https://www.goofish.com](https://www.goofish.com)
        
        点击右上角"登录"，用闲鱼APP扫码。
        
        ---
        
        **步骤2：获取Cookie**
        
        按 `F12` 打开开发者工具，点击 `Console` 标签，
        
        粘贴以下代码并回车：
        """)
        
        st.code("copy(document.cookie)", language="javascript")
        
        st.markdown("""
        Cookie已自动复制到剪贴板！
        
        ---
        
        **步骤3：粘贴到下方**
        
        将Cookie粘贴到下面的文本框，点击"导入"。
        """)
    
    st.markdown("---")
    
    # Cookie导入
    cookie_text = st.text_area(
        "粘贴Cookie",
        height=150,
        placeholder='cna=xxx; cookie2=xxx; t=xxx; _tb_token_=xxx',
        help="按F12 → Console → 输入 copy(document.cookie) 获取"
    )
    
    if st.button("📋 导入Cookie", type="primary", use_container_width=True):
        if cookie_text:
            # 解析Cookie
            cookies = {}
            for item in cookie_text.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()
            
            if cookies:
                st.session_state.cookies = cookies
                st.session_state.is_logged_in = True
                st.success(f"✅ 成功导入 {len(cookies)} 个Cookie")
                st.rerun()
            else:
                st.error("解析失败，请检查格式")
        else:
            st.warning("请先粘贴Cookie")
    
    # 可选：上传文件
    uploaded = st.file_uploader("或上传Cookie文件", type=['json'])
    if uploaded:
        try:
            cookies = json.load(uploaded)
            st.session_state.cookies = cookies
            st.session_state.is_logged_in = True
            st.success(f"✅ 成功导入 {len(cookies)} 个Cookie")
            st.rerun()
        except:
            st.error("文件格式错误")

# ========== 主界面 ==========
if st.session_state.is_logged_in:
    st.success("### ✅ 登录成功！")
    
    # 显示关键Cookie信息
    important = ['cna', 'cookie2', 't', 'tracknick', '_tb_token_']
    show_cookies = {k: v[:20] + "..." if len(v) > 20 else v 
                    for k, v in st.session_state.cookies.items() 
                    if k in important}
    if show_cookies:
        with st.expander("当前Cookie"):
            st.json(show_cookies)
    
    # ========== 功能卡片 ==========
    st.markdown("### 📦 功能列表")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("**查询我的商品**")
        if st.button("🔍 查询", use_container_width=True):
            st.info("功能开发中，敬请期待")
    
    with col2:
        st.info("**搜索商品**")
        keyword = st.text_input("关键词", placeholder="输入搜索内容")
        if st.button("搜索", use_container_width=True):
            st.info(f"搜索功能开发中: {keyword}")
    
    with col3:
        st.info("**数据统计**")
        if st.button("📊 查看", use_container_width=True):
            st.info("统计功能开发中")
    
    # ========== Cookie保存 ==========
    st.markdown("---")
    if st.button("💾 保存Cookie到本地", use_container_width=True):
        st.download_button(
            label="点击下载",
            data=json.dumps(st.session_state.cookies, indent=2),
            file_name="xianyu_cookies.json",
            mime="application/json"
        )
    
    # ========== 使用示例 ==========
    with st.expander("📖 Python调用示例"):
        st.code("""
import requests
import json

# 加载Cookie
with open('xianyu_cookies.json', 'r') as f:
    cookies = json.load(f)

# 创建会话
session = requests.Session()
session.cookies.update(cookies)
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# 调用闲鱼API
response = session.get('https://www.goofish.com/')
print(response.status_code)
        """, language="python")

else:
    # 未登录时的引导
    st.info("""
    ### 👋 欢迎使用闲鱼助手
    
    **要使用本工具，请先在左侧导入你的闲鱼Cookie。**
    
    #### 为什么需要Cookie？
    - Cookie是你的登录凭证
    - 只会保存在你自己的浏览器中
    - 我们不会收集你的任何信息
    
    #### 只需要操作一次！
    - Cookie有效期约1-2周
    - 过期后重复上述步骤即可
    """)
    
    # 演示
    st.markdown("### 🎬 快速演示")
    st.image("https://via.placeholder.com/600x300?text=1.登录闲鱼+2.复制Cookie+3.粘贴使用", use_container_width=True)

# ========== 页脚 ==========
st.markdown("---")
st.caption("⚠️ 本工具仅用于学习交流，请勿用于商业用途")
