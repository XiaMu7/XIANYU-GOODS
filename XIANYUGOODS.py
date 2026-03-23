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

# 禁用SSL警告（对应 2.txt 逻辑）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 常量配置 ---
APP_KEY = "12574478"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL" # 来自 2.txt 的固定设备ID
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
EDIT_API = "mtop.idle.wx.idleitem.edit" # 对应你的抓包接口名

# --- 核心工具函数 ---

def get_mtop_sign(token, t, app_key, data_str):
    """计算阿里签名"""
    base_str = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def generate_random_name(ext=".jpg"):
    """生成随机文件名，增加过审率"""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=16)) + ext

def init_session():
    """初始化带有重试机制的会话"""
    s = requests.Session()
    s.verify = False # 禁用 SSL 验证，方便抓包调试
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    s.mount('https://', HTTPAdapter(max_retries=retry))
    return s

def extract_json_from_text(text):
    """从可能包含请求头的文本中提取 JSON 部分"""
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
    except:
        return None
    return None

# --- 业务逻辑函数 ---

def upload_bytes_refined(session, file_bytes, file_name):
    """高级上传逻辑：参考 2.txt"""
    t = str(int(time.time() * 1000))
    token = session.cookies.get("_m_h5_tk", "").split("_")[0]
    
    if not token:
        return None, "未找到有效 Token，请在侧边栏更新 Cookie"

    # 上传接口的 data 负载
    upload_data = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
    data_str = json.dumps(upload_data)
    sign = get_mtop_sign(token, t, APP_KEY, data_str)
    
    # 动态识别 MIME
    mime_type, _ = mimetypes.guess_type(file_name)
    mime_type = mime_type or 'image/jpeg'
    
    params = {
        "jsv": "2.7.2", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
    }
    
    # 随机化文件名
    safe_name = generate_random_name(os.path.splitext(file_name)[1])
    files = {'file': (safe_name, file_bytes, mime_type)}
    
    url = "https://acs.m.goofish.com/gw/mtop.taobao.util.uploadImage/1.0/"
    try:
        res = session.post(url, params=params, data={"data": data_str}, files=files, timeout=15)
        res_j = res.json()
        if "SUCCESS" in str(res_j.get("ret")):
            return res_j["data"]["url"], None
        return None, f"上传失败: {res_j.get('ret')}"
    except Exception as e:
        return None, f"网络请求异常: {e}"

def edit_item_refined(session, item_id, img_url, template_path):
    """修改逻辑：结合 1.txt 模板"""
    if not os.path.exists(template_path):
        return None, "模板文件 1.txt 不存在"

    with open(template_path, "r", encoding="utf-8") as f:
        content = f.read()
        data = extract_json_from_text(content)
    
    if not data:
        return None, "1.txt 格式错误，无法解析 JSON"

    # 关键字段替换
    data["itemId"] = str(item_id)
    # 替换图片列表，保持闲鱼结构
    data["images"] = [{"url": img_url, "originalUrl": img_url}]
    
    data_str = json.dumps(data, ensure_ascii=False)
    t = str(int(time.time() * 1000))
    token = session.cookies.get("_m_h5_tk", "").split("_")[0]
    sign = get_mtop_sign(token, t, APP_KEY, data_str)
    
    params = {
        "jsv": "2.7.2", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": EDIT_API, "v": "1.0", "type": "originaljson"
    }
    
    url = f"https://acs.m.goofish.com/gw/{EDIT_API}/1.0/"
    try:
        res = session.post(url, params=params, data={"data": data_str}, timeout=15)
        return res.json(), None
    except Exception as e:
        return None, f"提交修改异常: {e}"

# --- Streamlit 界面 ---

st.set_page_config(page_title="闲鱼增强版助手", page_icon="⚙️")

if 'session' not in st.session_state:
    st.session_state.session = init_session()

st.title("⚙️ 闲鱼商品全自动更新 (增强版)")
st.info("本版本已整合重试机制、固定UTDID及GIF兼容逻辑。")

with st.sidebar:
    st.header("🔑 认证中心")
    cookie_input = st.text_area("在此粘贴最新 Cookie", height=250, help="请确保包含 _m_h5_tk")
    if st.button("同步 Cookie 至会话"):
        if cookie_input:
            # 清除旧 Cookie 重新设置
            st.session_state.session.cookies.clear()
            for item in cookie_input.split(';'):
                if '=' in item:
                    k, v = item.strip().split('=', 1)
                    st.session_state.session.cookies.set(k, v)
            st.success("Cookie 已更新并生效！")
        else:
            st.error("请输入内容")

# 主操作区
col1, col2 = st.columns(2)
with col1:
    item_id = st.text_input("待修改商品 ID", placeholder="从宝贝链接中获取")
with col2:
    new_file = st.file_uploader("选择新主图", type=["jpg", "jpeg", "png", "gif"])

if st.button("🚀 立即同步到闲鱼", use_container_width=True):
    if not item_id or not new_file:
        st.warning("请补全商品 ID 或上传图片")
    elif not st.session_state.session.cookies.get("_m_h5_tk"):
        st.error("检测到 Token 缺失，请先在侧边栏粘贴 Cookie")
    else:
        with st.status("正在执行深度同步...") as status:
            # 1. 上传
            st.write("正在上传图片（使用随机文件名策略）...")
            img_url, err = upload_bytes_refined(st.session_state.session, new_file.read(), new_file.name)
            
            if img_url:
                st.write(f"✅ CDN 同步完成: {img_url}")
                # 2. 修改
                st.write("正在应用 1.txt 模板并注入 ID...")
                result, edit_err = edit_item_refined(st.session_state.session, item_id, img_url, "1.txt")
                
                if result and "SUCCESS" in str(result.get("ret")):
                    status.update(label="🎉 商品信息已完美同步！", state="complete")
                    st.balloons()
                else:
                    st.error(f"同步失败: {result.get('ret') if result else edit_err}")
                    if result: st.json(result)
            else:
                st.error(f"上传环节失败: {err}")
