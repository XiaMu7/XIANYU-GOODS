# XIANYUGOODS.py - 最终版（使用你成功的完整请求）
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
import re

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 常量定义
APP_KEY = "12574478"
UPLOAD_URL = "https://stream-upload.goofish.com/api/upload.api"
BASE_URL_EDIT = "https://acs.m.goofish.com/h5/mtop.idle.wx.idleitem.edit/1.0/2.0/"
FIXED_UTDID = "v3UyIt1jJFECAXAaAnEns/UL"

# ==================== 从你成功的请求中提取的固定Headers ====================
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
    "bx-umidtoken": "S2gAzrQHfKhXzUXjfSOvIj2d9SgSFnu14MZLKiRfTjc0zh5cUsdstDWvgUJVjeAucMm9Of4Te1AlxZXBXxwtpHTuVwCEfriMaEL8b4GToS0leBUSyDpVIoRjW-ZVZDjrufGuGRetLWKEe4j9GjIDLNB9",
    "x-ticid": "AfmWKWh2CtvkqvArfKi2EmZVYNqGju3hN-ktfFwic4X2CZ6O-zrwo2dKdgOrY4XweWQtBPQVaVj3mj7tpc2ZwL9CN9SD",
    "mini-janus": "10%40sbHKQfVCNlt6fb3vm7IkTiRiCSdtZJGxrFC28EFNGoI2RZB%2BcnTDvmZbl1Vxtx3xSW0Yk7Fnp5%3D%3D",
}

# 全局session
session = requests.Session()
session.verify = False
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
    cookies = {}
    try:
        cookie_str = cookie_str.strip()
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
    cookies = parse_cookie_string(cookie_str)
    
    if not cookies:
        return False
    
    st.session_state.auth_info["cookies"] = cookies
    
    if '_m_h5_tk' in cookies:
        m_h5_tk = cookies['_m_h5_tk']
        st.session_state.auth_info["m_h5_tk"] = m_h5_tk
        if '_' in m_h5_tk:
            token = m_h5_tk.split('_')[0]
            st.session_state.auth_info["token"] = token
        else:
            st.session_state.auth_info["token"] = m_h5_tk
        st.session_state.auth_parsed = True
        return True
    else:
        st.error("Cookie中没有 _m_h5_tk")
        return False

def calc_sign(token: str, t: str, app_key: str, data_str: str) -> str:
    raw = f"{token}&{t}&{app_key}&{data_str}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

# ==================== 上传图片 ====================

def upload_image(file_bytes: bytes, file_name: str, mime: str) -> str:
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
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
    
    upload_headers = FIXED_HEADERS.copy()
    upload_headers['Content-Type'] = f'multipart/form-data; boundary={boundary}'
    upload_headers['sgcookie'] = cookies.get('sgcookie', '')
    
    params = {
        'folderId': '0',
        'appkey': 'fleamarket',
        '_input_charset': 'utf-8',
    }
    
    response = session.post(UPLOAD_URL, params=params, headers=upload_headers, cookies=cookies, data=body, timeout=60)
    
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

