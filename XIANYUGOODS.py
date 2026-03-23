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

# --- 常量配置（源自 2.txt 和 1.txt） ---
APP_KEY = "12574478"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL" 
# 上传接口改用 2.txt 中的流式专用地址
STREAM_UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
# 编辑接口
EDIT_API = "mtop.idle.wx.idleitem.edit"

def get_mtop_sign(token, t, app_key, data_str):
    """计算标准阿里签名"""
    base_str = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def init_session():
    s = requests.Session()
    s.verify = False 
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    s.mount('https://', HTTPAdapter(max_retries=retry))
    return s

def upload_logic_v2(session, file_bytes, file_name):
    """
    采用 2.txt 中的 stream-upload 逻辑，绕过 API_NOT_FOUND 错误
    """
    t = str(int(time.time() * 1000))
    # 提取最新的 token
    tk = session.cookies.get("_m_h5_tk", "").split("_")[0]
    if not tk:
        return None, "未检测到有效 _m_h5_tk，请更新侧边栏 Cookie"

    # 业务参数
    upload_params = {
        "bizCode": "idleItemEdit",
        "clientType": "pc",
        "utdid": FIXED_UTDID
    }
    data_str = json.dumps(upload_params)
    sign = get_mtop_sign(tk, t, APP_KEY, data_str)
    
    # 构建请求参数
    params = {
        "jsv": "2.7.2",
        "appKey": APP_KEY,
        "t": t,
        "sign": sign,
        "api": "mtop.taobao.util.uploadImage",
        "v": "1.0",
        "type": "originaljson",
        "dataType": "json"
    }
    
    # 自动识别 MIME 
    mime_type, _ = mimetypes.guess_type(file_name)
    mime_type = mime_type or 'image/jpeg'
    
    # 随机化文件名
    safe_name = "".join(random.choices(string.ascii_letters + string.digits, k=16)) + os.path.splitext(file_name)[1]
    
    files = {
        'file': (safe_name, file_bytes, mime_type),
        'data': (None, data_str) # 2.txt 中 data 是作为 multipart 的一部分发送的
    }
    
    try:
        # 尝试使用 stream-upload 域名
        res = session.post(STREAM_UPLOAD_URL, params=params, files=files, timeout=20)
        res_j = res.json()
        
        if "SUCCESS" in str(res_j.get("ret")):
            return res_j["data"]["url"], None
        else:
            return None, f"上传失败: {res_j.get('ret')}"
    except Exception as e:
        return None, f"请求异常: {str(e)}"

def edit_item_logic(session, item_id, img_url, template_path):
    """根据 1.txt 模板更新商品"""
    if not os.path.exists(template_path):
        return None, "找不到模板文件 1.txt"

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
        # 提取 JSON
        try:
            start = content.find('{')
            end = content.rfind('}')
            data = json.loads(content[start:end+1])
        except:
            return None, "1.txt JSON 解析失败"

    # 替换 ID 和图片
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

# --- UI 界面 ---
st.title("🐠 闲鱼商品替换终极版")

if 'session' not in st.session_state:
    st.session_state.session = init_session()

with st.sidebar:
    st.header("🔑 认证")
    ck = st.text_area("粘贴完整 Cookie", height=200)
    if st.button("更新并保存"):
        st.session_state.session.cookies.clear()
        for item in ck.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                st.session_state.session.cookies.set(k, v)
        st.success("Cookie 已加载")

item_id_in = st.text_input("商品 ID")
file_in = st.file_uploader("选择主图", type=["jpg","png","gif"])

if st.button("🚀 启动同步", use_container_width=True):
    if not item_id_in or not file_in:
        st.warning("请检查 ID 或图片")
    else:
        with st.status("处理中...") as s:
            url, err = upload_logic_v2(st.session_state.session, file_in.read(), file_in.name)
            if url:
                st.write("✅ 图片上传成功")
                res, e_err = edit_item_logic(st.session_state.session, item_id_in, url, "1.txt")
                if res and "SUCCESS" in str(res.get("ret")):
                    s.update(label="🎉 同步成功！", state="complete")
                    st.balloons()
                else:
                    st.error(f"编辑失败: {res.get('ret') if res else e_err}")
            else:
                st.error(f"上传失败: {err}")

# --- 底部错误原因详解 ---
st.divider()
with st.expander("❓ 为什么会出现 'FAIL_SYS_API_NOT_FOUNDED'？", expanded=True):
    st.markdown("""
    **主要原因有以下几点：**
    1. **网关不匹配**：闲鱼的图片上传（Upload）和商品编辑（Edit）虽然都属于 MTOP 协议，但它们部署在不同的服务器集群。如果你向 `acs.m.goofish.com`（主要处理商品逻辑）发送一个图片上传指令，它可能找不到对应的处理程序。
    2. **请求路径错误**：阿里接口的 URL 路径（例如 `/gw/api/v1/...`）必须与参数中的 `api` 字段完全对应。如果路径指向 H5 网关，但 API 参数写成了 PC 端的名称，就会触发此报错。
    3. **参数位置错误**：在上传文件时，`data` 字段（包含 bizCode 等信息）有时必须作为 `multipart/form-data` 的一个 Part 发送，而不仅仅是 URL 参数。
    4. **JSV 版本过低**：如果 `jsv` 版本（如 2.4.12）在某些新域名下已停用，也会报找不到 API。
    
    **本次修复方案：**
    * 强制将图片上传地址切换至 `stream-upload.goofish.com`（专为图片设计的流式网关）。
    * 将 `data` 参数同时放入 `multipart` 表单中，确保网关能正确解析。
    """)
