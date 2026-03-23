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

def get_tk_logic(cookie_str):
    """从 Cookie 字符串中自动解析出需要的 Token 信息"""
    tk_match = re.search(r'_m_h5_tk=([a-f0-9]+)_(\d+)', cookie_str)
    enc_match = re.search(r'_m_h5_tk_enc=([a-f0-9]+)', cookie_str)
    
    if tk_match:
        full_tk = f"{tk_match.group(1)}_{tk_match.group(2)}"
        clean_tk = tk_match.group(1)
        tk_enc = enc_match.group(1) if enc_match else ""
        return full_tk, clean_tk, tk_enc
    return None, None, None

def run_sync_process(item_id, file_bytes, cookie_str):
    session = requests.Session()
    
    # 1. 自动解析 Token
    full_tk, clean_tk, tk_enc = get_tk_logic(cookie_str)
    if not clean_tk:
        return False, "❌ 无法从 Cookie 中提取到 _m_h5_tk，请检查粘贴内容是否完整。"

    # 2. 注入所有 Cookie 到 Session
    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', cookie_str)
    for k, v in kv_pairs:
        session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")
        session.cookies.set(k.strip(), v.strip(), domain=".taobao.com")

    headers = {
        "User-Agent": PC_UA,
        "Origin": "https://2.taobao.com",
        "Referer": "https://2.taobao.com/",
        "Accept": "application/json, text/plain, */*"
    }

    try:
        # --- 步骤 A: 上传图片 ---
        st.write("🔄 正在上传二进制流至 stream-upload...")
        up_params = {
            "appkey": "fleamarket",
            "_input_charset": "utf-8",
            "floderId": "0"
        }
        files = {'file': ('image.jpg', file_bytes, 'image/jpeg')}
        
        res_up = session.post(
            "https://stream-upload.goofish.com/api/upload.api",
            params=up_params,
            headers=headers,
            files=files,
            timeout=30
        )
        
        up_data = res_up.json()
        img_url = up_data.get('url') or up_data.get('object', {}).get('url')
        
        if not img_url:
            return False, f"图片上传失败，响应：{res_up.text}"
        
        st.write(f"✅ 图片上传成功：{img_url[:50]}...")

        # --- 步骤 B: 提交业务修改 ---
        st.write("🔄 正在构造签名并更新商品主图...")
        t = str(int(time.time() * 1000))
        
        # 业务数据：确保格式与 Web 端一致
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": 1024, "heightSize": 1024}],
            "platform": "pc"
        }
        # 强制使用无空格的 JSON 字符串进行签名
        data_str = json.dumps(edit_data, separators=(',', ':'))
        
        # 计算 MD5 签名
        sign_payload = f"{clean_tk}&{t}&{APP_KEY}&{data_str}"
        sign = hashlib.md5(sign_payload.encode('utf-8')).hexdigest()

        params = {
            "jsv": "2.6.1",
            "appKey": APP_KEY,
            "t": t,
            "sign": sign,
            "v": "1.0",
            "api": EDIT_API,
            "type": "json",
            "dataType": "json"
        }

        # 发送业务请求
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=params,
            data={"data": data_str},
            headers={"Content-Type": "application/x-www-form-urlencoded", **headers}
        )

        result = res_edit.json()
        ret_msg = result.get("ret", ["未知错误"])[0]

        if "SUCCESS" in ret_msg:
            return True, "🎊 闲鱼主图更新成功！"
    except Exception as e:
        return False, f"发生异常: {str(e)}"

    return False, f"业务同步失败: {ret_msg}"

# --- UI 界面 ---
st.set_page_config(page_title="闲鱼自动同步工具", layout="centered")
st.title("🐟 闲鱼主图快速同步 (PC版)")

with st.expander("📌 使用说明 (必读)", expanded=True):
    st.markdown("""
    1. 登录电脑版闲鱼/淘宝。
    2. 按 F12 打开开发者工具，刷新页面，在 **Network** 找到任意 `mtop` 请求。
    3. 复制 **Request Headers** 里的整个 `Cookie` 字符串。
    4. 粘贴到下方，上传图片后点击执行。
    """)

item_id = st.text_input("📦 商品 itemId", placeholder="例如：1033424722209")
raw_cookie = st.text_area("🔑 粘贴完整 Cookie", height=150, placeholder="st=success; _m_h5_tk=xxxx; ...")
uploaded_file = st.file_uploader("🖼️ 选择新主图", type=['jpg', 'jpeg', 'png'])

if st.button("🚀 开始同步"):
    if not item_id or not raw_cookie or not uploaded_file:
        st.error("请完整填写 itemId、Cookie 并上传图片！")
    else:
        with st.status("执行中...", expanded=True) as status:
            success, message = run_sync_process(item_id, uploaded_file.read(), raw_cookie)
            if success:
                status.update(label="处理完成！", state="complete")
                st.balloons()
                st.success(message)
            else:
                status.update(label="处理失败", state="error")
                st.error(message)
