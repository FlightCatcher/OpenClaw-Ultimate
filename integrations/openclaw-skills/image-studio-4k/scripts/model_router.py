"""Deterministic image-model routing for the local 8 GB GPU stack."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass

ANIME_TERMS = {
    "anime",
    "manga",
    "2d",
    "cel shading",
    "official animation",
    "animation still",
    "二次元",
    "动漫",
    "动画",
    "漫画",
    "赛璐璐",
    "立绘",
    "角色设定",
    "原作画风",
    "卡通",
    "q版",
    "chibi",
    "vocaloid",
    "vsinger",
    "有兽焉",
}
PHOTO_TERMS = {
    "photo",
    "photograph",
    "photorealistic",
    "realistic photo",
    "raw photo",
    "portrait photo",
    "editorial photography",
    "camera",
    "lens",
    "macro shot",
    "真人",
    "照片",
    "摄影",
    "写实照片",
    "真实人像",
    "实拍",
    "镜头",
}
PRODUCT_TERMS = {
    "product photography",
    "packshot",
    "commercial product",
    "studio product",
    "产品图",
    "商品图",
    "电商",
    "棚拍",
}
ILLUSTRATION_TERMS = {
    "illustration",
    "concept art",
    "digital painting",
    "watercolor",
    "oil painting",
    "插画",
    "概念设计",
    "数字绘画",
    "水彩",
    "油画",
}
TEXT_TERMS = {
    "poster",
    "logo",
    "wordmark",
    "typography",
    "title card",
    "signage",
    "ui mockup",
    "海报",
    "标志",
    "文字",
    "标题",
    "排版",
    "招牌",
    "界面",
}


@dataclass(frozen=True)
class Route:
    style: str
    family: str
    engine: str
    identity_mode: str
    reason: str


def _contains(text: str, terms: set[str]) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in terms)


def route_request(
    prompt: str,
    *,
    requested_style: str = "auto",
    identity_context: str = "",
    has_reference: bool = False,
    text_mode: str = "auto",
) -> Route:
    combined = f"{prompt} {identity_context}".strip()
    text_detection_input = re.sub(
        r"\b(no|without|avoid)\s+(visible\s+)?(text|letters|numbers|signage)\b"
        r"|(?:无|不要|禁止|没有)(?:任何)?(?:文字|标题|字母|数字|招牌)",
        "",
        combined,
        flags=re.IGNORECASE,
    )
    explicit_text = text_mode == "clear" or (
        text_mode != "none" and _contains(text_detection_input, TEXT_TERMS)
    )

    if requested_style != "auto":
        style = requested_style
        reason = f"user-selected style={requested_style}"
    elif _contains(combined, ANIME_TERMS):
        style = "anime"
        reason = "anime/2D character cues"
    elif _contains(combined, PRODUCT_TERMS):
        style = "product"
        reason = "product-photography cues"
    elif _contains(combined, PHOTO_TERMS):
        style = "photo"
        reason = "photographic cues"
    elif _contains(combined, ILLUSTRATION_TERMS):
        style = "illustration"
        reason = "illustration cues"
    elif has_reference:
        style = "illustration"
        reason = "reference-led identity edit without photographic cues"
    else:
        style = "natural"
        reason = "general scene defaults to natural rendering"

    if explicit_text:
        return Route(
            style=style,
            family="flux2-text",
            engine="flux2",
            identity_mode="general",
            reason=f"{reason}; exact text/layout needs FLUX.2",
        )
    if style == "anime":
        return Route(
            style="anime",
            family="sdxl-anime",
            engine="animagine",
            identity_mode="general",
            reason=f"{reason}; use anime-specialized Animagine XL Opt",
        )
    if style in {"photo", "natural", "cinematic", "product"}:
        return Route(
            style=style,
            family="sdxl-photo",
            engine="animagine",
            identity_mode="face" if has_reference and style != "product" else "general",
            reason=f"{reason}; use photoreal RealVisXL",
        )
    return Route(
        style=style,
        family="flux2-reference" if has_reference else "sdxl-illustration",
        engine="flux2" if has_reference else "animagine",
        identity_mode="general",
        reason=f"{reason}; use {'FLUX.2 reference editing' if has_reference else 'SDXL illustration'}",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--style", default="auto")
    parser.add_argument("--identity-context", default="")
    parser.add_argument("--reference", action="store_true")
    parser.add_argument("--text-mode", choices=("auto", "clear", "none"), default="auto")
    args = parser.parse_args()
    route = route_request(
        args.prompt,
        requested_style=args.style,
        identity_context=args.identity_context,
        has_reference=args.reference,
        text_mode=args.text_mode,
    )
    print(json.dumps(asdict(route), ensure_ascii=False))


if __name__ == "__main__":
    main()
