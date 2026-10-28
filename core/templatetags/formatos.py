from django import template

register = template.Library()


@register.filter
def moeda_br(value):
    try:
        valor = float(value)
    except (TypeError, ValueError):
        valor = 0
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter
def atendente_fmt(texto):
    """Quem atendeu/cadastrou, como "matrícula - nome" (texto antigo que não acha usuário fica como está)."""
    from core.atendentes import formatar_atendente
    return formatar_atendente(texto)


@register.filter
def atendente_usuario(user):
    """O usuário logado como "matrícula - nome"."""
    from core.atendentes import atendente_do_usuario
    return atendente_do_usuario(user)
