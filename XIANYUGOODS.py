# XIANYUGOODS.py - 完整自动版（先获取c参数，再修改图片）
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
import mimetypes

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 常量定义
APP_KEY = "12574478"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
BASE_URL_EDIT_DETAIL = "https://acs.m.goofish.com/h5/mtop.idle.wx.idleitem.editdetail/1.0/2.0/"
BASE_URL_EDIT = "https://acs.m.goofish.com/h5/mtop.idle.wx.idleitem.edit/1.0/2.0/"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# 全局session
session = requests.Session()
session.verify = False

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
        "utdid": FIXED_UTDID,
        "token": "",
        "m_h5_tk": "",
    }

if 'auth_parsed' not in st.session_state:
    st.session_state.auth_parsed = False

if 'current_item_image' not in st.session_state:
    st.session_state.current_item_image = None

if 'current_m_h5_tk' not in st.session_state:
    st.session_state.current_m_h5_tk = ""

# ==================== 从Cookie中提取信息 ====================

def parse_cookie_string(cookie_str: str) -> dict:
    """解析cookie字符串为字典"""
    cookies = {}
    try:
        items = cookie_str.split(';')
        for item in items:
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                cookies[key.strip()] = value.strip()
    except Exception as e:
        st.error(f"Cookie解析失败: {str(e)}")
    return cookies

def update_auth_from_cookie(cookie_str: str) -> bool:
    """从Cookie更新认证信息"""
    cookies = parse_cookie_string(cookie_str)
    
    if not cookies:
        return False
    
    st.session_state.auth_info["cookies"] = cookies
    
    # 提取sgcookie
    if 'sgcookie' in cookies:
        st.session_state.auth_info["headers"]["sgcookie"] = cookies['sgcookie']
    
    # 提取_m_h5_tk
    if '_m_h5_tk' in cookies:
        m_h5_tk = cookies['_m_h5_tk']
        st.session_state.auth_info["m_h5_tk"] = m_h5_tk
        st.session_state.auth_info["token"] = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
        st.session_state.current_m_h5_tk = m_h5_tk
    
    # 提取bx-umidtoken（可能在headers中，这里需要用户提供）
    # 如果Cookie中有，就提取
    if 'bx-umidtoken' in cookies:
        st.session_state.auth_info["headers"]["bx-umidtoken"] = cookies['bx-umidtoken']
    
    return True

def add_headers_from_input(headers_str: str) -> bool:
    """从用户输入的headers字符串添加额外headers"""
    try:
        lines = headers_str.strip().split('\n')
        for line in lines:
            if ': ' in line:
                key, value = line.split(': ', 1)
                key_lower = key.lower()
                if key_lower in ['bx-umidtoken', 'x-ticid', 'x-tap', 'sgcookie']:
                    st.session_state.auth_info["headers"][key] = value
        return True
    except:
        return False

