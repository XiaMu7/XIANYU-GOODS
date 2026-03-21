# XIANYUGOODS.py - 完全按照头像脚本逻辑
import streamlit as st
import hashlib
import json
import time
from urllib.parse import urlencode, parse_qs, unquote
import os
import random
import string
import io
import requests
import urllib3
from PIL import Image
import re

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 常量定义
APP_KEY = "12574478"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"

# 全局session
session = requests.Session()
session.verify = False

# ===== 初始的 _m_h5_tk（第一次运行后会自动更新）=====
CURRENT_M_H5_TK = ""
# ===============================================

# 页面配置
st.set_page_config(
    page_title="闲鱼商品图片修改工具",
    page_icon="📷",
    layout="wide"
)

# 初始化session状态
if 'auth_info' not in st.session_state:
    st.session_state.auth_info = {
        "cookies": {},
        "headers": {},
        "params": {},
        "data": {},
        "utdid": None,
        "token": "",
        "m_h5_tk": "",
        "c_param": "",
    }

if 'auth_parsed' not in st.session_state:
    st.session_state.auth_parsed = False

if 'current_item_image' not in st.session_state:
    st.session_state.current_item_image = None

# ==================== 从请求中提取信息 ====================

def extract_from_request(request_text: str) -> dict:
    """从HTTP请求文本中提取所有必要信息"""
    global CURRENT_M_H5_TK
    
    info = {
        "cookies": {},
        "headers": {},
        "params": {},
        "data": {},
        "utdid": None,
        "token": CURRENT_M_H5_TK.split('_')[0] if '_' in CURRENT_M_H5_TK else CURRENT_M_H5_TK,
        "m_h5_tk": CURRENT_M_H5_TK,
        "c_param": "",
    }
    
    lines = request_text.strip().split('\n')
    
    # 解析第一行获取URL参数
    first_line = lines[0]
    url_match = re.search(r'\?(.*?)(?:\s|$)', first_line)
    if url_match:
        params_str = url_match.group(1)
        try:
            params = parse_qs(params_str)
            for k, v in params.items():
                info["params"][k] = v[0] if v else ""
        except:
            pass
        
        # 提取c参数
        if 'c' in info["params"]:
            info["c_param"] = info["params"]["c"]
    
    # 解析headers
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith('{') or line.startswith('h2') or line.startswith('POST') or line.startswith('GET'):
            continue
            
        if ': ' in line:
            key, value = line.split(': ', 1)
            key_lower = key.lower()
            
            info["headers"][key] = value
            
            # 特殊header处理 - 从x-smallstc提取cookie信息
            if key_lower == 'x-smallstc':
                try:
                    smallstc = json.loads(value)
                    
                    if 'cookie2' in smallstc:
                        info["cookies"]['cookie2'] = str(smallstc['cookie2'])
                    if 'sgcookie' in smallstc:
                        info["cookies"]['sgcookie'] = str(smallstc['sgcookie'])
                        info["headers"]['sgcookie'] = str(smallstc['sgcookie'])
                    if 'csg' in smallstc:
                        info["cookies"]['csg'] = str(smallstc['csg'])
                    if 'unb' in smallstc:
                        info["cookies"]['unb'] = str(smallstc['unb'])
                    if 'munb' in smallstc:
                        info["cookies"]['munb'] = str(smallstc['munb'])
                    if 'sid' in smallstc:
                        info["cookies"]['sid'] = str(smallstc['sid'])
                        
                except json.JSONDecodeError:
                    pass
            
            # 提取sgcookie
            elif key_lower == 'sgcookie':
                info["cookies"]['sgcookie'] = value
                info["headers"]['sgcookie'] = value
            
            # 提取_m_h5_tk（可能在bx-ua中）
            elif key_lower == 'bx-ua':
                match = re.search(r'_m_h5_tk=([^;]+)', value)
                if match and not info["m_h5_tk"]:
                    info["m_h5_tk"] = match.group(1)
                    info["token"] = info["m_h5_tk"].split('_')[0] if '_' in info["m_h5_tk"] else info["m_h5_tk"]
    
    # 解析data部分
    data_line = None
    for line in reversed(lines):
        line = line.strip()
        if line.startswith('data='):
            data_line = line
            break
    
    if data_line:
        try:
            data_str = data_line[5:]
            data_str = unquote(data_str)
            try:
                info["data"] = json.loads(data_str)
                info["utdid"] = info["data"].get("utdid")
            except json.JSONDecodeError:
                utdid_match = re.search(r'utdid[":]+([^"]+)', data_str)
                if utdid_match:
                    info["utdid"] = utdid_match.group(1)
        except Exception:
            pass
    
    print(f"\n=== 提取结果 ===")
    print(f"c_param: {info['c_param'][:50] if info['c_param'] else 'None'}")
    print(f"utdid: {info['utdid']}")
    print(f"token: {info['token'][:20] if info['token'] else 'None'}...")
    
    return info

