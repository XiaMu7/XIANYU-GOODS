import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3
from urllib.parse import quote

# 1. 基础环境配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"  # 网页版与小程序通用的 H5 AppKey
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"

# 关键：必须使用标准的 PC 浏览器 User-Agent，与你网页抓包环境保持一致
PC_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

# ==================== 核心逻辑模块 ====================

def run_pc_sync(item_id, file_bytes, cookie_str, tk_input):
    session = requests.Session()
    
    # --- 步骤 0: 身份指纹注入 ---
    # 注入原始 Cookie 字符串到 Session
    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', cookie_str)
    for k, v in kv_pairs:
        key, val = k.strip(), v.strip()
        # 网页版 Token 作用域通常是 .goofish.com 或 .taobao.com
        session.cookies.set(key, val, domain=".goofish.com")
        session.cookies.set(key, val, domain="stream-upload.goofish.com")

    # 强制注入你从网页获取的 _m_h5_tk
    full_tk = tk_input.strip()
    clean_tk = full_tk.split('_')[0]
    session.cookies.set("_m_h5_tk", full_tk, domain=".goofish.com")
    session.cookies.set("_m_h5_tk_enc", "any_val", domain=".goofish.com")

    # 对齐网页版的 Headers
    pc_headers = {
        "User-Agent": PC_UA,
        "Origin": "https://2.taobao.com",
        "Referer": "https://2.taobao.com/",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        # --- 步骤 1: 上传图片 (网页版上传逻辑) ---
        st.info("📤 步骤 1: 正在上传图片...")
        up_params = {
            "appkey": "fleamarket",
            "_input_charset": "utf-8",
            "floderId": "0"
        }
        files = {
            'bizCode': (None, 'fleamarket'),
            'file': ('image.jpg', file_bytes, 'image/jpeg')
        }
        
        res_up = session.post(UPLOAD_URL, params=up_params, headers=pc_headers, files=files, timeout=30)
        
        try:
            res_data = res_up.json()
            img_url = res_data.get('url') or res_data.get('object', {}).get('url')
        except:
            img_url = res_up.text if "http" in res_up.text else None

        if not img_url:
            st.error(f"上传失败，响应内容: {res_up.text}")
            return False, "图片上传未返回有效 URL"
        
        st.success(f"✅ 图片上传成功")

        # --- 步骤 2: 修改主图 (PC 网页签名模式) ---
        st.info("🚀 步骤 2: 正在提交业务修改...")
        t = str(int(time.time() * 1000))
        
        # 构造业务数据，platform 设为 pc
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": 1024, "heightSize": 1024}],
            "platform": "pc" 
        }
        data_str = json.dumps(edit_data, separators=(',', ':'))
        
        # 计算签名: token & t & appKey & data
        sign = hashlib.md5(f"{clean_tk}&{t}&{APP_KEY}&{data_str}".encode('utf-8')).hexdigest()

        # MTOP 网页版标准的请求参数
        params = {
            "jsv": "2.6.1",
            "appKey": APP_KEY,
            "t": t,
            "sign": sign,
            "v": "1.0",
            "api": EDIT_API,
            "type": "json",
            "dataType": "json"
        }

        # 手动构造 Body 并进行 URL 编码
        payload = f"data={quote(data_str)}"

        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=params,
            data=payload,
            headers=pc_headers
        )

        res_json = res_edit.json()
        ret_msg = res_json.get("ret", ["未知错误"])[0]
        
        if "SUCCESS" in ret_msg:
            return True, "🎊 同步更新成功！(PC 网页模式)"
        else:
            return False, f"业务修改失败: {ret_msg}"

    except Exception as e:
        return False, f"程序运行异常: {str(e)}"

# ==================== Streamlit UI 界面 ====================

st.set_page_config(page_title="闲鱼主图同步-网页版", page_icon="💻")

st.title("💻 闲鱼主图同步 (PC 网页专用版)")
st.markdown("""
    <style>
    .stButton>button { width: 100%; background-color: #4CAF50; color: white; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.warning("⚠️ 请确保你的 Token 是在电脑浏览器抓取的，而非手机小程序。")

col1, col2 = st.columns(2)
with col1:
    target_item_id = st.text_input("1. 商品 itemId", "1033424722209")
with col2:
    target_tk = st.text_input("2. 输入网页版 _m_h5_tk", placeholder="从浏览器 Cookie 中获取")

raw_cookies = st.text_area("3. 粘贴网页版原始 Cookie", height=100)
new_img = st.file_uploader("4. 选择新的主图图片", type=['png', 'jpg', 'jpeg'])

if st.button("🚀 执行同步 (网页模式)"):
    if not target_tk or not raw_cookies or not new_img:
        st.error("❌ 请完整填写所有必填项！")
    else:
        success, message = run_pc_sync(target_item_id, new_img.read(), raw_cookies, target_tk)
        
        if success:
            st.balloons()
            st.success(message)
        else:
            st.error(message)
            if "FAIL_SYS_ILLEGAL_ACCESS" in message:
                st.info("💡 仍报错非法请求？请检查你的电脑时间是否准确，或重新刷新网页获取最新 Token。")
