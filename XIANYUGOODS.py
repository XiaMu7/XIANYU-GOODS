# XIANYUGOODS.py - 简化测试版（只用Cookie）
import streamlit as st
import hashlib
import json
import time
from urllib.parse import urlencode, unquote
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
BASE_URL_EDIT = "https://acs.m.goofish.com/h5/mtop.idle.wx.idleitem.edit/1.0/2.0/"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 固定的Headers（从你之前的请求中提取）====================
FIXED_HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541022) XWEB/16467",
    "accept": "application/json",
    "referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    "origin": "https://servicewechat.com",
    "x-tap": "wx",
    "xweb_xhr": "1",
    "sec-fetch-site": "cross-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "accept-language": "zh-CN,zh;q=0.9",
    "priority": "u=1, i",
    "bx-umidtoken": "S2gAFccM8Ue3klCztyJmE7bRarp39uLDTdDrSiMlewyBfUC1_tjqj4RIi5ZzSTOSo_YdS9PkA1XoQKYpZ09Nu6DDcvFKsvoYPesWNKhdWCdZrh86c98g0bcSFUQxYKk6KTO027G4KUptfdaX2H2eEVzW",
    "x-ticid": "AV4xWPtPBbpHU3c6zyGp06Wcx0vh6CD6TdS4fr-Moyn1gHm_6MN_goRzcYjYaxqxOsNKFUeMprlUAzecNgRmwTxLkCUQ",
    "mini-janus": "10%40%2Fqsjuf84JPeypLnnQ%2FIJ3QSm%2Ffm8RUgaD2GwN9Aqyf8Ld9jP1SXppLDPkEUKp57IuDGIaqlQOPaqiBF%3D",
}

# 全局session
session = requests.Session()
session.verify = False

# 增加超时时间
session.timeout = 60

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
        "m_h5_tk": "",
        "token": "",
    }

if 'auth_parsed' not in st.session_state:
    st.session_state.auth_parsed = False

# ==================== 解析Cookie ====================

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
    
    # 提取_m_h5_tk
    if '_m_h5_tk' in cookies:
        m_h5_tk = cookies['_m_h5_tk']
        st.session_state.auth_info["m_h5_tk"] = m_h5_tk
        st.session_state.auth_info["token"] = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
        st.session_state.auth_parsed = True
        return True
    
    return False

def calc_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算签名"""
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

# ==================== 上传图片 ====================

def upload_image(file_bytes: bytes, file_name: str, mime: str) -> str:
    """上传图片到闲鱼服务器"""
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    m_h5_tk = st.session_state.auth_info.get("m_h5_tk", "")
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
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
        'User-Agent': FIXED_HEADERS.get('user-agent', 'Mozilla/5.0'),
        'sgcookie': cookies.get('sgcookie', ''),
        'bx-umidtoken': FIXED_HEADERS.get('bx-umidtoken', ''),
        'x-ticid': FIXED_HEADERS.get('x-ticid', ''),
        'x-tap': 'wx',
        'mini-janus': FIXED_HEADERS.get('mini-janus', ''),
    }
    
    params = {
        'folderId': '0',
        'appkey': 'fleamarket',
        '_input_charset': 'utf-8',
    }
    
    try:
        response = session.post(
            UPLOAD_URL,
            params=params,
            headers=upload_headers,
            cookies=cookies,
            data=body,
            timeout=60
        )
    except requests.exceptions.Timeout:
        raise Exception("上传超时，请检查网络")
    
    if response.status_code != 200:
        raise Exception(f"上传失败: HTTP {response.status_code}")
    
    result = response.json()
    
    if not result.get('success'):
        raise Exception(f"上传失败: {result.get('message', '未知错误')}")
    
    image_url = result.get('object', {}).get('url') or result.get('url')
    if not image_url:
        raise Exception("响应中没有图片URL")
    
    return image_url

# ==================== 直接修改商品图片（使用内置的c参数）====================

def edit_item_image_direct(item_id: str, image_url: str) -> dict:
    """直接修改商品图片 - 使用内置的c参数"""
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    m_h5_tk = st.session_state.auth_info.get("m_h5_tk", "")
    token = st.session_state.auth_info.get("token", "")
    
    if not token and m_h5_tk:
        token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    # 使用从你之前请求中提取的c参数（这个c参数可能已过期，但先试试）
    c_param = "a7aae20aaaf4c186b06debcc2f7e7854_1774073270430;62452af9c4e6371c500da3b3df1f5913"
    
    # 构建请求数据
    data_obj = {
        "utdid": FIXED_UTDID,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "imageUrl": image_url,
    }
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)
    
    t = str(int(time.time() * 1000))
    sign = calc_sign(token, t, APP_KEY, data_str) if token else ""
    
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
    
    headers = {
        "User-Agent": FIXED_HEADERS.get('user-agent', 'Mozilla/5.0'),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
        "sgcookie": cookies.get('sgcookie', ''),
        "bx-umidtoken": FIXED_HEADERS.get('bx-umidtoken', ''),
        "x-ticid": FIXED_HEADERS.get('x-ticid', ''),
        "x-tap": "wx",
        "mini-janus": FIXED_HEADERS.get('mini-janus', ''),
    }
    
    try:
        response = session.post(
            url,
            headers=headers,
            cookies=cookies,
            data={"data": data_str},
            timeout=60
        )
    except requests.exceptions.Timeout:
        raise Exception("请求超时，请检查网络")
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    return response.json()

# ==================== 下载图片 ====================

def download_image_from_url(url: str):
    """从URL下载图片"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=60, verify=False)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise Exception("下载图片超时")
    
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
        }
    except Exception as e:
        st.error(f"无法解析图片: {str(e)}")
        return None

