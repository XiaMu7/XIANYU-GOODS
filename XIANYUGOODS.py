# app_item_image.py - 闲鱼商品图片修改工具（简化版）
import streamlit as st
import hashlib
import json
import time
from urllib.parse import urlencode, quote
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
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# 页面配置
st.set_page_config(
    page_title="闲鱼商品图片修改工具",
    page_icon="📷",
    layout="wide"
)

# 初始化session状态
if 'session' not in st.session_state:
    st.session_state.session = requests.Session()
    st.session_state.session.verify = False

if 'current_m_h5_tk' not in st.session_state:
    st.session_state.current_m_h5_tk = ""

if 'current_token' not in st.session_state:
    st.session_state.current_token = ""

if 'current_c' not in st.session_state:
    st.session_state.current_c = ""

if 'auth_headers' not in st.session_state:
    st.session_state.auth_headers = {}

if 'cookies' not in st.session_state:
    st.session_state.cookies = {}

if 'auth_parsed' not in st.session_state:
    st.session_state.auth_parsed = False

# ==================== 工具函数 ====================

def extract_auth_info(request_text: str):
    """从HTTP请求文本中提取认证信息"""
    result = {
        "c_param": "",
        "m_h5_tk": "",
        "token": "",
        "sgcookie": "",
        "bx_umidtoken": "",
        "x_ticid": "",
        "x_tap": "",
        "bx_ua": "",
        "user_agent": "",
        "referer": ""
    }
    
    lines = request_text.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # 提取URL中的c参数
        if line.startswith('POST') or line.startswith('GET'):
            # 提取c参数
            match = re.search(r'c=([^&]+)', line)
            if match:
                result["c_param"] = match.group(1)
            
            # 提取_m_h5_tk（可能在URL中）
            match = re.search(r'_m_h5_tk=([^&]+)', line)
            if match:
                result["m_h5_tk"] = match.group(1)
                result["token"] = result["m_h5_tk"].split('_')[0]
        
        # 提取headers
        elif ':' in line and not line.startswith('POST') and not line.startswith('GET'):
            key, value = line.split(':', 1)
            key = key.strip().lower()
            value = value.strip()
            
            if key == 'sgcookie':
                result["sgcookie"] = value
            elif key == 'bx-umidtoken':
                result["bx_umidtoken"] = value
            elif key == 'x-ticid':
                result["x_ticid"] = value
            elif key == 'x-tap':
                result["x_tap"] = value
            elif key == 'bx-ua':
                result["bx_ua"] = value
                # 从bx-ua中提取_m_h5_tk
                match = re.search(r'_m_h5_tk=([^;]+)', value)
                if match and not result["m_h5_tk"]:
                    result["m_h5_tk"] = match.group(1)
                    result["token"] = result["m_h5_tk"].split('_')[0]
            elif key == 'user-agent':
                result["user_agent"] = value
            elif key == 'referer':
                result["referer"] = value
    
    return result

