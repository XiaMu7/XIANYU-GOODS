import streamlit as st
import hashlib
import json
import time
import re
import urllib.parse
import requests
import urllib3

# 1. 基础环境配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 核心逻辑模块 ====================

def get_safe_tk(session):
    """安全获取 _m_h5_tk，解决 CookieConflictError"""
    for cookie in session.cookies:
        if cookie.name == "_m_h5_tk":
            return cookie.value
    return None

def get_mtop_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """阿里 H5 签名算法：token_prefix & t & appKey & data"""
    if not token: return ""
    tk_prefix = token.split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def update_session_from_raw(session, raw_text):
    """深度解析：支持 Header、纯 Cookie、x-smallstc JSON"""
    # 1. 提取 x-smallstc 里的关键凭证
    stc_match = re.search(r'x-smallstc:\s*({.+})', raw_text)
    if stc_match:
        try:
            stc_json = json.loads(stc_match.group(1))
            for key in ['cookie2', 'sgcookie', 'sid', 'unb']:
                if key in stc_json:
                    session.cookies.set(key, str(stc_json[key]), domain=".goofish.com")
        except: pass

    # 2. 暴力正则提取所有键值对 (适配多种抓包格式)
    # 匹配规则：排除掉常见的 Header 键名，提取剩余的 k=v
    kv_pairs = re.findall(r'(?:^|;|,|(?<=\s))([^=;\s]+)=([^;\s,]+)', raw_text)
    for k, v in kv_pairs:
        key_low = k.strip().lower()
        if key_low not in ['host', 'content-length', 'content-type', 'connection', 'accept', 'user-agent']:
            session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")

def run_sync_process(item_id, file_bytes, file_name, raw_input):
    session = requests.Session()
    session.verify = False
    
    # --- 注入凭证 ---
    update_session_from_raw(session, raw_input)
    current_tk = get_safe_tk(session)
    
    if not current_tk:
        return False, "❌ 报文中未发现 _m_h5_tk。请确保粘贴的内容包含完整的 Cookie 字段。"

    common_headers = {
        "x-tap": "wx", 
        "xweb_xhr": "1", 
        "accept": "application/json",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html"
    }

    try:
        # --- 步骤 1: 上传图片到阿里 CDN ---
        st.info("正在上传图片到 CDN...")
        t1 = str(int(time.time() * 1000))
        # 注意：这里的 biz_data 参与签名，格式必须严谨
        biz_data_dict = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
        biz_data_str = json.dumps(biz_data_dict, ensure_ascii=False, separators=(',', ':'))
        
        sign1 = get_mtop_sign(current_tk, t1, APP_KEY, biz_data_str)
        
        up_params = {
            "appkey": "fleamarket", "appKey": APP_KEY, "t": t1, "sign": sign1,
            "api": "mtop.taobao.util.uploadImage", "v": "1.0", "type": "originaljson"
        }
        files = [('data', (None, biz_data_str)), ('file', (file_name, file_bytes, 'image/png'))]
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=common_headers, timeout=20)
        
        # 实时同步最新 Token (应对 Token 翻转)
        new_tk = get_safe_tk(session)
        if new_tk: current_tk = new_tk
            
        up_res_json = res_up.json()
        img_url = up_res_json.get('url') or up_res_json.get('object', {}).get('url')
        
        if not img_url:
            return False, f"图片上传失败: {res_up.text[:200]}"
        st.success(f"图片上传成功: {img_url[:40]}...")

        # --- 步骤 2: 修改商品主图 ---
        st.info("正在提交修改请求...")
        t2 = str(int(time.time() * 1000))
        
        # 构造编辑数据：major=True 表示设置为主图
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{
                "major": True, "url": img_url, "type": 0, 
                "widthSize": "800", "heightSize": "800"
            }],
            "utdid": FIXED_UTDID, 
            "platform": "ios"
        }
        
        # 核心：必须使用无空格的 JSON 字符串进行签名
        edit_json_str = json.dumps(edit_data, ensure_ascii=False, separators=(',', ':'))
        sign2 = get_mtop_sign(current_tk, t2, APP_KEY, edit_json_str)
        
        edit_params = {
            "jsv": "2.4.12", "appKey": APP_KEY, "t": t2, "sign": sign2, "v": "1.0",
            "api": EDIT_API, "type": "originaljson", "accountSite": "xianyu"
        }
        
        headers_post = common_headers.copy()
        headers_post["content-type"] = "application/x-www-form-urlencoded"
        
        # 编码 payload
        payload = f"data={urllib.parse.quote(edit_json_str)}"
        
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/", 
            params=edit_params, data=payload, headers=headers_post
        )
        
        result = res_edit.json()
        ret_msg = result.get("ret", ["未知错误"])
        
        if "SUCCESS" in str(ret_msg):
            return True, "🎊 同步成功！商品主图已更新。"
        else:
            return False, f"修改失败：{ret_msg}"

    except Exception as e:
        return False, f"程序运行时发生错误: {str(e)}"

# ==================== Streamlit UI 界面 ====================

st.set_page_config(page_title="闲鱼主图同步", page_icon="🐠", layout="centered")

st.title("🐠 闲鱼主图同步助手")
st.caption("基于 mtop 接口的商品主图快速替换工具")

# 侧边栏状态
with st.sidebar:
    st.header("🔑 状态监控")
    tk_state = st.empty()
    tk_state.warning("等待凭证输入...")

# 输入区
input_raw = st.text_area("1. 粘贴抓包原始数据", height=200, placeholder="粘贴包含 Cookie 或 x-smallstc 的 Headers/报文内容...")

col1, col2 = st.columns(2)
with col1:
    item_id = st.text_input("2. 商品 itemId", value="1033424722209")
with col2:
    img_file = st.file_uploader("3. 选择新主图", type=['jpg', 'jpeg', 'png'])

# 执行区
if st.button("🚀 开始同步更新", use_container_width=True):
    if not input_raw or not item_id or not img_file:
        st.error("请检查：凭证、ID 或图片是否遗漏？")
    else:
        # 预检查 Token
        test_session = requests.Session()
        update_session_from_raw(test_session, input_raw)
        found_tk = get_safe_tk(test_session)
        
        if found_tk:
            tk_state.success(f"Token 已识别: {found_tk[:12]}...")
            
            with st.spinner("正在执行两步同步任务..."):
                file_bytes = img_file.read()
                success, message = run_sync_process(item_id, file_bytes, img_file.name, input_raw)
                
                if success:
                    st.balloons()
                    st.success(message)
                else:
                    st.error(message)
                    st.info("提示：若报 UNKNOWN_THROWABLE，请尝试在手机上重新打开宝贝详情页并重新抓包。")
        else:
            tk_state.error("未能识别有效 Token")
            st.error("解析失败：输入的文本中没有找到 _m_h5_tk。")
