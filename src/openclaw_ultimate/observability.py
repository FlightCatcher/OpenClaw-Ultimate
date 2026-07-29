from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """配置统一的标准日志入口；无效级别会明确报错。"""

    normalized = level.strip().upper()
    numeric_level = getattr(logging, normalized, None)
    if not isinstance(numeric_level, int):
        raise TypeError(f"Unknown log level: {level}")

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )


__all__ = ["configure_logging"]
