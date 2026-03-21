# app_item_image.py - 闲鱼商品图片修改工具
import streamlit as st
import hashlib
import json
import time
import urllib.parse
from urllib.parse import urlencode
import os
import random
import string
import io
from typing import Optional, Tuple
import requests
import urllib3
from PIL import Image
import re

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 常量定义
APP_KEY = "12574478"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"

# 固定的utdid
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# 页面配置
st.set_page_config(
    page_title="闲鱼商品图片修改工具",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 初始化session状态
if 'session' not in st.session_state:
    st.session_state.session = requests.Session()
    st.session_state.session.verify = False

if 'current_m_h5_tk' not in st.session_state:
    st.session_state.current_m_h5_tk = ""

if 'auth_info' not in st.session_state:
    st.session_state.auth_info = {
        "cookies": {},
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541022) XWEB/16467",
            "Accept": "application/json",
            "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
        },
        "utdid": FIXED_UTDID,
        "token": None,
        "m_h5_tk": None,
    }

if 'preview_url' not in st.session_state:
    st.session_state.preview_url = None

if 'uploaded_file' not in st.session_state:
    st.session_state.uploaded_file = None

if 'uploaded_file_preview' not in st.session_state:
    st.session_state.uploaded_file_preview = None

if 'cookie_parsed' not in st.session_state:
    st.session_state.cookie_parsed = False

if 'login_success' not in st.session_state:
    st.session_state.login_success = False

if 'update_status' not in st.session_state:
    st.session_state.update_status = None

# ==================== 工具函数 ====================

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

def update_auth_info_from_cookie(cookie_str: str):
    """从cookie字符串更新认证信息"""
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
    
    return True

def download_image_with_fallback(url: str) -> Tuple[bytes, str, str]:
    """下载图片"""
    with st.spinner("🔄 下载图片中..."):
        session = requests.Session()
        session.verify = False
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            response = session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            content = response.content
            if len(content) == 0:
                raise Exception("文件为空")
            
            parsed = urllib.parse.urlparse(url)
            file_name = os.path.basename(parsed.path)
            if not file_name or '.' not in file_name:
                file_name = f"image_{int(time.time())}.jpg"
            
            content_type = response.headers.get('Content-Type', '')
            mime = content_type.split(';')[0].strip() or 'image/jpeg'
            
            return content, file_name, mime
            
        except Exception as e:
            raise e

