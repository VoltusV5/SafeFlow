from __future__ import annotations


def parse_wg_dump(raw: str) -> list[dict[str, int | str]]:
    """Разбор вывода `wg show <iface> dump` (табуляция)."""
    peers: list[dict[str, int | str]] = []
    for i, line in enumerate(raw.strip().splitlines()):
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        # Первая строка — интерфейс (у Amnezia AWG больше 4 полей); peer-строки идут далее.  # noqa: E501
        if i == 0:
            continue
        if len(parts) < 8:
            continue
        try:
            hs = int(parts[4]) if parts[4] else 0
            rx = int(parts[5])
            tx = int(parts[6])
        except ValueError:
            continue
        peers.append(
            {
                "public_key": parts[0],
                "handshake": hs,
                "rx": rx,
                "tx": tx,
            }
        )
    return peers


def read_proc_net_dev(iface: str) -> tuple[int, int] | None:
    """Сумма rx+tx байт по интерфейсу из /proc/net/dev."""
    try:
        with open("/proc/net/dev", encoding="utf-8") as f:
            for raw in f:
                if f"{iface}:" in raw:
                    parts = raw.split(":")
                    nums = parts[1].split()
                    rx = int(nums[0])
                    tx = int(nums[8])
                    return rx, tx
    except (OSError, ValueError, IndexError):
        pass
    return None
