from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from vpn_bot.config import get_settings
from vpn_bot.exceptions import PeerGenerationError

logger = logging.getLogger(__name__)


def _script_env() -> dict[str, str]:
    s = get_settings()
    env = os.environ.copy()
    env["AWG_IFACE"] = s.awg_iface
    use_v2 = (s.awg2_docker_container or "").strip() and (
        s.wg2_endpoint or ""
    ).strip()  # noqa: E501
    if use_v2:
        env["AWG_DOCKER_CONTAINER"] = s.awg2_docker_container.strip()
        env["AWG_WG_IFACE"] = (s.awg2_wg_iface or "wg0").strip() or "wg0"
        env["AWG_WG_CONF"] = (
            s.awg2_wg_conf or "/opt/amnezia/awg/wg0.conf"
        ).strip()  # noqa: E501
        env["WG_ENDPOINT"] = s.wg2_endpoint.strip()
        env["WG_CLIENT_IP_PREFIX"] = (
            s.wg2_client_ip_prefix or "10.8.2"
        ).strip() or "10.8.2"  # noqa: E501
        env["WG_SERVER_PUBLIC_KEY"] = (s.wg2_server_public_key or "").strip()
    else:
        ctr = (s.awg_docker_container or "").strip()
        if ctr:
            env["AWG_DOCKER_CONTAINER"] = ctr
            env["AWG_WG_IFACE"] = (s.awg_wg_iface or "wg0").strip() or "wg0"
            env["AWG_WG_CONF"] = (
                s.awg_wg_conf or "/opt/amnezia/awg/wg0.conf"
            ).strip()  # noqa: E501
        env["WG_SERVER_PUBLIC_KEY"] = s.wg_server_public_key
        env["WG_ENDPOINT"] = s.wg_endpoint
        env["WG_CLIENT_IP_PREFIX"] = s.wg_client_ip_prefix.strip() or "10.8.0"
    env["WG_CLIENT_DNS"] = s.wg_client_dns
    return env


async def generate_amnezia_wg_peer(
    user_hint: str,
) -> tuple[str, str, str]:  # noqa: C901, E501
    s = get_settings()
    raw_path = (s.generate_peer_script or "").strip()
    if not raw_path:
        raise PeerGenerationError("GENERATE_PEER_SCRIPT не задан в .env")
    path = Path(raw_path).expanduser()
    if not path.is_file():
        raise PeerGenerationError(f"Скрипт не найден: {path}")
    use_v2 = (s.awg2_docker_container or "").strip() and (
        s.wg2_endpoint or ""
    ).strip()  # noqa: E501
    if not use_v2:
        if not s.wg_endpoint.strip():
            raise PeerGenerationError(
                "Задайте WG_ENDPOINT (публичный IP:порт UDP)"
            )  # noqa: E501
        if not (s.awg_docker_container or "").strip() and (
            not s.wg_server_public_key.strip()
        ):
            raise PeerGenerationError(
                "Задайте WG_SERVER_PUBLIC_KEY или AWG_DOCKER_CONTAINER для авто-чтения ключа из контейнера"  # noqa: E501
            )

    try:
        proc = await asyncio.create_subprocess_exec(
            "/bin/bash",
            str(path),
            user_hint[:128],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_script_env(),
        )
    except FileNotFoundError:
        raise PeerGenerationError(
            "/bin/bash недоступен (нужен Linux для скрипта)"
        ) from None  # noqa: E501

    out_b, err_b = await proc.communicate()
    out = (out_b or b"").decode("utf-8", errors="replace").strip()
    err = (err_b or b"").decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        logger.warning(
            "generate_peer.sh rc=%s stderr=%s", proc.returncode, err
        )  # noqa: E501
        raise PeerGenerationError(
            err or f"скрипт завершился с кодом {proc.returncode}"
        )  # noqa: E501

    data: dict[str, object] | None = None
    for raw_line in reversed(
        [x.strip() for x in out.splitlines() if x.strip()]
    ):  # noqa: E501
        if not (raw_line.startswith("{") and raw_line.endswith("}")):
            continue
        try:
            candidate = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(candidate, dict):
            continue
        data = candidate
        break
    else:
        logger.warning("bad json from generate_peer: %s", out[:500])
        raise PeerGenerationError("Некорректный ответ скрипта")

    assert data is not None
    if not data.get("ok"):
        raise PeerGenerationError(str(data.get("error") or "ошибка генерации"))

    conf = str(data.get("conf") or "")
    pub = str(data.get("public_key") or "").strip()
    fn = str(data.get("filename") or "amnezia_wg.conf")
    if not conf or not pub:
        raise PeerGenerationError("В ответе скрипта нет conf или public_key")

    return fn, conf.strip(), pub
