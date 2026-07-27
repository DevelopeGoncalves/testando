from django import template

register = template.Library()


@register.filter
def moeda_br(value):
    try:
        valor = float(value)
    except (TypeError, ValueError):
        valor = 0
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