def calc_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算签名"""
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

# ==================== 获取c参数 ====================

def get_edit_c_param(item_id: str) -> str:
    """进入编辑页面获取c参数"""
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    headers = st.session_state.auth_info.get("headers", {}).copy()
    
    m_h5_tk = st.session_state.current_m_h5_tk
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    utdid = st.session_state.auth_info.get("utdid", FIXED_UTDID)
    
    # 构建请求数据 - 获取编辑页面信息
    data_obj = {
        "utdid": utdid,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
    }
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)
    
    t = str(int(time.time() * 1000))
    sign = calc_sign(token, t, APP_KEY, data_str)
    
    # 构建URL和参数
    params = {
        "jsv": "2.4.12",
        "appKey": APP_KEY,
        "t": t,
        "sign": sign,
        "v": "1.0",
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "api": "mtop.idle.wx.idleitem.editdetail",
        "_bx-m": "1",
    }
    
    url = f"{BASE_URL_EDIT_DETAIL}?{urlencode(params)}"
    
    request_headers = {
        "User-Agent": headers.get('user-agent', 
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    # 添加特殊headers
    for h in ['sgcookie', 'bx-umidtoken', 'x-ticid', 'x-tap']:
        if h in headers:
            request_headers[h] = headers[h]
    
    st.info(f"正在获取编辑页面c参数...")
    
    response = session.post(
        url,
        headers=request_headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20
    )
    
    if response.status_code != 200:
        raise Exception(f"获取c参数失败: HTTP {response.status_code}")
    
    result = response.json()
    
    # 从响应中提取c参数（通常在返回的URL中）
    # 或者从响应的headers中
    c_param = None
    
    # 尝试从响应内容中提取
    if result.get("data") and result["data"].get("redirectUrl"):
        redirect_url = result["data"]["redirectUrl"]
        # 解析URL中的c参数
        match = re.search(r'c=([^&]+)', redirect_url)
        if match:
            c_param = unquote(match.group(1))
            print(f"从redirectUrl提取c参数: {c_param[:80]}...")
    
    # 如果上面没找到，尝试从响应headers中
    if not c_param and 'location' in response.headers:
        match = re.search(r'c=([^&]+)', response.headers['location'])
        if match:
            c_param = unquote(match.group(1))
    
    if not c_param:
        # 如果还是没有，尝试构造一个（从token）
        c_param = f"{token}_{int(time.time() * 1000)};{hashlib.md5(f'{token}_{int(time.time() * 1000)}'.encode()).hexdigest()}"
        st.warning(f"未能从响应中提取c参数，使用临时构造的c参数")
    
    return c_param

# ==================== 图片上传 ====================

def upload_image(file_bytes: bytes, file_name: str, mime: str) -> str:
    """上传图片到闲鱼服务器"""
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    headers = st.session_state.auth_info.get("headers", {}).copy()
    
    if st.session_state.current_m_h5_tk:
        cookies["_m_h5_tk"] = st.session_state.current_m_h5_tk
    
    # 构建multipart数据
    boundary = '----WebKitFormBoundary' + ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=16))
    
    body_parts = []
    
    fields = {
        'name': 'fileFromAlbum',
        'appkey': 'fleamarket',
        'bizCode': 'fleamarket',
        'folderId': '0',
    }
    
    for key, value in fields.items():
        body_parts.append(f'--{boundary}')
        body_parts.append(f'Content-Disposition: form-data; name="{key}"')
        body_parts.append('')
        body_parts.append(str(value))
    
    body_parts.append(f'--{boundary}')
    body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"')
    body_parts.append(f'Content-Type: {mime}')
    body_parts.append('')
    
    body = '\r\n'.join(body_parts).encode() + b'\r\n' + file_bytes + f'\r\n--{boundary}--\r\n'.encode()
    
    upload_headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Accept': '*/*',
        'Origin': 'https://servicewechat.com',
        'Referer': 'https://servicewechat.com/wx9882f2a891880616/75/page-frame.html',
        'User-Agent': headers.get('user-agent', 'Mozilla/5.0'),
    }
    
    if 'sgcookie' in headers:
        upload_headers['sgcookie'] = headers['sgcookie']
    if 'bx-umidtoken' in headers:
        upload_headers['bx-umidtoken'] = headers['bx-umidtoken']
    if 'x-ticid' in headers:
        upload_headers['x-ticid'] = headers['x-ticid']
    
    params = {
        'folderId': '0',
        'appkey': 'fleamarket',
        '_input_charset': 'utf-8',
    }
    
    response = session.post(
        UPLOAD_URL,
        params=params,
        headers=upload_headers,
        cookies=cookies,
        data=body,
        timeout=60
    )
    
    if response.status_code != 200:
        raise Exception(f"上传失败: HTTP {response.status_code}")
    
    result = response.json()
    
    if not result.get('success'):
        raise Exception(f"上传失败: {result.get('message', '未知错误')}")
    
    image_url = result.get('object', {}).get('url') or result.get('url')
    if not image_url:
        raise Exception("响应中没有图片URL")
    
    return image_url

# ==================== 修改商品图片 ====================

def edit_item_image(item_id: str, image_url: str, c_param: str) -> dict:
    """编辑商品图片"""
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    headers = st.session_state.auth_info.get("headers", {}).copy()
    
    m_h5_tk = st.session_state.current_m_h5_tk
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    utdid = st.session_state.auth_info.get("utdid", FIXED_UTDID)
    
    # 构建请求数据 - 只修改图片
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
    
    params = {
        "jsv": "2.4.12",
        "appKey": APP_KEY,
        "t": t,
        "sign": sign,
        "c": c_param,
        "v": "1.0",
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "api": "mtop.idle.wx.idleitem.edit",
        "_bx-m": "1",
    }
    
    url = f"{BASE_URL_EDIT}?{urlencode(params)}"
    
    request_headers = {
        "User-Agent": headers.get('user-agent', 'Mozilla/5.0'),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    for h in ['sgcookie', 'bx-umidtoken', 'x-ticid', 'x-tap']:
        if h in headers:
            request_headers[h] = headers[h]
    
    response = session.post(
        url,
        headers=request_headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=30
    )
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    return response.json()

# ==================== 图片下载 ====================

def download_image_from_url(url: str):
    """从URL下载图片"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    response = requests.get(url, headers=headers, timeout=30, verify=False)
    response.raise_for_status()
    
    content = response.content
    if len(content) == 0:
        raise Exception("文件为空")
    
    parsed = urllib3.util.parse_url(url)
    file_name = os.path.basename(parsed.path or "")
    if not file_name or '.' not in file_name:
        file_name = f"image_{int(time.time())}.jpg"
    
    content_type = response.headers.get('Content-Type', '')
    mime = content_type.split(';')[0].strip() or 'image/jpeg'
    
    return content, file_name, mime

