import streamlit as st
import json
import requests
import time
import hashlib
import os

# --- 核心配置 ---
APP_KEY = "12574478"
MTOP_UPLOAD_API = "mtop.taobao.util.uploadImage"
MTOP_EDIT_API = "mtop.taobao.idle.item.edit"

def get_mtop_sign(token, t, app_key, data_str):
    """计算阿里 MTOP 接口所需的签名"""
    base_str = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def get_token_from_session(session):
    """从 Cookie 中提取 _m_h5_tk 校验位"""
    tk = session.cookies.get("_m_h5_tk", "")
    return tk.split("_")[0] if tk else ""

def upload_logic(session, file_bytes, file_name):
    """上传逻辑：支持根据后缀自动识别 MIME 类型"""
    t = str(int(time.time() * 1000))
    upload_data = {"bizCode": "idleItemEdit", "clientType": "pc"}
    data_str = json.dumps(upload_data)
    
    token = get_token_from_session(session)
    if not token:
        st.error("❌ Cookie 已失效或不包含 _m_h5_tk，请重新配置侧边栏！")
        return None

    sign = get_mtop_sign(token, t, APP_KEY, data_str)
    
    # 动态识别文件类型 (支持 gif)
    ext = os.path.splitext(file_name)[1].lower()
    mime_type = "image/gif" if ext == ".gif" else "image/jpeg"
    
    params = {
        "jsv": "2.7.2", "appKey": APP_KEY, "t": t, "sign": sign,
        "api": MTOP_UPLOAD_API, "v": "1.0", "type": "originaljson"
    }
    
    files = {'file': (file_name, file_bytes, mime_type)}
    url = f"https://acs.m.goofish.com/gw/{MTOP_UPLOAD_API}/1.0/"
    
    try:
        res = session.post(url, params=params, data={"data": data_str}, files=files)
        res_json = res.json()
        if "SUCCESS" in str(res_json.get("ret")):
            return res_json["data"]["url"]
        else:
            st.error(f"上传失败 ({ext}): {res_json.get('ret')}")
            return None
    except Exception as e:
        st.error(f"网络异常: {e}")
        return None

def edit_item_logic(session, item_id, new_img_url, template_path):
    """应用 1.txt 模板并更新商品"""
    if not os.path.exists(template_path):
        st.error(f"找不到模板文件: {template_path}")
        return None

    with open(template_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 替换关键字段
    data["itemId"] = item_id
    # 闲鱼商品图片是一个列表，此处替换为新上传的 URL
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
    res = session.post(url, params=params, data={"data": data_str})
    return res.json()

# --- Streamlit UI ---
st.set_page_config(page_title="闲鱼商品助手", page_icon="🐠")

st.title("🐠 闲鱼商品主图快速替换")

# 初始化 Session
if 's' not in st.session_state:
    st.session_state.s = requests.Session()

# 侧边栏配置
with st.sidebar:
    st.header("🔑 账户配置")
    raw_cookie = st.text_area("粘贴完整 Cookie", height=200, help="从 Charles 或 F12 复制")
    if st.button("保存并生效"):
        for c in raw_cookie.split(';'):
            if '=' in c:
                k, v = c.strip().split('=', 1)
                st.session_state.s.cookies.set(k, v)
        st.success("Cookie 已存入会话！")

# 主界面
target_id = st.text_input("目标商品 ID (itemId)", placeholder="如: 7752686815")
up_file = st.file_uploader("选择本地图片 (支持 jpg/png/gif)", type=["jpg", "jpeg", "png", "gif"])

if st.button("🚀 执行同步修改", use_container_width=True):
    if not target_id or not up_file:
        st.warning("请检查 ID 和图片是否已就绪。")
    else:
        with st.status("正在处理中...") as status:
            # 第一步：上传
            st.write(f"正在上传 {up_file.name} ...")
            img_url = upload_logic(st.session_state.s, up_file.read(), up_file.name)
            
            if img_url:
                st.write(f"✅ 上传成功：{img_url}")
                # 第二步：修改信息
                st.write("正在应用 1.txt 模板并更新...")
                edit_res = edit_item_logic(st.session_state.s, target_id, img_url, "1.txt")
                
                if edit_res and "SUCCESS" in str(edit_res.get("ret")):
                    status.update(label="🎉 商品修改成功！", state="complete")
                    st.balloons()
                else:
                    st.error(f"同步失败：{edit_res.get('ret')}")
                    st.json(edit_res)
