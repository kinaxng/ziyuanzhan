#!/usr/bin/env python3
"""
将 monitor.py 生成的 docs/data/latest.json 转换为 DecoTV 配置格式。

输出格式示例:
{
  "cache_time": 7200,
  "api_site": {
    "ziyuan_9": {
      "api": "https://jipinvip1.com/api.php/provide/vod/",
      "name": "新极品资源站",
      "detail": "https://jipinvip1.com"
    }
  },
  "custom_category": []
}
"""

import argparse
import json
import re
import sys
from urllib.parse import urlparse

DEFAULT_INPUT = "docs/data/latest.json"
DEFAULT_OUTPUT = "docs/data/decotv.json"
CACHE_TIME = 7200


def error(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)


def is_valid_api(url: str) -> bool:
    """API 必须以 http:// 或 https:// 开头。"""
    if not isinstance(url, str):
        return False
    return url.startswith("http://") or url.startswith("https://")


def is_online(resource: dict) -> bool:
    """默认保留在线站点；health 不存在时保留。"""
    health = resource.get("health")
    if not isinstance(health, dict):
        return True
    return bool(health.get("is_alive", False))


def extract_detail(resource: dict) -> str:
    """按优先级获取站点首页 URL。"""
    for key in ("link", "url", "source_url", "detail"):
        value = resource.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def domain_to_key(netloc: str) -> str:
    """将域名转换为 DecoTV key 的合法后缀。"""
    # 移除可选的端口
    netloc = netloc.split(":")[0]
    # 移除 www. 前缀
    if netloc.lower().startswith("www."):
        netloc = netloc[4:]
    # 只允许小写字母、数字、下划线
    key = re.sub(r"[^a-z0-9_]+", "_", netloc.lower()).strip("_")
    return key or "unknown"


def generate_key_from_api(api_url: str) -> str:
    """从 API URL 的域名生成 key。"""
    try:
        parsed = urlparse(api_url)
        netloc = parsed.netloc
        if not netloc:
            # urlparse 对某些字符串可能解析失败，做兜底处理
            netloc = api_url.split("/")[2]
    except Exception:
        netloc = "unknown"
    return f"ziyuan_{domain_to_key(netloc)}"


def make_unique_key(base_key: str, existing: set) -> str:
    """确保 key 唯一；重复时追加序号。"""
    if base_key not in existing:
        return base_key
    counter = 1
    while True:
        candidate = f"{base_key}_{counter}"
        if candidate not in existing:
            return candidate
        counter += 1


def build_decotv_site(resource: dict, existing_keys: set) -> tuple[str, dict] | None:
    """将单个资源站转换为 DecoTV 的 api_site 条目。"""
    if not isinstance(resource, dict):
        return None

    api = resource.get("api", "")
    if not is_valid_api(api):
        return None

    # key 生成
    raw_id = resource.get("id")
    if raw_id is not None:
        base_key = f"ziyuan_{raw_id}"
    else:
        base_key = generate_key_from_api(api)

    key = make_unique_key(base_key, existing_keys)

    name = resource.get("name", "")
    if not isinstance(name, str) or not name.strip():
        name = key
    else:
        name = name.strip()

    detail = extract_detail(resource)

    return key, {
        "api": api,
        "name": name,
        "detail": detail,
    }


def convert(input_path: str, output_path: str, include_offline: bool) -> dict:
    """读取 latest.json 并转换为 DecoTV 格式。"""
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        error(f"输入文件不存在: {input_path}")
        raise
    except json.JSONDecodeError as e:
        error(f"输入文件 JSON 解析失败: {e}")
        raise
    except Exception as e:
        error(f"读取输入文件失败: {e}")
        raise

    if not isinstance(data, dict):
        raise ValueError("latest.json 根对象必须是字典")

    resources = data.get("resources", [])
    if not isinstance(resources, list):
        raise ValueError("latest.json 中的 resources 必须是数组")

    api_site: dict[str, dict] = {}

    for resource in resources:
        if not isinstance(resource, dict):
            continue

        if not include_offline and not is_online(resource):
            continue

        result = build_decotv_site(resource, set(api_site.keys()))
        if result is None:
            continue

        key, site = result
        api_site[key] = site

    return {
        "cache_time": CACHE_TIME,
        "api_site": api_site,
        "custom_category": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="将 latest.json 转换为 DecoTV 配置格式"
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"输入文件路径 (默认: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"输出文件路径 (默认: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--include-offline",
        action="store_true",
        help="保留离线站点（默认只保留在线站点）",
    )

    args = parser.parse_args()

    try:
        output = convert(args.input, args.output, args.include_offline)
    except Exception:
        return 1

    try:
        import os
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except Exception as e:
        error(f"写入输出文件失败: {e}")
        return 1

    print(f"[INFO] DecoTV 配置已生成: {args.output}")
    print(f"[INFO] 共 {len(output['api_site'])} 个站点")
    return 0


if __name__ == "__main__":
    sys.exit(main())
