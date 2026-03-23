import streamlit as st
import json
import requests
import time
import hashlib
import mimetypes
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 微信版专用配置 ---
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
EDIT_API = "mtop.idle.wx.idleitem.edit"
APP_KEY = "12574478"

def init_session():
    s = requests.Session()
    s.verify = False
    # 必须包含 xweb_xhr 和正确的 Referer
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
        "xweb_xhr": "1",
        "accept": "*/*"
    })
    return s

def upload_to_wechat_goofish(session, file_bytes, file_name):
    """
    完全对齐抓包数据的上传逻辑
    """
    # 1. URL 参数
    params = {
        "floderId": "0",
        "appkey": "fleamarket",
        "_input_charset": "utf-8"
    }
    
    # 2. 构造 Multipart 表单 (严格按照抓包顺序)
    mime_type = mimetypes.guess_type(file_name)[0] or 'image/png'
    
    # 注意：在 requests 中，这些字段会按照字典顺序或元组顺序发送
    # 微信后端有时依赖字段顺序，建议使用元组列表
    files = [
        ('content-type', (None, 'multipart/form-data')),
        ('bizCode', (None, 'fleamarket')),
        ('name', (None, 'fileFromAlbum')),
        ('file', (file_name, file_bytes, mime_type))
    ]

    try:
        # 发送请求
        # 注意：不要手动设置 Content-Type，让 requests 自动生成带 boundary 的 Header
        res = session.post(UPLOAD_URL, params=params, files=files, timeout=20)
        
        # 打印调试信息（可选）
        # st.write(f"服务器原始响应: {res.text}")
        
        if res.status_code == 200:
            res_j = res.json()
            # 微信版返回通常直接包含 url 字段
            if res_j.get("success") or "url" in res_j:
                return res_j.get("url"), None
            return None, f"上传失败: {res_j.get('message') or res.text}"
        else:
            return None, f"HTTP错误: {res.status_code}"
            
    except Exception as e:
        return None, f"上传异常: {str(e)}"

def edit_item_wx(session, item_id, img_url):
    """
    执行微信版修改逻辑 (使用之前校准过的路径)
    """
    t = str(int(time.time() * 1000))
    tk = session.cookies.get("_m_h5_tk", "").split("_")[0]
    
    data = {
        "itemId": str(item_id),
        "imageInfoDOList": [{"major":True,"type":0,"url":img_url,"widthSize":"640","heightSize":"640"}],
        "utdid": "v3UyIt1jJFECAXAaAnEns/UL",
        "platform": "windows"
    }
    data_str = json.dumps(data, ensure_ascii=False)
    sign = hashlib.md5(f"{tk}&{t}&{APP_KEY}&{data_str}".encode('utf-8')).hexdigest()

    url = f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/2.0/"
    params = {
        "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
        "v": "1.0", "type": "originaljson", "api": EDIT_API
    }
    
    res = session.post(url, params=params, data={"data": data_str})
    return res.json()

# --- Streamlit UI ---
st.title("🐠 闲鱼微信版 - 主图同步工具")

if 'session' not in st.session_state:
    st.session_state.session = init_session()

with st.sidebar:
    ck = st.text_area("粘贴抓包的完整 Cookie", height=300)
    if st.button("更新 Cookie"):
        # 清除旧 Cookie 并设置新 Cookie
        st.session_state.session.cookies.clear()
        for item in ck.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                st.session_state.session.cookies.set(k.strip(), v.strip())
        st.success("Cookie 已更新")

iid = st.text_input("商品 ID (itemId)", value="1033424722209")
up_file = st.file_uploader("选择新主图")

if st.button("🚀 启动同步"):
    if iid and up_file:
        with st.spinner("正在上传图片到阿里 CDN..."):
            img_url, err = upload_to_wechat_goofish(st.session_state.session, up_file.read(), up_file.name)
            
            if img_url:
                st.success(f"图片上传成功!")
                with st.spinner("正在同步到商品详情..."):
                    res = edit_item_wx(st.session_state.session, iid, img_url)
                    if "SUCCESS" in str(res.get("ret")):
                        st.success("🎉 同步成功！")
                        st.balloons()
                    else:
                        st.error(f"修改失败: {res.get('ret')}")
                        st.json(res)
            else:
                st.error(f"上传环节失败: {err}")
