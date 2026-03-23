import streamlit as st
import hashlib
import json
import time
import re
import requests
import urllib3
from urllib.parse import quote

# 基础环境配置
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
APP_KEY = "12574478"
EDIT_API = "mtop.idle.wx.idleitem.edit"
PC_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

def get_tk_logic(cookie_str):
    """从 Cookie 中提取 _m_h5_tk 的前缀作为签名密钥"""
    tk_match = re.search(r'_m_h5_tk=([a-f0-9]+)_(\d+)', cookie_str)
    if tk_match:
        full_tk = f"{tk_match.group(1)}_{tk_match.group(2)}"
        clean_tk = tk_match.group(1)
        return full_tk, clean_tk
    return None, None

def run_sync_process(item_id, file_bytes, cookie_str):
    session = requests.Session()
    
    # 1. 解析 Token
    full_tk, clean_tk = get_tk_logic(cookie_str)
    if not clean_tk:
        return False, "❌ Cookie 格式错误：未找到 _m_h5_tk。请确保从浏览器 Network 标签完整复制。"

    # 2. 注入 Cookie 域
    kv_pairs = re.findall(r'([^=\s;]+)=([^;]*)', cookie_str)
    for k, v in kv_pairs:
        key, val = k.strip(), v.strip()
        session.cookies.set(key, val, domain=".goofish.com")
        session.cookies.set(key, val, domain=".taobao.com")

    # 公共请求头
    base_headers = {
        "User-Agent": PC_UA,
        "Origin": "https://2.taobao.com",
        "Referer": "https://2.taobao.com/",
        "Accept": "application/json, text/plain, */*"
    }

    try:
        # --- 步骤 A: 上传图片 (增加 bizCode) ---
        st.write("📤 正在上传图片流...")
        up_params = {
            "appkey": "fleamarket",
            "bizCode": "fleamarket",  # 显式指定业务码
            "_input_charset": "utf-8",
            "floderId": "0"
        }
        files = {'file': ('image.jpg', file_bytes, 'image/jpeg')}
        
        res_up = session.post(
            "https://stream-upload.goofish.com/api/upload.api",
            params=up_params,
            headers=base_headers,
            files=files,
            timeout=30
        )
        
        up_data = res_up.json()
        img_url = up_data.get('url') or up_data.get('object', {}).get('url')
        
        if not img_url:
            return False, f"图片上传失败，服务器返回：{res_up.text}"
        
        st.write(f"✅ 图片上传成功，地址：`{img_url[:40]}...`")

        # --- 步骤 B: 修改商品 (核心修复版) ---
        st.write("🚀 正在提交业务修改请求...")
        t = str(int(time.time() * 1000))
        
        # 修复点 1：itemId 必须尝试转换为数字类型，避免后端 Long 解析异常
        try:
            final_item_id = int(item_id)
        except ValueError:
            final_item_id = str(item_id)

        # 修复点 2：构造标准业务 JSON (补充长宽和排序)
        edit_data = {
            "itemId": final_item_id,
            "imageInfoDOList": [{
                "major": True, 
                "url": img_url, 
                "type": 0, 
                "widthSize": 1024, 
                "heightSize": 1024
            }],
            "platform": "pc"
        }
        
        # 修复点 3：确保签名字符串和 Data 字符串完全一致 (无空格，Key 排序)
        data_str = json.dumps(edit_data, separators=(',', ':'), sort_keys=True)
        
        # 计算签名: token&t&appKey&data
        sign_origin = f"{clean_tk}&{t}&{APP_KEY}&{data_str}"
        sign = hashlib.md5(sign_origin.encode('utf-8')).hexdigest()

        mtop_params = {
            "jsv": "2.6.1",
            "appKey": APP_KEY,
            "t": t,
            "sign": sign,
            "v": "1.0",
            "api": EDIT_API,
            "type": "json",
            "dataType": "json"
        }

        # 发送业务请求
        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params=mtop_params,
            data={"data": data_str},
            headers={"Content-Type": "application/x-www-form-urlencoded", **base_headers}
        )

        resp_json = res_edit.json()
        ret_list = resp_json.get("ret", ["未知错误"])
        
        if "SUCCESS" in ret_list[0]:
            return True, "🎊 恭喜！闲鱼主图已成功同步更新。"
        else:
            return False, f"业务同步失败：{ret_list[0]}\n提示：{resp_json.get('data', {}).get('errorMsg', '服务器未给出具体原因')}"

    except Exception as e:
        return False, f"程序执行异常：{str(e)}"

# --- Streamlit 界面 ---
st.set_page_config(page_title="闲鱼同步助手-修复版", page_icon="🐟")
st.title("🐟 闲鱼主图同步 (稳定版)")

st.info("💡 提示：如果依然报错 'UNKNOWN_THROWABLE'，请检查该商品是否为【下架】状态，或者该 itemId 是否属于当前 Cookie 登录的账号。")

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        item_id_input = st.text_input("📦 商品 itemId", placeholder="1033424722209")
    with col2:
        img_file = st.file_uploader("🖼️ 上传主图", type=['jpg', 'jpeg', 'png'])

    cookie_input = st.text_area("🔑 粘贴 Cookie 全文", height=150, placeholder="st=success; _m_h5_tk=...; _m_h5_tk_enc=...")

if st.button("🚀 执行同步任务"):
    if not item_id_input or not cookie_input or not img_file:
        st.error("请完整填写所有信息！")
    else:
        with st.status("正在处理...", expanded=True) as status:
            success, msg = run_sync_process(item_id_input, img_file.read(), cookie_input)
            if success:
                status.update(label="处理成功！", state="complete")
                st.balloons()
                st.success(msg)
            else:
                status.update(label="执行失败", state="error")
                st.error(msg)
