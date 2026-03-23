import streamlit as st
import hashlib
import json
import time
import re
import urllib.parse
import requests
import urllib3

# 基础配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 增强版解析逻辑 ====================

def update_session_from_raw(session, raw_text):
    """
    针对用户提供的长字符串 Cookie 进行精准解析
    """
    # 清理换行符
    raw_text = raw_text.replace('\n', '').strip()
    
    # 自动识别多种分隔符 (; 或空格)
    # 匹配模式: key=value
    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', raw_text)
    
    found_count = 0
    for k, v in kv_pairs:
        key = k.strip()
        val = v.strip()
        if key:
            # 统一注入到 .goofish.com 域名下
            session.cookies.set(key, val, domain=".goofish.com")
            session.cookies.set(key, val, domain="stream-upload.goofish.com")
            found_count += 1
            
    return found_count

def get_safe_tk(session):
    # 优先从 cookie 字典中找
    for cookie in session.cookies:
        if cookie.name == "_m_h5_tk":
            return cookie.value
    return None

def get_mtop_sign(token, t, app_key, data_str):
    if not token: return ""
    tk_prefix = token.split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

# ==================== 业务逻辑 ====================

def run_sync_process(item_id, file_bytes, file_name, raw_input):
    session = requests.Session()
    count = update_session_from_raw(session, raw_input)
    st.write(f"📊 已成功解析并注入 {count} 个 Cookie 字段")
    
    current_tk = get_safe_tk(session)
    if not current_tk:
        return False, "❌ 未识别到 _m_h5_tk，请确保输入包含该字段。"

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "x-tap": "wx",
        "xweb_xhr": "1",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html"
    }

    try:
        # --- 步骤 1: 上传图片 ---
        t1 = str(int(time.time() * 1000))
        biz_data = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
        biz_str = json.dumps(biz_data, separators=(',', ':'))
        sign1 = get_mtop_sign(current_tk, t1, APP_KEY, biz_str)
        
        up_params = {
            "appkey": "fleamarket", "appKey": APP_KEY, "t": t1, "sign": sign1,
            "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
        }

        # 重点：阿里上传接口有时对 files 顺序有要求
        files = [
            ('data', (None, biz_str)),
            ('file', ('image.png', file_bytes, 'image/png'))
        ]
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=headers, timeout=20)
        
        # 调试输出
        st.text_area("上传响应日志", value=res_up.text, height=100)
        
        up_json = res_up.json()
        img_url = up_json.get('url') or (up_json.get('object', {}).get('url') if isinstance(up_json.get('object'), dict) else None)
        
        if not img_url:
            return False, f"图片上传失败: {res_up.text[:100]}"

        # --- 步骤 2: 修改商品 ---
        new_tk = get_safe_tk(session)
        if new_tk: current_tk = new_tk

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
            return True, "🎊 修改成功！"
        else:
            return False, f"修改失败: {res_edit.text[:150]}"

    except Exception as e:
        return False, f"运行错误: {str(e)}"

# ==================== UI 保持不变 ====================
st.title("🐠 闲鱼主图同步助手 (精准解析版)")
raw_input = st.text_area("直接粘贴那一长串 Cookie", height=150)
item_id = st.text_input("商品 itemId", "1033424722209")
img_file = st.file_uploader("选择图片")

if st.button("🚀 开始同步"):
    if raw_input and img_file:
        ok, msg = run_sync_process(item_id, img_file.read(), img_file.name, raw_input)
        if ok: st.success(msg)
        else: st.error(msg)
