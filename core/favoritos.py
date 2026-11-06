"""Favoritos da página inicial: cada usuário marca (estrela amarela) os cards que quer ter à mão.
Por enquanto só os cards da aba Vendas (Produção > Vendas); o resto da lista é só acrescentar
novos itens no CATALOGO_FAVORITOS."""
from django.urls import reverse

LIMITE_FAVORITOS = 16  # no máximo 16 favoritos por usuário (4 linhas de 4 cards na página inicial)

# chave: nome gravado no banco (não mude depois de usar) | permissão: campo do PerfilUsuario
# aba: texto pequeno mostrado no card da página inicial | query: complemento da url
# (ex.: "?abrir=modal..." abre aquele pop-up ao entrar na tela)
CATALOGO_FAVORITOS = [
    # ---- Produção > Vendas ----
    {'chave': 'vendas_novo', 'aba': 'Produção > Vendas', 'titulo': 'Novo', 'subtitulo': 'Ligação', 'icone': 'fas fa-plus-circle', 'rota': 'vendas_novo_negocio', 'permissao': 'prod_vendas_novo'},
    {'chave': 'vendas_renovacao', 'aba': 'Produção > Vendas', 'titulo': 'Renovação', 'subtitulo': 'Ligação', 'icone': 'fas fa-redo', 'rota': 'vendas_nova_renovacao', 'permissao': 'prod_vendas_renovacao'},
    {'chave': 'vendas_endosso', 'aba': 'Produção > Vendas', 'titulo': 'Endosso', 'subtitulo': 'Ligação', 'icone': 'fas fa-file-medical', 'rota': 'vendas_novo_endosso', 'permissao': 'prod_vendas_endosso'},
    {'chave': 'vendas_emissao_banseg', 'aba': 'Produção > Vendas', 'titulo': 'Emissão Banseg', 'subtitulo': 'Acompanhar vendas a emitir', 'icone': 'fas fa-file-invoice-dollar', 'rota': 'vendas_emissao', 'query': '?cia=banseg', 'permissao': 'prod_vendas_emissao'},
    {'chave': 'vendas_emissao_outras', 'aba': 'Produção > Vendas', 'titulo': 'Emissão Outras cias', 'subtitulo': 'Acompanhar vendas a emitir', 'icone': 'fas fa-file-invoice-dollar', 'rota': 'vendas_emissao', 'query': '?cia=outras', 'permissao': 'prod_vendas_emissao'},
    {'chave': 'vendas_base_novo', 'aba': 'Produção > Vendas', 'titulo': 'Base Novo', 'subtitulo': 'Gerenciar base de novos negócios', 'icone': 'fas fa-file-signature', 'rota': 'lista_base_novo', 'permissao': 'prod_vendas_basenovo'},
    {'chave': 'vendas_base_renovacao', 'aba': 'Produção > Vendas', 'titulo': 'Base Renovação', 'subtitulo': 'Gerenciar base de renovação', 'icone': 'fas fa-sync-alt', 'rota': 'vendas_renovacao', 'permissao': 'prod_vendas_baserenovacao'},
    {'chave': 'vendas_base_endosso', 'aba': 'Produção > Vendas', 'titulo': 'Base Endosso', 'subtitulo': 'Gerenciar base de endossos', 'icone': 'fas fa-edit', 'rota': 'vendas_endosso', 'permissao': 'prod_vendas_baseendosso'},
    {'chave': 'vendas_base_emissao', 'aba': 'Produção > Vendas', 'titulo': 'Base Emissão', 'subtitulo': 'Gerenciar base de emissões', 'icone': 'fas fa-folder-open', 'rota': 'vendas_base_emissao', 'permissao': 'prod_vendas_baseemissao'},

    # ---- Base > Formulários ----
    {'chave': 'baseform_unidades', 'aba': 'Base > Formulários', 'titulo': 'Unidades', 'subtitulo': 'Gerenciar unidades', 'icone': 'fas fa-building', 'rota': 'lista_unidades', 'permissao': 'base_form_unidade'},
    {'chave': 'baseform_colaboradores', 'aba': 'Base > Formulários', 'titulo': 'Colaboradores', 'subtitulo': 'Gerenciar indicadores', 'icone': 'fas fa-user-tie', 'rota': 'lista_colaboradores', 'permissao': 'base_form_colaboradores'},
    {'chave': 'baseform_contratados', 'aba': 'Base > Formulários', 'titulo': 'Contratados', 'subtitulo': 'Gerenciar o cadastro de contratados', 'icone': 'fas fa-file-signature', 'rota': 'lista_contratados', 'permissao': 'base_form_contratados'},
    {'chave': 'baseform_seguradoras', 'aba': 'Base > Formulários', 'titulo': 'Seguradoras', 'subtitulo': 'Gerenciar o cadastro de seguradoras e afins', 'icone': 'fas fa-shield-alt', 'rota': 'lista_seguradoras', 'permissao': 'base_form_seguradoras'},
    {'chave': 'baseform_tiposdoc', 'aba': 'Base > Formulários', 'titulo': 'Tipos documento', 'subtitulo': 'Gerenciar os tipos de documentos', 'icone': 'fas fa-file-alt', 'rota': 'lista_tiposdoc', 'permissao': 'base_form_tiposdocumento'},
    {'chave': 'baseform_ramos', 'aba': 'Base > Formulários', 'titulo': 'Ramos', 'subtitulo': 'Gerenciar grupos e ramos de seguros', 'icone': 'fas fa-code-branch', 'rota': 'lista_ramos', 'permissao': 'base_form_ramos'},
    {'chave': 'baseform_produtos', 'aba': 'Base > Formulários', 'titulo': 'Produtos', 'subtitulo': 'Gerenciar catálogo de produtos', 'icone': 'fas fa-box-open', 'rota': 'lista_produtos', 'permissao': 'base_form_produtos'},
    {'chave': 'baseform_agrupamentos', 'aba': 'Base > Formulários', 'titulo': 'Agrupamentos', 'subtitulo': 'Gerenciar grupos de produtos', 'icone': 'fas fa-layer-group', 'rota': 'lista_agrupamentos', 'permissao': 'base_form_agrupamentos'},
    {'chave': 'baseform_metas', 'aba': 'Base > Formulários', 'titulo': 'Metas', 'subtitulo': 'Gerenciar metas mensais', 'icone': 'fas fa-bullseye', 'rota': 'lista_metas', 'permissao': 'base_form_metas'},
    {'chave': 'baseform_tipopessoa', 'aba': 'Base > Formulários', 'titulo': 'Tipos de pessoa', 'subtitulo': 'Gerenciar indicadores', 'icone': 'fas fa-id-card', 'rota': 'tipo_pessoa_lista', 'permissao': 'base_form_tipopessoa'},
    {'chave': 'baseform_clientes', 'aba': 'Base > Formulários', 'titulo': 'Clientes', 'subtitulo': 'Gerenciar cadastro de clientes', 'icone': 'fas fa-user-friends', 'rota': 'lista_clientes', 'permissao': 'base_form_clientes'},
    {'chave': 'baseform_estados_anbima', 'aba': 'Base > Formulários', 'titulo': 'Regiões ANBIMA', 'subtitulo': 'Gerenciar regiões ANBIMA', 'icone': 'fas fa-map-marker-alt', 'rota': 'lista_estados_anbima', 'permissao': 'base_form_estados_anbima'},
    {'chave': 'baseform_fundos_anbima', 'aba': 'Base > Formulários', 'titulo': 'Fundos de Previdência ANBIMA', 'subtitulo': 'Gerenciar fundos ANBIMA', 'icone': 'fas fa-coins', 'rota': 'lista_fundos_anbima', 'permissao': 'base_form_fundos_anbima'},
    {'chave': 'baseform_status_emissao', 'aba': 'Base > Formulários', 'titulo': 'Status (Emissões)', 'subtitulo': 'Gerenciar os status da emissão', 'icone': 'fas fa-tasks', 'rota': 'lista_status_emissao', 'permissao': 'base_form_status_emissao'},
    {'chave': 'baseform_retorno_emissao', 'aba': 'Base > Formulários', 'titulo': 'Retorno ao cliente (Emissões)', 'subtitulo': 'Gerenciar os retornos de cada status', 'icone': 'fas fa-reply', 'rota': 'lista_retorno_emissao', 'permissao': 'base_form_retorno_emissao'},

    # ---- Base > Processamentos (abrem o pop-up de importação) ----
    {'chave': 'baseproc_unidades', 'aba': 'Base > Processamentos', 'titulo': 'Importar Unidades', 'subtitulo': 'Atualizar base de unidades', 'icone': 'fas fa-file-import', 'rota': 'base_processamentos', 'query': '?abrir=modalImportarUnidades', 'permissao': 'base_proc_unidade'},
    {'chave': 'baseproc_colaboradores', 'aba': 'Base > Processamentos', 'titulo': 'Importar Colaboradores', 'subtitulo': 'Atualizar equipe', 'icone': 'fas fa-file-excel', 'rota': 'base_processamentos', 'query': '?abrir=modalImportarColaboradores', 'permissao': 'base_proc_colaboradores'},
    {'chave': 'baseproc_ramos', 'aba': 'Base > Processamentos', 'titulo': 'Importar Ramos', 'subtitulo': 'Atualizar grupos e ramos', 'icone': 'fas fa-upload', 'rota': 'base_processamentos', 'query': '?abrir=modalImportarRamos', 'permissao': 'base_proc_ramos'},

    # ---- Produção > Processamentos ----
    {'chave': 'prodproc_anbima', 'aba': 'Produção > Processamentos', 'titulo': 'ANBIMA', 'subtitulo': 'Processar planilha de previdência (ANBIMA)', 'icone': 'fas fa-cog', 'rota': 'producao_anbima_import', 'permissao': 'prod_proc_anbima'},
    {'chave': 'prodproc_habitacional', 'aba': 'Produção > Processamentos', 'titulo': 'Habitacional', 'subtitulo': 'Enviar planilha de dados', 'icone': 'fas fa-cog', 'rota': 'producao_habitacional_import', 'permissao': 'prod_proc_habitacional'},
    {'chave': 'prodproc_odonto', 'aba': 'Produção > Processamentos', 'titulo': 'Odonto', 'subtitulo': 'Enviar planilha de dados', 'icone': 'fas fa-cog', 'rota': 'producao_odonto_import', 'permissao': 'prod_proc_odonto'},

    # ---- Financeiro > Processamentos ----
    {'chave': 'finproc_habitacional', 'aba': 'Financeiro > Processamentos', 'titulo': 'Habitacional', 'subtitulo': 'Processar dados do Habitacional', 'icone': 'fas fa-wallet', 'rota': 'financeiro_habitacional', 'permissao': 'fin_proc_habitacional'},

    # ---- Administração > Estagiários ----
    {'chave': 'admin_lista_estagiarios', 'aba': 'Administração > Estagiários', 'titulo': 'Lista estagiários', 'subtitulo': 'Lista de estagiários', 'icone': 'fas fa-graduation-cap', 'rota': 'lista_estagiarios', 'permissao': 'admin_listaestagiarios'},
    {'chave': 'admin_ferias_estagiarios', 'aba': 'Administração > Estagiários', 'titulo': 'Férias estagiários', 'subtitulo': 'Férias dos estagiários', 'icone': 'fas fa-umbrella-beach', 'rota': 'ferias_estagiarios', 'permissao': 'admin_feriasestagiarios'},
]
POR_CHAVE = {c['chave']: c for c in CATALOGO_FAVORITOS}

