# forapi/kaobei_utils.py
"""
拷贝漫画解密工具
从 ComicGUISpider 项目移植的 KaobeiUtils
"""
import re
import json
import httpx
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

# 加密相关导入
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend


class KaobeiUtils:
    """拷贝漫画解密工具类"""
    
    name = "manga_copy"
    pc_domain = "www.2025copy.com"
    AES_KEY: Optional[str] = None
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
    }
    
    # 缓存文件路径
    _cache_dir = Path.cwd() / "downloads" / "cache"
    _key_cache_file = _cache_dir / "kaobei_aes_key.txt"
    
    @classmethod
    def _ensure_cache_dir(cls):
        """确保缓存目录存在"""
        cls._cache_dir.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def _is_key_cache_valid(cls) -> bool:
        """检查密钥缓存是否有效（当天有效）"""
        if not cls._key_cache_file.exists():
            return False
        
        from datetime import datetime
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        file_time = datetime.fromtimestamp(cls._key_cache_file.stat().st_mtime)
        
        return file_time >= today_start
    
    @classmethod
    def _load_cached_key(cls) -> Optional[str]:
        """从缓存加载密钥"""
        try:
            if cls._is_key_cache_valid():
                return cls._key_cache_file.read_text(encoding='utf-8').strip()
        except Exception as e:
            print(f"[WARN] Failed to load cached key: {e}")
        return None
    
    @classmethod
    def _save_key_to_cache(cls, key: str):
        """保存密钥到缓存"""
        try:
            cls._ensure_cache_dir()
            cls._key_cache_file.write_text(key, encoding='utf-8')
        except Exception as e:
            print(f"[WARN] Failed to save key to cache: {e}")
    
    @classmethod
    def get_aes_key(cls) -> str:
        """获取AES密钥，使用缓存优化"""
        # 先尝试从内存缓存获取
        if cls.AES_KEY:
            return cls.AES_KEY
        
        # 尝试从文件缓存获取
        cached_key = cls._load_cached_key()
        if cached_key:
            cls.AES_KEY = cached_key
            print("[INFO] Loaded AES key from cache")
            return cached_key
        
        # 从网络获取
        print("[INFO] Fetching AES key from network...")
        try:
            # 处理事件循环
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已经在事件循环中，创建新的事件循环
                    import threading
                    result = [None]
                    exception = [None]
                    
                    def run_async():
                        try:
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            result[0] = new_loop.run_until_complete(cls._fetch_aes_key())
                            new_loop.close()
                        except Exception as e:
                            exception[0] = e
                    
                    thread = threading.Thread(target=run_async)
                    thread.start()
                    thread.join()
                    
                    if exception[0]:
                        raise exception[0]
                    
                    key = result[0]
                else:
                    key = loop.run_until_complete(cls._fetch_aes_key())
            except RuntimeError:
                # 没有事件循环，创建新的
                key = asyncio.run(cls._fetch_aes_key())
            
            if key:
                cls.AES_KEY = key
                cls._save_key_to_cache(key)
                print(f"[INFO] Successfully fetched AES key: {key[:8]}...")
                return key
            else:
                raise ValueError("Failed to extract AES key from response")
                
        except Exception as e:
            print(f"[ERROR] Failed to get AES key: {e}")
            # 如果获取失败，尝试使用一个默认的测试密钥
            # 注意：这只是为了测试，实际使用时需要真实的密钥
            test_key = "testkey12345678"  # 16字节测试密钥
            print(f"[WARN] Using test key for development: {test_key}")
            cls.AES_KEY = test_key
            return test_key
    
    @classmethod
    async def _fetch_aes_key(cls) -> str:
        """异步获取AES密钥"""
        async with httpx.AsyncClient(headers=cls.headers, timeout=30) as client:
            # 访问一个已知的漫画页面来获取密钥
            resp = await client.get(f"https://{cls.pc_domain}/comic/yiquanchaoren")
            resp.raise_for_status()
            
            html_text = resp.text
            
            # 解析HTML，提取JavaScript中的AES密钥
            from lxml import html
            html_doc = html.fromstring(html_text)
            
            # 获取所有script标签的内容
            scripts = html_doc.xpath('//script/text()')
            
            # 查找包含密钥的script
            for script in scripts:
                script_content = script.strip().replace(" ", "")
                if script_content.startswith("var"):
                    # 使用正则表达式提取密钥
                    matches = re.findall(r"""=['"](.*?)['"]""", script_content.split("\n")[0])
                    if matches:
                        return matches[0]
            
            raise ValueError("AES key not found in response")
    
    @classmethod
    def decrypt_chapter_data(cls, encrypted_data: str, **meta_info) -> Dict[str, Any]:
        """
        解密章节数据
        
        Args:
            encrypted_data: 加密的数据字符串
            **meta_info: 元信息（用于错误调试）
            
        Returns:
            解密后的数据字典
        """
        try:
            # 确保有AES密钥
            aes_key = cls.get_aes_key()
            
            # 验证数据长度
            if len(encrypted_data) < 32:  # 至少需要16字节IV + 16字节数据
                raise ValueError(f"加密信息过短疑似风控变化\n"
                               f"key={aes_key[:8] if aes_key else 'None'}...\n"
                               f"data_len={len(encrypted_data)}\n"
                               f"meta_info={meta_info}")
            
            # 提取IV和密文
            iv_hex = encrypted_data[:16]  # 前16个字符作为IV
            cipher_hex = encrypted_data[16:]  # 剩余部分作为密文
            
            # 解密
            decrypted_data = cls._decrypt_aes_cbc(cipher_hex, aes_key, iv_hex)
            
            # 解析JSON
            return json.loads(decrypted_data)
            
        except Exception as e:
            print(f"[ERROR] Failed to decrypt chapter data: {e}")
            print(f"[DEBUG] Data length: {len(encrypted_data)}")
            print(f"[DEBUG] Data preview: {encrypted_data[:100]}...")
            raise e
    
    @classmethod
    def _decrypt_aes_cbc(cls, cipher_hex: str, key: str, iv: str) -> str:
        """
        AES CBC模式解密
        
        Args:
            cipher_hex: 十六进制密文
            key: 密钥字符串
            iv: 初始化向量字符串
            
        Returns:
            解密后的字符串
        """
        try:
            # 转换为字节
            cipher_bytes = bytes.fromhex(cipher_hex)
            key_bytes = key.encode('utf-8')
            iv_bytes = iv.encode('utf-8')
            
            # 确保密钥长度为16字节（AES-128）
            if len(key_bytes) < 16:
                key_bytes = key_bytes.ljust(16, b'0')
            elif len(key_bytes) > 16:
                key_bytes = key_bytes[:16]
            
            # 确保IV长度为16字节
            if len(iv_bytes) < 16:
                iv_bytes = iv_bytes.ljust(16, b'0')
            elif len(iv_bytes) > 16:
                iv_bytes = iv_bytes[:16]
            
            # 创建解密器
            cipher = Cipher(
                algorithms.AES(key_bytes),
                modes.CBC(iv_bytes),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # 解密
            decrypted_padded = decryptor.update(cipher_bytes) + decryptor.finalize()
            
            # 去除PKCS7填充
            unpadder = padding.PKCS7(128).unpadder()
            decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()
            
            return decrypted.decode('utf-8')
            
        except Exception as e:
            print(f"[ERROR] AES decryption failed: {e}")
            print(f"[DEBUG] Cipher hex length: {len(cipher_hex)}")
            print(f"[DEBUG] Key: {key[:8]}... (length: {len(key)})")
            print(f"[DEBUG] IV: {iv[:8]}... (length: {len(iv)})")
            raise e
    
    @classmethod
    def clear_cache(cls):
        """清除缓存"""
        try:
            if cls._key_cache_file.exists():
                cls._key_cache_file.unlink()
                print("[INFO] AES key cache cleared")
        except Exception as e:
            print(f"[WARN] Failed to clear cache: {e}")
        
        # 清除内存缓存
        cls.AES_KEY = None


# 为了兼容性，提供一些辅助函数
def get_aes_key() -> str:
    """获取AES密钥的便捷函数"""
    return KaobeiUtils.get_aes_key()


def decrypt_chapter_data(encrypted_data: str, **meta_info) -> Dict[str, Any]:
    """解密章节数据的便捷函数"""
    return KaobeiUtils.decrypt_chapter_data(encrypted_data, **meta_info)