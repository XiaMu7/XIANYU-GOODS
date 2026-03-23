import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3

# 基础环境
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 核心逻辑修复 ====================

def get_cookie_value_safe(session, cookie_name):
    """
    【核心修复】手动遍历 CookieJar，避免 CookieConflictError。
    即使存在多个同名不同域名的 Cookie，也会返回第一个找到的。
    """
    for cookie in session.cookies:
        if cookie.name == cookie_name:
            return cookie.value
    return None

def get_mtop_sign(token, t, app_key, data_str):
    """阿里签名：取 token 前 32 位"""
    tk_prefix = str(token).split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def inject_cookies_safe(session, raw_str):
    """解析并注入 Cookie"""
    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', raw_str)
    for k, v in kv_pairs:
        key, val = k.strip(), v.strip()
        # 注入到一个通用的父域名下即可，避免产生多个同名 Cookie 导致冲突
        session.cookies.set(key, val, domain=".goofish.com")
    return len(kv_pairs)

def run_sync_process(item_id, file_bytes, raw_input):
    session = requests.Session()
    # 注入时仅注入到一个域名，减少冲突概率
    inject_cookies_safe(session, raw_input)
    
    # 【修复点】使用安全获取方法，不再调用 session.cookies.get()
    full_tk = get_cookie_value_safe(session, "_m_h5_tk")
    
    if not full_tk:
        return False, "❌ 未发现 _m_h5_tk，请确认 Cookie 是否完整。"

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "x-tap": "wx",
        "xweb_xhr": "1",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html"
    }

    try:
        # --- 步骤 1: 上传图片 ---
        st.info("正在执行第一步：上传图片...")
        t1 = str(int(time.time() * 1000))
        biz_data = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
        biz_str = json.dumps(biz_data, separators=(',', ':'))
        
        sign1 = get_mtop_sign(full_tk, t1, APP_KEY, biz_str)
        
        up_params = {
            "appkey": "fleamarket", "appKey": APP_KEY, "t": t1, "sign": sign1,
            "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
        }

        # 阿里上传接口要求 'data' 字段在 'file' 之前
        files = [
            ('data', (None, biz_str)),
            ('file', ('image.png', file_bytes, 'image/png'))
        ]
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=headers, timeout=20)
        
        # 实时同步可能翻转的新 Token
        current_tk = get_cookie_value_safe(session, "_m_h5_tk") or full_tk

        if "success\":true" not in res_up.text.lower():
            st.error(f"CDN响应原始数据: {res_up.text}")
            return False, "CDN上传阶段失败（可能是 Session 或参数问题）。"

        up_json = res_up.json()
        img_url = up_json.get('url') or up_json.get('object', {}).get('url')
        st.success("图片上传成功！")

        # --- 步骤 2: 修改商品 ---
        st.info("正在执行第二步：同步主图...")
        t2 = str(int(time.time() * 1000))
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": "1024", "heightSize": "1024"}],
            "utdid": FIXED_UTDID, "platform": "ios"
        }
        edit_str = json.dumps(edit_data, ensure_ascii=False, separators=(',', ':'))
        sign2 = get_mtop_sign(current_tk, t2, APP_KEY, edit_str)
        
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params={"jsv": "2.4.12", "appKey": APP_KEY, "t": t2, "sign": sign2, "v": "1.0", "api": EDIT_API, "type": "originaljson"},
            data={"data": edit_str},
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if "SUCCESS" in res_edit.text:
            return True, "🎊 替换主图成功！"
        else:
            return False, f"修改失败: {res_edit.text}"

    except Exception as e:
        return False, f"发生不可预知错误: {str(e)}"

# ==================== Streamlit UI ====================
st.title("🐠 闲鱼主图同步 (Bug 修复版)")
cookie_input = st.text_area("1. 粘贴完整 Cookie 字符串", height=150)
item_id_input = st.text_input("2. itemId", value="1033424722209")
file_input = st.file_uploader("3. 选择主图文件")

if st.button("🚀 开始同步任务", use_container_width=True):
    if cookie_input and file_input:
        # 每次点击清空 session cookie 防止叠加导致冲突
        ok, msg = run_sync_process(item_id_input, file_input.read(), cookie_input)
        if ok:
            st.balloons()
            st.success(msg)
        else:
            st.error(msg)
