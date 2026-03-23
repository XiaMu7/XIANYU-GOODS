import streamlit as st
import hashlib
import json
import time
import re
import urllib.parse
import requests
import urllib3
import random

# 环境配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"

# ==================== 核心逻辑 ====================

def get_safe_tk(session):
    for cookie in session.cookies:
        if cookie.name == "_m_h5_tk":
            return cookie.value
    return None

def get_mtop_sign(token, t, app_key, data_str):
    if not token: return ""
    tk_prefix = token.split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def inject_credentials(session, raw_text):
    """全量注入，不放过任何一个 Cookie"""
    # 提取 x-smallstc
    stc_match = re.search(r'x-smallstc:\s*({.+})', raw_text)
    if stc_match:
        try:
            stc_data = json.loads(stc_match.group(1))
            for k, v in stc_data.items():
                session.cookies.set(str(k), str(v), domain=".goofish.com")
        except: pass

    # 提取所有 k=v
    pairs = re.findall(r'(?:^|;|,|(?<=\s))([^=;\s]+)=([^;\s,]+)', raw_text)
    for k, v in pairs:
        k_s = k.strip()
        if k_s.lower() not in ['host', 'content-length', 'content-type', 'connection']:
            session.cookies.set(k_s, v.strip(), domain=".goofish.com")

def run_sync_process(item_id, file_bytes, file_name, raw_input):
    session = requests.Session()
    inject_credentials(session, raw_input)
    
    current_tk = get_safe_tk(session)
    if not current_tk:
        return False, "❌ 未识别到 _m_h5_tk，请重新抓包并确保包含 Cookie。"

    # 模拟真实微信环境
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50(0x1800323c) NetType/WIFI Language/zh_CN"
    headers = {"User-Agent": ua, "x-tap": "wx", "xweb_xhr": "1"}

    try:
        # --- 1. 图片上传 ---
        t1 = str(int(time.time() * 1000))
        biz_data = json.dumps({"bizCode": "idleItemEdit", "clientType": "pc", "utdid": "v3UyIt1jJFECAXAaAnEns/UL"}, separators=(',', ':'))
        sign1 = get_mtop_sign(current_tk, t1, APP_KEY, biz_data)
        
        up_params = {
            "appkey": "fleamarket", "appKey": APP_KEY, "t": t1, "sign": sign1,
            "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
        }
        
        # 严格构造 Files 结构
        files = {
            'data': (None, biz_data),
            'file': ('image.png', file_bytes, 'image/png')
        }
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=headers, timeout=20)
        
        if res_up.status_code != 200:
            return False, f"上传接口响应异常: {res_up.status_code}"

        # 尝试解析 URL
        try:
            up_json = res_up.json()
            img_url = up_json.get('url') or (up_json.get('object', {}) if isinstance(up_json.get('object'), str) else up_json.get('object', {}).get('url'))
        except:
            img_url = re.search(r'"url":"(https?://[^"]+)"', res_up.text)
            img_url = img_url.group(1).replace("\\/", "/") if img_url else None

        if not img_url:
            return False, f"CDN返回错误: {res_up.text}"

        # --- 2. 提交修改 ---
        # 更新 Token (如果阿里刷新了它)
        new_tk = get_safe_tk(session)
        if new_tk: current_tk = new_tk

        t2 = str(int(time.time() * 1000))
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": "800", "heightSize": "800"}],
            "utdid": "v3UyIt1jJFECAXAaAnEns/UL", "platform": "ios"
        }
        edit_str = json.dumps(edit_data, ensure_ascii=False, separators=(',', ':'))
        sign2 = get_mtop_sign(current_tk, t2, APP_KEY, edit_str)
        
        edit_params = {
            "jsv": "2.4.12", "appKey": APP_KEY, "t": t2, "sign": sign2, "v": "1.0",
            "api": EDIT_API, "type": "originaljson", "accountSite": "xianyu"
        }
        
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=edit_params,
            data={"data": edit_str},
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if "SUCCESS" in res_edit.text:
            return True, "🎊 恭喜！同步更新成功！"
        else:
            return False, f"修改失败: {res_edit.text}"

    except Exception as e:
        return False, f"运行故障: {str(e)}"

# ==================== Streamlit UI ====================

st.set_page_config(page_title="闲鱼主图神器", page_icon="🐠")
st.title("🐠 闲鱼主图同步助手")

raw_input = st.text_area("1. 粘贴完整抓包信息", height=200, placeholder="此处粘贴包含 Cookie 的 Header...")
item_id = st.text_input("2. 商品 itemId", "1033424722209")
uploaded_file = st.file_uploader("3. 上传新图片", type=['png', 'jpg', 'jpeg'])

if st.button("🚀 开始执行同步", use_container_width=True):
    if raw_input and item_id and uploaded_file:
        with st.status("正在全力同步中...", expanded=True) as status:
            ok, msg = run_sync_process(item_id, uploaded_file.read(), uploaded_file.name, raw_input)
            if ok:
                status.update(label="同步成功！", state="complete")
                st.balloons()
                st.success(msg)
            else:
                status.update(label="任务失败", state="error")
                st.error(msg)
    else:
        st.warning("请确保所有字段均已填写且已上传图片。")