# Painéis de Produção > Formulários (um por agrupamento): só Odonto e Habitacional têm painel pronto.
PAINEIS_PRODUCAO = [('habitacional', 'prod_form_habitacional'), ('odonto', 'prod_form_odonto')]


def _nivel(user, campo):
    if user.is_superuser:
        return 3
    perfil = getattr(user, 'perfil', None)
    try:
        return int(getattr(perfil, campo, 0) or 0) if perfil else 0
    except (TypeError, ValueError):
        return 0


def _cards_dos_paineis(user):
    from .models import Agrupamento
    cards = []
    for ag in Agrupamento.objects.filter(inativo=False).order_by('ordem_apresentacao'):
        nome = (ag.agrupamento or '').lower()
        for trecho, permissao in PAINEIS_PRODUCAO:
            if trecho in nome and _nivel(user, permissao) > 0:
                cards.append({'chave': f'prodform_painel_{ag.id}', 'aba': 'Produção > Formulários', 'titulo': ag.agrupamento,
                              'subtitulo': 'Acessar painel', 'icone': 'fas fa-layer-group',
                              'url': reverse('producao_formularios_painel', args=[ag.id])})
    return cards


def cards_permitidos(user):
    """Cards que o usuário pode abrir (e portanto favoritar), já com a url."""
    cards = [dict(c, url=reverse(c['rota']) + c.get('query', ''))
             for c in CATALOGO_FAVORITOS if _nivel(user, c['permissao']) > 0]
    return cards + _cards_dos_paineis(user)


def chaves_favoritas(user):
    from .models import FavoritoUsuario
    return set(FavoritoUsuario.objects.filter(usuario=user).values_list('chave', flat=True))


def marcar_favoritos(user, cards):
    favoritas = chaves_favoritas(user)
    for c in cards:
        c['favorito'] = c['chave'] in favoritas
    return cards


def favoritos_na_ordem(user):
    """Favoritos do usuário na ordem que ele arrastou (ou na de marcação), só os que ainda pode abrir."""
    from .models import FavoritoUsuario
    ordem = list(FavoritoUsuario.objects.filter(usuario=user).order_by('ordem', 'criado_em', 'id').values_list('chave', flat=True))
    por_chave = {c['chave']: dict(c, favorito=True) for c in cards_permitidos(user)}
    return [por_chave[k] for k in ordem if k in por_chave]
