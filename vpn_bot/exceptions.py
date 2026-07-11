class TooManyKeysError(Exception):
    def __init__(self, limit: int, hours: int) -> None:
        self.limit = limit
        self.hours = hours
        super().__init__(f"Не больше {limit} ключей за {hours} ч.")


class PeerGenerationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ContainerIssueError(PeerGenerationError):
    """Ошибка docker exec / easyrsa / xray при выдаче конфигов Amnezia."""
