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
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
# 模拟 Mac 版微信小程序的真实 User-Agent
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781"

# ==================== 核心逻辑模块 ====================

def run_final_sync(item_id, file_bytes, cookie_str, tk_input):
    session = requests.Session()
    
    # --- 步骤 0: 指纹与 Cookie 预处理 ---
    # 动态提取 Cookie 中的 utdid (如果没有则使用默认)
    utdid_match = re.search(r'utdid=([^;]+)', cookie_str)
    current_utdid = utdid_match.group(1) if utdid_match else "v3UyIt1jJFECAXAaAnEns/UL"

    # 注入原始 Cookie 字符串到 Session
    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', cookie_str)
    for k, v in kv_pairs:
        key, val = k.strip(), v.strip()
        session.cookies.set(key, val, domain=".goofish.com")
        session.cookies.set(key, val, domain="stream-upload.goofish.com")

    # 【核心修复】强制覆盖注入手动输入的 Token
    full_tk = tk_input.strip()
    clean_tk = full_tk.split('_')[0]
    session.cookies.set("_m_h5_tk", full_tk, domain=".goofish.com")
    session.cookies.set("_m_h5_tk_enc", "any_val", domain=".goofish.com")

    common_headers = {
        "User-Agent": UA,
        "xweb_xhr": "1",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

    try:
        # --- 步骤 1: 上传图片 (复刻 cURL 成功路径) ---
        st.info("📤 步骤 1: 正在上传图片到阿里 CDN...")
        up_params = {"floderId": "0", "appkey": "fleamarket", "_input_charset": "utf-8"}
        # 按照闲鱼后端要求的 Multipart 顺序
        files = {
            'bizCode': (None, 'fleamarket'),
            'name': (None, 'fileFromAlbum'),
            'file': ('image.jpg', file_bytes, 'image/jpeg')
        }
        
        res_up = session.post(UPLOAD_URL, params=up_params, headers=common_headers, files=files, timeout=30)
        
        try:
            res_data = res_up.json()
            img_url = res_data.get('url') or res_data.get('object', {}).get('url')
        except:
            img_url = res_up.text if "http" in res_up.text else None

        if not img_url:
            st.error(f"上传响应解析失败: {res_up.text}")
            return False, "CDN 上传未返回有效 URL"
        
        st.success(f"✅ 图片上传成功")

        # --- 步骤 2: 修改主图 (MTOP 业务请求) ---
        st.info("🚀 步骤 2: 正在提交业务修改请求...")
        t = str(int(time.time() * 1000))
        
        # 构造业务数据 (Data)
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": 1024, "heightSize": 1024}],
            "utdid": current_utdid,
            "platform": "wx_mini"
        }
        data_str = json.dumps(edit_data, separators=(',', ':'))
        
        # 计算签名: token & t & appKey & data
        sign = hashlib.md5(f"{clean_tk}&{t}&{APP_KEY}&{data_str}".encode('utf-8')).hexdigest()

        # 构造 POST 参数
        params = {
            "jsv": "2.7.2",
            "appKey": APP_KEY,
            "t": t,
            "sign": sign,
            "v": "1.0",
            "api": EDIT_API,
            "type": "originaljson",
            "dataType": "json"
        }

        # 手动构造 Body 并进行标准的 URL 编码，防止非法请求报错
        payload = f"data={quote(data_str)}"

        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=params,
            data=payload,
            headers={
                **common_headers,
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )

        res_json = res_edit.json()
        ret_msg = res_json.get("ret", ["未知错误"])[0]
        
        if "SUCCESS" in ret_msg:
            return True, "🎊 恭喜！宝贝主图已成功同步更新。"
        else:
            return False, f"业务修改失败: {ret_msg}"

    except Exception as e:
        return False, f"程序运行异常: {str(e)}"

# ==================== Streamlit UI 界面 ====================

st.set_page_config(page_title="闲鱼主图同步工具", page_icon="🐠", layout="centered")

st.title("🐠 闲鱼主图同步 (终极版)")
st.markdown("""
    <style>
    .main { background-color: #f5f5f5; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #ffda00; color: black; font-weight: bold; border: none; }
    </style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("📌 操作指南")
    st.info("""
    1. **抓包**：在手机端闲鱼小程序进行一次编辑操作。
    2. **Cookie**：复制整个请求的 Cookie 字符串。
    3. **Token**：从 Cookie 中找到 `_m_h5_tk` 字段填入。
    4. **运行**：上传新图片并执行。
    """)
    st.warning("注意：Token 通常在 1 小时内有效，若报错非法请求，请重新抓包。")

# 输入区域
col1, col2 = st.columns([2, 3])
with col1:
    target_item_id = st.text_input("1. 商品 itemId", "1033424722209")
with col2:
    target_tk = st.text_input("2. 输入 _m_h5_tk (完整字段)", placeholder="xxx_123456789")

raw_cookies = st.text_area("3. 粘贴原始 Cookie 字符串", height=120)
new_img = st.file_uploader("4. 选择新的主图图片", type=['png', 'jpg', 'jpeg'])

if st.button("🚀 开始同步更新"):
    if not target_tk:
        st.error("❌ 缺少 _m_h5_tk，无法进行签名计算！")
    elif not raw_cookies or not new_img:
        st.error("❌ 请完整填写 Cookie 并上传图片！")
    else:
        # 执行同步逻辑
        success, message = run_final_sync(target_item_id, new_img.read(), raw_cookies, target_tk)
        
        if success:
            st.balloons()
            st.success(message)
        else:
            st.error(message)
            st.info("💡 提示：如果持续报错 '非法请求'，请尝试重新在手机端触发一次宝贝编辑，并更换最新的 Cookie 和 Token。")
