"""
astrbot_plugin_multi_search
============================

为 AstrBot 接入多源联网搜索。

- 在插件配置面板填写搜索源（名称 + 地址 + Key + 额外参数）。
- 填了名称的源会自动出现在「网页搜索提供商」下拉框中。
- 在原生下拉框选哪个源，就用哪个源搜索。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

logger = logging.getLogger(__name__)

# 各协议的默认端点
DEFAULT_URLS = {
    "tavily": "https://api.tavily.com/search",
    "bocha": "https://api.bochaai.com/v1/web-search",
    "brave": "https://api.search.brave.com/res/v1/web/search",
    "zhipu": "https://open.bigmodel.cn/api/paas/v4/web_search",
}


def _detect_proto(name: str, url: str) -> str:
    """根据源名和地址自动识别协议格式。"""
    text = f"{name} {url}".lower()
    if "tavily" in text:
        return "tavily"
    if "bocha" in text or "bita" in text:
        return "bocha"
    if "brave" in text:
        return "brave"
    if "bigmodel" in text or "zhipu" in text or "智谱" in text:
        return "zhipu"
    # 本地地址或其他情况默认按 SearXNG 处理
    return "searxng"

# 网页搜索 provider 下拉框在配置元数据中的路径
_WS_PROVIDER_PATH = (
    "ai_group",
    "metadata",
    "websearch",
    "items",
    "provider_settings.websearch_provider",
)


def _nested_get(node: dict, keys: tuple[str, ...]):
    cur = node
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


# ---------------------------------------------------------------------------
# 各协议 adapter —— 输入 url/key/extra/query，返回 [{title, url, content}]
# ---------------------------------------------------------------------------

async def _do_search(
    proto: str,
    base_url: str,
    api_key: str,
    extra: dict,
    query: str,
    count: int,
) -> list[dict]:
    if proto == "searxng":
        return await _search_searxng(base_url, query, count)
    if proto == "tavily":
        return await _search_tavily(base_url, api_key, query, count)
    if proto == "bocha":
        return await _search_bocha(base_url, api_key, query, count)
    if proto == "brave":
        return await _search_brave(base_url, api_key, query, count)
    if proto == "zhipu":
        engine = extra.get("search_engine", "search_pro")
        return await _search_zhipu(base_url, api_key, engine, query, count)
    raise ValueError(f"未知协议格式：{proto}")


async def _search_searxng(base_url: str, query: str, count: int) -> list[dict]:
    base_url = (base_url or "http://127.0.0.1:8088").rstrip("/")
    params = {"q": query, "format": "json"}
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.get(f"{base_url}/search", params=params, timeout=timeout) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
            data = await resp.json()
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
        for r in data.get("results", [])[:count]
    ]


async def _search_tavily(url: str, api_key: str, query: str, count: int) -> list[dict]:
    payload = {"api_key": api_key, "query": query, "max_results": count}
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.post(url, json=payload, timeout=timeout) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
            data = await resp.json()
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
        for r in data.get("results", [])[:count]
    ]


async def _search_bocha(url: str, api_key: str, query: str, count: int) -> list[dict]:
    payload = {"query": query, "count": count}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
            data = await resp.json()
    pages = data.get("data", {}).get("webPages", {}).get("value", [])[:count]
    return [
        {"title": r.get("name", ""), "url": r.get("url", ""), "content": r.get("snippet", "")}
        for r in pages
    ]


async def _search_brave(url: str, api_key: str, query: str, count: int) -> list[dict]:
    headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
    params = {"q": query, "count": count}
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.get(url, params=params, headers=headers, timeout=timeout) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
            data = await resp.json()
    return [
        {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("description", "")}
        for r in data.get("web", {}).get("results", [])[:count]
    ]


async def _search_zhipu(url: str, api_key: str, engine: str, query: str, count: int) -> list[dict]:
    payload = {
        "search_query": query[:70],
        "search_engine": engine,
        "search_intent": False,
        "count": count,
        "request_id": str(uuid.uuid4()),
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
            data = await resp.json()
    return [
        {"title": r.get("title", ""), "url": r.get("link", ""), "content": r.get("content", "")}
        for r in data.get("search_result", [])[:count]
    ]


def _format_results(results: list[dict]) -> str:
    if not results:
        return "搜索未返回任何结果。"
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"{i}. 标题：{r['title']}\n   链接：{r['url']}\n   摘要：{r['content']}"
        )
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# 插件主类
# ---------------------------------------------------------------------------


class Main(Star):
    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.context = context
        self.config = config or {}
        self._try_inject_schema()

    # ---- 动态收集已配置的搜索源 ----

    def _collect_sources(self) -> dict[str, dict]:
        """从插件配置中收集所有已填名称的源，返回 {name: {proto, url, key, extra}}。"""
        sources: dict[str, dict] = {}

        raw_list = self.config.get("search_sources") or []
        if isinstance(raw_list, list):
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "").strip()
                if not name:
                    continue
                url = str(item.get("url") or "").strip()
                key = str(item.get("key") or "").strip()
                extra_raw = str(item.get("extra") or "{}").strip()
                try:
                    extra = json.loads(extra_raw) if extra_raw else {}
                except (json.JSONDecodeError, TypeError):
                    extra = {}
                # 自动识别协议
                proto = _detect_proto(name, url)
                # 地址留空则用协议默认地址
                if not url:
                    url = DEFAULT_URLS.get(proto, "")
                sources[name] = {"proto": proto, "url": url, "key": key, "extra": extra}

        return sources

    def _inject_into_schema(self, schema: dict) -> bool:
        if not isinstance(schema, dict):
            return False
        provider_item = _nested_get(schema, _WS_PROVIDER_PATH)
        if not isinstance(provider_item, dict):
            return False
        options = provider_item.setdefault("options", [])
        if isinstance(options, list):
            for name in self._collect_sources():
                if name not in options:
                    options.append(name)
        return True

    def _try_inject_schema(self) -> None:
        sources = []
        try:
            from astrbot.core.config.default import CONFIG_METADATA_3
            sources.append(CONFIG_METADATA_3)
        except Exception as exc:
            logger.debug("无法导入 CONFIG_METADATA_3：%s", exc)
        try:
            cfg = self.context.get_config()
            schema_attr = getattr(cfg, "schema", None)
            if isinstance(schema_attr, dict):
                sources.append(schema_attr)
        except Exception as exc:
            logger.debug("无法访问 config.schema：%s", exc)
        for schema in sources:
            try:
                self._inject_into_schema(schema)
            except Exception as exc:
                logger.warning("注入搜索源选项失败（不影响功能）：%s", exc)
        names = list(self._collect_sources().keys())
        logger.info("多源搜索已加载 %d 个源：%s", len(names), ", ".join(names) or "（无，请在插件配置面板添加）")

    def _get_current_provider(self, event: AstrMessageEvent) -> str:
        try:
            cfg = self.context.get_config(umo=event.unified_msg_origin)
        except Exception:
            cfg = None
        if not isinstance(cfg, dict):
            try:
                cfg = self.context.get_config()
            except Exception:
                cfg = {}
        ps = cfg.get("provider_settings", {}) if isinstance(cfg, dict) else {}
        return str(ps.get("websearch_provider", "")).strip()

    @filter.llm_tool(name="web_search")
    async def web_search(
        self, event: AstrMessageEvent, query: str, count: int = 10
    ):
        """进行联网搜索，返回实时网页的标题、链接与摘要。当需要最新信息、新闻、事实查询时使用。

        Args:
            query(string): 搜索关键词。
            count(number): 返回结果条数，默认 10。
        """
        try:
            count = max(1, min(int(count), 20))
        except (TypeError, ValueError):
            count = 10

        provider = self._get_current_provider(event)
        sources = self._collect_sources()

        if provider not in sources:
            available = " / ".join(sources.keys()) or "（未配置任何搜索源）"
            return (
                f"当前网页搜索提供商是 {provider!r}，不是本插件配置的源。"
                f"请在「网页搜索」下拉框中选择：{available}。"
            )

        src = sources[provider]
        try:
            results = await _do_search(
                proto=src["proto"],
                base_url=src["url"],
                api_key=src["key"],
                extra=src["extra"],
                query=query,
                count=count,
            )
        except asyncio.TimeoutError:
            return f"搜索超时（{provider}），请稍后重试。"
        except Exception as exc:
            return f"搜索出错（{provider}）：{exc}"

        return _format_results(results)
