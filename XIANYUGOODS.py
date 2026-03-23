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

# --- 全局常量 ---
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

def get_mtop_sign(token, t, app_key, data_str):
    """计算阿里签名"""
    base_str = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def parse_advanced_package(raw_text):
    """
    高级解析器：支持从 Raw Headers 或 纯 Cookie 字符串中提取指纹
    """
    headers = {}
    cookies = {}
    
    # 1. 拆分行并初步提取
    lines = [line.strip() for line in raw_text.strip().split('\n') if line.strip()]
    
    for line in lines:
        if ':' in line: # 处理 Header 格式 (key: value)
            key, value = line.split(':', 1)
            key, value = key.strip().lower(), value.strip()
            if key == 'cookie':
                for item in value.split(';'):
                    if '=' in item:
                        k, v = item.strip().split('=', 1)
                        cookies[k] = v
            else:
                headers[key] = value
        elif '=' in line: # 处理纯 Cookie 格式 (k=v; k2=v2)
            for item in line.split(';'):
                if '=' in item:
                    parts = item.strip().split('=', 1)
                    if len(parts) == 2:
                        cookies[parts[0]] = parts[1]

    # 2. 从 x-smallstc (微信特有) 进一步穿透提取 Cookie
    if 'x-smallstc' in headers:
        try:
            stc_data = json.loads(headers['x-smallstc'])
            for k, v in stc_data.items():
                cookies[k] = str(v)
        except: pass

    # 3. 关键指纹清洗：移除会导致服务器返回 HTML 的冲突项
    # 必须移除 host 和 content-length，让 requests 库自动根据当前请求生成
    forbidden = ['host', 'content-length', 'content-type', 'accept-encoding', 'connection', 'priority', 'sec-ch-ua']
    clean_headers = {k: v for k, v in headers.items() if k not in forbidden}
    
    # 强制注入微信环境标识
    clean_headers.update({
        "x-tap": "wx",
        "xweb_xhr": "1",
        "referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
        "user-agent": headers.get("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781 NetType/WIFI MiniProgramEnv/Windows")
    })
    
    return clean_headers, cookies

def upload_logic(session, file_bytes, file_name, headers):
    """执行图片上传"""
    t = str(int(time.time() * 1000))
    tk_full = session.cookies.get("_m_h5_tk", "")
    token = tk_full.split("_")[0] if tk_full else ""

    # 签名数据
    biz_data = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
    data_str = json.dumps(biz_data)
    sign = get_mtop_sign(token, t, APP_KEY, data_str)

    params = {
        "floderId": "0", "appkey": "fleamarket", "_input_charset": "utf-8",
        "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
    }
    
    # 构造微信版 Multipart 表单
    fields = [
        ('content-type', (None, 'multipart/form-data')),
        ('bizCode', (None, 'fleamarket')),
        ('name', (None, 'fileFromAlbum')),
        ('data', (None, data_str)),
        ('file', (file_name, file_bytes, mimetypes.guess_type(file_name)[0] or 'image/png'))
    ]

    try:
        res = session.post(UPLOAD_URL, params=params, files=fields, headers=headers, timeout=20)
        # 结果解析：兼容 JSON 和正则提取
        match = re.search(r'"url":"(https?://img\.alicdn\.com/[^"]+)"', res.text)
        if match:
            return match.group(1).replace('\\/', '/'), None
        
        if "<html" in res.text.lower():
            return None, "拦截：返回了HTML页面。请尝试更换热点或重新抓取最新的 bx-ua。"
        return None, f"上传异常: {res.text[:100]}"
    except Exception as e:
        return None, f"请求崩溃: {str(e)}"

def edit_logic(session, item_id, img_url, headers):
    """执行商品编辑"""
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
    
    # 修改 Body 发送格式，微信版必须带 data=
    send_headers = headers.copy()
    send_headers["content-type"] = "application/x-www-form-urlencoded"
    payload = f"data={urllib.parse.quote(data_str)}"
    
    try:
        res = session.post(url, params=params, data=payload, headers=send_headers)
        return res.json()
    except Exception as e:
        return {"ret": [str(e)]}

# --- Streamlit 界面 ---
st.set_page_config(page_title="闲鱼微信环境同步器", layout="wide")
st.title("🛡️ 微信小程序环境 - 主图自动同步")

if 'session' not in st.session_state:
    st.session_state.session = requests.Session()
    st.session_state.session.verify = False
if 'headers' not in st.session_state:
    st.session_state.headers = {}

l, r = st.columns(2)

with l:
    st.subheader("第一步：获取身份指纹")
    raw_text = st.text_area("粘贴 Charles/Fiddler 里的 Request Headers 全部内容", height=450, 
                            placeholder="粘贴从 host: 到 priority: 的所有内容...")
    
    if st.button("✨ 一键解析并清洗指纹", use_container_width=True):
        h, c = parse_advanced_package(raw_text)
        st.session_state.headers = h
        st.session_state.session.cookies.clear()
        for k, v in c.items():
            st.session_state.session.cookies.set(k, v)
        
        # 状态反馈
        if "_m_h5_tk" in c:
            st.success("✅ 指纹提取成功！已包含核心 Token。")
        else:
            st.error("❌ 未检测到 _m_h5_tk！请确保你复制的是点开编辑页面后的抓包。")
            if c: st.warning(f"检测到的 Cookie 字段：{list(c.keys())}")

with r:
    st.subheader("第二步：同步操作")
    iid = st.text_input("待同步商品 ID", value="1033424722209")
    up_file = st.file_uploader("上传新图")
    
    if st.button("🚀 启动微信模拟同步", use_container_width=True):
        if not st.session_state.headers:
            st.error("请先解析左侧的指纹数据！")
        elif iid and up_file:
            with st.status("正在模拟微信环境...") as s:
                # 1. 上传
                s.write("正在绕过网关上传图片...")
                img_url, err = upload_logic(st.session_state.session, up_file.read(), up_file.name, st.session_state.headers)
                
                if img_url:
                    s.write(f"✅ 图片已进入 CDN: {img_url}")
                    # 2. 修改
                    s.write("正在向闲鱼提交修改请求...")
                    res = edit_logic(st.session_state.session, iid, img_url, st.session_state.headers)
                    
                    if "SUCCESS" in str(res.get("ret")):
                        s.update(label="🎉 同步成功！", state="complete")
                        st.balloons()
                    else:
                        st.error(f"修改失败: {res.get('ret')}")
                        st.json(res)
                else:
                    st.error(f"上传环节失败: {err}")
