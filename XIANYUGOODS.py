import streamlit as st
import json
import requests
import time
import hashlib
import mimetypes
import re
import urllib.parse
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 核心配置 ---
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"

def get_mtop_sign(token, t, app_key, data_str):
    base_str = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def parse_raw_headers(raw_text):
    """
    全自动解析器：从原始抓包文本中提取 Headers 和 Cookies
    """
    headers = {}
    cookies = {}
    
    # 提取所有 Header 键值对
    lines = raw_text.strip().split('\n')
    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            # 特殊处理 Cookie 字段
            if key == 'cookie':
                for cookie_item in value.split(';'):
                    if '=' in cookie_item:
                        ck, cv = cookie_item.strip().split('=', 1)
                        cookies[ck] = cv
            else:
                headers[key] = value

    # 如果存在 x-smallstc，从中补全缺失的 Cookie 字段
    if 'x-smallstc' in headers:
        try:
            stc_json = json.loads(headers['x-smallstc'])
            for k, v in stc_json.items():
                if isinstance(v, str) or isinstance(v, int):
                    cookies[k] = str(v)
        except:
            pass

    return headers, cookies

def upload_image_wx(session, file_bytes, file_name, extra_headers):
    """
    带指纹的图片上传
    """
    t = str(int(time.time() * 1000))
    # 获取签名用的 token
    tk_full = session.cookies.get("_m_h5_tk", "")
    token = tk_full.split("_")[0] if tk_full else ""

    upload_biz = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": "v3UyIt1jJFECAXAaAnEns/UL"}
    data_str = json.dumps(upload_biz)
    sign = get_mtop_sign(token, t, APP_KEY, data_str)

    params = {
        "floderId": "0", "appkey": "fleamarket", "_input_charset": "utf-8",
        "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
    }
    
    fields = [
        ('content-type', (None, 'multipart/form-data')),
        ('bizCode', (None, 'fleamarket')),
        ('name', (None, 'fileFromAlbum')),
        ('data', (None, data_str)),
        ('file', (file_name, file_bytes, mimetypes.guess_type(file_name)[0] or 'image/png'))
    ]

    # 合并指纹 Header，但移除 Content-Type 让 requests 自动生成
    headers = extra_headers.copy()
    headers.pop('content-type', None)
    headers.pop('content-length', None)

    try:
        res = session.post(UPLOAD_URL, params=params, files=fields, headers=headers, timeout=20)
        match = re.search(r'"url":"(https?://img\.alicdn\.com/[^"]+)"', res.text)
        if match:
            return match.group(1).replace('\\/', '/'), None
        return None, f"上传异常: {res.text[:100]}"
    except Exception as e:
        return None, str(e)

def edit_item_wx(session, item_id, img_url, extra_headers):
    """
    带指纹的商品修改
    """
    t = str(int(time.time() * 1000))
    tk = session.cookies.get("_m_h5_tk", "").split("_")[0] if session.cookies.get("_m_h5_tk") else ""
    
    edit_data = {
        "itemId": str(item_id),
        "imageInfoDOList": [{"major":True,"type":0,"url":img_url,"widthSize":"640","heightSize":"640"}],
        "utdid": "v3UyIt1jJFECAXAaAnEns/UL",
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
    
    # 注入抓包中的核心指纹
    headers = extra_headers.copy()
    headers.update({
        "content-type": "application/x-www-form-urlencoded",
        "x-tap": "wx"
    })
    
    payload = f"data={urllib.parse.quote(data_str)}"
    
    try:
        res = session.post(url, params=params, data=payload, headers=headers)
        return res.json()
    except Exception as e:
        return {"ret": [str(e)]}

# --- UI ---
st.set_page_config(page_title="全自动指纹版同步器", layout="wide")
st.title("🛡️ 闲鱼微信版 - 指纹同步同步器")

if 'session' not in st.session_state:
    st.session_state.session = requests.Session()
    st.session_state.session.verify = False
if 'saved_headers' not in st.session_state:
    st.session_state.saved_headers = {}

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 粘贴原始抓包数据")
    raw_input = st.text_area("直接把 Charles/Fiddler 的 Header 区域全部粘贴在这里", height=400, placeholder="host: acs.m.goofish.com\nuser-agent: ...\nbx-ua: ...")
    if st.button("✨ 解析并保存指纹"):
        h, c = parse_raw_headers(raw_input)
        st.session_state.saved_headers = h
        st.session_state.session.cookies.clear()
        for k, v in c.items():
            st.session_state.session.cookies.set(k, v)
        st.success(f"解析成功！已提取 {len(h)} 个 Header 和 {len(c)} 个 Cookie 字段。")

with col2:
    st.subheader("2. 执行同步")
    iid = st.text_input("商品 ID", value="1033424722209")
    up_file = st.file_uploader("选择新主图")
    
    if st.button("🚀 开始指纹同步", use_container_width=True):
        if not st.session_state.saved_headers:
            st.error("请先在左侧粘贴并解析 Header！")
        elif iid and up_file:
            with st.spinner("同步中..."):
                img_url, err = upload_image_wx(st.session_state.session, up_file.read(), up_file.name, st.session_state.saved_headers)
                if img_url:
                    st.write("📸 图片上传成功")
                    res = edit_item_wx(st.session_state.session, iid, img_url, st.session_state.saved_headers)
                    if "SUCCESS" in str(res.get("ret")):
                        st.balloons()
                        st.success("🎉 商品主图已更新成功！")
                    else:
                        st.error(f"修改失败: {res.get('ret')}")
                        st.json(res)
                else:
                    st.error(f"上传环节失败: {err}")