def process_uploaded_file(uploaded_file):
    """处理上传的文件"""
    try:
        image = Image.open(io.BytesIO(uploaded_file.getvalue()))
        return {
            "bytes": uploaded_file.getvalue(),
            "name": uploaded_file.name,
            "mime": uploaded_file.type or 'image/jpeg',
            "width": image.width,
            "height": image.height,
            "size": len(uploaded_file.getvalue()) / 1024
        }
    except Exception as e:
        st.error(f"无法解析图片: {str(e)}")
        return None

# ==================== 主界面 ====================
def main():
    st.title("📷 闲鱼商品图片修改工具")
    
    # 认证信息配置
    st.header("🔑 认证信息配置")
    
    st.info("请粘贴完整的Cookie字符串")
    
    cookie_input = st.text_area(
        "Cookie",
        height=150,
        placeholder="粘贴Cookie字符串..."
    )
    
    st.info("请粘贴额外的Headers（bx-umidtoken, x-ticid等，可选）")
    
    headers_input = st.text_area(
        "Headers",
        height=100,
        placeholder="bx-umidtoken: xxx\nx-ticid: xxx\nx-tap: wx\nsgcookie: xxx"
    )
    
    if st.button("解析认证信息", use_container_width=True):
        if cookie_input:
            if update_auth_from_cookie(cookie_input):
                if headers_input:
                    add_headers_from_input(headers_input)
                st.session_state.auth_parsed = True
                st.success("✅ 认证信息解析成功")
                st.info(f"_m_h5_tk: {st.session_state.current_m_h5_tk[:50]}...")
            else:
                st.error("❌ Cookie解析失败")
    
    if not st.session_state.auth_parsed:
        st.warning("⚠️ 请先配置并解析认证信息")
        return
    
    st.divider()
    
    # 商品信息
    st.header("📦 商品信息")
    
    item_id = st.text_input(
        "商品ID",
        placeholder="请输入要修改图片的商品ID",
        help="例如：1033424722209"
    )
    
    # 获取当前图片
    if item_id:
        if st.button("获取商品当前图片", use_container_width=True):
            try:
                with st.spinner("获取c参数中..."):
                    c_param = get_edit_c_param(item_id)
                    st.info(f"获取到c参数: {c_param[:80]}...")
                    st.session_state.current_c_param = c_param
                    st.success("✅ c参数获取成功")
            except Exception as e:
                st.error(f"获取c参数失败: {str(e)}")
    
    st.divider()
    
    # 图片上传
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
            img_info = process_uploaded_file(uploaded_file)
            if img_info:
                st.image(uploaded_file, width=200)
                st.caption(f"{img_info['width']}x{img_info['height']} | {img_info['size']:.1f}KB")
                new_image_data = {"type": "file", "value": img_info}
    
    st.divider()
    
    # 执行更新
    st.header("🚀 执行更新")
    
    if st.button("开始修改商品图片", type="primary", use_container_width=True):
        if not item_id:
            st.error("❌ 请输入商品ID")
        elif not new_image_data:
            st.error("❌ 请先选择图片")
        elif not hasattr(st.session_state, 'current_c_param'):
            st.error("❌ 请先点击'获取商品当前图片'获取c参数")
        else:
            try:
                with st.spinner("处理中..."):
                    # 上传图片
                    if new_image_data["type"] == "url":
                        st.info("下载图片中...")
                        img_bytes, img_name, img_mime = download_image_from_url(new_image_data["value"])
                        st.info("上传图片中...")
                        final_url = upload_image(img_bytes, img_name, img_mime)
                    else:
                        img_info = new_image_data["value"]
                        st.info("上传图片中...")
                        final_url = upload_image(img_info["bytes"], img_info["name"], img_info["mime"])
                    
                    st.success(f"✅ 图片上传成功")
                    
                    # 修改商品图片
                    st.info("正在修改商品图片...")
                    result = edit_item_image(item_id, final_url, st.session_state.current_c_param)
                    
                    if result.get("ret") and "SUCCESS" in str(result["ret"]):
                        st.success("✅ 商品图片修改成功！")
                        st.balloons()
                    else:
                        error_msg = result.get("ret", ["未知错误"])[0]
                        st.error(f"❌ 修改失败: {error_msg}")
                        
            except Exception as e:
                st.error(f"❌ 修改失败: {str(e)}")
    
    # 底部说明
    st.divider()
    st.caption("💡 使用说明：\n"
               "1. 粘贴Cookie和Headers\n"
               "2. 输入商品ID，点击'获取商品当前图片'获取c参数\n"
               "3. 选择新图片（支持URL或本地上传）\n"
               "4. 点击开始修改商品图片")

if __name__ == "__main__":
    main()
