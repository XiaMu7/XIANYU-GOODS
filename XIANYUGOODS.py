import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3
from urllib.parse import quote

# 1. 基础环境
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781"

def run_final_sync(item_id, file_bytes, cookie_str, tk_input):
    session = requests.Session()
    
    # 动态提取 Cookie 中的 utdid，如果没有则用默认值
    utdid_match = re.search(r'utdid=([^;]+)', cookie_str)
    current_utdid = utdid_match.group(1) if utdid_match else "v3UyIt1jJFECAXAaAnEns/UL"

    # 注入 Cookie
    for k, v in re.findall(r'([^=\s;]+)=([^;]*)', cookie_str):
        session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")
    
    # 强制注入 Token
    full_tk = tk_input.strip()
    clean_tk = full_tk.split('_')[0]
    session.cookies.set("_m_h5_tk", full_tk, domain=".goofish.com")
    session.cookies.set("_m_h5_tk_enc", "any", domain=".goofish.com")

    common_headers = {
        "User-Agent": UA,
        "xweb_xhr": "1",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

    try:
        # --- 步骤 1: 上传图片 (保持原样) ---
        st.info("📤 步骤 1: 上传图片...")
        up_params = {"floderId": "0", "appkey": "fleamarket", "_input_charset": "utf-8"}
        files = {
            'bizCode': (None, 'fleamarket'),
            'name': (None, 'fileFromAlbum'),
            'file': ('image.jpg', file_bytes, 'image/jpeg')
        }
        res_up = session.post(UPLOAD_URL, params=up_params, headers=common_headers, files=files, timeout=30)
        
        try:
            img_url = res_up.json().get('url') or res_up.json().get('object', {}).get('url')
        except:
            img_url = res_up.text if "http" in res_up.text else None

        if not img_url: return False, "图片上传失败"
        st.success("✅ 图片上传成功")

        # --- 步骤 2: 修改主图 (指纹加固版) ---
        st.info("🚀 步骤 2: 提交修改...")
        t = str(int(time.time() * 1000))
        
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": 1024, "heightSize": 1024}],
            "utdid": current_utdid,
            "platform": "wx_mini"
        }
        data_str = json.dumps(edit_data, separators=(',', ':'))
        
        # 签名计算
        sign = hashlib.md5(f"{clean_tk}&{t}&{APP_KEY}&{data_str}".encode('utf-8')).hexdigest()

        # 核心：URL 参数必须与 POST 表单内容完全对应
        params = {
            "jsv": "2.7.2",
            "appKey": APP_KEY,
            "t": t,
            "sign": sign,
            "v": "1.0",
            "api": EDIT_API,
            "type": "originaljson",
            "dataType": "json"
        }

        # 核心：手动构造 Body 并进行 URL 编码
        payload = f"data={quote(data_str)}"

        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=params,
            data=payload,
            headers={
                **common_headers,
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )

        res_json = res_edit.json()
        if "SUCCESS" in str(res_json.get("ret")):
            return True, "🎊 修改成功！"
        else:
            return False, f"修改失败: {res_json.get('ret')}"

    except Exception as e:
        return False, f"程序异常: {str(e)}"

# UI 保持不变... (省略，直接用上面的 UI 代码即可)
