import streamlit as st
import hashlib
import json
import time
import re
import urllib.parse
import requests
import urllib3
from PIL import Image
import io

# 1. 基础环境配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 核心逻辑模块 ====================

def get_mtop_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算阿里签名：token 只要下划线前的部分"""
    tk_prefix = token.split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def force_extract_tk(session, raw_text=""):
    """多渠道暴力提取 _m_h5_tk"""
    # 优先从 Session Cookies 拿
    tk = session.cookies.get("_m_h5_tk")
    if tk: return tk
    # 其次从原始文本正则匹配
    match = re.search(r'_m_h5_tk=([^; ]+)', raw_text)
    if match: return match.group(1).strip()
    return None

def parse_input_to_session(session, raw_text):
    """解析 Headers 或纯 Cookie 并注入 Session"""
    headers = {}
    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
    for line in lines:
        if line.startswith(('POST ', 'GET ', 'HTTP/')): continue
        if ':' in line:
            k, v = line.split(':', 1)
            k, v = k.strip().lower(), v.strip()
            if k == 'cookie':
                for item in v.split(';'):
                    if '=' in item:
                        ck, cv = item.strip().split('=', 1)
                        session.cookies.set(ck.strip(), cv.strip())
            else:
                headers[k] = v
        elif '=' in line: # 适配纯 Cookie 字符串
            for item in line.split(';'):
                if '=' in item:
                    ck, cv = item.strip().split('=', 1)
                    session.cookies.set(ck.strip(), cv.strip())
    
    # 注入必备 Header 指纹
    headers.update({"x-tap": "wx", "xweb_xhr": "1"})
    # 移除可能引起冲突的头
    for k in ['content-length', 'host', 'content-type', 'connection', 'priority']:
        headers.pop(k, None)
    return headers

# ==================== 业务执行模块 ====================

def run_sync_process(item_id, file_bytes, file_name, raw_input):
    session = requests.Session()
    session.verify = False
    
    # 注入凭证
    headers = parse_input_to_session(session, raw_input)
    current_tk = force_extract_tk(session, raw_input)
    
    if not current_tk:
        return False, "❌ 未能识别到 _m_h5_tk。请确保粘贴了完整的 Cookie。"

    try:
        # --- 步骤 A: 上传图片 ---
        st.info(f"正在上传图片... (当前Token: {current_tk[:6]}...)")
        t1 = str(int(time.time() * 1000))
        biz_data = json.dumps({"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID})
        sign1 = get_mtop_sign(current_tk, t1, APP_KEY, biz_data)
        
        up_params = {"appkey":"fleamarket","jsv":"2.4.12","appKey":APP_KEY,"t":t1,"sign":sign1,"api":"mtop.taobao.util.uploadImage","v":"1.0","type":"originaljson"}
        files = [('data',(None, biz_data)), ('file',(file_name, file_bytes, 'image/png'))]
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=headers, timeout=20)
        img_match = re.search(r'"url":"(https?://img\.alicdn\.com/[^"]+)"', res_up.text)
        
        if not img_match:
            return False, f"CDN上传失败: {res_up.text[:150]}"
        
        img_url = img_match.group(1).replace('\\/', '/')
        st.success(f"图片上传成功")

        # --- 核心：动态更新 Token ---
        new_tk = force_extract_tk(session)
        if new_tk: 
            current_tk = new_tk
            st.caption("✨ 令牌已自动完成第二阶段同步")

        # --- 步骤 B: 修改商品主图 ---
        st.info("正在更新闲鱼商品信息...")
        t2 = str(int(time.time() * 1000))
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major":True,"type":0,"url":img_url,"widthSize":"640","heightSize":"640"}],
            "utdid": FIXED_UTDID, "platform": "windows"
        }
        edit_json = json.dumps(edit_data, ensure_ascii=False)
        sign2 = get_mtop_sign(current_tk, t2, APP_KEY, edit_json)
        
        edit_params = {"jsv":"2.4.12","appKey":APP_KEY,"t":t2,"sign":sign2,"v":"1.0","api":EDIT_API,"accountSite":"xianyu","type":"originaljson"}
        
        # 必须模拟 Form 表单提交
        headers["content-type"] = "application/x-www-form-urlencoded"
        payload = f"data={urllib.parse.quote(edit_json)}"
        
        res_edit = session.post(f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/2.0/", 
                                params=edit_params, data=payload, headers=headers)
        
        result = res_edit.json()
        if "SUCCESS" in str(result.get("ret")):
            return True, "🎊 商品同步成功！主图已更新。"
        else:
            return False, f"同步失败: {result.get('ret')}"

    except Exception as e:
        return False, f"系统错误: {str(e)}"

# ==================== Streamlit 界面 ====================

st.set_page_config(page_title="闲鱼主图助手V10", layout="wide")
st.title("🐠 闲鱼微信主图同步助手")

with st.expander("📖 使用说明"):
    st.write("1. 在微信闲鱼小程序打开‘编辑宝贝’。")
    st.write("2. 抓取 `mtop.idle.wx.idleitem.edit` 请求。")
    st.write("3. 将 **Headers** 或 **Cookie** 粘贴到下方，点击启动。")

c1, c2 = st.columns(2)

with c1:
    st.subheader("身份指纹注入")
    input_text = st.text_area("粘贴 Headers 或 Cookie 字符串", height=350, 
                              placeholder="cookie2=...; _m_h5_tk=...")

with c2:
    st.subheader("同步设置")
    target_iid = st.text_input("商品 itemId", value="1033424722209")
    target_file = st.file_uploader("上传图片", type=['png', 'jpg', 'jpeg'])
    
    if st.button("🚀 启动同步任务", use_container_width=True):
        if not input_text or not target_file:
            st.warning("请检查凭证或图片是否缺失")
        else:
            ok, msg = run_sync_process(target_iid, target_file.read(), target_file.name, input_text)
            if ok:
                st.balloons()
                st.success(msg)
            else:
                st.error(msg)
