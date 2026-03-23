import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3

# 基础配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 核心解析函数 ====================

def parse_and_inject_cookies(session, cookie_str):
    """
    深度解析用户提供的 Cookie 字符串，并处理 _m_h5_tk
    """
    # 移除换行
    cookie_str = cookie_str.replace('\n', '').strip()
    # 匹配 key=value
    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', cookie_str)
    
    for k, v in kv_pairs:
        key = k.strip()
        val = v.strip()
        # 注入到所有相关域名，防止域名限制导致的 SYS_ERROR
        for domain in [".goofish.com", "stream-upload.goofish.com", ".alicdn.com"]:
            session.cookies.set(key, val, domain=domain)
            
    return len(kv_pairs)

def get_clean_tk(session):
    """获取 _m_h5_tk 并只保留下划线前的 32 位 MD5 部分"""
    for cookie in session.cookies:
        if cookie.name == "_m_h5_tk":
            return cookie.value.split('_')[0]
    return None

def get_mtop_sign(clean_token, t, app_key, data_str):
    """标准的阿里 MTOP 签名算法"""
    base_str = f"{clean_token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

# ==================== 业务执行逻辑 ====================

def run_sync_process(item_id, file_bytes, raw_input):
    session = requests.Session()
    session.verify = False
    
    # 1. 解析 Cookie
    count = parse_and_inject_cookies(session, raw_input)
    st.sidebar.success(f"已识别 {count} 个凭证字段")
    
    tk_prefix = get_clean_tk(session)
    if not tk_prefix:
        return False, "❌ 未识别到 _m_h5_tk，请重新抓包。"

    # 模拟真实小程序 Header
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "x-tap": "wx",
        "xweb_xhr": "1",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html"
    }

    try:
        # --- 步骤 1: 图片上传 ---
        st.info("正在尝试上传图片...")
        t1 = str(int(time.time() * 1000))
        
        # 严谨的参数构造
        biz_data = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
        biz_str = json.dumps(biz_data, separators=(',', ':'))
        
        # 计算签名
        sign1 = get_mtop_sign(tk_prefix, t1, APP_KEY, biz_str)
        
        up_params = {
            "appkey": "fleamarket", "appKey": APP_KEY, "t": t1, "sign": sign1,
            "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
        }

        # 重点：阿里上传接口要求 'data' 字段在 'file' 之前，且必须是 multipart 结构
        files = [
            ('data', (None, biz_str)),
            ('file', ('image.png', file_bytes, 'image/png'))
        ]
        
        # 发送请求
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=headers, timeout=20)
        
        # 调试输出：如果失败，显示原始响应
        if "success\":true" not in res_up.text.lower():
            return False, f"CDN上传失败: {res_up.text}"
            
        up_json = res_up.json()
        img_url = up_json.get('url') or up_json.get('object', {}).get('url')
        st.success(f"图片上传成功！")

        # --- 步骤 2: 更新商品主图 ---
        st.info("正在提交修改...")
        # 重新获取可能翻转的 Token
        new_tk_full = session.cookies.get("_m_h5_tk")
        if new_tk_full:
            tk_prefix = new_tk_full.split('_')[0]

        t2 = str(int(time.time() * 1000))
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": "1024", "heightSize": "1024"}],
            "utdid": FIXED_UTDID, "platform": "ios"
        }
        edit_str = json.dumps(edit_data, ensure_ascii=False, separators=(',', ':'))
        sign2 = get_mtop_sign(tk_prefix, t2, APP_KEY, edit_str)
        
        edit_params = {
            "jsv": "2.4.12", "appKey": APP_KEY, "t": t2, "sign": sign2, 
            "v": "1.0", "api": EDIT_API, "type": "originaljson", "accountSite": "xianyu"
        }
        
        # 使用 data 参数发送 x-www-form-urlencoded
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=edit_params,
            data={"data": edit_str},
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if "SUCCESS" in res_edit.text:
            return True, "🎊 恭喜！同步更新成功。"
        else:
            return False, f"修改失败: {res_edit.text}"

    except Exception as e:
        return False, f"发生异常: {str(e)}"

# ==================== Streamlit 界面 ====================

st.set_page_config(page_title="闲鱼同步助手", layout="centered")
st.title("🐠 闲鱼主图同步 (稳定版)")

with st.expander("ℹ️ 使用说明", expanded=False):
    st.write("1. 粘贴抓包获取的完整 Cookie 字符串。")
    st.write("2. 输入商品 ID。")
    st.write("3. 上传新图片并执行同步。")

input_text = st.text_area("1. 粘贴 Cookie 字符串", height=180, placeholder="cookie2=...; _m_h5_tk=...;")
target_iid = st.text_input("2. 商品 itemId", value="1033424722209")
target_file = st.file_uploader("3. 上传新主图", type=['jpg', 'jpeg', 'png'])

if st.button("🚀 开始执行同步", use_container_width=True):
    if not input_text or not target_file:
        st.error("请补全 Cookie 或图片。")
    else:
        ok, msg = run_sync_process(target_iid, target_file.read(), input_text)
        if ok:
            st.balloons()
            st.success(msg)
        else:
            st.error(msg)
