import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3
import shlex  # 用于解析 cURL 命令行

# 基础配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 逻辑增强 ====================

def parse_curl_to_session(session, curl_str):
    """
    解析 cURL 字符串，自动提取所有 Headers 和 Cookies
    """
    if not curl_str.strip().startswith('curl'):
        # 如果不是 curl，退化为普通 Cookie 解析
        kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', curl_str)
        for k, v in kv_pairs:
            session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")
        return {"User-Agent": "Mozilla/5.0"} 

    # 简易 cURL 解析器
    parts = shlex.split(curl_str)
    headers = {}
    for i in range(len(parts)):
        if parts[i] in ['-H', '--header']:
            header_line = parts[i+1]
            if ':' in header_line:
                k, v = header_line.split(':', 1)
                headers[k.strip()] = v.strip()
                if k.strip().lower() == 'cookie':
                    # 注入 Cookie 到 session
                    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', v)
                    for ck, cv in kv_pairs:
                        session.cookies.set(ck.strip(), cv.strip(), domain=".goofish.com")
    return headers

def get_cookie_value_safe(session, name):
    for c in session.cookies:
        if c.name == name: return c.value
    return None

def run_sync_process(item_id, file_bytes, curl_input):
    session = requests.Session()
    # 1. 深度解析凭证
    custom_headers = parse_curl_to_session(session, curl_input)
    
    full_tk = get_cookie_value_safe(session, "_m_h5_tk")
    if not full_tk:
        return False, "❌ 未识别到 _m_h5_tk，请重新抓包。"

    try:
        # --- 步骤 1: 上传图片 ---
        st.info("🚀 阶段 1: 正在上传图片...")
        t1 = str(int(time.time() * 1000))
        biz_data = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
        biz_str = json.dumps(biz_data, separators=(',', ':'))
        
        # 签名算法
        tk_prefix = full_tk.split('_')[0]
        sign1 = hashlib.md5(f"{tk_prefix}&{t1}&{APP_KEY}&{biz_str}".encode('utf-8')).hexdigest()
        
        up_params = {
            "appkey": "fleamarket", "appKey": APP_KEY, "t": t1, "sign": sign1,
            "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
        }

        files = [('data', (None, biz_str)), ('file', ('img.png', file_bytes, 'image/png'))]
        
        # 模拟上传
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=custom_headers, timeout=20)
        
        if "success\":true" not in res_up.text.lower():
            st.error(f"上传失败详细响应: {res_up.text}")
            return False, "CDN上传阶段依然失败，请确认是否在抓包后立即执行。"

        up_json = res_up.json()
        img_url = up_json.get('url') or up_json.get('object', {}).get('url')
        st.success(f"图片上传成功: {img_url[:40]}...")

        # --- 步骤 2: 修改商品 ---
        st.info("🚀 阶段 2: 正在更新宝贝...")
        new_tk = get_cookie_value_safe(session, "_m_h5_tk") or full_tk
        t2 = str(int(time.time() * 1000))
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": "1024", "heightSize": "1024"}],
            "utdid": FIXED_UTDID, "platform": "ios"
        }
        edit_str = json.dumps(edit_data, ensure_ascii=False, separators=(',', ':'))
        sign2 = hashlib.md5(f"{new_tk.split('_')[0]}&{t2}&{APP_KEY}&{edit_str}".encode('utf-8')).hexdigest()
        
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params={"jsv": "2.4.12", "appKey": APP_KEY, "t": t2, "sign": sign2, "v": "1.0", "api": EDIT_API, "type": "originaljson"},
            data={"data": edit_str},
            headers={**custom_headers, "Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if "SUCCESS" in res_edit.text:
            return True, "🎊 恭喜，主图同步成功！"
        else:
            return False, f"修改失败: {res_edit.text}"

    except Exception as e:
        return False, f"运行错误: {str(e)}"

# ==================== UI 界面 ====================
st.title("🐠 闲鱼主图同步 (cURL 强力版)")
st.markdown("> **提示**：建议在抓包工具中右键点击 `uploadImage` 请求，选择 **Copy as cURL** 后粘贴到下方。")

curl_input = st.text_area("1. 粘贴 cURL 或 Cookie 字符串", height=200)
item_id = st.text_input("2. 商品 itemId", value="1033424722209")
img_file = st.file_uploader("3. 选择图片")

if st.button("开始同步", use_container_width=True):
    if curl_input and img_file:
        ok, msg = run_sync_process(item_id, img_file.read(), curl_input)
        st.success(msg) if ok else st.error(msg)
