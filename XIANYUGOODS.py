# XIANYUGOODS.py - 最终修复版（获取完整商品数据后修改）
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
BASE_URL_EDIT = "https://acs.m.goofish.com/h5/mtop.idle.wx.idleitem.edit/1.0/2.0/"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 固定的Headers ====================
FIXED_HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541022) XWEB/16467",
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
    "origin": "https://servicewechat.com",
    "x-tap": "wx",
    "xweb_xhr": "1",
    "sec-fetch-site": "cross-site",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
    "accept-language": "zh-CN,zh;q=0.9",
    "priority": "u=1, i",
}

FIXED_AUTH_HEADERS = {
    "bx-umidtoken": "S2gAFccM8Ue3klCztyJmE7bRarp39uLDTdDrSiMlewyBfUC1_tjqj4RIi5ZzSTOSo_YdS9PkA1XoQKYpZ09Nu6DDcvFKsvoYPesWNKhdWCdZrh86c98g0bcSFUQxYKk6KTO027G4KUptfdaX2H2eEVzW",
    "x-ticid": "AV4xWPtPBbpHU3c6zyGp06Wcx0vh6CD6TdS4fr-Moyn1gHm_6MN_goRzcYjYaxqxOsNKFUeMprlUAzecNgRmwTxLkCUQ",
    "mini-janus": "10%40%2Fqsjuf84JPeypLnnQ%2FIJ3QSm%2Ffm8RUgaD2GwN9Aqyf8Ld9jP1SXppLDPkEUKp57IuDGIaqlQOPaqiBF%3D",
}

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
        "c_param": "",
        "user_id": "",
    }

if 'auth_parsed' not in st.session_state:
    st.session_state.auth_parsed = False

if 'current_item_image' not in st.session_state:
    st.session_state.current_item_image = None

if 'current_c_param' not in st.session_state:
    st.session_state.current_c_param = ""

if 'item_full_data' not in st.session_state:
    st.session_state.item_full_data = None

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
    
    headers = FIXED_HEADERS.copy()
    headers.update(FIXED_AUTH_HEADERS)
    
    st.session_state.auth_info["cookies"] = cookies
    st.session_state.auth_info["headers"] = headers
    
    if '_m_h5_tk' in cookies:
        m_h5_tk = cookies['_m_h5_tk']
        st.session_state.auth_info["m_h5_tk"] = m_h5_tk
        st.session_state.auth_info["token"] = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if 'sgcookie' in cookies:
        st.session_state.auth_info["headers"]["sgcookie"] = cookies['sgcookie']
    else:
        st.session_state.auth_info["headers"]["sgcookie"] = "M100K3xhsEszgqIlv4i1ZDy88vMklZMi5FgZlST1476WtlDj2eRBkE%2BlaarlKwvvNCRU1vzpeNWZ1Ney3iRVk1%2FRYHX61FGQgdPqvkRej8ihX2LjVX00XT6bcB%2BBeFIBvQaL"
    
    if 'unb' in cookies:
        st.session_state.auth_info["user_id"] = cookies['unb']
    
    return True

def calc_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    """计算签名"""
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

# ==================== 获取商品完整数据 ====================

def get_item_detail(item_id: str) -> dict:
    """获取商品详情"""
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    headers = st.session_state.auth_info.get("headers", {}).copy()
    m_h5_tk = st.session_state.auth_info.get("m_h5_tk", "")
    token = st.session_state.auth_info.get("token", "")
    utdid = st.session_state.auth_info.get("utdid", FIXED_UTDID)
    
    if not token and m_h5_tk:
        token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
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
    sign = calc_sign(token, t, APP_KEY, data_str) if token else ""
    
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
    
    request_headers = headers.copy()
    request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    
    response = session.post(
        url,
        headers=request_headers,
        cookies=cookies,
        data={"data": data_str},
        timeout=20
    )
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    return response.json()

# ==================== 获取c参数 ====================

