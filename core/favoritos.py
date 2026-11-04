"""Favoritos da página inicial: cada usuário marca (estrela amarela) os cards que quer ter à mão.
Por enquanto só os cards da aba Vendas (Produção > Vendas); o resto da lista é só acrescentar
novos itens no CATALOGO_FAVORITOS."""
from django.urls import reverse

# chave: nome gravado no banco (não mude depois de usar) | permissão: campo do PerfilUsuario
CATALOGO_FAVORITOS = [
    {'chave': 'vendas_novo', 'titulo': 'Novo', 'subtitulo': 'Ligação', 'icone': 'fas fa-plus-circle', 'rota': 'vendas_novo_negocio', 'permissao': 'prod_vendas_novo'},
    {'chave': 'vendas_renovacao', 'titulo': 'Renovação', 'subtitulo': 'Ligação', 'icone': 'fas fa-redo', 'rota': 'vendas_nova_renovacao', 'permissao': 'prod_vendas_renovacao'},
    {'chave': 'vendas_endosso', 'titulo': 'Endosso', 'subtitulo': 'Ligação', 'icone': 'fas fa-file-medical', 'rota': 'vendas_novo_endosso', 'permissao': 'prod_vendas_endosso'},
    {'chave': 'vendas_emissao_banseg', 'titulo': 'Emissão Banseg', 'subtitulo': 'Acompanhar vendas a emitir', 'icone': 'fas fa-file-invoice-dollar', 'rota': 'vendas_emissao', 'query': '?cia=banseg', 'permissao': 'prod_vendas_emissao'},
    {'chave': 'vendas_emissao_outras', 'titulo': 'Emissão Outras cias', 'subtitulo': 'Acompanhar vendas a emitir', 'icone': 'fas fa-file-invoice-dollar', 'rota': 'vendas_emissao', 'query': '?cia=outras', 'permissao': 'prod_vendas_emissao'},
    {'chave': 'vendas_base_novo', 'titulo': 'Base Novo', 'subtitulo': 'Gerenciar base de novos negócios', 'icone': 'fas fa-file-signature', 'rota': 'lista_base_novo', 'permissao': 'prod_vendas_basenovo'},
    {'chave': 'vendas_base_renovacao', 'titulo': 'Base Renovação', 'subtitulo': 'Gerenciar base de renovação', 'icone': 'fas fa-sync-alt', 'rota': 'vendas_renovacao', 'permissao': 'prod_vendas_baserenovacao'},
    {'chave': 'vendas_base_endosso', 'titulo': 'Base Endosso', 'subtitulo': 'Gerenciar base de endossos', 'icone': 'fas fa-edit', 'rota': 'vendas_endosso', 'permissao': 'prod_vendas_baseendosso'},
    {'chave': 'vendas_base_emissao', 'titulo': 'Base Emissão', 'subtitulo': 'Gerenciar base de emissões', 'icone': 'fas fa-folder-open', 'rota': 'vendas_base_emissao', 'permissao': 'prod_vendas_baseemissao'},
]
POR_CHAVE = {c['chave']: c for c in CATALOGO_FAVORITOS}


def _nivel(user, campo):
    if user.is_superuser:
        return 3
    perfil = getattr(user, 'perfil', None)
    try:
        return int(getattr(perfil, campo, 0) or 0) if perfil else 0
    except (TypeError, ValueError):
        return 0


def cards_permitidos(user):
    """Cards do catálogo que o usuário pode abrir, já com a url."""
    return [dict(c, url=reverse(c['rota']) + c.get('query', ''))
            for c in CATALOGO_FAVORITOS if _nivel(user, c['permissao']) > 0]


def chaves_favoritas(user):
    from .models import FavoritoUsuario
    return set(FavoritoUsuario.objects.filter(usuario=user).values_list('chave', flat=True))


def marcar_favoritos(user, cards):
    favoritas = chaves_favoritas(user)
    for c in cards:
        c['favorito'] = c['chave'] in favoritas
    return cards
