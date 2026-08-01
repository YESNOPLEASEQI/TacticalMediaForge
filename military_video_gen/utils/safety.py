"""Deterministic safety checks for military-video generation boundaries.

The project supports history, news, museum, legal, and high-level educational
content. The gate rejects explicit requests for actionable harm both before and
after model calls. It complements, but does not replace, provider moderation.
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


class UnsafeContentError(ValueError):
    """Raised when generation input asks for actionable real-world harm."""


_BLOCKED_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:write|create|draft|design|develop|prepare|produce|outline|give|show|provide)?\s*(?:an?\s+)?(?:step[- ]by[- ]step\s+)?(?:attack|strike|raid|assault|bombing)\s+(?:plan|strategy|operation|mission)\b",
        r"\b(?:which|what|select|identify|rank|choose|recommend).{0,50}(?:real[- ]world|real|named)?\s*(?:military\s+)?target.{0,30}(?:hit|attack|strike|bomb|first|vulnerable)\b",
        r"\b(?:select|identify|rank|choose|recommend).{0,30}(?:vulnerable|priority|real[- ]world).{0,30}target\b",
        r"\b(?:target|airport|base|facility).{0,30}(?:should|to)\s+be\s+(?:hit|attacked|struck|bombed)\s+first\b",
        r"\b(?:how(?:\s+can\s+\w+)?\s+to|how\s+can|steps?|instructions?|guide|show|explain).{0,40}(?:build|make|construct|assemble|synthesi[sz]e|manufacture|produce).{0,30}(?:explosive|charge|bomb|firearm|gun|weapon|detonator)\b",
        r"\b(?:modify|convert|alter|upgrade).{0,20}(?:rifle|firearm|gun|weapon).{0,30}(?:increase|maximi[sz]e|improve).{0,15}(?:lethality|damage|killing)\b",
        r"\b(?:how(?:\s+can\s+\w+)?|steps?|instructions?|guide|show).{0,35}(?:bypass|evade|defeat|avoid|circumvent).{0,25}(?:radar|surveillance|law[- ]enforcement|police|detection|tracking)\b",
        r"\b(?:provide|give|list|specify|describe).{0,45}(?:materials?|quantit(?:y|ies)|procedure|assembly|instructions?).{0,45}(?:assemble|build|make|construct|explosive|bomb|detonator).{0,25}(?:explosive|device|bomb|detonator)?\b",
        r"\b(?:precise|exact|target)?\s*(?:coordinates?|location).{0,45}(?:timing|time|bombing|strike|attack|base|airfield|airport)\b|\b(?:bombing|strike|attack).{0,45}(?:coordinates?|timing|least defended|vulnerable|base|airfield|airport)\b",
        r"\b(?:describe|provide|give|explain).{0,30}(?:method|way|procedure).{0,35}(?:avoid|evade|bypass|defeat).{0,25}(?:police|law[- ]enforcement|tracking|surveillance|detection)\b",
        r"\b(?:draft|write|provide|give).{0,30}(?:target\s+)?coordinates?.{0,35}(?:strike|attack|bombing).{0,35}(?:real[- ]world|named|base|airfield|airport)?\b",
        r"(?:制定|设计|规划|撰写|提供).{0,12}(?:真实|现实|具体|命名)?.{0,10}(?:攻击|打击|突袭|轰炸).{0,6}(?:计划|方案|步骤|行动)",
        r"(?:选择|识别|筛选|推荐|排序).{0,12}(?:最脆弱|薄弱|优先)?.{0,10}(?:现实|真实|具体)?.{0,8}(?:目标|机场|基地|设施).{0,8}(?:攻击|打击|轰炸|优先)",
        r"(?:选择|识别|筛选|推荐|排序).{0,24}(?:现实|真实|具体|脆弱|薄弱).{0,12}(?:目标|机场|基地|设施)",
        r"(?:如何|步骤|说明|教程|教我).{0,12}(?:制造|制作|合成|组装|改造).{0,10}(?:爆炸装置|炸弹|炸药|枪械|武器|雷管)",
        r"(?:改装|修改|升级).{0,8}(?:枪械|步枪|武器).{0,12}(?:杀伤|致命|威力)",
        r"(?:如何|步骤|教程|教我).{0,12}(?:逃避|规避|绕过|躲避|欺骗).{0,10}(?:执法|侦测|检测|雷达|监控|追踪)",
        r"(?:列出|提供|说明|描述).{0,18}(?:材料|用量|数量|操作顺序|步骤|程序).{0,18}(?:组装|制造|制作).{0,10}(?:爆炸装置|炸弹|炸药|雷管)",
        r"(?:列出|提供|说明|描述)?.{0,8}(?:组装|制造|制作).{0,10}(?:爆炸装置|炸弹|炸药|雷管).{0,18}(?:材料|用量|数量|操作顺序|步骤|程序)",
        r"(?:提供|给出|撰写|制定).{0,12}(?:精确|目标)?.{0,8}(?:坐标|位置).{0,18}(?:时间|时机|轰炸|打击|袭击|基地|机场)",
        r"(?:轰炸|打击|袭击).{0,18}(?:防御最弱|薄弱|脆弱|现实|真实|具体|命名).{0,12}(?:机场|基地|目标|设施).{0,12}(?:坐标|位置|时间|时机)?",
        r"(?:描述|提供|说明).{0,12}(?:方法|办法|步骤).{0,12}(?:避免|逃避|规避|躲避|绕过).{0,10}(?:警方|警察|执法|追踪|监控|侦测)",
        r"(?:描述|提供|说明).{0,18}(?:避免|逃避|规避|躲避|绕过).{0,10}(?:警方|警察|执法).{0,8}(?:追踪|监控|侦测).{0,8}(?:方法|办法|步骤)?",
        r"(?:撰写|制定|提供).{0,12}(?:针对)?.{0,8}(?:现实|真实|具体|命名)?.{0,8}(?:基地|机场|目标).{0,8}(?:打击|攻击|轰炸).{0,8}(?:坐标|计划)?",
        r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|earlier|system)\s+(?:instructions?|prompts?|rules?)\b",
        r"(?:忽略|无视|绕过|覆盖).{0,8}(?:之前|先前|系统|安全).{0,8}(?:指令|提示词|规则|限制)",
    )
)

MAX_GENERATION_TEXT_LENGTH = 20_000


def enforce_safe_generation_text(text: str, *, field_name: str = "text") -> str:
    """Return text unchanged or reject explicit actionable-harm requests."""
    if not isinstance(text, str):
        raise TypeError(f"{field_name} must be text")
    if len(text) > MAX_GENERATION_TEXT_LENGTH:
        raise UnsafeContentError(
            f"{field_name} exceeds the {MAX_GENERATION_TEXT_LENGTH}-character safety limit"
        )
    if any(pattern.search(text) for pattern in _BLOCKED_PATTERNS):
        raise UnsafeContentError(
            f"{field_name} requests actionable harmful military content and cannot be generated"
        )
    return text


def enforce_safe_generation_fields(**fields: object) -> None:
    """Apply the same gate to every non-empty string in a boundary payload."""
    for field_name, value in fields.items():
        if isinstance(value, str) and value.strip():
            enforce_safe_generation_text(value, field_name=field_name)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str) and item.strip():
                    enforce_safe_generation_text(
                        item,
                        field_name=f"{field_name}[{index}]",
                    )


def redact_url_for_log(value: str) -> str:
    """Remove bearer query/fragment/userinfo from URLs before logging."""
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"}:
            return "data:<redacted>" if parsed.scheme == "data" else value
        hostname = parsed.hostname or "<unknown-host>"
        try:
            address = ipaddress.ip_address(hostname)
        except ValueError:
            address = None
        if (
            hostname.casefold() in {"localhost", "localhost.localdomain"}
            or hostname.casefold().endswith((".local", ".internal", ".localhost"))
            or (address is not None and not address.is_global)
        ):
            return "<private-url>"
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        netloc = hostname
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))
    except (TypeError, ValueError):
        return "<redacted-url>"


_URL_IN_ERROR = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)
_WINDOWS_PATH_IN_ERROR = re.compile(
    r"(?i)(?<![\w])(?:[a-z]:[\\/](?:[^\\/\s:'\"<>|]+[\\/])*[^\\/\s:'\"<>|]*)"
)
_UNC_PATH_IN_ERROR = re.compile(r"\\\\[^\\\s]+\\[^\s'\"<>|]+")
_POSIX_PRIVATE_PATH_IN_ERROR = re.compile(
    r"(?<![:/])/(?:home|Users|private|tmp|var/tmp)/[^\s'\"<>]+"
)


def redact_path_for_log(value: object) -> str:
    """Return only a filename so logs do not expose a private directory tree."""
    if value is None:
        return "<no-path>"
    try:
        name = Path(str(value)).name
    except (TypeError, ValueError):
        return "<private-path>"
    return f"<path>/{name}" if name else "<private-path>"


def sanitize_error_message(value: object) -> str:
    """Redact signed URL credentials from exceptions, task state, and logs."""
    message = str(value)
    message = _URL_IN_ERROR.sub(
        lambda match: redact_url_for_log(match.group(0)),
        message,
    )
    message = _WINDOWS_PATH_IN_ERROR.sub("<private-path>", message)
    message = _UNC_PATH_IN_ERROR.sub("<private-path>", message)
    return _POSIX_PRIVATE_PATH_IN_ERROR.sub("<private-path>", message)