def get_c_param_from_edit_page(item_id: str, current_data: dict) -> str:
    """通过编辑页面获取c参数"""
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    headers = st.session_state.auth_info.get("headers", {}).copy()
    m_h5_tk = st.session_state.auth_info.get("m_h5_tk", "")
    token = st.session_state.auth_info.get("token", "")
    utdid = st.session_state.auth_info.get("utdid", FIXED_UTDID)
    
    if not token and m_h5_tk:
        token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    # 构建编辑页面的请求数据（需要完整的商品数据）
    # 从当前商品数据中提取必要字段
    item_data = current_data.get("data", {}).get("itemDO", {})
    
    # 构建编辑请求的数据
    edit_data_obj = {
        "utdid": utdid,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "imageInfoDOList": item_data.get("imageInfos", []),
        "itemTextDTO": item_data.get("itemTextDTO", {}),
        "itemPriceDTO": item_data.get("itemPriceDTO", {}),
        "itemAddrDTO": item_data.get("itemAddrDTO", {}),
        "itemCatDTO": item_data.get("itemCatDTO", {}),
        "stuffStatus": item_data.get("stuffStatus", "9"),
        "quantity": item_data.get("quantity", "1"),
    }
    
    data_str = json.dumps(edit_data_obj, separators=(",", ":"), ensure_ascii=False)
    
    t = str(int(time.time() * 1000))
    sign = calc_sign(token, t, APP_KEY, data_str) if token else ""
    
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
        "api": "mtop.idle.wx.idleitem.edit",
        "_bx-m": "1",
    }
    
    url = f"{BASE_URL_EDIT}?{urlencode(params)}"
    
    request_headers = headers.copy()
    request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    
    # 注意：这里先不发请求，只返回一个临时的c参数
    # 实际上c参数是在进入编辑页面时获得的，这里我们构造一个
    timestamp = str(int(time.time() * 1000))
    temp_c = f"{token}_{timestamp};{hashlib.md5(f'{token}_{timestamp}'.encode()).hexdigest()}"
    
    return temp_c

# ==================== 上传图片 ====================

def upload_image(file_bytes: bytes, file_name: str, mime: str) -> str:
    """上传图片到闲鱼服务器"""
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    headers = st.session_state.auth_info.get("headers", {}).copy()
    m_h5_tk = st.session_state.auth_info.get("m_h5_tk", "")
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
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
        'Referer': headers.get('referer', 'https://servicewechat.com/wx9882f2a891880616/75/page-frame.html'),
        'User-Agent': headers.get('user-agent', 'Mozilla/5.0'),
        'sgcookie': headers.get('sgcookie', ''),
        'bx-umidtoken': headers.get('bx-umidtoken', ''),
        'x-ticid': headers.get('x-ticid', ''),
        'x-tap': headers.get('x-tap', 'wx'),
        'mini-janus': headers.get('mini-janus', ''),
    }
    
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

# ==================== 修改商品图片（使用完整数据）====================

def edit_item_image_with_full_data(item_id: str, image_url: str, c_param: str, full_data: dict) -> dict:
    """编辑商品图片 - 使用完整的商品数据"""
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    headers = st.session_state.auth_info.get("headers", {}).copy()
    m_h5_tk = st.session_state.auth_info.get("m_h5_tk", "")
    token = st.session_state.auth_info.get("token", "")
    utdid = st.session_state.auth_info.get("utdid", FIXED_UTDID)
    
    if not token and m_h5_tk:
        token = m_h5_tk.split('_')[0] if '_' in m_h5_tk else m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    # 获取商品原始数据
    item_data = full_data.get("data", {}).get("itemDO", {})
    image_infos = item_data.get("imageInfos", [])
    
    # 替换图片URL
    if image_infos and len(image_infos) > 0:
        image_infos[0]["url"] = image_url
    
    # 构建完整的编辑请求数据
    edit_data_obj = {
        "utdid": utdid,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "itemId": str(item_id),
        "imageInfoDOList": image_infos,
        "itemTextDTO": item_data.get("itemTextDTO", {}),
        "itemPriceDTO": item_data.get("itemPriceDTO", {}),
        "itemAddrDTO": item_data.get("itemAddrDTO", {}),
        "itemCatDTO": item_data.get("itemCatDTO", {}),
        "stuffStatus": item_data.get("stuffStatus", "9"),
        "quantity": item_data.get("quantity", "1"),
        "itemLabelExtList": item_data.get("itemLabelExtList", []),
        "itemPostFeeDTO": item_data.get("itemPostFeeDTO", {}),
        "canBargain": item_data.get("canBargain", "true"),
        "supportBargainPrice": item_data.get("supportBargainPrice", "true"),
        "defaultPrice": item_data.get("defaultPrice", False),
        "simpleItem": item_data.get("simpleItem", "true"),
        "itemFrom": item_data.get("itemFrom", "wechat"),
        "itemTypeStr": item_data.get("itemTypeStr", "b"),
        "redirectUrl": item_data.get("redirectUrl", f"fleamarket://awesome_detail?itemId={item_id}&hitNativeDetail=true&flutter=true&needNotPreGet=true"),
        "jumpUrl": item_data.get("jumpUrl", f"fleamarket://awesome_detail?itemId={item_id}&hitNativeDetail=true&flutter=true&needNotPreGet=true"),
    }
    
    data_str = json.dumps(edit_data_obj, separators=(",", ":"), ensure_ascii=False)
    
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
    
    request_headers = headers.copy()
    request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    
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

