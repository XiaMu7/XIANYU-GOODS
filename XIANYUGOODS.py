import streamlit as st
import hashlib
import json
import time
import re
import urllib.parse
import requests
import urllib3
import mimetypes

# 基础设置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 核心逻辑：签名与动态令牌 ====================

def get_mtop_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算阿里 MTOP 签名，取 _m_h5_tk 下划线前的部分"""
    tk_prefix = token.split('_')[0]
    base_str = f"{tk_prefix}&{t}&{app_key}&{data_str}"
    return hashlib.md5(base_str.encode('utf-8')).hexdigest()

def sync_token_from_session(session):
    """从 Session 的 Cookies 中实时提取最新的 _m_h5_tk"""
    tk = session.cookies.get("_m_h5_tk", domain=".goofish.com") or \
         session.cookies.get("_m_h5_tk", domain=".taobao.com") or \
         session.cookies.get("_m_h5_tk")
    return tk

def parse_raw_headers(raw_text):
    """解析原始 Headers 并提取初始 Cookies"""
    headers = {}
    cookies = {}
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
                        cookies[ck.strip()] = cv.strip()
            else:
                headers[k] = v
    # 清洗 Header 冲突项
    forbidden = ['content-length', 'host', 'content-type', 'priority', 'connection']
    for k in forbidden: headers.pop(k, None)
    headers.update({"x-tap": "wx", "xweb_xhr": "1"})
    return headers, cookies

# ==================== 业务执行函数 ====================

def run_sync_task(item_id, file_bytes, file_name, raw_headers):
    # 1. 初始化 Session
    session = requests.Session()
    session.verify = False
    
    # 2. 注入初始凭证
    headers, init_cookies = parse_raw_headers(raw_headers)
    for k, v in init_cookies.items():
        session.cookies.set(k, v)
    
    # 获取初始 Token
    current_tk = sync_token_from_session(session)
    if not current_tk:
        return False, "❌ Cookie 中找不到 _m_h5_tk，请重新抓包并完整粘贴！"

    try:
        # --- [第一步：上传图片] ---
        st.write("⏳ 正在上传图片...")
        t1 = str(int(time.time() * 1000))
        biz_data = json.dumps({"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID})
        sign1 = get_mtop_sign(current_tk, t1, APP_KEY, biz_data)
        
        up_params = {
            "appkey": "fleamarket", "jsv": "2.4.12", "appKey": APP_KEY, 
            "t": t1, "sign": sign1, "api": "mtop.taobao.util.uploadImage", 
            "v": "1.0", "type": "originaljson"
        }
        
        files = [
            ('data', (None, biz_data)),
            ('file', (file_name, file_bytes, 'image/png'))
        ]
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=headers, timeout=20)
        img_match = re.search(r'"url":"(https?://img\.alicdn\.com/[^"]+)"', res_up.text)
        
        if not img_match:
            return False, f"图片上传阶段失败 (可能 bx-ua 已过期): {res_up.text[:200]}"
        
        final_url = img_match.group(1).replace('\\/', '/')
        st.write(f"✅ 图片上传成功: {final_url}")

        # --- [核心：强制同步令牌] ---
        # 上传后服务器可能通过 set-cookie 给了一个新令牌，必须重新同步
        new_tk = sync_token_from_session(session)
        if new_tk:
            current_tk = new_tk
            st.info(f"💡 令牌已动态更新")

        # --- [第二步：修改商品主图] ---
        st.write("⏳ 正在同步到商品...")
        t2 = str(int(time.time() * 1000))
        edit_obj = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "type": 0, "url": final_url, "widthSize": "640", "heightSize": "640"}],
            "utdid": FIXED_UTDID, "platform": "windows"
        }
        edit_str = json.dumps(edit_obj, ensure_ascii=False)
        sign2 = get_mtop_sign(current_tk, t2, APP_KEY, edit_str)
        
        edit_params = {
            "jsv": "2.4.12", "appKey": APP_KEY, "t": t2, "sign": sign2,
            "v": "1.0", "api": EDIT_API, "accountSite": "xianyu", "type": "originaljson"
        }
        
        edit_headers = headers.copy()
        edit_headers["content-type"] = "application/x-www-form-urlencoded"
        payload = f"data={urllib.parse.quote(edit_str)}"
        
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/2.0/", 
            params=edit_params, data=payload, headers=edit_headers
        )
        
        ret_data = res_edit.json()
        if "SUCCESS" in str(ret_data.get("ret")):
            return True, "🎉 商品主图同步成功！"
        else:
            return False, f"修改失败: {ret_data.get('ret')}"

    except Exception as e:
        return False, f"程序运行崩溃: {str(e)}"

# ==================== Streamlit UI ====================

st.set_page_config(page_title="闲鱼主图助手", layout="wide")
st.title("🐠 闲鱼微信版 - 主图全自动同步器")

c1, c2 = st.columns(2)

with c1:
    st.subheader("1. 环境指纹注入")
    raw_h = st.text_area("粘贴 Charles/Fiddler 原始 Headers (含完整 Cookie)", height=450, 
                         placeholder="包含 bx-ua, mini-janus, _m_h5_tk 等关键指纹...")
    st.caption("提示：请在微信里‘修改一次商品’，抓取那个 POST 请求的 Headers。")

with c2:
    st.subheader("2. 同步任务配置")
    target_id = st.text_input("目标商品 itemId", value="1033424722209")
    img_file = st.file_uploader("选择新主图", type=['png', 'jpg', 'jpeg'])
    
    if st.button("🚀 启动指纹级同步", use_container_width=True):
        if not raw_h:
            st.error("请先粘贴 Headers 内容！")
        elif not img_file:
            st.error("请上传图片！")
        else:
            success, message = run_sync_task(target_id, img_file.read(), img_file.name, raw_h)
            if success:
                st.balloons()
                st.success(message)
            else:
                st.error(message)
