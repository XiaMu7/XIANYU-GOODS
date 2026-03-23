import streamlit as st
import json
import requests
import time
import hashlib
import os
import re
import random
import string
import mimetypes
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 常量配置 ---
APP_KEY = "12574478"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL" 
EDIT_API = "mtop.idle.wx.idleitem.edit"

def get_mtop_sign(token, t, app_key, data_str):
    base_str = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def init_session():
    s = requests.Session()
    s.verify = False 
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://2.taobao.com/"
    })
    retry = Retry(total=2, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    s.mount('https://', HTTPAdapter(max_retries=retry))
    return s

def upload_logic_final(session, file_bytes, file_name):
    """
    多模式兼容上传：自动尝试 stream-upload 和 h5api 两种网关
    """
    t = str(int(time.time() * 1000))
    tk_full = session.cookies.get("_m_h5_tk", "")
    if not tk_full:
        return None, "未检测到有效 Cookie，请在侧边栏重新粘贴"
    
    token = tk_full.split("_")[0]
    upload_params = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
    data_str = json.dumps(upload_params)
    sign = get_mtop_sign(token, t, APP_KEY, data_str)
    
    # 尝试不同的接口地址（模式1：2.txt 模式；模式2：1.txt 模式）
    endpoints = [
        ("https://stream-upload.goofish.com/api/upload.api", "stream"),
        ("https://h5api.m.goofish.com/gw/mtop.taobao.util.uploadImage/1.0/", "h5api")
    ]
    
    last_err = ""
    for url, mode in endpoints:
        params = {
            "jsv": "2.7.2", "appKey": APP_KEY, "t": t, "sign": sign,
            "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
        }
        
        mime_type = mimetypes.guess_type(file_name)[0] or 'image/jpeg'
        safe_name = "".join(random.choices(string.ascii_letters + string.digits, k=16)) + os.path.splitext(file_name)[1]
        
        # 针对不同接口调整表单结构
        if mode == "stream":
            files = {'file': (safe_name, file_bytes, mime_type), 'data': (None, data_str)}
        else:
            files = {'file': (safe_name, file_bytes, mime_type)}
            # h5api 模式下 data 往往在 params 或 body 字段里
        
        try:
            res = session.post(url, params=params, files=files, timeout=15)
            # 关键：检查是否返回了 JSON
            if res.status_code != 200:
                last_err = f"服务器返回错误码: {res.status_code}"
                continue
            
            res_j = res.json() # 这里容易报错，如果返回的是 HTML
            if "SUCCESS" in str(res_j.get("ret")):
                return res_j["data"]["url"], None
            else:
                last_err = str(res_j.get("ret"))
        except Exception as e:
            last_err = f"模式 {mode} 请求失败: {str(e)}"
            continue
            
    return None, f"所有上传模式均失败。最后一次错误: {last_err}"

def edit_item_logic(session, item_id, img_url, template_path):
    if not os.path.exists(template_path):
        return None, "找不到 1.txt"
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if not match: return None, "模板内未发现JSON"
        data = json.loads(match.group())

    data["itemId"] = str(item_id)
    data["images"] = [{"url": img_url, "originalUrl": img_url}]
    
    data_str = json.dumps(data, ensure_ascii=False)
    t = str(int(time.time() * 1000))
    tk = session.cookies.get("_m_h5_tk", "").split("_")[0]
    sign = get_mtop_sign(tk, t, APP_KEY, data_str)
    
    params = {
        "jsv": "2.7.2", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": EDIT_API, "v": "1.0", "type": "originaljson"
    }
    
    url = f"https://acs.m.goofish.com/gw/{EDIT_API}/1.0/"
    res = session.post(url, params=params, data={"data": data_str})
    return res.json(), None

# --- UI ---
st.set_page_config(page_title="闲鱼同步助手", layout="wide")
st.title("🚀 闲鱼商品替换工具 (多模式版)")

if 'session' not in st.session_state:
    st.session_state.session = init_session()

with st.sidebar:
    st.header("🔑 认证配置")
    ck = st.text_area("在此粘贴最新 Cookie", height=300)
    if st.button("更新 Cookie"):
        st.session_state.session.cookies.clear()
        for item in ck.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                st.session_state.session.cookies.set(k, v)
        st.success("Cookie 已加载")

col1, col2 = st.columns(2)
with col1:
    item_id_in = st.text_input("商品 ID")
with col2:
    file_in = st.file_uploader("选择主图", type=["jpg","png","gif"])

if st.button("执行同步"):
    if not item_id_in or not file_in:
        st.warning("请检查输入")
    else:
        with st.spinner("正在尝试多种模式上传..."):
            url, err = upload_logic_final(st.session_state.session, file_in.read(), file_in.name)
            if url:
                st.write("✅ 图片上传成功")
                res, e_err = edit_item_logic(st.session_state.session, item_id_in, url, "1.txt")
                if res and "SUCCESS" in str(res.get("ret")):
                    st.success("🎉 商品修改成功！")
                    st.balloons()
                else:
                    st.error(f"编辑失败: {res.get('ret') if res else e_err}")
            else:
                st.error(err)

# --- 报错原因分析 ---
st.divider()
st.subheader("❌ 报错详解：Expecting value: line 2 column 1")
st.markdown("""
**原因一：接口被拦截（最常见）**
当你频繁上传或 Cookie 异常时，服务器会返回一个 **HTML 验证码页面** 或 **WAF 拦截页面**。脚本预期收到 JSON（类似 `{"ret":...}`），但实际收到了 `<!DOCTYPE html>...`。因为 HTML 的第二行通常是空的或不是 `{` 开头，所以 Python 报错“解析 JSON 失败”。

**原因二：域名无法解析**
`stream-upload.goofish.com` 是闲鱼内部域名，有时在某些网络环境下（如公司内网、特定梯子）无法访问，导致返回了运营商的错误导航页。

**原因三：MIME 类型不匹配**
如果上传 GIF 但没有正确设置 `image/gif`，部分网关会直接断开连接或报错，导致返回内容为空。

**本次修复改进：**
* **加入了 `res.status_code` 检查**：只有当服务器返回 200 时才尝试解析 JSON，避免直接崩溃。
* **增加了 H5API 备用网关**：如果 `stream-upload` 报错，会自动切换到 `h5api.m.goofish.com`。
* **强化了 Header**：模拟了真实的浏览器 Referer 和 UA。
""")
