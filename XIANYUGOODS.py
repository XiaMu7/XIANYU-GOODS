import streamlit as st
import json
import requests
import time
import hashlib
import mimetypes
import re
import urllib.parse
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 核心配置 ---
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

def get_mtop_sign(token, t, app_key, data_str):
    """计算阿里 MTOP 签名"""
    base_str = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def parse_full_package(raw_text):
    """
    深度解析器：从原始抓包文本中提取 Headers 和 Cookies，并清洗掉干扰项
    """
    headers = {}
    cookies = {}
    
    lines = raw_text.strip().split('\n')
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if key == 'cookie':
                for cookie_item in value.split(';'):
                    if '=' in cookie_item:
                        ck, cv = cookie_item.strip().split('=', 1)
                        cookies[ck.strip()] = cv.strip()
            else:
                headers[key] = value

    # 从 x-smallstc 穿透提取 Cookie
    if 'x-smallstc' in headers:
        try:
            stc_json = json.loads(headers['x-smallstc'])
            for k, v in stc_json.items():
                cookies[k] = str(v)
        except: pass

    # --- 关键清洗：移除会导致 HTML 报错的 Header ---
    forbidden = ['content-type', 'content-length', 'host', 'accept-encoding', 'connection', 'priority']
    clean_headers = {k: v for k, v in headers.items() if k not in forbidden}
    
    # 强制补全微信小程序标识
    clean_headers["x-tap"] = "wx"
    clean_headers["xweb_xhr"] = "1"
    
    return clean_headers, cookies

def upload_logic(session, file_bytes, file_name, clean_headers):
    """执行图片上传"""
    t = str(int(time.time() * 1000))
    tk_full = session.cookies.get("_m_h5_tk", "")
    token = tk_full.split("_")[0] if tk_full else ""

    # 业务参数
    upload_biz = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
    data_str = json.dumps(upload_biz)
    sign = get_mtop_sign(token, t, APP_KEY, data_str)

    params = {
        "floderId": "0", "appkey": "fleamarket", "_input_charset": "utf-8",
        "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
    }
    
    # 严格字段顺序
    fields = [
        ('content-type', (None, 'multipart/form-data')),
        ('bizCode', (None, 'fleamarket')),
        ('name', (None, 'fileFromAlbum')),
        ('data', (None, data_str)),
        ('file', (file_name, file_bytes, mimetypes.guess_type(file_name)[0] or 'image/png'))
    ]

    try:
        res = session.post(UPLOAD_URL, params=params, files=fields, headers=clean_headers, timeout=20)
        
        # 结果解析：优先正则提取，防止返回包含 HTML 标签的混合字符串
        match = re.search(r'"url":"(https?://img\.alicdn\.com/[^"]+)"', res.text)
        if match:
            return match.group(1).replace('\\/', '/'), None
        
        if "<html" in res.text.lower():
            return None, "服务器返回 HTML 页面（可能指纹 bx-ua 已过期，请重新抓包）"
        return None, f"上传失败: {res.text[:100]}"
    except Exception as e:
        return None, str(e)

def edit_logic(session, item_id, img_url, clean_headers):
    """执行商品修改"""
    t = str(int(time.time() * 1000))
    tk = session.cookies.get("_m_h5_tk", "").split("_")[0] if session.cookies.get("_m_h5_tk") else ""
    
    edit_data = {
        "itemId": str(item_id),
        "imageInfoDOList": [{"major":True,"type":0,"url":img_url,"widthSize":"640","heightSize":"640"}],
        "utdid": FIXED_UTDID,
        "platform": "windows"
    }
    data_str = json.dumps(edit_data, ensure_ascii=False)
    sign = get_mtop_sign(tk, t, APP_KEY, data_str)

    params = {
        "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
        "v": "1.0", "type": "originaljson", "api": EDIT_API,
        "accountSite": "xianyu", "dataType": "json"
    }
    
    url = f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/2.0/"
    
    # 构造微信专用 Body 格式
    headers = clean_headers.copy()
    headers["content-type"] = "application/x-www-form-urlencoded"
    payload = f"data={urllib.parse.quote(data_str)}"
    
    try:
        res = session.post(url, params=params, data=payload, headers=headers)
        return res.json()
    except Exception as e:
        return {"ret": [str(e)]}

# --- Streamlit 布局 ---
st.set_page_config(page_title="闲鱼同步终极版", layout="wide")
st.title("🛡️ 闲鱼微信版 - 全自动指纹同步工具")

if 'session' not in st.session_state:
    st.session_state.session = requests.Session()
    st.session_state.session.verify = False
if 'headers' not in st.session_state:
    st.session_state.headers = {}

c1, c2 = st.columns([1, 1])

with c1:
    st.subheader("第一步：注入指纹")
    raw_text = st.text_area("粘贴 Charles/Fiddler 里的完整 Request Headers", height=450, 
                            placeholder="在此粘贴包含 bx-ua, x-smallstc, mini-janus 的原始文本...")
    
    if st.button("🔄 解析并清洗数据", use_container_width=True):
        h, c = parse_full_package(raw_text)
        st.session_state.headers = h
        st.session_state.session.cookies.clear()
        for k, v in c.items():
            st.session_state.session.cookies.set(k, v)
        
        if "_m_h5_tk" in c:
            st.success(f"解析成功！已提取指纹及登录态。")
        else:
            st.warning("解析成功但未检测到 _m_h5_tk，请确保粘贴的 Headers 包含 Cookie 字段。")

with c2:
    st.subheader("第二步：同步操作")
    iid = st.text_input("商品 itemId", value="1033424722209")
    up_file = st.file_uploader("选择新图", type=['png', 'jpg', 'jpeg'])
    
    if st.button("🚀 启动指纹同步", use_container_width=True):
        if not st.session_state.headers:
            st.error("请先完成左侧的 Headers 解析！")
        elif iid and up_file:
            with st.spinner("微信环境模拟中..."):
                img_url, err = upload_logic(st.session_state.session, up_file.read(), up_file.name, st.session_state.headers)
                if img_url:
                    st.write("✅ 图片已上传 CDN")
                    res = edit_logic(st.session_state.session, iid, img_url, st.session_state.headers)
                    if "SUCCESS" in str(res.get("ret")):
                        st.balloons()
                        st.success("🎉 同步成功！")
                    else:
                        st.error(f"修改失败: {res.get('ret')}")
                        st.json(res)
                else:
                    st.error(f"上传失败: {err}")
