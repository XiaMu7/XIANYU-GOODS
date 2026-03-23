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
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781"

# ==================== 核心逻辑 ====================

def run_final_sync(item_id, file_bytes, cookie_str, tk_input):
    session = requests.Session()
    
    # 1. 注入 Cookie
    for k, v in re.findall(r'([^=\s;]+)=([^;]*)', cookie_str):
        session.cookies.set(k.strip(), v.strip(), domain="stream-upload.goofish.com")
        session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")

    headers = {
        "User-Agent": UA,
        "xweb_xhr": "1",
        "referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html"
    }

    try:
        # --- 步骤 1: 上传图片 (复刻你的 cURL) ---
        st.info("📤 正在上传图片...")
        up_params = {"floderId": "0", "appkey": "fleamarket", "_input_charset": "utf-8"}
        files = {
            'bizCode': (None, 'fleamarket'),
            'name': (None, 'fileFromAlbum'),
            'file': ('image.jpg', file_bytes, 'image/jpeg')
        }
        
        res_up = session.post(UPLOAD_URL, params=up_params, headers=headers, files=files, timeout=20)
        
        # 提取上传后的图片 URL
        try:
            res_data = res_up.json()
            img_url = res_data.get('url') or res_data.get('object', {}).get('url')
        except:
            img_url = res_up.text if "http" in res_up.text else None

        if not img_url:
            return False, f"上传失败，原始响应: {res_up.text}"
        
        st.success(f"✅ 图片上传成功")

        # --- 步骤 2: 修改主图 (使用手动输入的 Token) ---
        st.info("🚀 正在提交修改请求...")
        
        # 自动清洗 Token：只取下划线前的 MD5 部分
        clean_tk = tk_input.split('_')[0]
        t = str(int(time.time() * 1000))
        
        # 组装修改参数
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": 1024, "heightSize": 1024}],
            "utdid": "v3UyIt1jJFECAXAaAnEns/UL",
            "platform": "wx_mini"
        }
        data_str = json.dumps(edit_data, separators=(',', ':'))
        
        # 计算签名 (token&t&appKey&data)
        sign_str = f"{clean_tk}&{t}&{APP_KEY}&{data_str}"
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

        edit_params = {
            "appKey": APP_KEY, "t": t, "sign": sign, "api": EDIT_API, 
            "v": "1.0", "type": "originaljson"
        }

        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=edit_params,
            data={"data": data_str},
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}
        )

        if "SUCCESS" in res_edit.text:
            return True, "🎊 恭喜！同步修改已全部完成。"
        else:
            return False, f"修改失败，返回: {res_edit.text}"

    except Exception as e:
        return False, f"程序异常: {str(e)}"

# ==================== UI 界面 ====================
st.title("🐠 闲鱼主图同步 (手动 Token 版)")

col1, col2 = st.columns(2)
with col1:
    item_id = st.text_input("1. 商品 itemId", "1033424722209")
with col2:
    tk_val = st.text_input("2. 输入 _m_h5_tk", placeholder="例如: 095c6d9d5ba5..._177426...")

cookie_area = st.text_area("3. 粘贴 cURL 里的 Cookie", height=100)
img_file = st.file_uploader("4. 选择新图片")

if st.button("🔥 执行最终同步", use_container_width=True):
    if not tk_val:
        st.warning("请填入 _m_h5_tk 令牌！")
    elif cookie_area and img_file:
        ok, msg = run_final_sync(item_id, img_file.read(), cookie_area, tk_val)
        st.success(msg) if ok else st.error(msg)
