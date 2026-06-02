from enum import StrEnum


class Role(StrEnum):
    admin = "Admin"
    operator = "Operator"
    viewer = "Viewer"


ROLE_ORDER: dict[Role, int] = {Role.viewer: 1, Role.operator: 2, Role.admin: 3}


def role_allows(current: Role, required: Role) -> bool:
    return ROLE_ORDER[current] >= ROLE_ORDER[required]
