# app_item_image.py - 闲鱼商品图片修改工具（基于你的脚本逻辑）
import streamlit as st
import hashlib
import json
import time
from urllib.parse import urlencode, parse_qs
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
BASE_URL_DETAIL = "https://acs.m.goofish.com/h5/mtop.taobao.idle.weixin.detail/1.0/2.0/"
BASE_URL_UPDATE = "https://acs.m.goofish.com/h5/mtop.taobao.idle.item.update/1.0/"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# 全局session
session = requests.Session()
session.verify = False

# 全局 _m_h5_tk
CURRENT_M_H5_TK = ""

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
        "utdid": FIXED_UTDID,
        "token": "",
        "m_h5_tk": "",
    }

if 'auth_parsed' not in st.session_state:
    st.session_state.auth_parsed = False

if 'current_item_image' not in st.session_state:
    st.session_state.current_item_image = None

# ==================== 从请求中提取信息 ====================

def extract_from_request(request_text: str) -> dict:
    """从HTTP请求文本中提取所有必要信息"""
    info = {
        "cookies": {},
        "headers": {},
        "params": {},
        "data": {},
        "utdid": None,
        "token": "",
        "m_h5_tk": "",
    }
    
    lines = request_text.strip().split('\n')
    
    # 解析第一行获取URL参数
    first_line = lines[0]
    url_match = re.search(r'\?(.*?)(?:\s|$)', first_line)
    if url_match:
        params_str = url_match.group(1)
        params = parse_qs(params_str)
        for k, v in params.items():
            info["params"][k] = v[0] if v else ""
    
    # 解析headers
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith('{') or line.startswith('h2'):
            continue
            
        if ': ' in line:
            key, value = line.split(': ', 1)
            key_lower = key.lower()
            
            info["headers"][key] = value
            
            # 特殊header处理 - 从x-smallstc提取cookie信息
            if key_lower == 'x-smallstc':
                try:
                    smallstc = json.loads(value)
                    
                    # 提取cookie字段
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
                    info["token"] = info["m_h5_tk"].split('_')[0]
    
    # 从URL参数中提取_m_h5_tk
    if not info["m_h5_tk"] and "_m_h5_tk" in info["params"]:
        info["m_h5_tk"] = info["params"]["_m_h5_tk"]
        info["token"] = info["m_h5_tk"].split('_')[0]
    
    # 解析data部分 - 查找最后的数据行
    data_line = None
    for line in reversed(lines):
        if line.strip().startswith('data='):
            data_line = line.strip()
            break
    
    if data_line:
        data_str = data_line[5:]  # 去掉"data="
        # URL解码
        data_str = urllib.parse.unquote(data_str)
        try:
            info["data"] = json.loads(data_str)
            info["utdid"] = info["data"].get("utdid")
        except json.JSONDecodeError:
            # 如果JSON解析失败，尝试正则提取
            utdid_match = re.search(r'utdid[":]+([^"]+)', data_str)
            if utdid_match:
                info["utdid"] = utdid_match.group(1)
    
    # 如果没有utdid，使用默认值
    if not info["utdid"]:
        info["utdid"] = FIXED_UTDID
    
    return info

def update_auth_info(request_text: str) -> bool:
    """从请求文本更新认证信息"""
    global CURRENT_M_H5_TK
    
    info = extract_from_request(request_text)
    
    if not info:
        return False
    
    st.session_state.auth_info = info
    
    # 更新全局token
    if info["m_h5_tk"]:
        CURRENT_M_H5_TK = info["m_h5_tk"]
        st.session_state.auth_info["m_h5_tk"] = info["m_h5_tk"]
        st.session_state.auth_info["token"] = info["token"]
    
    return True

