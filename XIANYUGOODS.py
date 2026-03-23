import streamlit as st
import json
import requests
import time
import os
import re
import mimetypes
import urllib.parse
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 最新校准的常量 ---
# 使用你抓到的流式上传地址
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
# 商品编辑 API（基于你之前的抓包）
EDIT_API = "mtop.idle.wx.idleitem.edit"
APP_KEY = "12574478"

def init_session():
    s = requests.Session()
    s.verify = False
    # 必须模拟微信小程序的 User-Agent 才能通过校验
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 MicroMessenger/7.0.20.1781 NetType/WIFI MiniProgramEnv/Windows",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    })
    return s

def upload_to_fleamarket(session, file_bytes, file_name):
    """
    使用你抓到的 fleamarket 专用流式上传接口
    """
    # 构造上传参数
    params = {
        "floderId": "0",
        "appkey": "fleamarket",
        "_input_charset": "utf-8"
    }
    
    mime_type = mimetypes.guess_type(file_name)[0] or 'image/jpeg'
    # 阿里流式接口通常将文件放在 'file' 字段
    files = {
        'file': (file_name, file_bytes, mime_type)
    }

    try:
        # 注意：这种接口通常不需要额外签名，直接带 Cookie 发送即可
        res = session.post(UPLOAD_URL, params=params, files=files, timeout=20)
        
        # 兼容处理：有的返回是 JSON，有的返回是带 URL 的字符串
        try:
            res_j = res.json()
            if "url" in res_j: return res_j["url"], None
            if "data" in res_j and "url" in res_j["data"]: return res_j["data"]["url"], None
            return None, f"接口返回异常: {res.text}"
        except:
            # 如果不是 JSON，尝试正则提取 URL
            match = re.search(r'(https?://img\.alicdn\.com/[^"\s]+)', res.text)
            if match: return match.group(1), None
            return None, f"无法解析返回内容: {res.text[:100]}"
            
    except Exception as e:
        return None, f"上传连接失败: {str(e)}"

def edit_item_wx(session, item_id, img_url):
    """
    执行商品修改
    """
    t = str(int(time.time() * 1000))
    # 提取签名用的 Token
    tk = session.cookies.get("_m_h5_tk", "").split("_")[0]
    
    # 构造修改数据（完全匹配你之前的抓包结构）
    data = {
        "itemId": str(item_id),
        "imageInfoDOList": [{"major":True,"type":0,"url":img_url,"widthSize":"640","heightSize":"640"}],
        "utdid": "v3UyIt1jJFECAXAaAnEns/UL",
        "platform": "windows"
    }
    data_str = json.dumps(data, ensure_ascii=False)
    
    # 计算签名
    base_sign = f"{tk}&{t}&{APP_KEY}&{data_str}"
    sign = hashlib.md5(base_sign.encode('utf-8')).hexdigest()

    # 微信小程序专用 H5 路径
    url = f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/2.0/"
    params = {
        "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
        "v": "1.0", "type": "originaljson", "api": EDIT_API, "dataType": "json"
    }
    
    try:
        # 微信版 Body 必须是 data=...
        res = session.post(url, params=params, data={"data": data_str})
        return res.json()
    except Exception as e:
        return {"ret": [f"请求异常: {str(e)}"]}

# --- 界面部分 ---
st.set_page_config(page_title="闲鱼微信版同步器")
st.title("🐠 闲鱼微信版 - 主图快速同步")

if 'session' not in st.session_state:
    st.session_state.session = init_session()

with st.sidebar:
    st.header("🔑 认证")
    ck = st.text_area("粘贴微信抓包的完整 Cookie", height=300)
    if st.button("更新 Cookie"):
        for item in ck.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                st.session_state.session.cookies.set(k, v)
        st.success("Cookie 已加载")

iid = st.text_input("商品 ID (itemId)", placeholder="从抓包或链接中获取")
up_file = st.file_uploader("选择新主图 (支持JPG/PNG/GIF)")

if st.button("🚀 开始同步", use_container_width=True):
    if not iid or not up_file:
        st.warning("请填写完整信息")
    else:
        with st.status("正在处理...") as s:
            # 1. 上传图片
            s.write("正在通过流式接口上传图片...")
            img_url, err = upload_to_fleamarket(st.session_state.session, up_file.read(), up_file.name)
            
            if img_url:
                st.write(f"✅ 图片已托管: {img_url}")
                # 2. 修改商品
                s.write("正在提交商品修改请求...")
                res = edit_item_wx(st.session_state.session, iid, img_url)
                
                if "SUCCESS" in str(res.get("ret")):
                    s.update(label="🎉 同步成功！", state="complete")
                    st.balloons()
                    st.success(f"商品 {iid} 的主图已更新。")
                else:
                    st.error(f"修改失败: {res.get('ret')}")
                    st.json(res)
            else:
                st.error(f"上传环节失败: {err}")
