"""Подсчёт записей journalctl за интервал (ошибки уровня err)."""

from __future__ import annotations

import logging
import subprocess
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def count_journal_errors_by_unit(
    since_utc: datetime,
    until_utc: datetime,
    units: list[str],
) -> tuple[int, list[str]]:
    """
    Для каждого systemd-юнита: journalctl -p err.
    Возвращает (сумма строк, строки вида "unit: n").
    """
    if not units:
        return 0, ["юниты не заданы"]
    su = f"@{int(since_utc.astimezone(UTC).timestamp())}"
    uu = f"@{int(until_utc.astimezone(UTC).timestamp())}"
    total = 0
    lines: list[str] = []
    for unit in units:
        try:
            p = subprocess.run(
                [
                    "journalctl",
                    "-u",
                    unit,
                    "--since",
                    su,
                    "--until",
                    uu,
                    "-p",
                    "err",
                    "--no-pager",
                    "-q",
                ],
                capture_output=True,
                text=True,
                timeout=90,
            )
            n = sum(1 for line in p.stdout.splitlines() if line.strip())
            total += n
            lines.append(f"{unit}: {n}")
        except FileNotFoundError:
            lines.append(f"{unit}: journalctl не найден")
        except subprocess.TimeoutExpired:
            lines.append(f"{unit}: таймаут")
        except Exception as e:
            logger.debug("journalctl %s: %s", unit, e)
            lines.append(f"{unit}: ошибка ({e!s:.80})")
    return total, lines
