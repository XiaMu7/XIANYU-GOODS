import streamlit as st
import hashlib
import json
import time
import re
import urllib.parse
import requests
import urllib3
from PIL import Image
import io

# 1. 基础环境配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 核心逻辑模块 (借鉴 m_h5_tk 用法) ====================

def get_mtop_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算阿里签名：核心在于提取下划线前的部分"""
    if not token: return ""
    tk_prefix = token.split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def update_session_from_raw(session, raw_text):
    """
    借鉴点：全方位暴力提取。支持 Header 格式、Cookie 字符串、x-smallstc JSON
    """
    # 1. 解析 x-smallstc (如果存在)
    stc_match = re.search(r'x-smallstc:\s*({.+})', raw_text)
    if stc_match:
        try:
            stc_json = json.loads(stc_match.group(1))
            for key in ['cookie2', 'sgcookie', 'sid', 'unb']:
                if key in stc_json:
                    val = str(stc_json[key])
                    for domain in [".goofish.com", "acs.m.goofish.com"]:
                        session.cookies.set(key, val, domain=domain)
        except: pass

    # 2. 正则提取 _m_h5_tk (这是最稳妥的用法)
    tk_match = re.search(r'_m_h5_tk=([^; ]+)', raw_text)
    if tk_match:
        tk_val = tk_match.group(1).strip()
        session.cookies.set("_m_h5_tk", tk_val, domain=".goofish.com")
        session.cookies.set("_m_h5_tk", tk_val, domain="acs.m.goofish.com")

    # 3. 提取常规 Cookie 键值对
    cookie_pattern = re.compile(r'(?:^|;)\s*([^=\s]+)\s*=\s*([^;]+)')
    for k, v in cookie_pattern.findall(raw_text):
        if k.lower() not in ['x-smallstc', 'host', 'content-length']:
            session.cookies.set(k, v.strip(), domain=".goofish.com")

def run_sync_process(item_id, file_bytes, file_name, raw_input):
    session = requests.Session()
    session.verify = False
    
    # 注入凭证
    update_session_from_raw(session, raw_input)
    
    # 初始获取 Token
    current_tk = session.cookies.get("_m_h5_tk")
    if not current_tk:
        return False, "❌ 报文中未发现 _m_h5_tk。请确保粘贴的内容包含 Cookie 字段。"

    # 统一 Header 指纹
    common_headers = {
        "x-tap": "wx", "xweb_xhr": "1", "accept": "application/json",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html"
    }

    try:
        # --- 步骤 1: 上传图片 (计算第一次 Sign) ---
        t1 = str(int(time.time() * 1000))
        biz_data = json.dumps({"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID})
        sign1 = get_mtop_sign(current_tk, t1, APP_KEY, biz_data)
        
        up_params = {"appkey":"fleamarket","appKey":APP_KEY,"t":t1,"sign":sign1,"api":"mtop.taobao.util.uploadImage","v":"1.0","type":"originaljson"}
        files = [('data',(None, biz_data)), ('file',(file_name, file_bytes, 'image/png'))]
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=common_headers, timeout=20)
        
        # 借鉴点：处理 Token 翻转 (阿里可能在响应中下发新 Token)
        if "_m_h5_tk" in res_up.cookies:
            current_tk = res_up.cookies.get("_m_h5_tk")
            
        img_url = None
        up_json = res_up.json()
        if up_json.get('success'):
            img_url = up_json.get('url') or up_json.get('object', {}).get('url')
        
        if not img_url:
            return False, f"图片上传失败，原因：{res_up.text[:200]}"

        # --- 步骤 2: 修改主图 (使用最新 Token 计算第二次 Sign) ---
        t2 = str(int(time.time() * 1000))
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major":True,"type":0,"url":img_url,"widthSize":"800","heightSize":"800"}],
            "utdid": FIXED_UTDID, "platform": "windows"
        }
        edit_json = json.dumps(edit_data, ensure_ascii=False, separators=(',', ':'))
        sign2 = get_mtop_sign(current_tk, t2, APP_KEY, edit_json)
        
        edit_params = {
            "jsv":"2.4.12","appKey":APP_KEY,"t":t2,"sign":sign2,"v":"1.0",
            "api":EDIT_API,"type":"originaljson","accountSite":"xianyu"
        }
        
        post_headers = common_headers.copy()
        post_headers["content-type"] = "application/x-www-form-urlencoded"
        payload = {"data": edit_json}
        
        res_edit = session.post(f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/", 
                                params=edit_params, data=payload, headers=post_headers)
        
        result = res_edit.json()
        if "SUCCESS" in str(result.get("ret", "")):
            return True, "🎊 同步成功！商品主图已更新。"
        else:
            return False, f"修改失败：{result.get('ret')}"

    except Exception as e:
        return False, f"程序异常: {str(e)}"

# ==================== Streamlit 界面 ====================

st.set_page_config(page_title="闲鱼助手", page_icon="🐠")
st.title("🐠 闲鱼主图同步助手")

# 侧边栏身份显示
with st.sidebar:
    st.header("🔑 当前状态")
    if 'tk_display' not in st.session_state: st.session_state.tk_display = "未注入"
    st.info(f"Token状态: {st.session_state.tk_display}")

raw_input = st.text_area("1. 粘贴抓包数据 (Header/Cookie/x-smallstc)", height=250, placeholder="直接 Ctrl+A, Ctrl+V 粘贴 Fiddler 抓到的内容...")

col1, col2 = st.columns(2)
with col1:
    target_iid = st.text_input("2. 商品 itemId", placeholder="例如: 1033424722209")
with col2:
    target_file = st.file_uploader("3. 选择新主图", type=['jpg', 'png', 'jpeg'])

if st.button("🚀 开始同步", use_container_width=True):
    if not raw_input or not target_iid or not target_file:
        st.error("请完整填写以上三项内容")
    else:
        with st.spinner("同步中..."):
            # 预解析一次更新侧边栏状态
            temp_session = requests.Session()
            update_session_from_raw(temp_session, raw_input)
            st.session_state.tk_display = temp_session.cookies.get("_m_h5_tk", "未发现")[:15] + "..."
            
            ok, msg = run_sync_process(target_iid, target_file.read(), target_file.name, raw_input)
            if ok:
                st.balloons()
                st.success(msg)
            else:
                st.error(msg)