def calc_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算签名"""
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

def upload_image(file_bytes: bytes, file_name: str, mime: str) -> str:
    """上传图片到闲鱼服务器"""
    cookies = {"_m_h5_tk": st.session_state.current_m_h5_tk}
    
    # 构建multipart数据
    boundary = '----WebKitFormBoundary' + ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=16))
    
    body_parts = []
    
    # 表单字段
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
    
    # 文件
    body_parts.append(f'--{boundary}')
    body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"')
    body_parts.append(f'Content-Type: {mime}')
    body_parts.append('')
    
    # 组合body
    body = '\r\n'.join(body_parts).encode() + b'\r\n' + file_bytes + f'\r\n--{boundary}--\r\n'.encode()
    
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Accept': '*/*',
        'Origin': 'https://servicewechat.com',
        'Referer': 'https://servicewechat.com/wx9882f2a891880616/75/page-frame.html',
        'User-Agent': st.session_state.auth_headers.get('user_agent', 'Mozilla/5.0'),
    }
    
    if st.session_state.auth_headers.get('sgcookie'):
        headers['sgcookie'] = st.session_state.auth_headers['sgcookie']
    
    params = {
        'folderId': '0',
        'appkey': 'fleamarket',
        '_input_charset': 'utf-8',
    }
    
    response = st.session_state.session.post(
        UPLOAD_URL,
        params=params,
        headers=headers,
        cookies=cookies,
        data=body,
        timeout=30
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

def get_item_detail(item_id: str) -> dict:
    """获取商品详情"""
    token = st.session_state.current_token
    if not token:
        raise Exception("Token为空，请重新解析认证信息")
    
    # 构建请求数据
    data_obj = {
        "utdid": FIXED_UTDID,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "formScene": "",
        "extra": json.dumps({"isShare": False})
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
        "api": "mtop.taobao.idle.weixin.detail",
        "_bx-m": "1",
    }
    
    if st.session_state.current_c:
        params["c"] = st.session_state.current_c
    
    url = f"https://acs.m.goofish.com/h5/mtop.taobao.idle.weixin.detail/1.0/2.0/"
    
    headers = {
        "User-Agent": st.session_state.auth_headers.get('user_agent', 'Mozilla/5.0'),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    # 添加其他headers
    if st.session_state.auth_headers.get('sgcookie'):
        headers['sgcookie'] = st.session_state.auth_headers['sgcookie']
    if st.session_state.auth_headers.get('bx_umidtoken'):
        headers['bx-umidtoken'] = st.session_state.auth_headers['bx_umidtoken']
    if st.session_state.auth_headers.get('x_ticid'):
        headers['x-ticid'] = st.session_state.auth_headers['x_ticid']
    if st.session_state.auth_headers.get('x_tap'):
        headers['x-tap'] = st.session_state.auth_headers['x_tap']
    
    cookies = {"_m_h5_tk": st.session_state.current_m_h5_tk}
    
    # 发送请求
    response = st.session_state.session.post(
        url,
        params=params,
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20
    )
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    try:
        return response.json()
    except:
        raise Exception(f"响应解析失败: {response.text[:200]}")

def update_item_image(item_id: str, image_url: str) -> dict:
    """更新商品图片"""
    token = st.session_state.current_token
    if not token:
        raise Exception("Token为空，请重新解析认证信息")
    
    # 构建请求数据 - 修改商品图片
    data_obj = {
        "utdid": FIXED_UTDID,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "images": [image_url],
    }
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)
    
    t = str(int(time.time() * 1000))
    sign = calc_sign(token, t, APP_KEY, data_str)
    
    # 构建URL和参数 - 使用编辑商品接口
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
        "api": "mtop.taobao.idle.item.update",
        "_bx-m": "1",
    }
    
    if st.session_state.current_c:
        params["c"] = st.session_state.current_c
    
    url = f"https://acs.m.goofish.com/h5/mtop.taobao.idle.item.update/1.0/"
    
    headers = {
        "User-Agent": st.session_state.auth_headers.get('user_agent', 'Mozilla/5.0'),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    # 添加其他headers
    if st.session_state.auth_headers.get('sgcookie'):
        headers['sgcookie'] = st.session_state.auth_headers['sgcookie']
    if st.session_state.auth_headers.get('bx_umidtoken'):
        headers['bx-umidtoken'] = st.session_state.auth_headers['bx_umidtoken']
    if st.session_state.auth_headers.get('x_ticid'):
        headers['x-ticid'] = st.session_state.auth_headers['x_ticid']
    if st.session_state.auth_headers.get('x_tap'):
        headers['x-tap'] = st.session_state.auth_headers['x_tap']
    
    cookies = {"_m_h5_tk": st.session_state.current_m_h5_tk}
    
    # 发送请求
    response = st.session_state.session.post(
        url,
        params=params,
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20
    )
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    try:
        return response.json()
    except:
        raise Exception(f"响应解析失败: {response.text[:200]}")

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
    
    st.info("请粘贴从浏览器复制的完整HTTP请求头")
    
    request_text = st.text_area(
        "HTTP请求头",
        height=400,
        placeholder="粘贴完整的HTTP请求头..."
    )
    
    if st.button("解析认证信息", use_container_width=True):
        if request_text:
            auth_info = extract_auth_info(request_text)
            
            # 保存认证信息
            st.session_state.current_m_h5_tk = auth_info["m_h5_tk"]
            st.session_state.current_token = auth_info["token"]
            st.session_state.current_c = auth_info["c_param"]
            st.session_state.auth_headers = auth_info
            
            if auth_info["token"]:
                st.session_state.auth_parsed = True
                st.success("✅ 认证信息解析成功")
                
                # 显示解析结果
                st.info(f"Token: {auth_info['token'][:20]}...")
                st.info(f"c参数: {auth_info['c_param'][:30]}...")
                if auth_info['sgcookie']:
                    st.info(f"sgcookie: {auth_info['sgcookie'][:30]}...")
            else:
                st.error("❌ 解析失败，未找到Token")
                st.info("请确保请求头中包含 _m_h5_tk 参数")
    
    if not st.session_state.auth_parsed:
        st.warning("⚠️ 请先配置并解析认证信息")
        return
    
    st.divider()
    
    # 商品信息
    st.header("📦 商品信息")
    
    item_id = st.text_input(
        "商品ID",
        placeholder="请输入要修改图片的商品ID"
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
                            st.success("✅ 获取商品信息成功")
                            
                            # 显示商品信息
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
                    
                    st.info(f"图片上传成功，正在修改商品...")
                    
                    # 修改商品图片
                    result = update_item_image(item_id, final_url)
                    
                    if result.get("ret") and "SUCCESS" in str(result["ret"]):
                        st.success("✅ 商品图片修改成功！")
                        st.balloons()
                    else:
                        error_msg = result.get("ret", ["未知错误"])[0]
                        st.error(f"❌ 修改失败: {error_msg}")
                        st.json(result)
                        
            except Exception as e:
                st.error(f"❌ 修改失败: {str(e)}")

if __name__ == "__main__":
    main()
