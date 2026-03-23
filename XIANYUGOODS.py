import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3
import shlex

# 1. 基础配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 逻辑处理模块 ====================

def get_cookie_value_safe(session, name):
    for c in session.cookies:
        if c.name == name: return c.value
    return None

def parse_credentials(session, input_str):
    """支持 cURL 解析和普通字符串解析"""
    if input_str.strip().startswith('curl'):
        parts = shlex.split(input_str)
        for i in range(len(parts)):
            if parts[i] in ['-H', '--header']:
                header_line = parts[i+1]
                if ':' in header_line and header_line.lower().startswith('cookie:'):
                    cookie_content = header_line.split(':', 1)[1]
                    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', cookie_content)
                    for k, v in kv_pairs:
                        session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")
        return True
    else:
        kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', input_str)
        for k, v in kv_pairs:
            session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")
        return len(kv_pairs) > 0

def run_sync_process(item_id, file_bytes, cred_input):
    session = requests.Session()
    parse_credentials(session, cred_input)
    
    full_tk = get_cookie_value_safe(session, "_m_h5_tk")
    if not full_tk:
        return False, "❌ 未发现 _m_h5_tk，请重新抓包。"

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "x-tap": "wx", "xweb_xhr": "1",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html"
    }

    try:
        # --- 步骤 1: 上传图片 ---
        st.info("🔄 步骤 1: 正在同步图片到云端...")
        t1 = str(int(time.time() * 1000))
        biz_data = {"bizCode": "idleItemEdit", "clientType": "pc", "utdid": FIXED_UTDID}
        biz_str = json.dumps(biz_data, separators=(',', ':'))
        sign1 = hashlib.md5(f"{full_tk.split('_')[0]}&{t1}&{APP_KEY}&{biz_str}".encode('utf-8')).hexdigest()
        
        up_params = {"appkey":"fleamarket","appKey":APP_KEY,"t":t1,"sign":sign1,"api":"mtop.taobao.util.uploadImage","v":"1.0","type":"originaljson"}
        files = [('data',(None,biz_str)), ('file',('img.png',file_bytes,'image/png'))]
        
        res_up = session.post(UPLOAD_URL, params=up_params, files=files, headers=headers)
        if "success\":true" not in res_up.text.lower():
            return False, f"上传失败: {res_up.text}"
        
        img_url = res_up.json().get('url') or res_up.json().get('object', {}).get('url')
        st.success("✅ 图片上传成功")

        # --- 步骤 2: 修改主图 (核心优化点) ---
        st.info("🔄 步骤 2: 正在更新商品主图...")
        # 获取可能翻转的最新 Token
        new_tk = get_cookie_value_safe(session, "_m_h5_tk") or full_tk
        t2 = str(int(time.time() * 1000))
        
        # 更加丰满的参数结构，绕过 UNKNOWN_THROWABLE
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{
                "major": True, 
                "url": img_url, 
                "type": 0, 
                "index": 0,  # 显式指定索引
                "widthSize": 800,  # 尝试传数字而非字符串
                "heightSize": 800
            }],
            "bizType": "idleItem", # 增加业务类型标识
            "utdid": FIXED_UTDID,
            "platform": "wx_mini" # 标记为微信小程序环境
        }
        
        edit_str = json.dumps(edit_data, ensure_ascii=False, separators=(',', ':'))
        sign2 = hashlib.md5(f"{new_tk.split('_')[0]}&{t2}&{APP_KEY}&{edit_str}".encode('utf-8')).hexdigest()
        
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params={"jsv":"2.4.12","appKey":APP_KEY,"t":t2,"sign":sign2,"v":"1.0","api":EDIT_API,"type":"originaljson"},
            data={"data": edit_str},
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}
        )
        
        res_json = res_edit.json()
        if "SUCCESS" in str(res_json.get("ret")):
            return True, "🎊 恭喜，商品主图已更新成功！"
        else:
            # 如果依然失败，提示用户检查商品状态
            error_msg = str(res_json.get("ret"))
            if "UNKNOWN_THROWABLE" in error_msg:
                return False, "❌ 业务异常：可能是商品已被锁定或处于风险保护期。请尝试在手机上‘擦亮’后再运行。"
            return False, f"修改失败: {error_msg}"

    except Exception as e:
        return False, f"程序异常: {str(e)}"

# ==================== Streamlit 界面 ====================
st.set_page_config(page_title="闲鱼主图神器", page_icon="🐠")
st.title("🐠 闲鱼主图同步助手")

with st.sidebar:
    st.header("💡 使用技巧")
    st.write("1. 确保商品处于【出售中】状态")
    st.write("2. 如果报错业务异常，请在手机上先手动点一下【擦亮】")
    st.write("3. 建议使用 Copy as cURL 粘贴，更稳定")

cred_input = st.text_area("1. 粘贴 Cookie 或 cURL", height=150)
target_id = st.text_input("2. 商品 itemId", value="1033424722209")
target_img = st.file_uploader("3. 选择新主图")

if st.button("🚀 立即执行同步", use_container_width=True):
    if cred_input and target_img:
        ok, msg = run_sync_process(target_id, target_img.read(), cred_input)
        if ok:
            st.balloons()
            st.success(msg)
        else:
            st.error(msg)
