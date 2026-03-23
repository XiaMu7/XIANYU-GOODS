import streamlit as st
import requests
import re
import time
import json
import urllib3

# 禁用警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 从你提供的 cURL 中提取的固定配置
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
REFERER = "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.7(0x13080712) UnifiedPCMacWechat(0xf26406f0) XWEB/14304"

def run_sync_via_curl(item_id, file_bytes, cookie_str):
    session = requests.Session()
    
    # 1. 注入 Cookie
    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', cookie_str)
    for k, v in kv_pairs:
        session.cookies.set(k.strip(), v.strip(), domain="stream-upload.goofish.com")

    # 2. 构造 Headers (完全复刻 cURL)
    headers = {
        "User-Agent": UA,
        "xweb_xhr": "1",
        "sec-fetch-site": "cross-site",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": REFERER,
        "accept-language": "zh-CN,zh;q=0.9",
        "priority": "u=1, i"
    }

    # 3. 构造参数 (完全复刻 cURL)
    params = {
        "floderId": "0",
        "appkey": "fleamarket",
        "_input_charset": "utf-8"
    }

    try:
        # --- 步骤 1: 上传图片 ---
        st.info("📤 正在复刻 cURL 环境上传图片...")
        
        # 严格按照 cURL 中的表单字段
        files = {
            'bizCode': (None, 'fleamarket'),
            'name': (None, 'fileFromAlbum'),
            'file': ('image.jpg', file_bytes, 'image/jpeg')
        }

        res_up = session.post(
            UPLOAD_URL, 
            params=params, 
            headers=headers, 
            files=files, 
            timeout=30
        )

        st.text_area("服务器返回原始数据", value=res_up.text, height=100)

        # 尝试解析返回的图片 URL
        # 阿里这个接口成功通常返回格式如: {"url":"...","object":"..."} 或类似的 JSON
        try:
            res_data = res_up.json()
            # 兼容多种可能的返回路径
            img_url = res_data.get('url') or res_data.get('object', {}).get('url')
        except:
            # 备选：如果返回的是纯文本 URL
            img_url = res_up.text if "http" in res_up.text else None

        if not img_url:
            return False, "❌ 上传成功但未获取到 URL，请检查返回数据。"

        st.success(f"✅ 图片上传成功: {img_url[:50]}...")

        # --- 步骤 2: 修改宝贝主图 ---
        # 注意：修改接口依然需要 _m_h5_tk 签名，请确保 Cookie 包含它
        st.info("🚀 正在同步修改宝贝主图...")
        
        # 这里延用之前的详情修改逻辑，但需要从 session 中取最新的 tk
        tk_full = session.cookies.get("_m_h5_tk")
        if not tk_full:
            return False, "❌ 缺少 _m_h5_tk，无法完成最后一步修改。"
        
        tk_prefix = tk_full.split('_')[0]
        t = str(int(time.time() * 1000))
        edit_api = "mtop.idle.wx.idleitem.edit"
        edit_data = {
            "itemId": str(item_id),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0}],
            "utdid": "v3UyIt1jJFECAXAaAnEns/UL",
            "platform": "wx_mini"
        }
        data_str = json.dumps(edit_data, separators=(',', ':'))
        sign = hashlib.md5(f"{tk_prefix}&{t}&12574478&{data_str}".encode('utf-8')).hexdigest()

        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{edit_api}/1.0/",
            params={"appKey": "12574478", "t": t, "sign": sign, "api": edit_api, "v": "1.0", "type": "originaljson"},
            data={"data": data_str},
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA}
        )

        if "SUCCESS" in res_edit.text:
            return True, "🎊 修改成功！主图已同步。"
        else:
            return False, f"修改失败: {res_edit.text}"

    except Exception as e:
        return False, f"运行出错: {str(e)}"

# ==================== Streamlit UI ====================
st.title("🐠 闲鱼 cURL 复刻同步器")
st.markdown("使用你提供的 `stream-upload` 接口参数进行强制同步。")

# 只输入 Cookie 部分，因为 URL 和 Headers 已经写死在脚本里最稳
cookie_input = st.text_area("粘贴 cURL 里的 Cookie 部分", height=150)
item_id = st.text_input("商品 itemId", "1033424722209")
img_file = st.file_uploader("选择新图片")

if st.button("开始强制同步", use_container_width=True):
    if cookie_input and img_file:
        ok, msg = run_sync_via_curl(item_id, img_file.read(), cookie_input)
        if ok: st.success(msg)
        else: st.error(msg)
