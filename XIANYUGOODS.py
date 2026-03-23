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
EDIT_API = "mtop.idle.wx.idleitem.edit"
PC_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

def get_tk(cookie_str):
    tk_match = re.search(r'_m_h5_tk=([a-f0-9]+)_(\d+)', cookie_str)
    return tk_match.group(1) if tk_match else None

def run_force_sync(item_id, file_bytes, cookie_str, title, price, category_id):
    session = requests.Session()
    clean_tk = get_tk(cookie_str)
    if not clean_tk: return False, "❌ Cookie 缺少 _m_h5_tk"

    # 注入 Cookie
    for k, v in re.findall(r'([^=\s;]+)=([^;]*)', cookie_str):
        session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")

    headers = {
        "User-Agent": PC_UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://2.taobao.com/"
    }

    try:
        # 1. 上传新图片
        st.write("📤 正在上传新主图...")
        up_url = "https://stream-upload.goofish.com/api/upload.api?appkey=fleamarket&bizCode=fleamarket"
        up_res = session.post(up_url, files={'file': ('img.jpg', file_bytes, 'image/jpeg')}, headers=headers)
        img_url = up_res.json().get('url') or up_res.json().get('object', {}).get('url')
        if not img_url: return False, f"图片上传失败: {up_res.text}"
        st.write(f"✅ 图片已托管: {img_url[:40]}...")

        # 2. 构造全量数据包 (暴力填充)
        st.write("🚀 正在暴力同步业务数据...")
        t = str(int(time.time() * 1000))
        
        # 这里的字段是闲鱼后端校验的“生死线”
        update_payload = {
            "itemId": int(item_id),
            "title": title,
            "desc": title, # 描述暂时与标题同步
            "price": str(int(float(price) * 100)), # 元转分，且必须是字符串或整型
            "categoryId": str(category_id),
            "divisionId": "0", # 默认地区
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": 1024, "heightSize": 1024}],
            "platform": "pc",
            "from": "h5",
            "apiFrom": "idle-wx"
        }

        # 签名与提交
        data_str = json.dumps(update_payload, separators=(',', ':'), sort_keys=True)
        sign_payload = f"{clean_tk}&{t}&{APP_KEY}&{data_str}"
        sign = hashlib.md5(sign_payload.encode('utf-8')).hexdigest()

        params = {
            "jsv": "2.6.1", "appKey": APP_KEY, "t": t, "sign": sign,
            "v": "1.0", "api": EDIT_API, "type": "json", "dataType": "json"
        }

        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=params,
            data={"data": data_str},
            headers=headers
        )

        resp = res_edit.json()
        ret_msg = resp.get("ret", ["未知错误"])[0]

        if "SUCCESS" in ret_msg:
            return True, "🎊 暴力同步成功！主图已强制更新。"
        else:
            return False, f"修改失败: {ret_msg}\n详细报错: {resp.get('data', {}).get('errorMsg', '无')}"

    except Exception as e:
        return False, f"执行异常: {str(e)}"

# --- UI 界面 ---
st.set_page_config(page_title="闲鱼暴力同步器", page_icon="💥")
st.title("💥 闲鱼主图暴力同步 (最终方案)")
st.warning("此方案不再自动读取原数据，请手动输入以下关键信息以确保后端校验通过。")

col1, col2 = st.columns(2)
with col1:
    item_id_in = st.text_input("📦 商品 itemId", "1033424722209")
    price_in = st.text_input("💰 价格 (元)", "99.00")
with col2:
    cat_id_in = st.text_input("标签 CategoryId", "50025386") # 示例 ID
    title_in = st.text_input("📝 商品标题", "测试商品标题")

cookie_in = st.text_area("🔑 粘贴 Cookie 全文", height=100)
file_in = st.file_uploader("🖼️ 上传新主图", type=['jpg', 'png'])

if st.button("🔥 强制执行同步"):
    if not all([item_id_in, cookie_in, file_in, title_in, price_in, cat_id_in]):
        st.error("所有字段均为必填项！")
    else:
        success, msg = run_force_sync(item_id_in, file_in.read(), cookie_in, title_in, price_in, cat_id_in)
        if success: st.success(msg); st.balloons()
        else: st.error(msg)
