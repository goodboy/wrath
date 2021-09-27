import typing as t


def is_interval(arg: str) -> bool:
    try:
        start, end = map(int, arg.split('-'))

        assert 0 <= start <= 65535
        assert 0 <= end <= 65535
        assert start < end

        return True
    except ValueError:
        return False


def is_port(port: str) -> bool:
    try:
        port = int(port)
        assert 0 <= port <= 65535
        return True
    except ValueError:
        return False


def to_port(port: str) -> int:
    return int(port)


def to_interval(interval: str) -> t.Tuple[int, int]:
    start, end = map(int, interval.split('-'))
    return start, end