def update_auth_info(request_text: str) -> bool:
    """从请求文本更新认证信息"""
    global CURRENT_M_H5_TK
    
    info = extract_from_request(request_text)
    
    if not info["c_param"]:
        st.error("未能提取到c参数")
        return False
    
    st.session_state.auth_info = info
    
    # 从c参数中提取token
    if info["c_param"] and '_' in info["c_param"]:
        token_part = info["c_param"].split('_')[0]
        if token_part:
            st.session_state.auth_info["token"] = token_part
            # 如果没有_m_h5_tk，用token构造一个
            if not info["m_h5_tk"]:
                CURRENT_M_H5_TK = f"{token_part}_{int(time.time() * 1000)}"
                st.session_state.auth_info["m_h5_tk"] = CURRENT_M_H5_TK
            else:
                CURRENT_M_H5_TK = info["m_h5_tk"]
    
    st.session_state.auth_parsed = True
    
    return True

def calc_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算签名"""
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

# ==================== 图片上传（完全按照头像脚本）====================

def upload_bytes(file_name: str, file_bytes: bytes, mime: str) -> str:
    """上传图片到闲鱼服务器"""
    global CURRENT_M_H5_TK
    
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    
    # 使用最新的 _m_h5_tk
    cookies["_m_h5_tk"] = CURRENT_M_H5_TK
    
    files = {
        "file": (file_name, file_bytes, mime),
    }
    data = {
        "content-type": "multipart/form-data",
        "appkey": "fleamarket",
        "bizCode": "fleamarket",
        "floderId": "0",
        "name": "fileFromAlbum",
    }
    params = {
        "floderId": "0",
        "appkey": "fleamarket",
        "_input_charset": "utf-8",
    }
    
    headers = {
        "User-Agent": st.session_state.auth_info.get("headers", {}).get("user-agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/126.0.0.0"
        ),
        "Accept": "*/*",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html",
    }
    
    # 添加必要的headers
    for h in ["bx-umidtoken", "x-ticid", "mini-janus", "sgcookie", "bx-ua"]:
        if h in st.session_state.auth_info.get("headers", {}):
            headers[h] = st.session_state.auth_info["headers"][h]

    print(f"上传文件到: {UPLOAD_URL}")
    print(f"使用的_m_h5_tk: {CURRENT_M_H5_TK}")
    
    response = session.post(
        UPLOAD_URL,
        params=params,
        headers=headers,
        cookies=cookies,
        data=data,
        files=files,
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("success"):
        raise RuntimeError(f"Upload failed: {body}")
    image_url = body.get("object", {}).get("url")
    if not image_url:
        raise RuntimeError(f"Upload response missing object.url: {body}")
    return image_url

def upload_from_url(file_url: str) -> str:
    """从URL下载图片并上传"""
    print(f"下载图片: {file_url}")
    response = requests.get(file_url, timeout=30)
    response.raise_for_status()
    content = response.content
    if not content:
        raise RuntimeError("Downloaded file is empty.")

    parsed = urllib3.util.parse_url(file_url)
    raw_name = os.path.basename(parsed.path or "") or "remote.gif"
    if "." not in raw_name:
        raw_name = f"{raw_name}.gif"
    mime = response.headers.get("Content-Type", "").split(";")[0].strip() or (
        mimetypes.guess_type(raw_name)[0] or "application/octet-stream"
    )
    print(f"下载完成: {len(content)} bytes, MIME: {mime}")
    return upload_bytes(raw_name, content, mime)

def upload_from_local(uploaded_file) -> str:
    """从本地上传图片"""
    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name
    mime = uploaded_file.type or 'image/jpeg'
    return upload_bytes(file_name, file_bytes, mime)

# ==================== 商品操作（完全按照头像脚本逻辑）====================

def update_item_image(item_id: str, image_url: str, retry_count: int = 0) -> dict:
    """更新商品图片"""
    global CURRENT_M_H5_TK
    
    # 构建cookies
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    
    # 使用当前的 _m_h5_tk
    m_h5_tk = CURRENT_M_H5_TK
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    # 添加到cookies
    cookies["_m_h5_tk"] = m_h5_tk
    
    # 获取utdid
    utdid = st.session_state.auth_info.get("utdid")
    if not utdid:
        raise ValueError("Missing utdid")

    # 构建请求数据
    data_obj = {
        "utdid": utdid,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "imageUrl": image_url,
    }
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)

    t = str(int(time.time() * 1000))
    sign = calc_sign(token, t, APP_KEY, data_str)

    # 使用正确的编辑API
    API_EDIT = "mtop.idle.wx.idleitem.edit"
    BASE_URL_EDIT = f"https://acs.m.goofish.com/h5/{API_EDIT}/1.0/2.0/"
    
    params = {
        "jsv": "2.4.12",
        "appKey": APP_KEY,
        "t": t,
        "sign": sign,
        "c": st.session_state.auth_info.get("c_param", ""),
        "v": "1.0",
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "api": API_EDIT,
        "_bx-m": "1",
    }

    # 合并headers
    headers = {
        "User-Agent": st.session_state.auth_info.get("headers", {}).get("user-agent", 
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/126.0.0.0"
        ),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html",
    }
    
    # 添加原始请求中的特殊headers
    special_headers = ["bx-umidtoken", "x-ticid", "x-tap", "mini-janus", "sgcookie", "bx-ua"]
    for h in special_headers:
        if h in st.session_state.auth_info.get("headers", {}):
            headers[h] = st.session_state.auth_info["headers"][h]

    print(f"\n发送请求到: {BASE_URL_EDIT}")
    print(f"使用的token: {token}")
    print(f"使用的_m_h5_tk: {m_h5_tk}")

    # 使用session发送请求
    response = session.post(
        f"{BASE_URL_EDIT}?{urlencode(params)}",
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20,
    )
    
    print(f"响应状态码: {response.status_code}")
    
    # 自动提取新的 _m_h5_tk 并更新
    token_updated = False
    if '_m_h5_tk' in response.cookies:
        new_m_h5_tk = response.cookies['_m_h5_tk']
        if new_m_h5_tk != CURRENT_M_H5_TK:
            print(f"发现新的 _m_h5_tk: {new_m_h5_tk}")
            print(f"自动更新当前token")
            CURRENT_M_H5_TK = new_m_h5_tk
            # 更新到auth_info
            st.session_state.auth_info['m_h5_tk'] = new_m_h5_tk
            st.session_state.auth_info['token'] = new_m_h5_tk.split('_')[0] if '_' in new_m_h5_tk else new_m_h5_tk
            token_updated = True
    
    result = response.json()
    
    # 如果返回非法令牌且没有重试过，并且token被更新了，则自动重试一次
    if result.get("ret") and "FAIL_SYS_TOKEN" in str(result["ret"]) and retry_count == 0 and token_updated:
        print("\n检测到新token，自动重试一次...")
        time.sleep(1)
        return update_item_image(item_id, image_url, retry_count=1)
    
    return result

def get_item_detail(item_id: str, retry_count: int = 0) -> dict:
    """获取商品详情"""
    global CURRENT_M_H5_TK
    
    # 构建cookies
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    
    # 使用当前的 _m_h5_tk
    m_h5_tk = CURRENT_M_H5_TK
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    # 添加到cookies
    cookies["_m_h5_tk"] = m_h5_tk
    
    # 获取utdid
    utdid = st.session_state.auth_info.get("utdid")
    if not utdid:
        raise ValueError("Missing utdid")

    # 构建请求数据
    data_obj = {
        "utdid": utdid,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "formScene": "",
        "extra": json.dumps({"isShare": False})
    }
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)

    t = str(int(time.time() * 1000))
    sign = calc_sign(token, t, APP_KEY, data_str)

    API_DETAIL = "mtop.taobao.idle.weixin.detail"
    BASE_URL_DETAIL = f"https://acs.m.goofish.com/h5/{API_DETAIL}/1.0/2.0/"
    
    params = {
        "jsv": "2.4.12",
        "appKey": APP_KEY,
        "t": t,
        "sign": sign,
        "c": st.session_state.auth_info.get("c_param", ""),
        "v": "1.0",
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "api": API_DETAIL,
        "_bx-m": "1",
    }

    headers = {
        "User-Agent": st.session_state.auth_info.get("headers", {}).get("user-agent", 
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/126.0.0.0"
        ),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/74/page-frame.html",
    }
    
    special_headers = ["bx-umidtoken", "x-ticid", "x-tap", "mini-janus", "sgcookie", "bx-ua"]
    for h in special_headers:
        if h in st.session_state.auth_info.get("headers", {}):
            headers[h] = st.session_state.auth_info["headers"][h]

    response = session.post(
        f"{BASE_URL_DETAIL}?{urlencode(params)}",
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20,
    )
    
    # 自动提取新的 _m_h5_tk 并更新
    token_updated = False
    if '_m_h5_tk' in response.cookies:
        new_m_h5_tk = response.cookies['_m_h5_tk']
        if new_m_h5_tk != CURRENT_M_H5_TK:
            print(f"发现新的 _m_h5_tk: {new_m_h5_tk}")
            CURRENT_M_H5_TK = new_m_h5_tk
            st.session_state.auth_info['m_h5_tk'] = new_m_h5_tk
            st.session_state.auth_info['token'] = new_m_h5_tk.split('_')[0] if '_' in new_m_h5_tk else new_m_h5_tk
            token_updated = True
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    result = response.json()
    
    if result.get("ret") and "FAIL_SYS_TOKEN" in str(result["ret"]) and retry_count == 0 and token_updated:
        print("\n检测到新token，自动重试一次...")
        time.sleep(1)
        return get_item_detail(item_id, retry_count=1)
    
    return result

# ==================== 主界面 ====================
def main():
    global CURRENT_M_H5_TK
    
    st.title("📷 闲鱼商品图片修改工具")
    
    st.header("🔑 认证信息配置")
    st.info("请粘贴从浏览器复制的完整HTTP请求头（包含data部分）")
    
    request_text = st.text_area(
        "HTTP请求头",
        height=400,
        placeholder="粘贴完整的HTTP请求头..."
    )
    
    if st.button("解析认证信息", use_container_width=True):
        if request_text:
            if update_auth_info(request_text):
                st.session_state.auth_parsed = True
                st.success("✅ 认证信息解析成功")
                st.info(f"c参数: {st.session_state.auth_info['c_param'][:50]}...")
                st.info(f"utdid: {st.session_state.auth_info['utdid']}")
                st.info(f"token: {st.session_state.auth_info['token'][:30]}...")
                st.info(f"_m_h5_tk: {CURRENT_M_H5_TK[:50] if CURRENT_M_H5_TK else 'None'}...")
            else:
                st.error("❌ 解析失败")
    
    if not st.session_state.auth_parsed:
        st.warning("⚠️ 请先配置并解析认证信息")
        return
    
    st.divider()
    
    st.header("📦 商品信息")
    
    item_id = st.text_input(
        "商品ID",
        placeholder="请输入要修改图片的商品ID",
        help="例如：1033424722209"
    )
    
    if item_id:
        if st.button("获取商品当前图片", use_container_width=True):
            try:
                with st.spinner("获取商品信息中..."):
                    result = get_item_detail(item_id)
                    
                    if result.get("ret") and "SUCCESS" in str(result["ret"]):
                        item_data = result.get("data", {}).get("itemDO", {})
                        image_infos = item_data.get("imageInfos", [])
                        
                        if image_infos:
                            current_image_url = image_infos[0].get("url", "")
                            st.session_state.current_item_image = current_image_url
                            st.success("✅ 获取商品信息成功")
                            
                            st.subheader("当前商品信息")
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.image(current_image_url, width=200)
                            with col2:
                                st.write(f"**标题:** {item_data.get('title', '')}")
                                st.write(f"**描述:** {item_data.get('desc', '')[:100]}...")
                                st.write(f"**价格:** {item_data.get('soldPrice', '')}元")
                        else:
                            st.warning("未找到商品图片")
                    else:
                        error_msg = result.get("ret", ["未知错误"])[0]
                        st.error(f"获取商品信息失败: {error_msg}")
            except Exception as e:
                st.error(f"获取商品信息失败: {str(e)}")
    
    st.divider()
    
    st.header("📤 新图片上传")
    
    image_source = st.radio(
        "选择图片来源",
        ["网络图片URL", "本地上传"],
        horizontal=True
    )
    
    new_image_data = None
    
    if image_source == "网络图片URL":
        new_image_url = st.text_input("图片URL", placeholder="https://example.com/new_image.jpg")
        
        if new_image_url and st.button("预览新图片"):
            try:
                st.image(new_image_url, width=200)
            except:
                st.error("无法预览图片")
        
        if new_image_url:
            new_image_data = {"type": "url", "value": new_image_url}
        
    else:
        uploaded_file = st.file_uploader(
            "选择图片文件",
            type=['png', 'jpg', 'jpeg', 'gif', 'webp']
        )
        
        if uploaded_file:
            try:
                image = Image.open(io.BytesIO(uploaded_file.getvalue()))
                st.image(uploaded_file, width=200)
                st.caption(f"{image.width}x{image.height}")
                new_image_data = {"type": "file", "value": uploaded_file}
            except Exception as e:
                st.error(f"无法解析图片: {str(e)}")
    
    st.divider()
    
    st.header("🚀 执行更新")
    
    if st.button("开始修改商品图片", type="primary", use_container_width=True):
        if not item_id:
            st.error("❌ 请输入商品ID")
        elif not new_image_data:
            st.error("❌ 请先选择图片")
        else:
            try:
                with st.spinner("处理中..."):
                    # 上传图片
                    if new_image_data["type"] == "url":
                        final_url = upload_from_url(new_image_data["value"])
                    else:
                        final_url = upload_from_local(new_image_data["value"])
                    
                    st.info(f"图片上传成功，正在修改商品...")
                    
                    # 修改商品图片
                    result = update_item_image(item_id, final_url)
                    
                    if result.get("ret") and "SUCCESS" in str(result["ret"]):
                        st.success("✅ 商品图片修改成功！")
                        st.balloons()
                    else:
                        error_msg = result.get("ret", ["未知错误"])[0]
                        st.error(f"❌ 修改失败: {error_msg}")
                        
            except Exception as e:
                st.error(f"❌ 修改失败: {str(e)}")

if __name__ == "__main__":
    main()
