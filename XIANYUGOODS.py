import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3

# 1. 基础环境配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
# 模拟你 cURL 中的真实 UA
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781"

# ==================== 核心逻辑 ====================

def run_final_sync(item_id, file_bytes, cookie_str, tk_input):
    # 创建持久化 Session
    session = requests.Session()
    
    # --- 步骤 0: 预处理 Cookie 和 Token ---
    # 注入原始 Cookie 字符串中的所有项
    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', cookie_str)
    for k, v in kv_pairs:
        key, val = k.strip(), v.strip()
        # 注入到主域名和上传域名
        session.cookies.set(key, val, domain=".goofish.com")
        session.cookies.set(key, val, domain="stream-upload.goofish.com")

    # 【关键修复】强行覆盖/注入手动输入的 Token 到 Cookie 中
    # 这样请求头里就会带上：Cookie: ...;_m_h5_tk=xxxx;...
    full_tk = tk_input.strip()
    clean_tk = full_tk.split('_')[0]
    session.cookies.set("_m_h5_tk", full_tk, domain=".goofish.com")
    session.cookies.set("_m_h5_tk_enc", "any_value", domain=".goofish.com")

    common_headers = {
        "User-Agent": UA,
        "xweb_xhr": "1",
        "referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html"
    }

    try:
        # --- 步骤 1: 上传图片 (复刻 cURL 逻辑) ---
        st.info("📤 正在上传图片到阿里 CDN...")
        up_params = {"floderId": "0", "appkey": "fleamarket", "_input_charset": "utf-8"}
        files = {
            'bizCode': (None, 'fleamarket'),
            'name': (None, 'fileFromAlbum'),
            'file': ('image.jpg', file_bytes, 'image/jpeg')
        }
        
        res_up = session.post(UPLOAD_URL, params=up_params, headers=common_headers, files=files, timeout=30)
        
        # 尝试解析返回的 URL
        try:
            res_data = res_up.json()
            img_url = res_data.get('url') or res_data.get('object', {}).get('url')
        except:
            img_url = res_up.text if "http" in res_up.text else None

        if not img_url:
            st.error(f"上传接口返回异常: {res_up.text}")
            return False, "图片上传成功但解析 URL 失败"
        
        st.success(f"✅ 图片上传成功")

        # --- 步骤 2: 修改主图 (MTOP 业务请求) ---
        st.info("🚀 正在提交修改主图请求...")
        t = str(int(time.time() * 1000))
        
        # 构造修改参数
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": 1024, "heightSize": 1024}],
            "utdid": "v3UyIt1jJFECAXAaAnEns/UL",
            "platform": "wx_mini"
        }
        data_str = json.dumps(edit_data, separators=(',', ':'))
        
        # 计算签名: token & t & appKey & data
        sign_str = f"{clean_tk}&{t}&{APP_KEY}&{data_str}"
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

        # 发送修改请求
        # 注意：这里不带手动 Cookie，session 会自动带上我们刚才注入的 _m_h5_tk
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params={"appKey": APP_KEY, "t": t, "sign": sign, "api": EDIT_API, "v": "1.0", "type": "originaljson"},
            data={"data": data_str},
            headers={**common_headers, "Content-Type": "application/x-www-form-urlencoded"}
        )

        res_json = res_edit.json()
        if "SUCCESS" in str(res_json.get("ret")):
            return True, "🎊 恭喜！主图同步修改成功。"
        else:
            return False, f"修改失败: {res_json.get('ret')}"

    except Exception as e:
        return False, f"程序运行异常: {str(e)}"

# ==================== Streamlit UI ====================
st.set_page_config(page_title="闲鱼主图同步", page_icon="🐠")
st.title("🐠 闲鱼主图同步 (Token 增强版)")

with st.expander("📝 使用说明"):
    st.write("1. 从抓包的 cURL 中提取原始 Cookie 粘贴到下方。")
    st.write("2. 找到 `_m_h5_tk` 字段（通常带下划线和长数字），单独粘贴到 Token 框。")
    st.write("3. 点击执行，系统会自动完成上传和替换。")

col1, col2 = st.columns(2)
with col1:
    item_id_input = st.text_input("1. 商品 itemId", "1033424722209")
with col2:
    tk_input_val = st.text_input("2. 输入 _m_h5_tk", placeholder="例如: 095c6..._17742...")

cookie_area = st.text_area("3. 粘贴原始 Cookie 字符串", height=100)
uploaded_file = st.file_uploader("4. 选择新主图图片")

if st.button("🔥 执行最终同步", use_container_width=True):
    if not tk_input_val:
        st.warning("⚠️ 必须填写 _m_h5_tk 才能计算签名！")
    elif cookie_area and uploaded_file:
        ok, msg = run_final_sync(item_id_input, uploaded_file.read(), cookie_area, tk_input_val)
        if ok:
            st.balloons()
            st.success(msg)
        else:
            st.error(msg)
