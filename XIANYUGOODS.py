#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import hashlib
import json
import mimetypes
import time
import sys
import re
import urllib.parse
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qs

import requests

API = "mtop.idle.wx.idleitem.edit"
APP_KEY = "12574478"
BASE_URL = "https://acs.m.goofish.com/h5/mtop.idle.wx.idleitem.edit/1.0/"

# 会话对象，用于保持cookie
session = requests.Session()


class XianyuItemUpdater:
    """闲鱼商品信息更新器"""
    
    def __init__(self, cookies_str=None, utdid=None):
        """
        初始化更新器
        
        Args:
            cookies_str: Cookie字符串，格式如 "key1=value1; key2=value2"
            utdid: 设备标识，从抓包中获取
        """
        self.cookies = {}
        self.utdid = utdid
        self.m_h5_tk = None
        self.token = None
        
        # 解析cookie字符串
        if cookies_str:
            self.parse_cookies(cookies_str)
        
        # 设置默认headers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541022) XWEB/16467",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Referer": "https://servicewechat.com/wx9882f2a891880616/75/page-frame.html",
            "x-tap": "wx",
        }
        
        # 从cookies中提取_m_h5_tk
        if "_m_h5_tk" in self.cookies:
            self.m_h5_tk = self.cookies["_m_h5_tk"]
            self.token = self.m_h5_tk.split('_')[0] if '_' in self.m_h5_tk else self.m_h5_tk
    
    def parse_cookies(self, cookies_str):
        """解析Cookie字符串"""
        for item in cookies_str.split(';'):
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                self.cookies[key.strip()] = value.strip()
    
    def set_headers_from_dict(self, headers_dict):
        """从字典设置headers"""
        for key, value in headers_dict.items():
            self.headers[key] = value
    
    def calc_sign(self, token, t, app_key, data_str):
        """计算签名"""
        raw = f"{token}&{t}&{app_key}&{data_str}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()
    
    def update_item_image(self, item_id, image_url, retry_count=0):
        """
        更新商品图片
        
        Args:
            item_id: 商品ID
            image_url: 图片URL
            retry_count: 重试次数
        
        Returns:
            更新结果
        """
        if not self.m_h5_tk:
            raise ValueError("未找到 _m_h5_tk cookie")
        
        if not self.utdid:
            raise ValueError("未提供 utdid")
        
        # 构建请求数据
        data_obj = {
            "utdid": self.utdid,
            "platform": "windows",
            "miniAppVersion": "9.9.9",
            "imageInfoDOList": [
                {
                    "major": True,
                    "type": 0,
                    "url": image_url,
                    "widthSize": "640",
                    "heightSize": "640"
                }
            ],
            "itemId": item_id,
            "itemFrom": "wechat",
            "simpleItem": "true"
        }
        
        data_str = json.dumps(data_obj, separators=(",", ":"), ensure_ascii=False)
        
        t = str(int(time.time() * 1000))
        sign = self.calc_sign(self.token, t, APP_KEY, data_str)
        
        # 构建请求参数
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
        
        # 准备cookies
        cookies = self.cookies.copy()
        cookies["_m_h5_tk"] = self.m_h5_tk
        
        print(f"\n发送更新请求...")
        print(f"商品ID: {item_id}")
        print(f"图片URL: {image_url}")
        
        # 发送请求
        response = session.post(
            f"{BASE_URL}?{urlencode(params)}",
            headers=self.headers,
            cookies=cookies,
            data={"data": data_str},
            timeout=20,
        )
        
        print(f"响应状态码: {response.status_code}")
        
        # 检查并更新token
        token_updated = False
        if '_m_h5_tk' in response.cookies:
            new_m_h5_tk = response.cookies['_m_h5_tk']
            if new_m_h5_tk != self.m_h5_tk:
                print(f"发现新的 _m_h5_tk: {new_m_h5_tk}")
                print(f"自动更新当前token")
                self.m_h5_tk = new_m_h5_tk
                self.token = new_m_h5_tk.split('_')[0] if '_' in new_m_h5_tk else new_m_h5_tk
                self.cookies['_m_h5_tk'] = new_m_h5_tk
                token_updated = True
        
        result = response.json()
        
        # 如果返回非法令牌且没有重试过，并且token被更新了，则自动重试一次
        if result.get("ret") and "FAIL_SYS_TOKEN_ILLEGAL" in str(result["ret"]) and retry_count == 0 and token_updated:
            print("\n检测到新token，自动重试一次...")
            time.sleep(1)
            return self.update_item_image(item_id, image_url, retry_count=1)
        
        return result
    
    def upload_image_from_url(self, image_url):
        """
        从URL上传图片到闲鱼服务器
        
        Args:
            image_url: 图片URL
        
        Returns:
            上传后的图片URL
        """
        print(f"下载图片: {image_url}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        content = response.content
        
        if not content:
            raise RuntimeError("下载的图片为空")
        
        parsed = urlparse(image_url)
        raw_name = Path(parsed.path).name or "remote.jpg"
        if "." not in raw_name:
            raw_name = f"{raw_name}.jpg"
        
        mime = response.headers.get("Content-Type", "").split(";")[0].strip()
        if not mime:
            mime = mimetypes.guess_type(raw_name)[0] or "image/jpeg"
        
        print(f"下载完成: {len(content)} bytes, MIME: {mime}")
        
        return self.upload_bytes(raw_name, content, mime)
    
    def upload_bytes(self, file_name, file_bytes, mime):
        """
        上传图片字节流
        
        Args:
            file_name: 文件名
            file_bytes: 文件字节流
            mime: MIME类型
        
        Returns:
            上传后的图片URL
        """
        upload_url = "https://stream-upload.goofish.com/api/upload.api"
        
        cookies = self.cookies.copy()
        if self.m_h5_tk:
            cookies["_m_h5_tk"] = self.m_h5_tk
        
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
        
        print(f"上传文件到: {upload_url}")
        
        response = session.post(
            upload_url,
            params=params,
            headers=self.headers,
            cookies=cookies,
            data=data,
            files=files,
            timeout=30,
        )
        
        response.raise_for_status()
        body = response.json()
        
        if not body.get("success"):
            raise RuntimeError(f"上传失败: {body}")
        
        image_url = body.get("object", {}).get("url")
        if not image_url:
            raise RuntimeError(f"上传响应缺少object.url: {body}")
        
        return image_url


def main():
    """主函数"""
    print("=" * 50)
    print("闲鱼商品图片更新工具")
    print("=" * 50)
    
    # 获取商品ID
    print("\n请输入要修改的闲鱼商品ID：")
    print("（可以在商品详情页URL中找到，如 itemId=1033424722209）")
    item_id = input("商品ID: ").strip()
    
    if not item_id:
        print("错误：商品ID不能为空")
        sys.exit(1)
    
    # 获取图片URL
    print("\n请输入新的图片URL：")
    print("支持格式：https://xxx.jpg 或本地文件路径")
    image_input = input("图片URL/路径: ").strip()
    
    if not image_input:
        print("错误：图片URL不能为空")
        sys.exit(1)
    
    # 获取Cookie
    print("\n请输入Cookie字符串：")
    print("（从浏览器或抓包工具中复制，格式如：cookie2=xxx; _m_h5_tk=xxx; ...）")
    print("提示：复制完整的Cookie字符串，包含所有必要的认证信息")
    cookies_str = input("Cookie: ").strip()
    
    if not cookies_str:
        print("警告：未提供Cookie，将使用默认值（可能导致认证失败）")
    
    # 获取utdid
    print("\n请输入utdid（从抓包中的data字段获取）：")
    print("示例：v3UyIt1jJFECAXAaAnEns/UL")
    utdid = input("utdid: ").strip()
    
    if not utdid:
        print("错误：utdid不能为空")
        print("提示：请在抓包中找到请求中的data字段，提取utdid值")
        sys.exit(1)
    
    # 创建更新器
    updater = XianyuItemUpdater(cookies_str=cookies_str, utdid=utdid)
    
    # 可选：添加其他必要的headers
    print("\n是否添加额外的headers？（可选，按回车跳过）")
    extra_headers = input("headers (JSON格式，如 {\"bx-umidtoken\":\"xxx\"}): ").strip()
    if extra_headers:
        try:
            headers_dict = json.loads(extra_headers)
            updater.set_headers_from_dict(headers_dict)
        except json.JSONDecodeError:
            print("警告：headers格式错误，将跳过")
    
    try:
        # 处理图片
        print("\n" + "-" * 50)
        print("处理图片...")
        
        # 判断是本地文件还是URL
        if image_input.startswith(('http://', 'https://')):
            # 如果是URL，直接使用
            final_image_url = image_input
            print(f"使用图片URL: {final_image_url}")
        else:
            # 如果是本地文件，先上传
            print(f"读取本地文件: {image_input}")
            with open(image_input, 'rb') as f:
                file_bytes = f.read()
            
            file_name = Path(image_input).name
            mime = mimetypes.guess_type(file_name)[0] or "image/jpeg"
            
            final_image_url = updater.upload_bytes(file_name, file_bytes, mime)
            print(f"上传成功: {final_image_url}")
        
        # 更新商品图片
        print("\n" + "-" * 50)
        print("更新商品图片...")
        result = updater.update_item_image(item_id, final_image_url)
        
        # 输出结果
        print("\n" + "-" * 50)
        print("更新结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if result.get("ret") and "SUCCESS" in str(result["ret"]):
            print("\n✓ 商品图片更新成功！")
        else:
            print("\n✗ 商品图片更新失败，请检查返回信息")
            
    except FileNotFoundError:
        print(f"\n✗ 错误：找不到本地文件 {image_input}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
