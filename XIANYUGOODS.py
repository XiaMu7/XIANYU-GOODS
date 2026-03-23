import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3
from urllib.parse import quote

# 基础配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
GET_API = "mtop.idle.item.get"
EDIT_API = "mtop.idle.wx.idleitem.edit"
PC_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

def get_tk(cookie_str):
    tk_match = re.search(r'_m_h5_tk=([a-f0-9]+)_(\d+)', cookie_str)
    return (tk_match.group(1), tk_match.group(1)) if tk_match else (None, None)

def mtop_request(session, api, v, data, clean_tk, headers):
    """通用 MTOP 签名请求封装"""
    t = str(int(time.time() * 1000))
    data_str = json.dumps(data, separators=(',', ':'), sort_keys=True)
    sign_payload = f"{clean_tk}&{t}&{APP_KEY}&{data_str}"
    sign = hashlib.md5(sign_payload.encode('utf-8')).hexdigest()
    
    params = {
        "jsv": "2.6.1", "appKey": APP_KEY, "t": t, "sign": sign,
        "v": v, "api": api, "type": "json", "dataType": "json"
    }
    url = f"https://acs.m.goofish.com/h5/{api}/{v}/"
    res = session.post(url, params=params, data={"data": data_str}, headers=headers)
    return res.json()

def run_safe_sync(item_id, file_bytes, cookie_str):
    session = requests.Session()
    _, clean_tk = get_tk(cookie_str)
    if not clean_tk: return False, "Cookie 中缺少 _m_h5_tk"

    # 注入 Cookie
    for k, v in re.findall(r'([^=\s;]+)=([^;]*)', cookie_str):
        session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")

    headers = {"User-Agent": PC_UA, "Content-Type": "application/x-www-form-urlencoded", "Referer": "https://2.taobao.com/"}

    try:
        # 1. 获取原商品数据
        st.write("🔍 步骤 1: 正在拉取商品原始数据...")
        get_res = mtop_request(session, GET_API, "1.0", {"itemId": item_id}, clean_tk, headers)
        
        if "SUCCESS" not in get_res.get("ret", [""])[0]:
            return False, f"获取商品失败: {get_res.get('ret')[0]}"
        
        old_data = get_res.get("data", {}).get("detail", {})
        if not old_data: return False, "未能解析到商品详情，请检查 itemId 是否正确。"

        # 2. 上传新图片
        st.write("📤 步骤 2: 正在上传新图片...")
        up_res = session.post(
            "https://stream-upload.goofish.com/api/upload.api?appkey=fleamarket&bizCode=fleamarket",
            files={'file': ('img.jpg', file_bytes, 'image/jpeg')},
            headers=headers
        )
        img_url = up_res.json().get('url') or up_res.json().get('object', {}).get('url')
        if not img_url: return False, "图片上传失败"

        # 3. 构造更新数据包 (核心修复：保留原数据，仅改图片)
        st.write("🚀 步骤 3: 正在合并数据并提交更新...")
        
        # 从旧数据中提取关键字段，防止后端校验失败
        update_payload = {
            "itemId": item_id,
            "title": old_data.get("title"),
            "desc": old_data.get("desc"),
            "price": old_data.get("price"),
            "categoryId": old_data.get("categoryId"),
            "divisionId": old_data.get("divisionId", "0"),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": 1024, "heightSize": 1024}],
            "platform": "pc"
        }

        edit_res = mtop_request(session, EDIT_API, "1.0", update_payload, clean_tk, headers)
        ret_msg = edit_res.get("ret", ["未知错误"])[0]

        if "SUCCESS" in ret_msg:
            return True, "🎊 深度同步成功！主图已更新且保留了所有商品属性。"
        else:
            return False, f"修改失败: {ret_msg}\n详细信息: {edit_res.get('data', {}).get('errorMsg', '无')}"

    except Exception as e:
        return False, f"运行异常: {str(e)}"

# --- Streamlit UI ---
st.set_page_config(page_title="闲鱼主图深度同步", page_icon="🛡️")
st.title("🛡️ 闲鱼主图同步 (高成功率版)")
st.caption("采用 '获取-修改-提交' 闭环逻辑，规避 UNKNOWN_THROWABLE 错误")

item_id = st.text_input("📦 商品 itemId")
raw_cookie = st.text_area("🔑 粘贴 Cookie 全文", height=100)
img_file = st.file_uploader("🖼️ 上传新主图", type=['jpg', 'png'])

if st.button("🚀 开始安全同步"):
    if not item_id or not raw_cookie or not img_file:
        st.error("请完整填写信息")
    else:
        with st.status("同步中...", expanded=True) as status:
            success, msg = run_safe_sync(item_id, img_file.read(), raw_cookie)
            if success:
                status.update(label="同步完成", state="complete")
                st.success(msg)
                st.balloons()
            else:
                status.update(label="同步失败", state="error")
                st.error(msg)