# ==================== 下载图片 ====================

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
    
    cookie_input = st.text_area(
        "Cookie",
        height=200,
        placeholder="粘贴完整的Cookie字符串...",
        value="cookie2=1a1dc873b657af0c33ff47d8c27e7742; cna=OPA7Ivhd/iECAXAaAnFXYRhf; _samesite_flag_=true; t=6d0f3df81668bb7846291186b5a28502; _tb_token_=79bd1113ebe57; tracknick=123%E5%88%98%E5%B0%8F%E5%9D%8F; unb=2886592894; xlly_s=1; sgcookie=E100aNNYp0IDJBysa3MJGiZUbMKaQFO1Y2qwaiOqzPX%2BpHfZ2egKALOm4OvbrvCyrX0ic1Hfq%2FyOzaWT3sUrYC3zD9rAS0%2FP3ciM84EWBTONcHY%3D; csg=6e2a6f6f; mtop_partitioned_detect=1; _m_h5_tk=42ad3a94196e85ca4f7fcb1938a70b36_1774082610841; _m_h5_tk_enc=c3b6dcad0faa6c0c387a917bb3fa190a"
    )
    
    if st.button("解析Cookie", use_container_width=True):
        if cookie_input:
            if update_auth_from_cookie(cookie_input):
                st.session_state.auth_parsed = True
                st.success("✅ Cookie解析成功")
                if st.session_state.auth_info.get("m_h5_tk"):
                    st.info(f"_m_h5_tk: {st.session_state.auth_info['m_h5_tk'][:50]}...")
            else:
                st.error("❌ Cookie解析失败")
    
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
    
    if item_id:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("获取商品完整数据", use_container_width=True):
                try:
                    with st.spinner("获取商品信息中..."):
                        result = get_item_detail(item_id)
                        
                        if result.get("ret") and "SUCCESS" in str(result["ret"]):
                            st.session_state.item_full_data = result
                            item_data = result.get("data", {}).get("itemDO", {})
                            image_infos = item_data.get("imageInfos", [])
                            
                            if image_infos:
                                current_image_url = image_infos[0].get("url", "")
                                st.session_state.current_item_image = current_image_url
                                st.success("✅ 获取商品数据成功")
                                
                                st.subheader("当前商品信息")
                                col_a, col_b = st.columns([1, 2])
                                with col_a:
                                    st.image(current_image_url, width=200)
                                with col_b:
                                    st.write(f"**标题:** {item_data.get('title', '')[:50]}...")
                                    st.write(f"**价格:** {item_data.get('soldPrice', '')}元")
                                    st.write(f"**分类:** {item_data.get('itemCatDTO', {}).get('catName', '未知')}")
                            else:
                                st.warning("未找到商品图片")
                        else:
                            error_msg = result.get("ret", ["未知错误"])[0]
                            st.error(f"获取商品信息失败: {error_msg}")
                except Exception as e:
                    st.error(f"获取商品信息失败: {str(e)}")
        
        with col2:
            if st.button("生成c参数", use_container_width=True):
                if st.session_state.item_full_data:
                    try:
                        with st.spinner("生成c参数中..."):
                            c_param = get_c_param_from_edit_page(item_id, st.session_state.item_full_data)
                            st.session_state.current_c_param = c_param
                            st.success(f"✅ c参数生成成功")
                            st.info(f"c参数: {c_param[:80]}...")
                    except Exception as e:
                        st.error(f"生成c参数失败: {str(e)}")
                else:
                    st.warning("请先点击'获取商品完整数据'")
        
        if st.session_state.current_c_param:
            st.success(f"✅ c参数已就绪")
    
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
        elif not st.session_state.current_c_param:
            st.error("❌ 请先生成c参数")
        elif not st.session_state.item_full_data:
            st.error("❌ 请先获取商品完整数据")
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
                    
                    # 修改商品图片（使用完整数据）
                    st.info("正在修改商品图片...")
                    result = edit_item_image_with_full_data(item_id, final_url, st.session_state.current_c_param, st.session_state.item_full_data)
                    
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
               "1. 粘贴Cookie\n"
               "2. 输入商品ID\n"
               "3. 点击'获取商品完整数据'获取当前商品所有信息\n"
               "4. 点击'生成c参数'\n"
               "5. 选择新图片\n"
               "6. 点击开始修改商品图片")

if __name__ == "__main__":
    main()
