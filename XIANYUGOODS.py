import streamlit as st
import json
import requests
import time
import hashlib
import urllib.parse
import re
import mimetypes
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 核心静态配置 ---
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

def get_mtop_sign(token, t, app_key, data_str):
    """计算阿里 MTOP 签名：取 _m_h5_tk 下划线前的部分"""
    tk = token.split('_')[0]
    base_str = f"{tk}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def parse_cookies(cookie_raw):
    """解析原始 Cookie 字符串"""
    cookie_dict = {}
    for item in cookie_raw.split(';'):
        if '=' in item:
            k, v = item.strip().split('=', 1)
            cookie_dict[k] = v
    return cookie_dict

# --- 业务函数 ---
def perform_sync(session, item_id, file_bytes, file_name, raw_headers):
    # 1. 提取 Headers 和 Cookies
    headers = {}
    for line in raw_headers.split('\n'):
        if ':' in line:
            k, v = line.split(':', 1)
            headers[k.strip().lower()] = v.strip()
    
    # 清理导致报错的 Header
    forbidden = ['content-length', 'host', 'content-type', 'priority', 'connection']
    for k in forbidden: headers.pop(k, None)
    
    # 强制注入微信入口特征
    headers.update({"x-tap": "wx", "xweb_xhr": "1"})
    
    # 2. 获取 Token
    tk = session.cookies.get("_m_h5_tk", "")
    if not tk: return False, "Cookie中缺少 _m_h5_tk，请重新注入"

    try:
        # --- 步骤 1: 上传图片 ---
        t_up = str(int(time.time() * 1000))
        biz_data = json.dumps({"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID})
        sign_up = get_mtop_sign(tk, t_up, APP_KEY, biz_data)
        
        up_params = {
            "appkey": "fleamarket", "jsv": "2.4.12", "appKey": APP_KEY, 
            "t": t_up, "sign": sign_up, "api": "mtop.taobao.util.uploadImage", 
            "v": "1.0", "type": "originaljson"
        }
        
        files = [
            ('bizCode', (None, 'fleamarket')),
            ('name', (None, 'fileFromAlbum')),
            ('data', (None, biz_data)),
            ('file', (file_name, file_bytes, 'image/png'))
        ]
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=headers, timeout=20)
        img_match = re.search(r'"url":"(https?://img\.alicdn\.com/[^"]+)"', res_up.text)
        
        if not img_match:
            return False, f"图片上传失败: {res_up.text[:150]}"
        
        img_url = img_match.group(1).replace('\\/', '/')
        st.write(f"✅ 图片上传成功: {img_url}")

        # --- 步骤 2: 修改商品 ---
        t_edit = str(int(time.time() * 1000))
        edit_obj = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major":True,"type":0,"url":img_url,"widthSize":"640","heightSize":"640"}],
            "utdid": FIXED_UTDID, "platform": "windows"
        }
        edit_str = json.dumps(edit_obj, ensure_ascii=False)
        sign_edit = get_mtop_sign(tk, t_edit, APP_KEY, edit_str)
        
        edit_params = {
            "jsv": "2.4.12", "appKey": APP_KEY, "t": t_edit, "sign": sign_edit,
            "v": "1.0", "api": EDIT_API, "accountSite": "xianyu", "type": "originaljson"
        }
        
        headers["content-type"] = "application/x-www-form-urlencoded"
        payload = f"data={urllib.parse.quote(edit_str)}"
        
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/2.0/", 
            params=edit_params, data=payload, headers=headers
        )
        
        result = res_edit.json()
        if "SUCCESS" in str(result.get("ret")):
            return True, "同步成功"
        else:
            return False, f"修改失败: {result.get('ret')}"

    except Exception as e:
        return False, f"程序崩溃: {str(e)}"

# --- Streamlit UI ---
st.set_page_config(page_title="闲鱼同步-稳定版", layout="wide")
st.title("🛡️ 闲鱼微信主图同步 - 核心令牌版")

if 'session' not in st.session_state:
    st.session_state.session = requests.Session()
    st.session_state.session.verify = False

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. 身份信息注入")
    cookie_input = st.text_area("粘贴完整 Cookie 字符串 (包含 _m_h5_tk)", height=250)
    header_input = st.text_area("粘贴原始 Request Headers (用于 bx-ua 等指纹)", height=250)
    
    if st.button("💾 注入凭证", use_container_width=True):
        if cookie_input:
            ck_dict = parse_cookies(cookie_input)
            st.session_state.session.cookies.clear()
            for k, v in ck_dict.items():
                st.session_state.session.cookies.set(k, v)
            st.success("Cookie 已注入！已检测到 Token。" if "_m_h5_tk" in ck_dict else "警告：Cookie中未发现 _m_h5_tk")

with col2:
    st.subheader("2. 同步任务")
    iid = st.text_input("商品 itemId", value="1033424722209")
    up_file = st.file_uploader("上传新主图", type=['png', 'jpg', 'jpeg'])
    
    if st.button("🚀 启动同步", use_container_width=True):
        if not cookie_input or not header_input:
            st.error("请先完成左侧的凭证注入！")
        elif iid and up_file:
            with st.spinner("微信环境模拟同步中..."):
                success, msg = perform_sync(st.session_state.session, iid, up_file.read(), up_file.name, header_input)
                if success:
                    st.balloons()
                    st.success(f"🎉 {msg}")
                else:
                    st.error(msg)