def edit_item_image(item_id: str, image_url: str) -> dict:
    """修改商品图片 - 使用你成功的请求格式"""
    cookies = st.session_state.auth_info.get("cookies", {}).copy()
    m_h5_tk = st.session_state.auth_info.get("m_h5_tk", "")
    token = st.session_state.auth_info.get("token", "")
    
    if not token:
        if '_' in m_h5_tk:
            token = m_h5_tk.split('_')[0]
        else:
            token = m_h5_tk
    
    if m_h5_tk:
        cookies["_m_h5_tk"] = m_h5_tk
    
    # 构建图片信息
    image_info = {
        "major": True,
        "widthSize": "640",
        "heightSize": "640",
        "type": 0,
        "url": image_url
    }
    
    # 构建请求数据 - 基于你成功的请求
    data_obj = {
        "utdid": FIXED_UTDID,
        "platform": "windows",
        "miniAppVersion": "9.9.9",
        "imageInfoDOList": [image_info],
        "trendyGroupBuyInfo": {},
        "canBorrow": "false",
        "attribute_product": None,
        "redirectUrl": f"fleamarket://awesome_detail?itemId={item_id}&hitNativeDetail=true&flutter=true&needNotPreGet=true",
        "simpleItem": "true",
        "itemPriceDTO": {
            "priceInCent": 150,
            "origPriceInCent": 200
        },
        "itemTimestampDTO": {},
        "categoryBarDTO": {"url": "https://market.m.taobao.com/app/idleFish-F2e/IdleFish4Weex/CateSecondary?wh_weex=true"},
        "commonTagList": [],
        "canBargain": "true",
        "intellectSpuInfoDTO": {"defaultDes": "关联淘宝同款", "defaultTitle": "宝贝将被多人看到"},
        "jumpUrl": f"fleamarket://awesome_detail?itemId={item_id}&hitNativeDetail=true&flutter=true&needNotPreGet=true",
        "lockCpv": "false",
        "inputProperties": "",
        "uniqueCode": int(time.time() * 1000),
        "bizActivityType": None,
        "itemStatus": None,
        "itemTypeStr": "b",
        "mtopTransformData": "{}",
        "itemTopicParams": {"topicInfos": []},
        "attribute_bizActivityType": None,
        "itemLabelExtList": [
            {
                "channelCateId": "126854790",
                "isUserClick": "1",
                "labelType": "common",
                "from": "newPublishChoice",
                "text": "猫咪",
                "propertyId": "-10000",
                "properties": "-10000##分类:126854790##猫咪"
            }
        ],
        "itemToBuyDTO": None,
        "itemAddrDTO": {
            "area": "天长市",
            "city": "滁州",
            "poiName": "安徽睿弘环保科技有限公司",
            "divisionId": "341181",
            "gps": "32.662261,118.935768",
            "poiId": "B0GD0A7HZL",
            "prov": "安徽"
        },
        "textLabelList": [],
        "defaultPrice": False,
        "trendyFache": {},
        "userRightsProtocols": [],
        "quantity": "1",
        "itemSkuExtra": {},
        "supportBargainPrice": "true",
        "defaultPicUrl": "false",
        "userId": "0",
        "tags": [],
        "hideProSwitcher": "false",
        "itemId": str(item_id),
        "freebies": "false",
        "itemFrom": "wechat",
        "itemTableMap": {},
        "itemTextDTO": {
            "titleDescSeparate": "false",
            "descPath": "desc/icoss!01033424722209!11516426499",
            "title": "哈哈哈",
            "desc": "\n感兴趣的话点“我想要”和我私聊吧～",
            "wlDescription": "哈哈哈哈哈哈哈哈哈哈哈\n感兴趣的话点“我想要”和我私聊吧～"
        },
        "stuffStatus": "9",
        "attribute_biz_line": "normalbuynow",
        "itemPostFeeDTO": {
            "canFreeShipping": "false",
            "onlyTakeSelf": "false",
            "supportFreight": "false",
            "idleTemplateId": "0",
            "templateId": "0",
            "postPriceInCent": 0
        },
        "itemCatDTO": {
            "catId": "50025452",
            "catName": "猫咪",
            "tbCatId": "50016383",
            "channelCatId": "126854790"
        },
        "hideBid": "false",
        "properties": "15808291:60465429"
    }
    
    data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)
    
    # 生成新的签名参数
    t = str(int(time.time() * 1000))
    sign = calc_sign(token, t, APP_KEY, data_str)
    
    # 生成新的c参数（使用token和时间戳）
    c_param = f"{token}_{t};{hashlib.md5(f'{token}_{t}'.encode()).hexdigest()}"
    
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
    
    headers = FIXED_HEADERS.copy()
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
    headers['sgcookie'] = cookies.get('sgcookie', '')
    
    response = session.post(url, headers=headers, cookies=cookies, data={"data": data_str}, timeout=60)
    
    if response.status_code != 200:
        raise Exception(f"HTTP错误: {response.status_code}")
    
    return response.json()