# ==================== 主界面 ====================
def main():
    st.title("📷 闲鱼商品图片修改工具 - 测试版")
    
    # 认证信息配置
    st.header("🔑 认证信息配置")
    
    cookie_input = st.text_area(
        "Cookie",
        height=150,
        placeholder="粘贴完整的Cookie字符串...",
        value="cookie2=1a1dc873b657af0c33ff47d8c27e7742; cna=OPA7Ivhd/iECAXAaAnFXYRhf; _samesite_flag_=true; t=6d0f3df81668bb7846291186b5a28502; _tb_token_=79bd1113ebe57; tracknick=123%E5%88%98%E5%B0%8F%E5%9D%8F; unb=2886592894; xlly_s=1; sgcookie=E100aNNYp0IDJBysa3MJGiZUbMKaQFO1Y2qwaiOqzPX%2BpHfZ2egKALOm4OvbrvCyrX0ic1Hfq%2FyOzaWT3sUrYC3zD9rAS0%2FP3ciM84EWBTONcHY%3D; csg=6e2a6f6f; mtop_partitioned_detect=1; _m_h5_tk=42ad3a94196e85ca4f7fcb1938a70b36_1774082610841; _m_h5_tk_enc=c3b6dcad0faa6c0c387a917bb3fa190a"
    )
    
    if st.button("解析Cookie", use_container_width=True):
        if cookie_input:
            if update_auth_from_cookie(cookie_input):
                st.success("✅ Cookie解析成功")
                st.info(f"_m_h5_tk: {st.session_state.auth_info['m_h5_tk'][:50]}...")
                st.info(f"token: {st.session_state.auth_info['token'][:30]}...")
            else:
                st.error("❌ Cookie解析失败，请确保包含 _m_h5_tk")
    
    if not st.session_state.auth_parsed:
        st.warning("⚠️ 请先粘贴Cookie并解析")
        return
    
    st.divider()
    
    # 商品信息
    st.header("📦 商品信息")
    
    item_id = st.text_input(
        "商品ID",
        placeholder="请输入要修改图片的商品ID",
        value="1033424722209"
    )
    
    st.info("💡 提示：c参数已内置，但可能已过期。如果修改失败，请重新抓取新的c参数。")
    
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
                st.caption(f"{img_info['width']}x{img_info['height']}")
                new_image_data = {"type": "file", "value": img_info}
    
    st.divider()
    
    # 执行更新
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
                    result = edit_item_image_direct(item_id, final_url)
                    
                    if result.get("ret") and "SUCCESS" in str(result["ret"]):
                        st.success("✅ 商品图片修改成功！")
                        st.balloons()
                    else:
                        error_msg = result.get("ret", ["未知错误"])[0]
                        st.error(f"❌ 修改失败: {error_msg}")
                        
            except requests.exceptions.Timeout:
                st.error("❌ 请求超时，请检查网络后重试")
            except Exception as e:
                st.error(f"❌ 修改失败: {str(e)}")
    
    # 底部说明
    st.divider()
    st.caption("💡 使用说明：\n"
               "1. Cookie已自动填入\n"
               "2. 点击'解析Cookie'确认有效\n"
               "3. 输入商品ID\n"
               "4. 选择新图片\n"
               "5. 点击开始修改\n\n"
               "⚠️ 注意：内置的c参数可能已过期，如果修改失败，需要重新抓取新的c参数")

if __name__ == "__main__":
    main()
