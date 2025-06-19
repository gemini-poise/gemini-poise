import logging
import time
import json
from typing import Optional, Dict, Any, Union
from contextlib import contextmanager
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)


class HttpUtil:
    """
    HTTP 工具类，提供统一的 HTTP 请求接口
    支持连接池、重试机制、超时控制等功能
    """
    
    _client = None
    _async_client = None
    
    # 配置常量
    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1
    DEFAULT_POOL_LIMITS = httpx.Limits(max_keepalive_connections=20, max_connections=100)
    
    # 默认请求头
    DEFAULT_HEADERS = {
        'User-Agent': 'HttpUtil/1.0',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }

    @classmethod
    def _get_client(cls, timeout: Optional[float] = None) -> httpx.Client:
        """获取或创建 HTTP 客户端实例"""
        if cls._client is None or cls._client.is_closed:
            timeout_config = httpx.Timeout(timeout or cls.DEFAULT_TIMEOUT)
            cls._client = httpx.Client(
                timeout=timeout_config,
                limits=cls.DEFAULT_POOL_LIMITS,
                headers=cls.DEFAULT_HEADERS,
                follow_redirects=True
            )
        return cls._client

    @classmethod
    def _get_async_client(cls, timeout: Optional[float] = None) -> httpx.AsyncClient:
        """获取或创建异步 HTTP 客户端实例"""
        if cls._async_client is None or cls._async_client.is_closed:
            timeout_config = httpx.Timeout(timeout or cls.DEFAULT_TIMEOUT)
            cls._async_client = httpx.AsyncClient(
                timeout=timeout_config,
                limits=cls.DEFAULT_POOL_LIMITS,
                headers=cls.DEFAULT_HEADERS,
                follow_redirects=True
            )
        return cls._async_client

    @classmethod
    def close_clients(cls):
        """关闭所有客户端连接"""
        if cls._client and not cls._client.is_closed:
            cls._client.close()
            cls._client = None
        if cls._async_client and not cls._async_client.is_closed:
            cls._async_client.aclose()
            cls._async_client = None

    @contextmanager
    def _measure_time(self, url: str, method: str = "REQUEST"):
        """测量请求执行时间的上下文管理器"""
        start_time = time.time()
        logger.info(f"Starting {method} request to {url}")
        try:
            yield start_time
        finally:
            end_time = time.time()
            elapsed_time = end_time - start_time
            logger.info(f"Completed {method} request to {url}. Elapsed time: {elapsed_time:.4f} seconds")

    def _prepare_request_data(self, 
                            headers: Optional[Dict[str, str]] = None,
                            params: Optional[Dict[str, Any]] = None,
                            **kwargs) -> tuple:
        """准备请求数据"""
        # 合并请求头
        final_headers = self.DEFAULT_HEADERS.copy()
        if headers:
            final_headers.update(headers)
        
        # 处理参数
        request_kwargs = kwargs.copy()
        if params is not None:
            request_kwargs['json'] = params
        
        return final_headers, request_kwargs

    def _handle_response(self, response: httpx.Response, url: str) -> Dict[str, Any]:
        """处理响应数据"""
        try:
            # 检查状态码
            response.raise_for_status()
            
            # 尝试解析 JSON
            if response.headers.get('content-type', '').startswith('application/json'):
                json_data = response.json()
                logger.debug(f"Request to {url} successful. Response data keys: {list(json_data.keys()) if isinstance(json_data, dict) else 'non-dict response'}")
                return json_data
            else:
                # 非 JSON 响应
                logger.warning(f"Non-JSON response from {url}. Content-Type: {response.headers.get('content-type')}")
                return {"text": response.text, "status_code": response.status_code}
                
        except json.JSONDecodeError as json_err:
            logger.error(f"JSON parsing error for {url}: {json_err}. Response content: {response.text[:500]}...")
            raise RuntimeError(f"Invalid JSON response from {url}: {json_err}")

    def _execute_with_retry(self, 
                          request_func,
                          url: str,
                          max_retries: int = DEFAULT_MAX_RETRIES,
                          retry_delay: float = DEFAULT_RETRY_DELAY,
                          **kwargs) -> Dict[str, Any]:
        """带重试机制的请求执行"""
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                response = request_func(url, **kwargs)
                return self._handle_response(response, url)
                
            except httpx.HTTPStatusError as http_err:
                last_exception = http_err
                if http_err.response.status_code < 500 or attempt == max_retries:
                    # 客户端错误或最后一次重试，不再重试
                    logger.error(f"HTTP status error (attempt {attempt + 1}): {http_err}. Status: {http_err.response.status_code}")
                    raise RuntimeError(f"HTTP {http_err.response.status_code}: {http_err.response.text}")
                else:
                    logger.warning(f"HTTP status error (attempt {attempt + 1}), retrying: {http_err}")
                    
            except httpx.RequestError as req_err:
                last_exception = req_err
                if attempt == max_retries:
                    logger.error(f"Request error after {max_retries + 1} attempts: {req_err}")
                    raise RuntimeError(f"Request failed: {req_err}")
                else:
                    logger.warning(f"Request error (attempt {attempt + 1}), retrying: {req_err}")
            
            # 等待后重试
            if attempt < max_retries:
                sleep_time = retry_delay * (2 ** attempt)  # 指数退避
                logger.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
        
        # 如果所有重试都失败了
        raise RuntimeError(f"Request failed after {max_retries + 1} attempts: {last_exception}")

    def post(self, 
            url: str,
            headers: Optional[Dict[str, str]] = None,
            params: Optional[Dict[str, Any]] = None,
            timeout: Optional[float] = None,
            max_retries: int = DEFAULT_MAX_RETRIES,
            retry_delay: float = DEFAULT_RETRY_DELAY,
            **kwargs) -> Dict[str, Any]:
        """
        发送 POST 请求
        
        Args:
            url: 请求 URL
            headers: 请求头
            params: 请求参数（将作为 JSON 发送）
            timeout: 超时时间
            max_retries: 最大重试次数
            retry_delay: 重试延迟
            **kwargs: 其他请求参数
            
        Returns:
            Dict[str, Any]: 响应数据
        """
        with self._measure_time(url, "POST"):
            client = self._get_client(timeout)
            final_headers, request_kwargs = self._prepare_request_data(headers, params, **kwargs)
            
            logger.debug(f"POST request to {url} with headers: {final_headers} and data: {params}")
            
            return self._execute_with_retry(
                client.post,
                url,
                headers=final_headers,
                max_retries=max_retries,
                retry_delay=retry_delay,
                **request_kwargs
            )

    def get(self,
           url: str,
           headers: Optional[Dict[str, str]] = None,
           params: Optional[Dict[str, Any]] = None,
           timeout: Optional[float] = None,
           max_retries: int = DEFAULT_MAX_RETRIES,
           retry_delay: float = DEFAULT_RETRY_DELAY,
           **kwargs) -> Dict[str, Any]:
        """
        发送 GET 请求
        
        Args:
            url: 请求 URL
            headers: 请求头
            params: 查询参数
            timeout: 超时时间
            max_retries: 最大重试次数
            retry_delay: 重试延迟
            **kwargs: 其他请求参数
            
        Returns:
            Dict[str, Any]: 响应数据
        """
        with self._measure_time(url, "GET"):
            client = self._get_client(timeout)
            final_headers, request_kwargs = self._prepare_request_data(headers, **kwargs)
            
            # GET 请求的参数作为查询参数
            if params:
                request_kwargs['params'] = params
            
            logger.debug(f"GET request to {url} with headers: {final_headers} and params: {params}")
            
            return self._execute_with_retry(
                client.get,
                url,
                headers=final_headers,
                max_retries=max_retries,
                retry_delay=retry_delay,
                **request_kwargs
            )

    def put(self,
           url: str,
           headers: Optional[Dict[str, str]] = None,
           params: Optional[Dict[str, Any]] = None,
           timeout: Optional[float] = None,
           max_retries: int = DEFAULT_MAX_RETRIES,
           retry_delay: float = DEFAULT_RETRY_DELAY,
           **kwargs) -> Dict[str, Any]:
        """发送 PUT 请求"""
        with self._measure_time(url, "PUT"):
            client = self._get_client(timeout)
            final_headers, request_kwargs = self._prepare_request_data(headers, params, **kwargs)
            
            return self._execute_with_retry(
                client.put,
                url,
                headers=final_headers,
                max_retries=max_retries,
                retry_delay=retry_delay,
                **request_kwargs
            )

    def delete(self,
              url: str,
              headers: Optional[Dict[str, str]] = None,
              timeout: Optional[float] = None,
              max_retries: int = DEFAULT_MAX_RETRIES,
              retry_delay: float = DEFAULT_RETRY_DELAY,
              **kwargs) -> Dict[str, Any]:
        """发送 DELETE 请求"""
        with self._measure_time(url, "DELETE"):
            client = self._get_client(timeout)
            final_headers, request_kwargs = self._prepare_request_data(headers, **kwargs)
            
            return self._execute_with_retry(
                client.delete,
                url,
                headers=final_headers,
                max_retries=max_retries,
                retry_delay=retry_delay,
                **request_kwargs
            )

    # 异步方法
    async def async_post(self,
                        url: str,
                        headers: Optional[Dict[str, str]] = None,
                        params: Optional[Dict[str, Any]] = None,
                        timeout: Optional[float] = None,
                        **kwargs) -> Dict[str, Any]:
        """异步 POST 请求"""
        start_time = time.time()
        logger.info(f"Starting async POST request to {url}")
        
        try:
            client = self._get_async_client(timeout)
            final_headers, request_kwargs = self._prepare_request_data(headers, params, **kwargs)
            
            response = await client.post(url, headers=final_headers, **request_kwargs)
            result = self._handle_response(response, url)
            
            elapsed_time = time.time() - start_time
            logger.info(f"Completed async POST request to {url}. Elapsed time: {elapsed_time:.4f} seconds")
            
            return result
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Async POST request failed for {url}. Elapsed time: {elapsed_time:.4f} seconds. Error: {e}")
            raise RuntimeError(f"Async request failed: {e}")

    # 静态方法保持向后兼容
    @staticmethod
    def post(url: str, headers: Optional[Dict[str, str]] = None, params: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """静态方法，保持向后兼容"""
        instance = HttpUtil()
        return instance.post(url, headers, params, **kwargs)


# 创建全局实例
http_util = HttpUtil()

# 便捷函数
def post_request(url: str, **kwargs) -> Dict[str, Any]:
    """便捷的 POST 请求函数"""
    return http_util.post(url, **kwargs)

def get_request(url: str, **kwargs) -> Dict[str, Any]:
    """便捷的 GET 请求函数"""
    return http_util.get(url, **kwargs)

def put_request(url: str, **kwargs) -> Dict[str, Any]:
    """便捷的 PUT 请求函数"""
    return http_util.put(url, **kwargs)

def delete_request(url: str, **kwargs) -> Dict[str, Any]:
    """便捷的 DELETE 请求函数"""
    return http_util.delete(url, **kwargs)
