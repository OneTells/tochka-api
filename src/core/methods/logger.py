from starlette.types import Scope


def get_real_ip(scope: Scope) -> str:
    for key, value in scope["headers"]:
        if key == b'x-real-ip':
            return value.decode('latin-1')

    return scope["client"][0]