# ==================== 下载图片 ====================

def download_image_from_url(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    response = requests.get(url, headers=headers, timeout=60, verify=False)
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
    st.title("📷 闲鱼商品图片修改工具")
    
    st.header("🔑 认证信息配置")
    
    cookie_input = st.text_area(
        "Cookie",
        height=200,
        placeholder="粘贴完整的Cookie字符串...",
        value="cookie2=1a1dc873b657af0c33ff47d8c27e7742; cna=OPA7Ivhd/iECAXAaAnFXYRhf; _samesite_flag_=true; t=6d0f3df81668bb7846291186b5a28502; _tb_token_=79bd1113ebe57; tracknick=123%E5%88%98%E5%B0%8F%E5%9D%8F; unb=2886592894; xlly_s=1; mtop_partitioned_detect=1; _m_h5_tk=ec8694d86518d128448f0b819d3f089b_1774091684488; _m_h5_tk_enc=a809f19be94bf748147fc9d411b4db5c; sgcookie=E100tUNLOsTQY33%2FL0jZKmAFrBufJwT6LV4TzgAGk4XXV3aqO6T0GuMdqd6Q37lpv0QJdWmIyqDTU%2Fl4zu1FXv2HhBcoCnx4zSC24RNYRrxRGWw%3D; csg=c712c3e6"
    )
    
    if st.button("解析Cookie", use_container_width=True):
        if update_auth_from_cookie(cookie_input):
            st.success("✅ Cookie解析成功")
            st.info(f"token: {st.session_state.auth_info['token'][:30]}...")
    
    if not st.session_state.auth_parsed:
        st.warning("⚠️ 请先粘贴Cookie并解析")
        return
    
    st.divider()
    
    st.header("📦 商品信息")
    item_id = st.text_input("商品ID", value="1033424722209")
    
    st.divider()
    
    st.header("📤 新图片上传")
    image_source = st.radio("选择图片来源", ["网络图片URL", "本地上传"], horizontal=True)
    
    new_image_data = None
    
    if image_source == "网络图片URL":
        new_image_url = st.text_input("图片URL")
        if new_image_url and st.button("预览新图片"):
            try:
                st.image(new_image_url, width=200)
            except:
                st.error("无法预览图片")
        if new_image_url:
            new_image_data = {"type": "url", "value": new_image_url}
    else:
        uploaded_file = st.file_uploader("选择图片文件", type=['png', 'jpg', 'jpeg', 'gif', 'webp'])
        if uploaded_file:
            img_info = process_uploaded_file(uploaded_file)
            if img_info:
                st.image(uploaded_file, width=200)
                st.caption(f"{img_info['width']}x{img_info['height']}")
                new_image_data = {"type": "file", "value": img_info}
    
    st.divider()
    
    if st.button("开始修改商品图片", type="primary", use_container_width=True):
        if not item_id:
            st.error("❌ 请输入商品ID")
        elif not new_image_data:
            st.error("❌ 请先选择图片")
        else:
            try:
                with st.spinner("处理中..."):
                    if new_image_data["type"] == "url":
                        img_bytes, img_name, img_mime = download_image_from_url(new_image_data["value"])
                        final_url = upload_image(img_bytes, img_name, img_mime)
                    else:
                        img_info = new_image_data["value"]
                        final_url = upload_image(img_info["bytes"], img_info["name"], img_info["mime"])
                    
                    st.success(f"✅ 图片上传成功")
                    
                    result = edit_item_image(item_id, final_url)
                    
                    if result.get("ret") and "SUCCESS" in str(result["ret"]):
                        st.success("✅ 商品图片修改成功！")
                        st.balloons()
                    else:
                        error_msg = result.get("ret", ["未知错误"])[0]
                        st.error(f"❌ 修改失败: {error_msg}")
                        with st.expander("查看详细返回"):
                            st.json(result)
            except Exception as e:
                st.error(f"❌ 修改失败: {str(e)}")

if __name__ == "__main__":
    main()
