# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import logging
from typing import Annotated

from langchain_core.tools import tool
from .decorators import log_io

from src.crawler import Crawler

logger = logging.getLogger(__name__)


@tool
@log_io
def crawl_tool(
    url: Annotated[str, "The url to crawl."],
) -> str:
    """Use this to crawl a url and get a readable content in markdown format."""
    try:
        crawler = Crawler()
        article = crawler.crawl(url)
        return {"url": url, "crawled_content": article.to_markdown()[:1000]}
    except BaseException as e:
        error_msg = f"Failed to crawl. Error: {repr(e)}"
        logger.error(error_msg)
        return error_msg

@tool
@log_io
def rag_tool(
    query: Annotated[str, "The query to send to the RAG system."],
) -> str:
    """Use this to retrieve information from the RAG (Retrieval-Augmented Generation) system.
    
    This tool sends your query to the deployed RAG server to retrieve relevant information
    from the knowledge base.
    """
    logger.info(f"正在使用RAG工具查询: {query}")
    try:
        # 从环境变量读取RAG服务器配置
        url = os.getenv("RAG_SERVER_URL")
        auth_token = os.getenv("RAG_SERVER_AUTH_TOKEN")
        model = os.getenv("RAG_SERVER_MODEL", "model")  # 默认值为"model"
        timeout = float(os.getenv("RAG_SERVER_TIMEOUT", "60.0"))  # 默认超时时间30秒
        
        # 检查必要的配置是否存在
        if not url or not auth_token:
            error_msg = "RAG服务器配置不完整。请检查.env文件中的RAG_SERVER_URL和RAG_SERVER_AUTH_TOKEN。"
            logger.error(error_msg)
            return error_msg
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}"
        }
        
        # 构建请求数据
        data = {
            "model": model,
            "messages": [{"role": "user", "content": query}],
            "stream": False
        }
        
        # 使用httpx发送POST请求
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json=data)
        
        # 检查响应状态
        if response.status_code == 200:
            response_data = response.json()
            # 提取回答内容
            assistant_message = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.info(f"RAG查询结果: {assistant_message}")
            return assistant_message
        else:
            error_msg = f"RAG服务请求失败。状态码: {response.status_code}, 响应: {response.text}"
            logger.error(error_msg)
            return error_msg
            
    except BaseException as e:
        error_msg = f"RAG查询失败。错误: {repr(e)}"
        logger.error(error_msg)
        return error_msg