def calc_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算签名"""
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

def upload_bytes(file_name: str, file_bytes: bytes, mime: str, auth_info: dict) -> str:
    """上传文件到闲鱼服务器"""
    cookies = auth_info.get("cookies", {}).copy()
    
    if st.session_state.current_m_h5_tk:
        cookies["_m_h5_tk"] = st.session_state.current_m_h5_tk
    
    # 构建multipart数据
    boundary = '----WebKitFormBoundary' + ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=16))
    
    body = []
    
    # 表单字段
    fields = {
        'name': 'fileFromAlbum',
        'appkey': 'fleamarket',
        'bizCode': 'fleamarket',
        'folderId': '0',
    }
    
    for key, value in fields.items():
        body.append(f'--{boundary}'.encode())
        body.append(f'Content-Disposition: form-data; name="{key}"'.encode())
        body.append(b'')
        body.append(str(value).encode())
    
    # 文件
    body.append(f'--{boundary}'.encode())
    body.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"'.encode())
    body.append(f'Content-Type: {mime}'.encode())
    body.append(b'')
    body.append(file_bytes)
    
    # 结束
    body.append(f'--{boundary}--'.encode())
    body.append(b'')
    
    request_body = b'\r\n'.join(body)
    
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(request_body)),
        'Accept': '*/*',
        'Origin': 'https://servicewechat.com',
        'Referer': 'https://servicewechat.com/wx9882f2a891880616/75/page-frame.html',
        'User-Agent': auth_info.get('headers', {}).get('User-Agent', 'Mozilla/5.0'),
    }
    
    if 'sgcookie' in cookies:
        headers['sgcookie'] = cookies['sgcookie']
    
    params = {
        'folderId': '0',
        'appkey': 'fleamarket',
        '_input_charset': 'utf-8',
    }

    try:
        response = st.session_state.session.post(
            UPLOAD_URL,
            params=params,
            headers=headers,
            cookies=cookies,
            data=request_body,
            timeout=30,
            verify=False
        )
        
        if response.status_code != 200:
            response.raise_for_status()
        
        body = response.json()
        
        if not body.get('success'):
            error_msg = body.get('message', body.get('errorMsg', '未知错误'))
            raise Exception(f"上传失败: {error_msg}")
        
        image_url = None
        if 'object' in body and 'url' in body['object']:
            image_url = body['object']['url']
        elif 'url' in body:
            image_url = body['url']
        
        if not image_url:
            raise Exception(f"响应中没有图片URL")
        
        return image_url
        
    except Exception as e:
        raise e

def update_item_image(item_id: str, image_url: str, auth_info: dict) -> dict:
    """更新商品图片"""
    cookies = auth_info.get("cookies", {}).copy()
    
    m_h5_tk = st.session_state.current_m_h5_tk
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    utdid = auth_info.get("utdid", FIXED_UTDID)

    # 构建请求数据
    data_obj = {
        "utdid": utdid,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "imageUrl": image_url,  # 修改商品的图片URL
    }
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)

    t = str(int(time.time() * 1000))
    sign = calc_sign(token, t, APP_KEY, data_str)

    # 商品图片更新接口
    API = "mtop.taobao.idle.item.update"
    BASE_URL = f"https://acs.m.goofish.com/h5/{API}/1.0/"
    
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
        "api": API,
        "_bx-m": "1",
    }

    headers = {
        "User-Agent": auth_info.get('headers', {}).get('User-Agent', 'Mozilla/5.0'),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    if 'sgcookie' in cookies:
        headers['sgcookie'] = cookies['sgcookie']

    response = st.session_state.session.post(
        f"{BASE_URL}?{urlencode(params)}",
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20,
        verify=False
    )
    
    return response.json()

def get_item_detail(item_id: str, auth_info: dict) -> dict:
    """获取商品详情"""
    cookies = auth_info.get("cookies", {}).copy()
    
    m_h5_tk = st.session_state.current_m_h5_tk
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    utdid = auth_info.get("utdid", FIXED_UTDID)

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

    # 商品详情接口
    API = "mtop.taobao.idle.weixin.detail"
    BASE_URL = f"https://acs.m.goofish.com/h5/{API}/1.0/2.0/"
    
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
        "api": API,
        "_bx-m": "1",
    }

    headers = {
        "User-Agent": auth_info.get('headers', {}).get('User-Agent', 'Mozilla/5.0'),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    if 'sgcookie' in cookies:
        headers['sgcookie'] = cookies['sgcookie']

    response = st.session_state.session.post(
        f"{BASE_URL}?{urlencode(params)}",
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20,
        verify=False
    )
    
    return response.json()

def process_image_file(uploaded_file):
    """处理上传的图片文件"""
    if uploaded_file is not None:
        try:
            image = Image.open(io.BytesIO(uploaded_file.getvalue()))
            st.session_state.uploaded_file_preview = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "size": len(uploaded_file.getvalue()) / 1024
            }
            return True
        except Exception as e:
            st.error(f"无法解析图片: {str(e)}")
            return False
    return False

def upload_from_url(file_url: str, auth_info: dict) -> str:
    """从URL上传图片"""
    content, file_name, mime = download_image_with_fallback(file_url)
    return upload_bytes(file_name, content, mime, auth_info)

def upload_from_local(uploaded_file, auth_info: dict) -> str:
    """从本地上传图片"""
    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name
    mime = uploaded_file.type or 'image/jpeg'
    return upload_bytes(file_name, file_bytes, mime, auth_info)

# ==================== 登录页面 ====================
def login_page():
    st.title("🔐 登录")
    st.write("请输入管理员密码")
    
    password = st.text_input("密码", type="password")
    
    if st.button("登录"):
        if password == "夏目":
            st.session_state.login_success = True
            st.rerun()
        else:
            st.error("密码错误")

# ==================== 主界面 ====================
def main_app():
    st.title("📷 闲鱼商品图片修改工具")
    
    # 认证信息配置
    st.header("🔑 认证信息配置")
    
    cookie_input = st.text_area(
        "Cookie字符串",
        height=100,
        placeholder="在这里粘贴完整的Cookie字符串...",
        help="从浏览器开发者工具中复制Cookie"
    )
    
    if st.button("解析Cookie"):
        if cookie_input:
            if update_auth_info_from_cookie(cookie_input):
                st.session_state.cookie_parsed = True
                st.success("✅ Cookie解析成功")
            else:
                st.error("❌ Cookie解析失败，请检查格式")
    
    if not st.session_state.cookie_parsed:
        st.warning("⚠️ 请先配置并解析Cookie")
        return
    
    st.divider()
    
    # 商品信息
    st.header("📦 商品信息")
    
    item_id = st.text_input(
        "商品ID",
        placeholder="请输入要修改图片的商品ID",
        help="例如：1033424722209"
    )
    
    if item_id:
        # 获取商品当前图片
        if st.button("获取商品当前图片"):
            try:
                with st.spinner("获取商品信息中..."):
                    result = get_item_detail(item_id, st.session_state.auth_info)
                    
                    if result.get("ret") and "SUCCESS" in str(result["ret"]):
                        item_data = result.get("data", {}).get("itemDO", {})
                        image_infos = item_data.get("imageInfos", [])
                        
                        if image_infos:
                            current_image_url = image_infos[0].get("url", "")
                            st.session_state.current_item_image = current_image_url
                            st.success(f"✅ 获取商品信息成功")
                            
                            # 显示当前图片
                            st.subheader("当前商品图片")
                            st.image(current_image_url, width=200)
                            
                            # 显示商品标题
                            title = item_data.get("title", "")
                            if title:
                                st.info(f"商品标题: {title}")
                        else:
                            st.warning("未找到商品图片")
                    else:
                        st.error("获取商品信息失败")
            except Exception as e:
                st.error(f"获取商品信息失败: {str(e)}")
    
    st.divider()
    
    # 图片上传
    st.header("📤 图片上传")
    
    image_source = st.radio(
        "选择图片来源",
        ["网络图片URL", "本地上传"],
        horizontal=True
    )
    
    if image_source == "网络图片URL":
        image_url = st.text_input(
            "图片URL",
            placeholder="https://example.com/image.jpg"
        )
        
        if st.button("预览图片"):
            if image_url:
                st.session_state.preview_url = image_url
                st.session_state.uploaded_file = None
        
    else:
        uploaded_file = st.file_uploader(
            "选择图片文件",
            type=['png', 'jpg', 'jpeg', 'gif', 'webp']
        )
        
        if uploaded_file:
            if process_image_file(uploaded_file):
                st.session_state.uploaded_file = uploaded_file
                st.session_state.preview_url = None
                st.success(f"✅ 已选择: {uploaded_file.name}")
    
    # 显示预览
    if st.session_state.get('preview_url'):
        st.subheader("图片预览")
        st.image(st.session_state.preview_url, width=200)
    elif st.session_state.get('uploaded_file'):
        st.subheader("图片预览")
        st.image(st.session_state.uploaded_file, width=200)
        preview_info = st.session_state.get('uploaded_file_preview')
        if preview_info:
            st.caption(f"{preview_info['width']}x{preview_info['height']} | {preview_info['format']} | {preview_info['size']:.1f}KB")
    
    st.divider()
    
    # 执行更新
    st.header("🚀 执行更新")
    
    if st.button("开始修改商品图片", type="primary"):
        if not item_id:
            st.error("❌ 请输入商品ID")
        else:
            has_image = False
            if image_source == "网络图片URL":
                has_image = 'image_url' in locals() and image_url
            else:
                has_image = st.session_state.uploaded_file is not None
            
            if not has_image:
                st.error("❌ 请先选择图片")
            else:
                try:
                    with st.spinner("处理中..."):
                        # 上传图片
                        if image_source == "网络图片URL":
                            final_url = upload_from_url(image_url, st.session_state.auth_info)
                        else:
                            final_url = upload_from_local(st.session_state.uploaded_file, st.session_state.auth_info)
                        
                        st.info(f"图片已上传: {final_url[:100]}...")
                        
                        # 修改商品图片
                        result = update_item_image(item_id, final_url, st.session_state.auth_info)
                        
                        if result.get("ret") and "SUCCESS" in str(result["ret"]):
                            st.session_state.update_status = 'success'
                            st.success("✅ 商品图片修改成功！")
                        else:
                            error_msg = result.get("ret", ["未知错误"])[0]
                            st.error(f"❌ 修改失败: {error_msg}")
                            st.session_state.update_status = 'error'
                        
                except Exception as e:
                    st.error(f"❌ 修改失败: {str(e)}")
                    st.session_state.update_status = 'error'
    
    # 底部说明
    st.divider()
    st.caption("💡 提示：请确保Cookie具有编辑商品的权限")

# ==================== 主程序 ====================
def main():
    if not st.session_state.login_success:
        login_page()
    else:
        main_app()

if __name__ == "__main__":
    main()
