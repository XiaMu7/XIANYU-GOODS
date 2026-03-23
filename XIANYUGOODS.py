import streamlit as st
import json
import requests
import time
import hashlib
import os
import re
import mimetypes
import urllib.parse
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 微信版专用常量 ---
APP_KEY = "12574478"
# 根据你的抓包，这是修改商品的 API
EDIT_API = "mtop.idle.wx.idleitem.edit"
# 微信版上传图片的可能 API（如果这个报错，我们需要抓一个上传图片的包）
UPLOAD_API = "mtop.taobao.util.uploadImage" 

def get_mtop_sign(token, t, app_key, data_str):
    """计算阿里签名"""
    base_str = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def init_session():
    s = requests.Session()
    s.verify = False
    # 模拟微信环境的 User-Agent
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 MicroMessenger/7.0.20.1781 NetType/WIFI MiniProgramEnv/Windows",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
        "content-type": "application/x-www-form-urlencoded"
    })
    return s

def upload_logic_wx(session, file_bytes, file_name):
    """上传逻辑（尝试适配微信网关）"""
    t = str(int(time.time() * 1000))
    tk_full = session.cookies.get("_m_h5_tk", "")
    if not tk_full: return None, "请先在侧边栏更新 Cookie"
    
    token = tk_full.split("_")[0]
    upload_data = {"bizCode": "idleItemEdit", "clientType": "pc"}
    data_str = json.dumps(upload_data)
    sign = get_mtop_sign(token, t, APP_KEY, data_str)
    
    # 微信版的上传 URL 往往带有 /h5/ 前缀
    url = f"https://acs.m.goofish.com/gw/{UPLOAD_API}/1.0/"
    params = {
        "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": UPLOAD_API, "v": "1.0", "type": "originaljson"
    }
    
    mime_type = mimetypes.guess_type(file_name)[0] or 'image/jpeg'
    files = {'file': (file_name, file_bytes, mime_type)}
    
    try:
        # 上传时不要带全局的 content-type，由 requests 自动生成 multipart
        res = session.post(url, params=params, data={"data": data_str}, files=files, headers={"content-type": None})
        res_j = res.json()
        if "SUCCESS" in str(res_j.get("ret")):
            return res_j["data"]["url"], None
        return None, f"上传失败: {res_j.get('ret')}"
    except Exception as e:
        return None, str(e)

def edit_item_wx(session, item_id, img_url, template_path):
    """编辑逻辑：完全匹配你提供的 POST 数据结构"""
    if not os.path.exists(template_path): return None, "缺少 1.txt"
    
    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
        # 提取 JSON 负载
        json_match = re.search(r'data=(%7B.*%7D)', content)
        if json_match:
            raw_json = urllib.parse.unquote(json_match.group(1))
            data = json.loads(raw_json)
        else:
            # 尝试直接解析全文件 JSON
            data = json.loads(content[content.find('{'):content.rfind('}')+1])

    # 核心替换：ID 和 图片
    data["itemId"] = str(item_id)
    # 匹配抓包中的 imageInfoDOList 结构
    data["imageInfoDOList"] = [{
        "major": True, "type": 0, "url": img_url, "widthSize": "640", "heightSize": "640"
    }]
    
    data_str = json.dumps(data, ensure_ascii=False)
    t = str(int(time.time() * 1000))
    tk = session.cookies.get("_m_h5_tk", "").split("_")[0]
    sign = get_mtop_sign(tk, t, APP_KEY, data_str)
    
    # 匹配你抓包中的请求 URL 格式
    url = f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/2.0/"
    params = {
        "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
        "v": "1.0", "type": "originaljson", "api": EDIT_API, "dataType": "json"
    }
    
    # 微信版必须用 data= 这种 form 格式
    payload = f"data={urllib.parse.quote(data_str)}"
    
    res = session.post(url, params=params, data=payload)
    return res.json(), None

# --- Streamlit UI ---
st.set_page_config(page_title="微信闲鱼同步器")
st.title("微信版闲鱼 - 商品主图同步")

if 'session' not in st.session_state:
    st.session_state.session = init_session()

with st.sidebar:
    st.header("🔑 认证")
    ck = st.text_area("在此粘贴从微信抓包获取的 Cookie", height=250)
    if st.button("保存 Cookie"):
        for item in ck.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                st.session_state.session.cookies.set(k, v)
        st.success("Cookie 已加载")

target_id = st.text_input("宝贝 itemId", placeholder="例如: 1033424722209")
up_file = st.file_uploader("选择新图片", type=["jpg","png","gif"])

if st.button("🚀 执行微信环境同步"):
    if not target_id or not up_file:
        st.error("请填写 ID 并上传图片")
    else:
        with st.status("正在模拟微信请求...") as s:
            url, err = upload_logic_wx(st.session_state.session, up_file.read(), up_file.name)
            if url:
                st.write(f"✅ 图片上传成功: {url}")
                res, e_err = edit_item_wx(st.session_state.session, target_id, url, "1.txt")
                if res and "SUCCESS" in str(res.get("ret")):
                    s.update(label="🎉 修改成功！", state="complete")
                    st.balloons()
                else:
                    st.error(f"修改失败: {res.get('ret') if res else e_err}")
                    if res: st.json(res)
            else:
                st.error(f"上传环节失败: {err}")
