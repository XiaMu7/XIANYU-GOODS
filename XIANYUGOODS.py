import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3
from urllib.parse import quote

# 基础配置 (从抓包中精准提取)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
GET_API = "mtop.taobao.idle.wx.user.publish.items.mini"
EDIT_API = "mtop.idle.wx.idleitem.edit"
JSV = "2.4.12"
PC_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781"

def get_tk(cookie_str):
    tk_match = re.search(r'_m_h5_tk=([a-f0-9]+)_(\d+)', cookie_str)
    return (tk_match.group(1), tk_match.group(1)) if tk_match else (None, None)

def mtop_post(session, api, v, data, clean_tk, headers):
    """通用的签名请求函数"""
    t = str(int(time.time() * 1000))
    data_str = json.dumps(data, separators=(',', ':'), sort_keys=True)
    # 签名公式: token & t & appKey & data
    sign_origin = f"{clean_tk}&{t}&{APP_KEY}&{data_str}"
    sign = hashlib.md5(sign_origin.encode('utf-8')).hexdigest()
    
    params = {
        "jsv": JSV, "appKey": APP_KEY, "t": t, "sign": sign,
        "v": v, "api": api, "type": "originaljson", "dataType": "json"
    }
    url = f"https://acs.m.goofish.com/h5/{api}/{v}/"
    res = session.post(url, params=params, data={"data": data_str}, headers=headers)
    return res.json()

def run_safe_sync(item_id, file_bytes, cookie_str):
    session = requests.Session()
    _, clean_tk = get_tk(cookie_str)
    if not clean_tk: return False, "❌ Cookie 中未找到 _m_h5_tk"

    for k, v in re.findall(r'([^=\s;]+)=([^;]*)', cookie_str):
        session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")

    headers = {
        "User-Agent": PC_UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }

    try:
        # 1. 获取原商品数据 (使用你抓包里的 API)
        st.write("🔍 步骤 1: 正在拉取商品全量详情...")
        get_payload = {
            "utdid": "Wg4zIi+WPAUCASQGAksSETS9", # 沿用抓包值
            "platform": "mac",
            "miniAppVersion": "9.9.9",
            "pageNumber": 1,
            "auctionTypes": "1,2",
            "items": str(item_id)
        }
        get_res = mtop_post(session, GET_API, "1.0", get_payload, clean_tk, headers)
        
        # 解析详情数据
        item_list = get_res.get("data", {}).get("items", [])
        if not item_list:
            return False, f"未找到商品详情，请确认该商品属于当前账号。返回：{get_res.get('ret',[''])[0]}"
        
        old_data = item_list[0]
        st.write(f"✅ 已找到商品：{old_data.get('title')[:20]}...")

        # 2. 上传图片
        st.write("📤 步骤 2: 正在同步新主图...")
        up_url = "https://stream-upload.goofish.com/api/upload.api?appkey=fleamarket&bizCode=fleamarket"
        up_res = session.post(up_url, files={'file': ('img.jpg', file_bytes, 'image/jpeg')}, headers=headers)
        img_url = up_res.json().get('url') or up_res.json().get('object', {}).get('url')
        if not img_url: return False, "图片上传失败"

        # 3. 构造合并后的数据包
        st.write("🚀 步骤 3: 正在合并原始属性并提交修改...")
        update_payload = {
            "itemId": int(item_id),
            "title": old_data.get("title"),
            "desc": old_data.get("description") or old_data.get("title"),
            "price": old_data.get("price"),
            "categoryId": old_data.get("categoryId"),
            "divisionId": old_data.get("divisionId", "0"),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": 1024, "heightSize": 1024}],
            "platform": "pc",
            "apiFrom": "idle-wx"
        }

        edit_res = mtop_post(session, EDIT_API, "1.0", update_payload, clean_tk, headers)
        ret_msg = edit_res.get("ret", ["未知错误"])[0]

        if "SUCCESS" in ret_msg:
            return True, "🎊 恭喜！商品主图安全同步成功。"
        else:
            return False, f"最终修改失败: {ret_msg}\n原因: {edit_res.get('data', {}).get('errorMsg', '无')}"

    except Exception as e:
        return False, f"运行异常: {str(e)}"

# --- UI 保持不变 ---
st.title("🛡️ 闲鱼全量数据同步 (抓包对齐版)")
item_id_in = st.text_input("商品 ID", "1033424722209")
cookie_in = st.text_area("Cookie")
file_in = st.file_uploader("选择新主图", type=['jpg','png'])

if st.button("开始同步"):
    success, msg = run_safe_sync(item_id_in, file_in.read(), cookie_in)
    if success: st.success(msg)
    else: st.error(msg)
