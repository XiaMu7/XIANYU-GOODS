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
DETAIL_API = "mtop.idle.wx.idleitem.detail" # 获取详情
EDIT_API = "mtop.idle.wx.idleitem.edit"     # 覆盖提交
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 核心逻辑 ====================

def get_cookie(session, name):
    for c in session.cookies:
        if c.name == name: return c.value
    return None

def get_sign(token, t, data_str):
    tk_prefix = str(token).split('_')[0]
    base = f"{tk_prefix}&{t}&{APP_KEY}&{data_str}"
    return hashlib.md5(base.encode('utf-8')).hexdigest()

def run_full_sync(item_id, file_bytes, cookie_input):
    session = requests.Session()
    # 注入 Cookie
    for k, v in re.findall(r'([^=\s;]+)=([^;]*)', cookie_input):
        session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")
    
    tk = get_cookie(session, "_m_h5_tk")
    if not tk: return False, "❌ 缺少 _m_h5_tk"

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "x-tap": "wx", "xweb_xhr": "1",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        # --- 阶段 0: 获取宝贝完整原始信息 ---
        st.info("🔍 阶段 0: 正在获取宝贝原始详情...")
        t0 = str(int(time.time() * 1000))
        detail_data = json.dumps({"itemId": str(item_id)}, separators=(',', ':'))
        sign0 = get_sign(tk, t0, detail_data)
        
        res_detail = session.get(
            f"https://acs.m.goofish.com/h5/{DETAIL_API}/1.0/",
            params={"jsv":"2.4.12","appKey":APP_KEY,"t":t0,"sign":sign0,"v":"1.0","api":DETAIL_API,"type":"originaljson","data":detail_data},
            headers=headers
        )
        
        full_info = res_detail.json().get("data", {}).get("itemDO", {})
        if not full_info:
            return False, f"获取详情失败: {res_detail.text}"
        st.success("✅ 原始数据提取成功")

        # --- 阶段 1: 上传新主图 ---
        st.info("📤 阶段 1: 正在上传新主图...")
        t1 = str(int(time.time() * 1000))
        biz_str = json.dumps({"bizCode":"idleItemEdit","clientType":"pc","utdid":FIXED_UTDID}, separators=(',', ':'))
        sign1 = get_sign(tk, t1, biz_str)
        
        files = [('data',(None,biz_str)), ('file',('img.png',file_bytes,'image/png'))]
        res_up = session.post(UPLOAD_URL, params={"appKey":APP_KEY,"t":t1,"sign":sign1,"api":"mtop.taobao.util.uploadImage","v":"1.0","type":"originaljson"}, files=files)
        
        img_url = res_up.json().get('url') or res_up.json().get('object', {}).get('url')
        if not img_url: return False, "上传图片失败"
        st.success(f"✅ 图片已托管: {img_url[:30]}...")

        # --- 阶段 2: 组装全量数据并覆盖提交 ---
        st.info("🚀 阶段 2: 正在执行全量覆盖更新...")
        # 核心：保留原样，只改图片
        # 闲鱼编辑接口需要将原始 itemDO 转换为提交格式
        submit_data = {
            "itemId": str(item_id),
            "title": full_info.get("title"),
            "desc": full_info.get("desc"),
            "price": full_info.get("price"),
            "categoryId": full_info.get("categoryId"),
            "divisionId": full_info.get("divisionId"),
            # 替换图片列表的第一张
            "imageInfoDOList": [{
                "major": True, "url": img_url, "type": 0, "widthSize": 800, "heightSize": 800
            }],
            "utdid": FIXED_UTDID,
            "platform": "wx_mini"
        }
        
        # 补全可能缺失的其他字段（可选）
        if full_info.get("postage"): submit_data["postage"] = full_info.get("postage")

        final_json = json.dumps(submit_data, ensure_ascii=False, separators=(',', ':'))
        tk = get_cookie(session, "_m_h5_tk") or tk # 刷新tk
        t2 = str(int(time.time() * 1000))
        sign2 = get_sign(tk, t2, final_json)

        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params={"jsv":"2.4.12","appKey":APP_KEY,"t":t2,"sign":sign2,"v":"1.0","api":EDIT_API,"type":"originaljson"},
            data={"data": final_json},
            headers=headers
        )

        if "SUCCESS" in res_edit.text:
            return True, "🎊 全量同步覆盖成功！主图已更新。"
        else:
            return False, f"覆盖失败: {res_edit.text}"

    except Exception as e:
        return False, f"运行故障: {str(e)}"

# ==================== UI ====================
st.title("🐠 闲鱼宝贝全量覆盖助手")
st.warning("此模式会先读取宝贝详情，然后进行完整覆盖提交，稳定性更高。")

c_input = st.text_area("1. 粘贴完整 Cookie", height=130)
i_id = st.text_input("2. 商品 itemId", value="1033424722209")
i_file = st.file_uploader("3. 选择新主图")

if st.button("🔥 执行全量覆盖同步", use_container_width=True):
    if c_input and i_file:
        ok, msg = run_full_sync(i_id, i_file.read(), c_input)
        st.success(msg) if ok else st.error(msg)
