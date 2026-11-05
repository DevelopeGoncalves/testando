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


@register.simple_tag(takes_context=True)
def estrela_favorito(context, chave):
    """Estrela de favorito do card (amarela se já favoritado). Usar dentro de um bloco com a classe fav-cell."""
    from django.utils.html import format_html
    from core.favoritos import chaves_favoritas
    request = context.get('request')
    if request is None or not request.user.is_authenticated:
        return ''
    if not hasattr(request, '_favoritos_cache'):
        request._favoritos_cache = chaves_favoritas(request.user)
    ativo = chave in request._favoritos_cache
    return format_html(
        '<button type="button" class="btn-estrela{}" data-chave="{}" title="Favoritar (aparece na página inicial)" '
        'onclick="alternarFavorito(this)"><i class="{} fa-star ignorar-icone-global"></i></button>',
        ' ativo' if ativo else '', chave, 'fas' if ativo else 'far')
