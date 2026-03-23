import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3

# 基础环境
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 逻辑处理 ====================

def get_mtop_sign(token, t, app_key, data_str):
    """阿里签名：token_prefix & t & appKey & data"""
    # 强制截取下划线前的部分
    tk_prefix = token.split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def inject_cookies(session, raw_str):
    """解析并多域名注入 Cookie"""
    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', raw_str)
    for k, v in kv_pairs:
        key, val = k.strip(), v.strip()
        for dom in [".goofish.com", "stream-upload.goofish.com", ".alicdn.com"]:
            session.cookies.set(key, val, domain=dom)
    return len(kv_pairs)

def run_sync_process(item_id, file_bytes, raw_input):
    session = requests.Session()
    inject_cookies(session, raw_input)
    
    # 获取 Token
    full_tk = session.cookies.get("_m_h5_tk")
    if not full_tk:
        return False, "❌ 未发现 _m_h5_tk，请确认 Cookie 是否完整。"

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "x-tap": "wx",
        "xweb_xhr": "1",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html"
    }

    try:
        # --- 步骤 1: 上传图片 ---
        st.info("正在执行第一步：上传图片到阿里服务器...")
        t1 = str(int(time.time() * 1000))
        biz_data = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
        biz_str = json.dumps(biz_data, separators=(',', ':'))
        
        # 签名计算
        sign1 = get_mtop_sign(full_tk, t1, APP_KEY, biz_str)
        
        up_params = {
            "appkey": "fleamarket", "appKey": APP_KEY, "t": t1, "sign": sign1,
            "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
        }

        # 核心修复：手动构造 files 元组，确保 data 字典在 file 之前发送
        files = [
            ('data', (None, biz_str)),
            ('file', ('image.png', file_bytes, 'image/png'))
        ]
        
        # 注意：这里不手动设置 Content-Type，让 requests 自动生成 boundary
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=headers, timeout=20)
        
        if "success\":true" not in res_up.text.lower():
            st.error(f"CDN响应原始数据: {res_up.text}")
            return False, "CDN上传阶段失败，请检查登录状态。"

        up_json = res_up.json()
        img_url = up_json.get('url') or up_json.get('object', {}).get('url')
        st.success("图片上传成功！")

        # --- 步骤 2: 修改商品 ---
        st.info("正在执行第二步：同步到闲鱼宝贝...")
        # 检查 Token 是否翻转
        final_tk = session.cookies.get("_m_h5_tk") or full_tk
        
        t2 = str(int(time.time() * 1000))
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": "1024", "heightSize": "1024"}],
            "utdid": FIXED_UTDID, "platform": "ios"
        }
        edit_str = json.dumps(edit_data, ensure_ascii=False, separators=(',', ':'))
        sign2 = get_mtop_sign(final_tk, t2, APP_KEY, edit_str)
        
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params={"jsv": "2.4.12", "appKey": APP_KEY, "t": t2, "sign": sign2, "v": "1.0", "api": EDIT_API, "type": "originaljson"},
            data={"data": edit_str},
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if "SUCCESS" in res_edit.text:
            return True, "🎊 替换主图成功！"
        else:
            return False, f"修改失败: {res_edit.text}"

    except Exception as e:
        return False, f"发生不可预知错误: {str(e)}"

# ==================== Streamlit UI ====================
st.title("🐠 闲鱼主图同步 (最终稳定版)")
cookie_input = st.text_area("1. 粘贴完整 Cookie 字符串", height=150)
item_id_input = st.text_input("2. itemId", value="1033424722209")
file_input = st.file_uploader("3. 选择主图文件")

if st.button("🚀 开始同步任务", use_container_width=True):
    if cookie_input and file_input:
        ok, msg = run_sync_process(item_id_input, file_input.read(), cookie_input)
        st.success(msg) if ok else st.error(msg)
