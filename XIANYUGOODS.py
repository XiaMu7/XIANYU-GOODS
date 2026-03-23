import streamlit as st
import json
import requests
import time
import hashlib
import os
import mimetypes
import urllib.parse
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 核心常量 (严格匹配 2.txt) ---
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
EDIT_API = "mtop.idle.wx.idleitem.edit"
APP_KEY = "12574478"
# 这是你文件中固定的 utdid，非常重要
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

def init_session():
    s = requests.Session()
    s.verify = False
    # 模拟微信环境的 UA，必须和抓包一致
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 MicroMessenger/7.0.20.1781 NetType/WIFI MiniProgramEnv/Windows",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html"
    })
    return s

def upload_to_fleamarket_v3(session, file_bytes, file_name):
    """
    完全照搬 2.txt 中的 upload_bytes 逻辑
    """
    t = str(int(time.time() * 1000))
    # 提取签名用的 Token
    tk_full = session.cookies.get("_m_h5_tk", "")
    if not tk_full: return None, "未检测到有效 Cookie，请在侧边栏更新"
    token = tk_full.split("_")[0]

    # 1. 构造上传业务参数 (data 字段)
    upload_biz_params = {
        "bizCode": "idleItemEdit",
        "clientType": "pc",
        "utdid": FIXED_UTDID
    }
    data_str = json.dumps(upload_biz_params)

    # 2. 计算上传签名 (签名对象是 data_str)
    base_sign = f"{token}&{t}&{APP_KEY}&{data_str}"
    sign = hashlib.md5(base_sign.encode('utf-8')).hexdigest()

    # 3. 构造请求参数 (URL 后面带的部分)
    params = {
        "jsv": "2.4.12",
        "appKey": APP_KEY,
        "t": t,
        "sign": sign,
        "api": "mtop.taobao.util.uploadImage",
        "v": "1.0",
        "type": "originaljson",
        "dataType": "json"
    }
    
    # 4. 构造 Multipart 表单 (关键点：data 必须作为一个 Part 发送)
    mime_type = mimetypes.guess_type(file_name)[0] or 'image/jpeg'
    files = {
        'file': (file_name, file_bytes, mime_type),
        'data': (None, data_str) # 必须有这个 data part，否则报 SYS_ERROR
    }

    try:
        # 使用你在抓包里看到的那个带有 appkey=fleamarket 的 URL 前缀
        # 混合 2.txt 的逻辑
        target_url = "https://stream-upload.goofish.com/api/upload.api"
        # 额外增加微信抓包里看到的参数
        params["appkey"] = "fleamarket" 
        
        res = session.post(target_url, params=params, files=files, timeout=20)
        
        # 调试信息打印在网页上，方便看报错
        # st.write(f"调试：服务器原始返回：{res.text}")
        
        res_j = res.json()
        if "SUCCESS" in str(res_j.get("ret")) or res_j.get("success") == True:
            # 兼容不同返回格式
            url = res_j.get("url") or res_j.get("data", {}).get("url")
            return url, None
        
        return None, f"上传失败: {res_j.get('message') or res_j.get('ret')}"
            
    except Exception as e:
        return None, f"上传环节崩溃: {str(e)}"

def edit_item_wx(session, item_id, img_url):
    """
    完全适配微信版编辑逻辑
    """
    t = str(int(time.time() * 1000))
    tk = session.cookies.get("_m_h5_tk", "").split("_")[0]
    
    # 修改数据
    edit_data = {
        "itemId": str(item_id),
        "imageInfoDOList": [{"major":True,"type":0,"url":img_url,"widthSize":"640","heightSize":"640"}],
        "utdid": FIXED_UTDID,
        "platform": "windows"
    }
    data_str = json.dumps(edit_data, ensure_ascii=False)
    
    # 计算签名
    sign = hashlib.md5(f"{tk}&{t}&{APP_KEY}&{data_str}".encode('utf-8')).hexdigest()

    # 路径使用你抓包看到的特殊路径
    url = f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/2.0/"
    params = {
        "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
        "v": "1.0", "type": "originaljson", "api": EDIT_API
    }
    
    res = session.post(url, params=params, data={"data": data_str})
    return res.json()

# --- UI ---
st.title("🐠 闲鱼微信版主图同步 - 修正版V3")

if 'session' not in st.session_state:
    st.session_state.session = init_session()

with st.sidebar:
    ck = st.text_area("在此粘贴完整 Cookie", height=300)
    if st.button("更新 Cookie"):
        for item in ck.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                st.session_state.session.cookies.set(k, v)
        st.success("Cookie 同步成功")

iid = st.text_input("商品 ID")
up_file = st.file_uploader("选择新图")

if st.button("🚀 开始同步", use_container_width=True):
    if iid and up_file:
        with st.status("正在处理微信同步...") as s:
            url, err = upload_to_fleamarket_v3(st.session_state.session, up_file.read(), up_file.name)
            if url:
                st.write(f"✅ 图片上传成功: {url}")
                res = edit_item_wx(st.session_state.session, iid, url)
                if "SUCCESS" in str(res.get("ret")):
                    s.update(label="🎉 修改成功！", state="complete")
                    st.balloons()
                else:
                    st.error(f"提交修改失败: {res.get('ret')}")
                    st.json(res)
            else:
                st.error(f"上传环节失败: {err}")

# --- 报错原因分析 ---
st.divider()
st.subheader("❌ 为什么会报 'SYS_ERROR'？")
st.markdown("""
这个报错通常不是代码写错了，而是**请求被阿里防火墙拦截**了，常见于：
1. **Cookie 失效**：微信环境的 `_m_h5_tk` 过期极快，请确保你复制的是**刚刚**在微信里操作时产生的包。
2. **缺少 data 字段**：在流式上传中，`data` 必须作为 `multipart` 的一个部分，且里面必须包含 `utdid` 和 `bizCode`。
3. **域名不一致**：你抓包看到的 URL 带有 `appkey=fleamarket`，这说明后端可能在做灰度测试。
""")