def calc_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算签名"""
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

# ==================== 图片上传 ====================

def upload_image(file_bytes: bytes, file_name: str, mime: str) -> str:
    """上传图片到闲鱼服务器"""
    global CURRENT_M_H5_TK
    
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    
    # 使用当前的 _m_h5_tk
    if CURRENT_M_H5_TK:
        cookies["_m_h5_tk"] = CURRENT_M_H5_TK
    
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
        'User-Agent': st.session_state.auth_info.get('headers', {}).get('User-Agent', 
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
    }
    
    # 添加特殊headers
    for h in ['sgcookie', 'bx-umidtoken', 'x-ticid', 'x-tap']:
        if h in st.session_state.auth_info.get('headers', {}):
            headers[h] = st.session_state.auth_info['headers'][h]
    
    params = {
        'folderId': '0',
        'appkey': 'fleamarket',
        '_input_charset': 'utf-8',
    }
    
    response = session.post(
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

# ==================== 商品操作 ====================

def get_item_detail(item_id: str, retry_count: int = 0) -> dict:
    """获取商品详情"""
    global CURRENT_M_H5_TK
    
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    
    # 使用当前的 _m_h5_tk
    m_h5_tk = CURRENT_M_H5_TK
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    utdid = st.session_state.auth_info.get("utdid", FIXED_UTDID)
    
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
    
    # 添加c参数
    if "c" in st.session_state.auth_info.get("params", {}):
        params["c"] = st.session_state.auth_info["params"]["c"]
    
    url = f"{BASE_URL_DETAIL}?{urlencode(params)}"
    
    headers = {
        "User-Agent": st.session_state.auth_info.get('headers', {}).get('User-Agent',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    # 添加特殊headers
    for h in ['sgcookie', 'bx-umidtoken', 'x-ticid', 'x-tap']:
        if h in st.session_state.auth_info.get('headers', {}):
            headers[h] = st.session_state.auth_info['headers'][h]
    
    response = session.post(
        url,
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20
    )
    
    # 更新token
    if '_m_h5_tk' in response.cookies:
        new_m_h5_tk = response.cookies['_m_h5_tk']
        if new_m_h5_tk != CURRENT_M_H5_TK:
            print(f"更新 _m_h5_tk: {new_m_h5_tk}")
            CURRENT_M_H5_TK = new_m_h5_tk
            st.session_state.auth_info['m_h5_tk'] = new_m_h5_tk
            st.session_state.auth_info['token'] = new_m_h5_tk.split('_')[0]
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    result = response.json()
    
    # 如果token非法且有新token，重试一次
    if result.get("ret") and "FAIL_SYS_TOKEN_ILLEGAL" in str(result["ret"]) and retry_count == 0:
        print("检测到token非法，使用新token重试...")
        return get_item_detail(item_id, retry_count=1)
    
    return result

def update_item_image(item_id: str, image_url: str, retry_count: int = 0) -> dict:
    """更新商品图片"""
    global CURRENT_M_H5_TK
    
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    
    # 使用当前的 _m_h5_tk
    m_h5_tk = CURRENT_M_H5_TK
    token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    utdid = st.session_state.auth_info.get("utdid", FIXED_UTDID)
    
    # 构建请求数据
    data_obj = {
        "utdid": utdid,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "images": [image_url],
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
        "api": "mtop.taobao.idle.item.update",
        "_bx-m": "1",
    }
    
    # 添加c参数
    if "c" in st.session_state.auth_info.get("params", {}):
        params["c"] = st.session_state.auth_info["params"]["c"]
    
    url = f"{BASE_URL_UPDATE}?{urlencode(params)}"
    
    headers = {
        "User-Agent": st.session_state.auth_info.get('headers', {}).get('User-Agent',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    }
    
    # 添加特殊headers
    for h in ['sgcookie', 'bx-umidtoken', 'x-ticid', 'x-tap']:
        if h in st.session_state.auth_info.get('headers', {}):
            headers[h] = st.session_state.auth_info['headers'][h]
    
    response = session.post(
        url,
        headers=headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20
    )
    
    # 更新token
    if '_m_h5_tk' in response.cookies:
        new_m_h5_tk = response.cookies['_m_h5_tk']
        if new_m_h5_tk != CURRENT_M_H5_TK:
            print(f"更新 _m_h5_tk: {new_m_h5_tk}")
            CURRENT_M_H5_TK = new_m_h5_tk
            st.session_state.auth_info['m_h5_tk'] = new_m_h5_tk
            st.session_state.auth_info['token'] = new_m_h5_tk.split('_')[0]
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    result = response.json()
    
    # 如果token非法且有新token，重试一次
    if result.get("ret") and "FAIL_SYS_TOKEN_ILLEGAL" in str(result["ret"]) and retry_count == 0:
        print("检测到token非法，使用新token重试...")
        return update_item_image(item_id, image_url, retry_count=1)
    
    return result

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
    global CURRENT_M_H5_TK
    
    st.title("📷 闲鱼商品图片修改工具")
    
    # 认证信息配置
    st.header("🔑 认证信息配置")
    
    st.info("请粘贴从浏览器复制的完整HTTP请求头（包含data部分）")
    
    request_text = st.text_area(
        "HTTP请求头",
        height=500,
        placeholder="粘贴完整的HTTP请求头，例如：\nPOST /h5/mtop.taobao.idle.weixin.detail/1.0/2.0/?... HTTP/2\nhost: acs.m.goofish.com\n...\ndata=%7B%22utdid%22%3A...%7D"
    )
    
    if st.button("解析认证信息", use_container_width=True):
        if request_text:
            if update_auth_info(request_text):
                st.session_state.auth_parsed = True
                st.success("✅ 认证信息解析成功")
                
                # 显示解析结果
                if st.session_state.auth_info.get("m_h5_tk"):
                    CURRENT_M_H5_TK = st.session_state.auth_info["m_h5_tk"]
                    st.info(f"✅ _m_h5_tk: {CURRENT_M_H5_TK[:30]}...")
                    st.info(f"✅ token: {st.session_state.auth_info['token'][:20]}...")
                if st.session_state.auth_info.get("utdid"):
                    st.info(f"✅ utdid: {st.session_state.auth_info['utdid']}")
                if st.session_state.auth_info.get("cookies"):
                    st.info(f"✅ cookies: {list(st.session_state.auth_info['cookies'].keys())}")
            else:
                st.error("❌ 解析失败，请检查格式")
    
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
                            
                            # 显示商品信息
                            st.subheader("当前商品信息")
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                st.image(current_image_url, width=200)
                            with col2:
                                st.write(f"**标题:** {item_data.get('title', '')}")
                                st.write(f"**描述:** {item_data.get('desc', '')[:100]}...")
                                st.write(f"**价格:** {item_data.get('soldPrice', '')}元")
                                st.write(f"**图片数量:** {len(image_infos)}张")
                        else:
                            st.warning("未找到商品图片")
                    else:
                        error_msg = result.get("ret", ["未知错误"])[0]
                        st.error(f"获取商品信息失败: {error_msg}")
                        st.json(result)
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
    
    # 底部说明
    st.divider()
    st.caption("💡 使用说明：\n"
               "1. 从浏览器开发者工具复制完整的HTTP请求头（从 POST 开始到 data=... 结束）\n"
               "2. 粘贴到上方文本框并点击解析\n"
               "3. 程序会自动提取 _m_h5_tk 和认证信息\n"
               "4. 输入商品ID，点击获取当前图片确认商品\n"
               "5. 选择新图片（支持URL或本地上传）\n"
               "6. 点击开始修改商品图片\n"
               "7. 程序会自动处理token更新和重试")

if __name__ == "__main__":
    main()
