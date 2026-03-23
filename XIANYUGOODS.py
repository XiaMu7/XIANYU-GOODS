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
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# 待探测的详情接口列表（按成功率排序）
DETAIL_APIS = [
    "mtop.taobao.idle.item.get",        # 通用版 (2024-2026 常用)
    "mtop.idle.item.detail",           # H5 标准版
    "mtop.idle.wx.item.detail.get"     # 部分小程序版
]

# ==================== 核心逻辑 ====================

def get_cookie(session, name):
    for c in session.cookies:
        if c.name == name: return c.value
    return None

def get_sign(token, t, data_str):
    tk_prefix = str(token).split('_')[0]
    base = f"{tk_prefix}&{t}&{APP_KEY}&{data_str}"
    return hashlib.md5(base.encode('utf-8')).hexdigest()

def try_get_detail(session, item_id, tk, headers):
    """自动探测可用的详情接口"""
    for api_name in DETAIL_APIS:
        st.write(f"📡 正在尝试探测接口: `{api_name}`...")
        t = str(int(time.time() * 1000))
        data_str = json.dumps({"itemId": str(item_id)}, separators=(',', ':'))
        sign = get_sign(tk, t, data_str)
        
        try:
            res = session.get(
                f"https://acs.m.goofish.com/h5/{api_name}/1.0/",
                params={
                    "jsv": "2.4.12", "appKey": APP_KEY, "t": t, "sign": sign,
                    "v": "1.0", "api": api_name, "type": "originaljson", "data": data_str
                },
                headers=headers, timeout=5
            )
            res_json = res.json()
            # 兼容不同的返回路径
            data = res_json.get("data", {})
            item_do = data.get("itemDO") or data.get("detail") or data.get("item")
            
            if item_do and "title" in str(item_do):
                st.success(f"✅ 探测成功！有效接口: `{api_name}`")
                return item_do
            else:
                st.warning(f"⚠️ 接口 `{api_name}` 返回异常: {res_json.get('ret',[''])[0]}")
        except Exception as e:
            st.warning(f"❌ 接口 `{api_name}` 连接失败")
            continue
    return None

def run_smart_sync(item_id, file_bytes, cookie_input):
    session = requests.Session()
    # 注入 Cookie
    for k, v in re.findall(r'([^=\s;]+)=([^;]*)', cookie_input):
        session.cookies.set(k.strip(), v.strip(), domain=".goofish.com")
    
    tk = get_cookie(session, "_m_h5_tk")
    if not tk: return False, "❌ 缺少 _m_h5_tk，请重新复制 Cookie。"

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.50",
        "x-tap": "wx", "xweb_xhr": "1"
    }

    try:
        # --- 阶段 0: 探测并获取详情 ---
        full_info = try_get_detail(session, item_id, tk, headers)
        if not full_info:
            return False, "😭 所有详情接口均失效，请检查商品 ID 是否正确或 Cookie 是否过期。"

        # --- 阶段 1: 上传图片 ---
        st.info("📤 正在上传新主图...")
        t1 = str(int(time.time() * 1000))
        biz_str = json.dumps({"bizCode":"idleItemEdit","clientType":"pc","utdid":FIXED_UTDID}, separators=(',', ':'))
        sign1 = get_sign(tk, t1, biz_str)
        files = [('data',(None,biz_str)), ('file',('img.png',file_bytes,'image/png'))]
        res_up = session.post(UPLOAD_URL, params={"appKey":APP_KEY,"t":t1,"sign":sign1,"api":"mtop.taobao.util.uploadImage","v":"1.0","type":"originaljson"}, files=files)
        img_url = res_up.json().get('url') or res_up.json().get('object', {}).get('url')
        if not img_url: return False, "图片上传失败"

        # --- 阶段 2: 覆盖提交 ---
        st.info("🚀 正在提交全量覆盖请求...")
        # 组装数据（根据详情返回的数据结构进行智能适配）
        submit_data = {
            "itemId": str(item_id),
            "title": full_info.get("title"),
            "desc": full_info.get("desc") or full_info.get("description"),
            "price": full_info.get("price"),
            "imageInfoDOList": [{"major": True, "url": img_url, "type": 0, "widthSize": 1024, "heightSize": 1024}],
            "utdid": FIXED_UTDID,
            "platform": "wx_mini"
        }
        
        # 刷新令牌
        new_tk = get_cookie(session, "_m_h5_tk") or tk
        t2 = str(int(time.time() * 1000))
        final_json = json.dumps(submit_data, ensure_ascii=False, separators=(',', ':'))
        sign2 = get_sign(new_tk, t2, final_json)

        res_edit = session.post(
            f"https://acs.m.goofish.com/h5/{EDIT_API}/1.0/",
            params={"jsv":"2.4.12","appKey":APP_KEY,"t":t2,"sign":sign2,"v":"1.0","api":EDIT_API,"type":"originaljson"},
            data={"data": final_json},
            headers={**headers, "Content-Type": "application/x-www-form-urlencoded"}
        )

        if "SUCCESS" in res_edit.text:
            return True, "🎊 全量同步覆盖成功！主图已替换。"
        else:
            return False, f"修改失败: {res_edit.text}"

    except Exception as e:
        return False, f"运行故障: {str(e)}"

# ==================== UI ====================
st.title("🐠 闲鱼宝贝主图替换 (自动探测版)")
st.caption("会自动寻找可用接口获取商品信息，解决 API 不存在的问题。")

c_input = st.text_area("粘贴抓包 Cookie", height=130)
i_id = st.text_input("商品 itemId", value="1033424722209")
i_file = st.file_uploader("选择新主图")

if st.button("🚀 执行同步", use_container_width=True):
    if c_input and i_file:
        ok, msg = run_smart_sync(i_id, i_file.read(), c_input)
        st.success(msg) if ok else st.error(msg)
