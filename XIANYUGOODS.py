# app_item_image.py - 闲鱼商品图片修改工具（简化版）
import streamlit as st
import hashlib
import json
import time
from urllib.parse import urlencode
import os
import random
import string
import io
import requests
import urllib3
from PIL import Image

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

if 'cookie_parsed' not in st.session_state:
    st.session_state.cookie_parsed = False

if 'current_item_image' not in st.session_state:
    st.session_state.current_item_image = None

if 'item_info' not in st.session_state:
    st.session_state.item_info = None

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

def calc_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算签名"""
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

def upload_image(file_bytes: bytes, file_name: str, mime: str) -> str:
    """上传图片到闲鱼服务器"""
    cookies = st.session_state.auth_info["cookies"].copy()
    
    if st.session_state.current_m_h5_tk:
        cookies["_m_h5_tk"] = st.session_state.current_m_h5_tk
    
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
        'User-Agent': st.session_state.auth_info['headers']['User-Agent'],
    }
    
    if 'sgcookie' in cookies:
        headers['sgcookie'] = cookies['sgcookie']
    
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
    cookies = st.session_state.auth_info["cookies"].copy()
    
    m_h5_tk = st.session_state.current_m_h5_tk
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    utdid = st.session_state.auth_info["utdid"]
    
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
    
    # 构建URL参数
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
    
    url = f"https://acs.m.goofish.com/h5/mtop.taobao.idle.weixin.detail/1.0/2.0/?{urlencode(params)}"
    
    headers = {
        "User-Agent": st.session_state.auth_info['headers']['User-Agent'],
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    if 'sgcookie' in cookies:
        headers['sgcookie'] = cookies['sgcookie']
    
    # 发送请求
    response = st.session_state.session.post(
        url,
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20
    )
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    return response.json()

def update_item_image(item_id: str, image_url: str) -> dict:
    """更新商品图片"""
    cookies = st.session_state.auth_info["cookies"].copy()
    
    m_h5_tk = st.session_state.current_m_h5_tk
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    utdid = st.session_state.auth_info["utdid"]
    
    # 构建请求数据 - 修改商品图片
    data_obj = {
        "utdid": utdid,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "images": [image_url],  # 商品图片列表
    }
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)
    
    t = str(int(time.time() * 1000))
    sign = calc_sign(token, t, APP_KEY, data_str)
    
    # 构建URL参数
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
    
    url = f"https://acs.m.goofish.com/h5/mtop.taobao.idle.item.update/1.0/?{urlencode(params)}"
    
    headers = {
        "User-Agent": st.session_state.auth_info['headers']['User-Agent'],
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    if 'sgcookie' in cookies:
        headers['sgcookie'] = cookies['sgcookie']
    
    # 发送请求
    response = st.session_state.session.post(
        url,
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20
    )
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    return response.json()

def download_image_from_url(url: str) -> Tuple[bytes, str, str]:
    """从URL下载图片"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    response = requests.get(url, headers=headers, timeout=30, verify=False)
    response.raise_for_status()
    
    content = response.content
    if len(content) == 0:
        raise Exception("文件为空")
    
    # 获取文件名
    parsed = urllib3.util.parse_url(url)
    file_name = os.path.basename(parsed.path or "")
    if not file_name or '.' not in file_name:
        file_name = f"image_{int(time.time())}.jpg"
    
    # 获取MIME类型
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
    
    cookie_input = st.text_area(
        "Cookie字符串",
        height=150,
        placeholder="在这里粘贴完整的Cookie字符串...\n\n例如: _m_h5_tk=xxx; sgcookie=xxx; ..."
    )
    
    if st.button("解析Cookie", use_container_width=True):
        if cookie_input:
            if update_auth_info_from_cookie(cookie_input):
                st.session_state.cookie_parsed = True
                st.success("✅ Cookie解析成功")
                # 显示解析到的关键信息
                if st.session_state.current_m_h5_tk:
                    st.info(f"已获取 _m_h5_tk: {st.session_state.current_m_h5_tk[:30]}...")
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
                            st.session_state.item_info = {
                                "title": item_data.get("title", ""),
                                "desc": item_data.get("desc", ""),
                                "price": item_data.get("soldPrice", ""),
                                "image_count": len(image_infos)
                            }
                            st.success("✅ 获取商品信息成功")
                            st.rerun()
                        else:
                            st.warning("未找到商品图片")
                    else:
                        error_msg = result.get("ret", ["未知错误"])[0]
                        st.error(f"获取商品信息失败: {error_msg}")
            except Exception as e:
                st.error(f"获取商品信息失败: {str(e)}")
        
        # 显示商品信息
        if st.session_state.get('current_item_image'):
            st.subheader("当前商品信息")
            
            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(st.session_state.current_item_image, width=200)
            with col2:
                if st.session_state.item_info:
                    st.write(f"**标题:** {st.session_state.item_info['title']}")
                    st.write(f"**描述:** {st.session_state.item_info['desc'][:100]}...")
                    st.write(f"**价格:** {st.session_state.item_info['price']}元")
                    st.write(f"**图片数量:** {st.session_state.item_info['image_count']}张")
    
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
                        # 清除缓存
                        st.session_state.current_item_image = None
                        st.session_state.item_info = None
                    else:
                        error_msg = result.get("ret", ["未知错误"])[0]
                        st.error(f"❌ 修改失败: {error_msg}")
                        if "ret" in result:
                            st.json(result.get("ret"))
                        
            except Exception as e:
                st.error(f"❌ 修改失败: {str(e)}")
    
    # 底部说明
    st.divider()
    st.caption("💡 使用说明：\n"
               "1. 从浏览器获取完整的Cookie字符串\n"
               "2. 粘贴Cookie并点击解析\n"
               "3. 输入商品ID，点击获取当前图片确认商品\n"
               "4. 选择新图片（支持URL或本地上传）\n"
               "5. 点击开始修改商品图片")

if __name__ == "__main__":
    main()
