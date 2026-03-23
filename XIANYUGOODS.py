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

# --- 核心常量 (严格对齐你的 2.txt 和抓包) ---
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
EDIT_API = "mtop.idle.wx.idleitem.edit"
APP_KEY = "12574478"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

def get_mtop_sign(token, t, app_key, data_str):
    base_str = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def upload_to_wechat(session, file_bytes, file_name):
    """
    完全模拟微信小程序上传：严格字段顺序 + XWeb Header
    """
    t = str(int(time.time() * 1000))
    tk_full = session.cookies.get("_m_h5_tk", "")
    if not tk_full: return None, "未检测到Cookie，请在侧边栏粘贴"
    token = tk_full.split("_")[0]

    # 1. URL 参数
    params = {
        "floderId": "0",
        "appkey": "fleamarket",
        "_input_charset": "utf-8",
        "jsv": "2.4.12",
        "appKey": APP_KEY,
        "t": t,
        "api": "mtop.taobao.util.uploadImage",
        "v": "1.0",
        "type": "originaljson"
    }
    
    # 2. 计算签名 (针对上传业务)
    upload_biz = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
    data_str = json.dumps(upload_biz)
    params["sign"] = get_mtop_sign(token, t, APP_KEY, data_str)

    # 3. 构造 Multipart 字段 (注意：顺序必须是 content-type -> bizCode -> name -> file)
    mime_type = mimetypes.guess_type(file_name)[0] or 'image/png'
    fields = [
        ('content-type', (None, 'multipart/form-data')),
        ('bizCode', (None, 'fleamarket')),
        ('name', (None, 'fileFromAlbum')),
        ('data', (None, data_str)), # 2.txt 里的逻辑要求这个
        ('file', (file_name, file_bytes, mime_type))
    ]

    # 4. 模拟微信 XWeb 特有请求头
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows",
        "xweb_xhr": "1",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
        "Accept": "*/*"
    }

    try:
        # 发送请求时强行清空 session 中可能存在的干扰 content-type
        res = session.post(UPLOAD_URL, params=params, files=fields, headers=headers, timeout=20)
        
        if res.status_code == 200:
            # 兼容处理：正则提取 URL，防止 JSON 解析失败
            match = re.search(r'"url":"(https?://img\.alicdn\.com/[^"]+)"', res.text)
            if match:
                return match.group(1).replace('\\/', '/'), None
            
            res_j = res.json()
            if "url" in res_j: return res_j["url"], None
            if "data" in res_j and "url" in res_j["data"]: return res_j["data"]["url"], None
            return None, f"上传失败，返回内容: {res.text}"
        else:
            return None, f"HTTP状态码错误: {res.status_code}"
    except Exception as e:
        return None, f"网络异常: {str(e)}"

def edit_item_wx(session, item_id, img_url):
    """
    微信小程序版商品修改逻辑
    """
    t = str(int(time.time() * 1000))
    tk = session.cookies.get("_m_h5_tk", "").split("_")[0]
    
    # 构造微信要求的 Body
    edit_data = {
        "itemId": str(item_id),
        "imageInfoDOList": [{"major":True,"type":0,"url":img_url,"widthSize":"640","heightSize":"640"}],
        "utdid": FIXED_UTDID,
        "platform": "windows"
    }
    data_str = json.dumps(edit_data, ensure_ascii=False)
    sign = get_mtop_sign(tk, t, APP_KEY, data_str)

    # 使用你抓包确认的微信专用 H5 路径
    url = f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/2.0/"
    params = {
        "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
        "v": "1.0", "type": "originaljson", "api": EDIT_API, "dataType": "json"
    }
    
    # 微信小程序通常在 body 中传 data=...
    res = session.post(url, params=params, data={"data": data_str})
    return res.json()

# --- Streamlit 界面 ---
st.set_page_config(page_title="微信闲鱼主图同步", layout="centered")
st.title("🐠 闲鱼微信版 - 主图同步工具")

if 'session' not in st.session_state:
    st.session_state.session = requests.Session()
    st.session_state.session.verify = False

with st.sidebar:
    st.header("🔑 认证配置")
    raw_ck = st.text_area("在此粘贴从微信抓到的完整 Cookie", height=300)
    if st.button("更新 Cookie"):
        st.session_state.session.cookies.clear()
        for item in raw_ck.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                st.session_state.session.cookies.set(k, v)
        st.success("Cookie 已加载！")

st.info("提示：此版本专门针对微信小程序环境，请确保使用小程序中的 Cookie。")

iid = st.text_input("待修改商品 ID", placeholder="例如: 1033424722209")
up_file = st.file_uploader("选择电脑上的新图 (JPG/PNG)")

if st.button("🚀 开始同步更新", use_container_width=True):
    if not iid or not up_file:
        st.warning("请完整填写 ID 并选择图片")
    else:
        with st.status("正在执行同步...") as status:
            # 1. 执行微信版上传
            status.write("正在通过流式网关上传图片...")
            img_url, err = upload_to_wechat(st.session_state.session, up_file.read(), up_file.name)
            
            if img_url:
                status.write(f"✅ 图片上传成功")
                # 2. 执行商品编辑
                status.write("正在提交修改到闲鱼服务器...")
                res = edit_item_wx(st.session_state.session, iid, img_url)
                
                if "SUCCESS" in str(res.get("ret")):
                    status.update(label="🎉 同步成功！", state="complete")
                    st.balloons()
                    st.success(f"商品 {iid} 的主图已更新为：\n{img_url}")
                else:
                    st.error(f"修改失败: {res.get('ret')}")
                    st.json(res)
            else:
                st.error(f"上传失败原因: {err}")
