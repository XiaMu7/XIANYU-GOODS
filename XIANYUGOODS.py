import streamlit as st
import json
import requests
import time
import hashlib
from io import BytesIO

# --- 核心配置 ---
APP_KEY = "12574478"
MTOP_UPLOAD_API = "mtop.taobao.util.uploadImage"
MTOP_EDIT_API = "mtop.taobao.idle.item.edit"

def get_mtop_sign(token, t, app_key, data_str):
    """计算阿里 MTOP 接口所需的 MD5 签名"""
    # 签名算法：token + & + timestamp + & + appkey + & + data内容
    base_str = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def get_token_from_session(session):
    """从 requests.Session 的 Cookie 中提取 _m_h5_tk 的前 32 位"""
    tk = session.cookies.get("_m_h5_tk", "")
    return tk.split("_")[0] if tk else ""

def upload_image_logic(session, img_bytes):
    """步骤 1: 上传本地图片字节流，获取阿里 CDN URL"""
    t = str(int(time.time() * 1000))
    # 这里的 bizCode 根据抓包建议保持一致
    upload_data = {"bizCode": "idleItemEdit", "clientType": "pc"}
    data_str = json.dumps(upload_data)
    
    token = get_token_from_session(session)
    sign = get_mtop_sign(token, t, APP_KEY, data_str)
    
    params = {
        "jsv": "2.7.2", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": MTOP_UPLOAD_API, "v": "1.0", "type": "originaljson"
    }
    
    # 模拟抓包中的 multipart/form-data 上传
    files = {'file': ('item_img.jpg', img_bytes, 'image/jpeg')}
    
    url = f"https://acs.m.goofish.com/gw/{MTOP_UPLOAD_API}/1.0/"
    try:
        res = session.post(url, params=params, data={"data": data_str}, files=files)
        res_json = res.json()
        if "SUCCESS" in res_json.get("ret", [""])[0]:
            return res_json["data"]["url"]
        else:
            st.error(f"CDN 上传失败: {res_json.get('ret')}")
            return None
    except Exception as e:
        st.error(f"上传异常: {e}")
        return None

def edit_item_logic(session, item_id, new_img_url, template_path):
    """步骤 2: 读取 1.txt 模板，替换关键信息并提交修改"""
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        st.error(f"无法读取模板文件 {template_path}: {e}")
        return None

    # 核心字段替换 (依据“抓包-修改了图片.txt”)
    data["itemId"] = item_id
    # 注意：如果抓包里 images 包含更多字段（如 fileId），需在此处补齐
    data["images"] = [{"url": new_img_url, "originalUrl": new_img_url}]
    
    data_str = json.dumps(data, ensure_ascii=False)
    t = str(int(time.time() * 1000))
    token = get_token_from_session(session)
    sign = get_mtop_sign(token, t, APP_KEY, data_str)
    
    params = {
        "jsv": "2.7.2", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": MTOP_EDIT_API, "v": "1.0", "type": "originaljson"
    }
    
    url = f"https://acs.m.goofish.com/gw/{MTOP_EDIT_API}/1.0/"
    try:
        res = session.post(url, params=params, data={"data": data_str})
        return res.json()
    except Exception as e:
        st.error(f"修改接口请求异常: {e}")
        return None

# --- Streamlit 界面渲染 ---

st.set_page_config(page_title="闲鱼商品图片修改助手", layout="centered")

st.title("📦 闲鱼商品图片一键修改")
st.caption("基于 Python Streamlit + MTOP 接口协议实现")

# 初始化 Session (持久化 Cookie)
if 'session' not in st.session_state:
    st.session_state.session = requests.Session()

# 侧边栏：配置 Cookie（通常通过抓包获取浏览器或 App 的 Cookie）
with st.sidebar:
    st.header("🔑 认证配置")
    cookie_str = st.text_area("粘贴你的闲鱼 Cookie (包含 _m_h5_tk)", height=150)
    if st.button("更新 Cookie"):
        if cookie_str:
            for item in cookie_str.split(';'):
                if '=' in item:
                    k, v = item.strip().split('=', 1)
                    st.session_state.session.cookies.set(k, v)
            st.success("Cookie 已加载！")

# 主界面：操作区
col1, col2 = st.columns([2, 1])
with col1:
    target_item_id = st.text_input("商品 ID (itemId)", placeholder="请输入你要修改的商品 ID")
with col2:
    uploaded_file = st.file_uploader("选择新图片", type=["jpg", "png", "jpeg"])

if st.button("🚀 开始同步修改", use_container_width=True):
    if not target_item_id or not uploaded_file:
        st.warning("请填写完整的商品 ID 并上传图片文件！")
    elif not st.session_state.session.cookies.get("_m_h5_tk"):
        st.error("请在侧边栏配置有效的 Cookie (需包含 _m_h5_tk)！")
    else:
        with st.status("正在执行自动化流程...") as status:
            # 1. 上传图片
            st.write("正在读取本地文件并上传至阿里 CDN...")
            img_bytes = uploaded_file.read()
            remote_url = upload_image_logic(st.session_state.session, img_bytes)
            
            if remote_url:
                st.write(f"✅ 图片托管成功: {remote_url}")
                
                # 2. 修改商品
                st.write("正在应用 1.txt 模板并提交修改...")
                result = edit_item_logic(st.session_state.session, target_item_id, remote_url, "1.txt")
                
                if result and "SUCCESS" in result.get("ret", [""])[0]:
                    status.update(label="🎉 商品图片修改成功！", state="complete")
                    st.balloons()
                else:
                    st.error(f"同步失败: {result.get('ret') if result else '未知错误'}")
                    if result: st.json(result)

st.divider()
st.info("💡 提示：修改前请确保 1.txt 与本脚本在同一目录下，且 1.txt 包含完整的 data 结构。")
