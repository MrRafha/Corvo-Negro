"""Sistema de permissoes por bitmask.

Cada role guarda um inteiro `permissions` que e um OR de flags de Permission.
has_permission(mask, flag) checa se uma flag especifica esta presente na
mascara combinada de todas as roles do membro.
"""

from __future__ import annotations


class Permission:
    SEND_MESSAGE = 1
    DELETE_MESSAGE = 2
    PIN_MESSAGE = 4
    SEND_IMAGE = 8
    CREATE_CHANNEL = 16
    KICK_MEMBER = 32
    BAN_MEMBER = 64
    MANAGE_ROLES = 128
    MANAGE_FORUM = 256
    CREATE_INVITE = 512
    ALL = 1023


def has_permission(mask: int, flag: int) -> bool:
    """Checa se `flag` esta presente na mascara combinada `mask`."""
    return (mask & flag) == flag


def combine_masks(masks: list[int]) -> int:
    """Combina (OR) as mascaras de todas as roles de um membro."""
    combined = 0
    for mask in masks:
        combined |= mask
    return combined
