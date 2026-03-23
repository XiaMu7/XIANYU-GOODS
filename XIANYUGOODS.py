import streamlit as st
import hashlib
import json
import time
import re
import urllib.parse
import requests
import urllib3

# 1. 基础环境配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 核心逻辑模块 ====================

def get_safe_tk(session):
    """安全获取 _m_h5_tk，解决 CookieConflictError"""
    for cookie in session.cookies:
        if cookie.name == "_m_h5_tk":
            return cookie.value
    return None

def get_mtop_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """阿里签名算法"""
    if not token: return ""
    tk_prefix = token.split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def update_session_from_raw(session, raw_text):
    """深度解析凭证"""
    # 提取 x-smallstc
    stc_match = re.search(r'x-smallstc:\s*({.+})', raw_text)
    if stc_match:
        try:
            stc_json = json.loads(stc_match.group(1))
            for key in ['cookie2', 'sgcookie', 'sid', 'unb']:
                if key in stc_json:
                    session.cookies.set(key, str(stc_json[key]), domain=".goofish.com")
        except: pass

    # 提取所有 k=v 格式 Cookie
    kv_pairs = re.findall(r'(?:^|;|,|(?<=\s))([^=;\s]+)=([^;\s,]+)', raw_text)
    for k, v in kv_pairs:
        if k.strip().lower() not in ['host', 'content-length', 'content-type']:
            session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")

def run_sync_process(item_id, file_bytes, file_name, raw_input):
    session = requests.Session()
    session.verify = False
    update_session_from_raw(session, raw_input)
    current_tk = get_safe_tk(session)
    
    if not current_tk:
        return False, "❌ 未发现 _m_h5_tk。请检查抓包内容。"

    # 模拟更真实的微信小程序 Headers
    common_headers = {
        "x-tap": "wx",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html"
    }

    try:
        # --- 步骤 1: 上传图片 (关键修复点) ---
        st.info("正在上传图片...")
        t1 = str(int(time.time() * 1000))
        
        # 闲鱼小程序标准的 bizData 结构
        biz_data_dict = {
            "bizCode": "idleItemEdit",
            "clientType": "pc",
            "utdid": FIXED_UTDID
        }
        biz_data_str = json.dumps(biz_data_dict, separators=(',', ':'))
        sign1 = get_mtop_sign(current_tk, t1, APP_KEY, biz_data_str)
        
        up_params = {
            "appkey": "fleamarket",
            "appKey": APP_KEY,
            "t": t1,
            "sign": sign1,
            "api": "mtop.taobao.util.uploadImage",
            "v": "1.0",
            "type": "originaljson"
        }
        
        # 修复：multipart 表单中，'data' 字段通常直接传字符串，而不是 (None, str)
        # 且文件名如果是中文建议统一为 image.png
        files = {
            'data': (None, biz_data_str),
            'file': ('image.png', file_bytes, 'image/png')
        }
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=common_headers, timeout=20)
        
        # 检查是否因为 Token 刷新导致失败
        if "FAIL_SYS_TOKEN_EXPIRED" in res_up.text:
            return False, "❌ Token 已过期，请重新抓包。"
            
        up_res_json = res_up.json()
        img_url = up_res_json.get('url') or up_res_json.get('object', {}).get('url')
        
        if not img_url:
            return False, f"上传失败 (SYS_ERROR): 请尝试更换一张图片或重新抓包。"

        # 更新可能翻转的 Token
        new_tk = get_safe_tk(session)
        if new_tk: current_tk = new_tk

        # --- 步骤 2: 修改主图 ---
        st.info("正在修改主图...")
        t2 = str(int(time.time() * 1000))
        
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{
                "major": True, "url": img_url, "type": 0, "widthSize": "800", "heightSize": "800"
            }],
            "utdid": FIXED_UTDID, "platform": "ios"
        }
        edit_json_str = json.dumps(edit_data, separators=(',', ':'))
        sign2 = get_mtop_sign(current_tk, t2, APP_KEY, edit_json_str)
        
        edit_params = {
            "jsv": "2.4.12", "appKey": APP_KEY, "t": t2, "sign": sign2, "v": "1.0",
            "api": EDIT_API, "type": "originaljson", "accountSite": "xianyu"
        }
        
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=edit_params,
            data={"data": edit_json_str}, # 自动 urlencode
            headers={**common_headers, "content-type": "application/x-www-form-urlencoded"}
        )
        
        if "SUCCESS" in res_edit.text:
            return True, "🎊 替换成功！"
        else:
            return False, f"修改失败：{res_edit.json().get('ret')}"

    except Exception as e:
        return False, f"运行错误: {str(e)}"

# ==================== Streamlit UI ====================

st.set_page_config(page_title="闲鱼助手")
st.title("🐠 闲鱼主图同步 (修复 SYS_ERROR)")

input_raw = st.text_area("1. 粘贴抓包原始数据", height=150)
item_id = st.text_input("2. 商品 itemId", value="1033424722209")
img_file = st.file_uploader("3. 选择新主图", type=['jpg', 'jpeg', 'png'])

if st.button("🚀 执行同步", use_container_width=True):
    if input_raw and item_id and img_file:
        ok, msg = run_sync_process(item_id, img_file.read(), img_file.name, input_raw)
        st.success(msg) if ok else st.error(msg)
    else:
        st.warning("内容不完整")
