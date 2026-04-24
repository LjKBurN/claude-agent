"""异步网页爬虫。"""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from backend.core.rag.types import ExtractedDocument

logger = logging.getLogger(__name__)


class WebCrawler:
    """异步 URL 爬虫，支持同域名子链接递归爬取。"""

    def __init__(self, max_depth: int = 0, max_pages: int = 10, timeout: int = 30):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.timeout = timeout

    async def crawl(self, url: str) -> list[ExtractedDocument]:
        """爬取 URL，返回页面列表。"""
        visited: set[str] = set()
        results: list[ExtractedDocument] = []
        base_domain = urlparse(url).netloc

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RAGBot/1.0)"},
        ) as client:
            await self._crawl_page(client, url, base_domain, 0, visited, results)

        return results[: self.max_pages]

    async def _crawl_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        base_domain: str,
        depth: int,
        visited: set[str],
        results: list[ExtractedDocument],
    ) -> None:
        if url in visited or len(results) >= self.max_pages:
            return

        visited.add(url)

        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Failed to crawl %s: %s", url, e)
            return

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            logger.debug("Skipping non-HTML: %s (%s)", url, content_type)
            return

        soup = BeautifulSoup(resp.text, "lxml")

        # 提取标题
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        # 提取正文
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        sections = []
        for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
            text = element.get_text(strip=True)
            if not text:
                continue
            if element.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(element.name[1])
                sections.append(f"{'#' * level} {text}")
            else:
                sections.append(text)

        page_text = "\n\n".join(sections)
        if page_text.strip():
            results.append(
                ExtractedDocument(
                    text=page_text,
                    title=title or url,
                    mime_type="text/html",
                    metadata={"source_type": "url", "url": url},
                )
            )

        # 递归爬取子链接
        if depth < self.max_depth:
            links = self._extract_links(soup, url, base_domain)
            for link in links:
                if len(results) >= self.max_pages:
                    break
                await self._crawl_page(client, link, base_domain, depth + 1, visited, results)

    @staticmethod
    def _extract_links(soup: BeautifulSoup, base_url: str, base_domain: str) -> list[str]:
        """提取同域名的子链接。"""
        links = []
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            # 跳过锚点、mailto、javascript
            if href.startswith(("#", "mailto:", "javascript:", "tel:")):
                continue
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            # 仅同域名、http(s) 协议
            if parsed.netloc == base_domain and parsed.scheme in ("http", "https"):
                # 去除锚点
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"
                links.append(clean_url)
        return list(dict.fromkeys(links))  # 去重保序
