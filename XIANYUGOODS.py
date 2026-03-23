import streamlit as st
import hashlib
import json
import time
import re
import urllib.parse
import requests
import urllib3
import io

# 1. 基础环境配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 核心逻辑模块 ====================

def get_safe_tk(session):
    """安全获取 Token，避免 CookieConflictError"""
    # 遍历所有 cookie，只要名字对上就返回第一个，不纠结域名
    for cookie in session.cookies:
        if cookie.name == "_m_h5_tk":
            return cookie.value
    return None

def get_mtop_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算签名：只取 Token 下划线前面的部分"""
    if not token: return ""
    tk_prefix = token.split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def update_session_from_raw(session, raw_text):
    """从原始文本中智能提取所有凭证"""
    # 1. 尝试解析 x-smallstc 里的 JSON
    stc_match = re.search(r'x-smallstc:\s*({.+})', raw_text)
    if stc_match:
        try:
            stc_json = json.loads(stc_match.group(1))
            for key in ['cookie2', 'sgcookie', 'sid', 'unb']:
                if key in stc_json:
                    session.cookies.set(key, str(stc_json[key]), domain=".goofish.com")
        except: pass

    # 2. 暴力提取所有符合 k=v 格式的 Cookie (包括 _m_h5_tk)
    # 使用正则匹配，排除掉 Header 关键词
    cookie_pairs = re.findall(r'(?:^|;|,|(?<=\s))([^=;\s]+)=([^;\s,]+)', raw_text)
    for k, v in cookie_pairs:
        clean_k = k.strip()
        # 排除掉干扰项
        if clean_k.lower() not in ['host', 'content-length', 'content-type', 'x-smallstc']:
            session.cookies.set(clean_k, v.strip(), domain=".goofish.com")

def run_sync_process(item_id, file_bytes, file_name, raw_input):
    session = requests.Session()
    session.verify = False
    
    # 注入凭证
    update_session_from_raw(session, raw_input)
    current_tk = get_safe_tk(session)
    
    if not current_tk:
        return False, "❌ 未发现 _m_h5_tk。请检查抓包内容是否包含 Cookie。"

    common_headers = {
        "x-tap": "wx", "xweb_xhr": "1", "accept": "application/json",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
    }

    try:
        # --- 步骤 1: 上传图片 ---
        t1 = str(int(time.time() * 1000))
        biz_data = json.dumps({"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID})
        sign1 = get_mtop_sign(current_tk, t1, APP_KEY, biz_data)
        
        up_params = {"appkey":"fleamarket","appKey":APP_KEY,"t":t1,"sign":sign1,"api":"mtop.taobao.util.uploadImage","v":"1.0","type":"originaljson"}
        files = [('data',(None, biz_data)), ('file',(file_name, file_bytes, 'image/png'))]
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=common_headers, timeout=20)
        
        # 检查 Token 是否翻转（阿里接口特性）
        new_tk = get_safe_tk(session)
        if new_tk: current_tk = new_tk
            
        up_json = res_up.json()
        img_url = up_json.get('url') or up_json.get('object', {}).get('url')
        
        if not img_url:
            return False, f"上传失败: {res_up.text[:150]}"

        # --- 步骤 2: 更新主图 ---
        t2 = str(int(time.time() * 1000))
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major":True,"type":0,"url":img_url,"widthSize":"800","heightSize":"800"}],
            "utdid": FIXED_UTDID, "platform": "windows"
        }
        edit_json = json.dumps(edit_data, ensure_ascii=False, separators=(',', ':'))
        sign2 = get_mtop_sign(current_tk, t2, APP_KEY, edit_json)
        
        edit_params = {"jsv":"2.4.12","appKey":APP_KEY,"t":t2,"sign":sign2,"v":"1.0","api":EDIT_API,"type":"originaljson","accountSite":"xianyu"}
        
        headers_post = common_headers.copy()
        headers_post["content-type"] = "application/x-www-form-urlencoded"
        
        res_edit = session.post(f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/", 
                                params=edit_params, data={"data": edit_json}, headers=headers_post)
        
        result = res_edit.json()
        if "SUCCESS" in str(result.get("ret")):
            return True, "🎊 替换成功！"
        else:
            return False, f"修改失败: {result.get('ret')}"

    except Exception as e:
        return False, f"异常: {str(e)}"

# ==================== Streamlit 界面 ====================

st.set_page_config(page_title="闲鱼主图同步", layout="centered")
st.title("🐠 闲鱼主图助手 (Stable版)")

with st.sidebar:
    st.markdown("### 🔑 Token 监控")
    tk_monitor = st.empty()
    tk_monitor.info("等待注入...")

raw_input = st.text_area("1. 粘贴抓包 Headers/Cookies", height=200)

c1, c2 = st.columns(2)
with c1:
    iid = st.text_input("2. itemId", "1033424722209")
with c2:
    file = st.file_uploader("3. 选择图片", type=['jpg','png','jpeg'])

if st.button("🚀 执行更新", use_container_width=True):
    if raw_input and iid and file:
        with st.spinner("正在处理..."):
            # 预览 Token 状态
            temp_s = requests.Session()
            update_session_from_raw(temp_s, raw_input)
            found_tk = get_safe_tk(temp_s)
            tk_monitor.success(f"已识别 Token: {found_tk[:10]}...") if found_tk else tk_monitor.error("未识别到 Token")
            
            ok, msg = run_sync_process(iid, file.read(), file.name, raw_input)
            if ok:
                st.balloons()
                st.success(msg)
            else:
                st.error(msg)
    else:
        st.warning("请检查输入是否完整")
