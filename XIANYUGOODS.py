import streamlit as st
import hashlib
import json
import time
import re
import urllib.parse
import requests
import urllib3
import io

# 基础配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 日志辅助模块 ====================
def log_info(msg):
    st.session_state.logs.append(f"🔵 [INFO] {msg}")

def log_success(msg):
    st.session_state.logs.append(f"🟢 [SUCCESS] {msg}")

def log_error(msg):
    st.session_state.logs.append(f"🔴 [ERROR] {msg}")

def log_debug(msg):
    st.session_state.logs.append(f"🟡 [DEBUG] {msg}")

# ==================== 核心逻辑模块 ====================

def get_safe_tk(session):
    for cookie in session.cookies:
        if cookie.name == "_m_h5_tk":
            return cookie.value
    return None

def get_mtop_sign(token, t, app_key, data_str):
    if not token: return ""
    tk_prefix = token.split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    log_debug(f"待签名串: {base_str}")
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def update_session_from_raw(session, raw_text):
    # 注入 x-smallstc
    stc_match = re.search(r'x-smallstc:\s*({.+})', raw_text)
    if stc_match:
        try:
            stc_json = json.loads(stc_match.group(1))
            for k, v in stc_json.items():
                session.cookies.set(str(k), str(v), domain=".goofish.com")
            log_info("已从 x-smallstc 注入关键 Cookie")
        except: pass

    # 注入所有常规 Cookie
    pairs = re.findall(r'(?:^|;|,|(?<=\s))([^=;\s]+)=([^;\s,]+)', raw_text)
    for k, v in pairs:
        if k.strip().lower() not in ['host', 'content-length', 'content-type']:
            session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")
    
    current_tk = get_safe_tk(session)
    if current_tk:
        log_success(f"Token 获取成功: {current_tk[:15]}...")
    else:
        log_error("未能识别 _m_h5_tk，请检查输入！")

def run_sync_process(item_id, file_bytes, file_name, raw_input):
    session = requests.Session()
    session.verify = False
    update_session_from_raw(session, raw_input)
    
    current_tk = get_safe_tk(session)
    if not current_tk:
        return False, "缺乏 Token"

    common_headers = {
        "x-tap": "wx", "xweb_xhr": "1",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html"
    }

    try:
        # --- 步骤 1: 上传图片 ---
        log_info(">>> 阶段 1: 正在上传图片至阿里 CDN...")
        t1 = str(int(time.time() * 1000))
        biz_data = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
        biz_str = json.dumps(biz_data, separators=(',', ':'))
        sign1 = get_mtop_sign(current_tk, t1, APP_KEY, biz_str)
        
        up_params = {
            "appkey": "fleamarket", "appKey": APP_KEY, "t": t1, "sign": sign1,
            "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
        }
        files = {'data': (None, biz_str), 'file': ('image.png', file_bytes, 'image/png')}
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=common_headers, timeout=20)
        log_debug(f"上传响应内容: {res_up.text}")
        
        # 实时更新 Token
        new_tk = get_safe_tk(session)
        if new_tk: current_tk = new_tk

        up_json = res_up.json()
        img_url = up_json.get('url') or (up_json.get('object', {}).get('url') if isinstance(up_json.get('object'), dict) else None)
        
        if not img_url:
            log_error(f"CDN 上传失败响应: {res_up.text}")
            return False, "图片上传失败"
        log_success(f"图片上传成功，URL: {img_url}")

        # --- 步骤 2: 更新商品 ---
        log_info(">>> 阶段 2: 正在请求修改商品主图...")
        t2 = str(int(time.time() * 1000))
        
        # 尝试模拟真实的图片尺寸和参数
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": "1024", "heightSize": "1024"}],
            "utdid": FIXED_UTDID, "platform": "ios"
        }
        edit_str = json.dumps(edit_data, ensure_ascii=False, separators=(',', ':'))
        log_debug(f"修改请求 Data: {edit_str}")
        
        sign2 = get_mtop_sign(current_tk, t2, APP_KEY, edit_str)
        edit_params = {
            "jsv": "2.4.12", "appKey": APP_KEY, "t": t2, "sign": sign2, "v": "1.0",
            "api": EDIT_API, "type": "originaljson", "accountSite": "xianyu"
        }
        
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=edit_params,
            data={"data": edit_str},
            headers={**common_headers, "content-type": "application/x-www-form-urlencoded"}
        )
        
        log_debug(f"修改响应原文: {res_edit.text}")
        result = res_edit.json()
        
        if "SUCCESS" in str(result.get("ret")):
            log_success("闲鱼后台已接受修改请求！")
            return True, "🎊 替换成功！"
        else:
            log_error(f"业务逻辑拒绝: {result.get('ret')}")
            return False, f"修改失败: {result.get('ret')}"

    except Exception as e:
        log_error(f"运行崩坏: {str(e)}")
        return False, f"系统错误: {str(e)}"

# ==================== Streamlit UI ====================

st.set_page_config(page_title="闲鱼主图调试版", layout="wide")

if 'logs' not in st.session_state:
    st.session_state.logs = []

st.title("🐠 闲鱼主图同步 (调试控制台版)")

col_left, col_right = st.columns([1, 1.2])

with col_left:
    st.subheader("🛠️ 输入参数")
    raw_input = st.text_area("1. 粘贴 Header/Cookie", height=200)
    item_id_val = st.text_input("2. 商品 itemId", value="1033424722209")
    img_file = st.file_uploader("3. 选择图片", type=['jpg','png','jpeg'])
    
    if st.button("🚀 执行并监控日志", use_container_width=True):
        if raw_input and item_id_val and img_file:
            st.session_state.logs = [] # 清空旧日志
            ok, msg = run_sync_process(item_id_val, img_file.read(), img_file.name, raw_input)
            if ok: st.balloons()
        else:
            st.warning("参数不全")

with col_right:
    st.subheader("📜 运行日志 (实时)")
    log_container = st.container(border=True)
    with log_container:
        if not st.session_state.logs:
            st.write("等待任务开始...")
        for log in st.session_state.logs:
            st.markdown(log)

# 添加一个清除日志的按钮
if st.sidebar.button("🗑️ 清除日志"):
    st.session_state.logs = []
    st.rerun()
