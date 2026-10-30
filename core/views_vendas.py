import hashlib
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.contrib import messages
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, OuterRef, Subquery, Prefetch
from django.http import JsonResponse, FileResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .auditoria import registrar_auditoria_backend
from .cache_vendas import (  # cache das telas de Vendas no navegador
    cache_navegador_vendas, TABELAS_NOVO, TABELAS_RENOVACAO, TABELAS_ENDOSSO, TABELAS_EMISSAO,
)
from .clientes_sync import sincronizar_cliente, buscar_cliente
from .forms import IndicacaoForm, IndicacaoRenovacaoForm, IndicacaoEndossoForm
from .models import (
    Unidade, Colaborador, Seguradora, Indicacao, LigacaoIndicacao,
    IndicacaoRenovacao, LigacaoRenovacao, IndicacaoEndosso, LigacaoEndosso, AcompanhamentoEmissao,
    StatusEmissao, RetornoClienteEmissao,
)
from .atendentes import atendente_do_usuario, formatar_atendente
from .emissao_padroes import garantir_padroes_emissao
from .odonto import _sem_acento as _texto_comparavel
from .validadores import verificar_documento_por_tipo  # validador cpf alex


@login_required
def producao_vendas(request):

    # negar acesso ao usuario
    user = request.user
    tem_permissao_base = False

    if not user.is_superuser and hasattr(user, 'perfil'):
        tem_permissao_base = any(
            valor > 0 
            for campo, valor in user.perfil.__dict__.items() 
            if campo.startswith('prod_vendas_') and isinstance(valor, int)
        )

    if not (user.is_superuser or tem_permissao_base):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    #----

    return render(request, 'core/producao/vendas/index.html')

@login_required
@cache_navegador_vendas(TABELAS_ENDOSSO)
def vendas_endosso(request):
    """Card 'Base Endosso'. Mesma lógica do Base Novo/Base Renovação, mas na tabela
    própria IndicacaoEndosso/LigacaoEndosso (não mistura os dados com os outros)."""
    # validador cpf alex: nega acesso a quem o Usuários deixou sem permissão neste card
    if _nivel_vendas(request.user, 'prod_vendas_baseendosso') == 0:
        messages.error(request, 'Acesso Negado.')
        return redirect('producao_vendas')
    if request.method == 'POST':
        form, erro_formulario_msg = _salvar_indicacao_e_ligacoes(
            request, processar_ligacoes=True, travar_dados=True,
            campo_permissao='prod_vendas_baseendosso',
            model_indicacao=IndicacaoEndosso, model_ligacao=LigacaoEndosso,
            form_class=IndicacaoEndossoForm,
        )
        if form is None:
            return redirect('vendas_endosso')
    else:
        form = IndicacaoEndossoForm()
        erro_formulario_msg = ''

    indicacoes = list(
        IndicacaoEndosso.objects.all().order_by('-id')
        .select_related('ramo', 'responsavel_demanda', 'seguradora', 'tipo_documento')
        .prefetch_related(Prefetch('ligacoes', queryset=LigacaoEndosso.objects.select_related('seguradora')))
    )
    cids = {(i.cid_agencia or '').strip() for i in indicacoes if i.cid_agencia}
    mapa_agencia = {u.cid_unidade: u.unidade for u in Unidade.objects.filter(cid_unidade__in=cids)} if cids else {}
    limite_atend = timezone.now() - timedelta(seconds=ATENDIMENTO_TIMEOUT_SEG)
    for ind in indicacoes:
        ind.nome_agencia = mapa_agencia.get((ind.cid_agencia or '').strip(), '')
        ind.atendimento_ativo = bool(ind.atendimento_por and ind.atendimento_em and ind.atendimento_em >= limite_atend)
        ind.status_fechamento = _status_fechamento_indicacao(ind)
        ind.responsavel_ultima_ligacao = _responsavel_ultima_ligacao(ind)

    return render(request, 'core/producao/vendas/base_endosso.html', {
        'indicacoes': indicacoes,
        'form_indicacao': form,
        'erro_formulario_msg': erro_formulario_msg,
        'motivos_nao_venda': LigacaoEndosso.MOTIVO_NAO_VENDA,
        'seguradoras': Seguradora.objects.all().order_by('seguradora'),
        'usuario_gestor': _usuario_e_gestor(request.user, 'prod_vendas_baseendosso'),
        'usuario_pode_editar': _usuario_pode_editar_dados(request.user, 'prod_vendas_baseendosso'),
        'usuario_pode_excluir': _usuario_pode_excluir(request.user, 'prod_vendas_baseendosso'),
        'colaboradores_demanda': Colaborador.objects.filter(inativo=False).order_by('colaborador'),
        'unidades_agencia': Unidade.objects.filter(inativada=False).order_by('cid_unidade'),
    })

@login_required
@cache_navegador_vendas(TABELAS_NOVO)
def vendas_novo_negocio(request):

    # validador cpf alex: nega acesso a quem o Usuários deixou sem permissão neste card
    if _nivel_vendas(request.user, 'prod_vendas_novo') == 0:
        messages.error(request, 'Acesso Negado.')
        return redirect('producao_vendas')

    if request.method == 'POST':
        form, erro_formulario_msg = _salvar_indicacao_e_ligacoes(request, campo_permissao='prod_vendas_novo')
        if form is None:
            return redirect('vendas_novo_negocio')
    else:
        # A ficha do Novo fica travada visualmente, mas os dados podem ser editados pelo
        # pop-up (lápis) e salvos de verdade - por isso o form NÃO é mais só leitura.
        form = IndicacaoForm()
        erro_formulario_msg = ''

    ultima_ligacao = LigacaoIndicacao.objects.filter(indicacao=OuterRef('pk')).order_by('-id')
    indicacoes = Indicacao.objects.annotate(
        ultima_central=Subquery(ultima_ligacao.values('venda_central')[:1]),
        ultima_agn=Subquery(ultima_ligacao.values('agn')[:1]),
        ultima_motivo=Subquery(ultima_ligacao.values('motivo_nao_venda')[:1]),
    ).filter(
        Q(ultima_central__isnull=True)
        | Q(ultima_central=False, ultima_agn=False, ultima_motivo__isnull=True)
    #).order_by('-id').select_related('seguradora', 'ramo', 'tipo_documento', 'responsavel_demanda').prefetch_related('ligacoes')
    ).order_by('-id').select_related('ramo', 'responsavel_demanda', 'seguradora', 'tipo_documento').prefetch_related(Prefetch('ligacoes', queryset=LigacaoIndicacao.objects.select_related('seguradora')))

    indicacoes = list(indicacoes)
    # Mapa CID -> nome da agência (tabela Unidade), para exibir "CID - Nome" concatenado
    # na lista do Novo (facilita a busca/filtro). Se o CID não existir em Unidade, fica só o CID.
    cids = {(i.cid_agencia or '').strip() for i in indicacoes if i.cid_agencia}
    mapa_agencia = {u.cid_unidade: u.unidade for u in Unidade.objects.filter(cid_unidade__in=cids)} if cids else {}
    limite_atend = timezone.now() - timedelta(seconds=ATENDIMENTO_TIMEOUT_SEG)
    for ind in indicacoes:
        ligacoes = list(ind.ligacoes.all())
        ultima = ligacoes[0] if ligacoes else None
        ind.responsavel = ultima.cadastrado_por if ultima else ''
        ind.proxima_ligacao = ultima.proximo_contato if ultima else None
        ind.nome_agencia = mapa_agencia.get((ind.cid_agencia or '').strip(), '')
        ind.atendimento_ativo = bool(ind.atendimento_por and ind.atendimento_em and ind.atendimento_em >= limite_atend)
        ind.status_fechamento = _status_fechamento_indicacao(ind)
        ind.responsavel_ultima_ligacao = _responsavel_ultima_ligacao(ind)

    return render(request, 'core/producao/vendas/novo.html', {
        'indicacoes': indicacoes,
        'form_indicacao': form,
        'erro_formulario_msg': erro_formulario_msg,
        'motivos_nao_venda': LigacaoIndicacao.MOTIVO_NAO_VENDA,
        # alex: seguradoras para o dropdown da LIGAÇÃO (relacionamento só na ligação)
        'seguradoras': Seguradora.objects.all().order_by('seguradora'),
        'apenas_pendentes': True,
        # Permissões deste card usam o campo do "Novo" (prod_vendas_novo).
        'usuario_gestor': _usuario_e_gestor(request.user, 'prod_vendas_novo'),
        'usuario_pode_editar': _usuario_pode_editar_dados(request.user, 'prod_vendas_novo'),
        'usuario_pode_excluir': _usuario_pode_excluir(request.user, 'prod_vendas_novo'),
        'colaboradores_demanda': Colaborador.objects.filter(inativo=False).order_by('colaborador'),
        # alex: autocomplete do campo Agência (Unidade: "CID - nome")
        'unidades_agencia': Unidade.objects.filter(inativada=False).order_by('cid_unidade'),
    })

@login_required
@cache_navegador_vendas(TABELAS_RENOVACAO)
def vendas_nova_renovacao(request):
    """Card 'Renovação' (Ligação). Mesma lógica do card 'Novo', mas grava na tabela
    própria IndicacaoRenovacao/LigacaoRenovacao (não mistura os dados com o Novo)."""
    # validador cpf alex: nega acesso a quem o Usuários deixou sem permissão neste card
    if _nivel_vendas(request.user, 'prod_vendas_renovacao') == 0:
        messages.error(request, 'Acesso Negado.')
        return redirect('producao_vendas')
    if request.method == 'POST':
        form, erro_formulario_msg = _salvar_indicacao_e_ligacoes(
            request, campo_permissao='prod_vendas_renovacao',
            model_indicacao=IndicacaoRenovacao, model_ligacao=LigacaoRenovacao,
            form_class=IndicacaoRenovacaoForm,
        )
        if form is None:
            return redirect('vendas_nova_renovacao')
    else:
        form = IndicacaoRenovacaoForm()
        erro_formulario_msg = ''

    ultima_ligacao = LigacaoRenovacao.objects.filter(indicacao=OuterRef('pk')).order_by('-id')
    indicacoes = IndicacaoRenovacao.objects.annotate(
        ultima_central=Subquery(ultima_ligacao.values('venda_central')[:1]),
        ultima_agn=Subquery(ultima_ligacao.values('agn')[:1]),
        ultima_motivo=Subquery(ultima_ligacao.values('motivo_nao_venda')[:1]),
    ).filter(
        Q(ultima_central__isnull=True)
        | Q(ultima_central=False, ultima_agn=False, ultima_motivo__isnull=True)
    ).order_by('-id').select_related('ramo', 'responsavel_demanda', 'seguradora', 'tipo_documento').prefetch_related(Prefetch('ligacoes', queryset=LigacaoRenovacao.objects.select_related('seguradora')))

    indicacoes = list(indicacoes)
    cids = {(i.cid_agencia or '').strip() for i in indicacoes if i.cid_agencia}
    mapa_agencia = {u.cid_unidade: u.unidade for u in Unidade.objects.filter(cid_unidade__in=cids)} if cids else {}
    limite_atend = timezone.now() - timedelta(seconds=ATENDIMENTO_TIMEOUT_SEG)
    for ind in indicacoes:
        ligacoes = list(ind.ligacoes.all())
        ultima = ligacoes[0] if ligacoes else None
        ind.responsavel = ultima.cadastrado_por if ultima else ''
        ind.proxima_ligacao = ultima.proximo_contato if ultima else None
        ind.nome_agencia = mapa_agencia.get((ind.cid_agencia or '').strip(), '')
        ind.atendimento_ativo = bool(ind.atendimento_por and ind.atendimento_em and ind.atendimento_em >= limite_atend)
        ind.status_fechamento = _status_fechamento_indicacao(ind)
        ind.responsavel_ultima_ligacao = _responsavel_ultima_ligacao(ind)

    return render(request, 'core/producao/vendas/renovacao.html', {
        'indicacoes': indicacoes,
        'form_indicacao': form,
        'erro_formulario_msg': erro_formulario_msg,
        'motivos_nao_venda': LigacaoRenovacao.MOTIVO_NAO_VENDA,
        'seguradoras': Seguradora.objects.all().order_by('seguradora'),
        'apenas_pendentes': True,
        'usuario_gestor': _usuario_e_gestor(request.user, 'prod_vendas_renovacao'),
        'usuario_pode_editar': _usuario_pode_editar_dados(request.user, 'prod_vendas_renovacao'),
        'usuario_pode_excluir': _usuario_pode_excluir(request.user, 'prod_vendas_renovacao'),
        'colaboradores_demanda': Colaborador.objects.filter(inativo=False).order_by('colaborador'),
        'unidades_agencia': Unidade.objects.filter(inativada=False).order_by('cid_unidade'),
    })

@login_required
@cache_navegador_vendas(TABELAS_ENDOSSO)
def vendas_novo_endosso(request):
    """Card 'Endosso' (Ligação). Mesma lógica do card 'Novo'/'Renovação', mas grava na
    tabela própria IndicacaoEndosso/LigacaoEndosso (não mistura os dados com os outros)."""
    # validador cpf alex: nega acesso a quem o Usuários deixou sem permissão neste card
    if _nivel_vendas(request.user, 'prod_vendas_endosso') == 0:
        messages.error(request, 'Acesso Negado.')
        return redirect('producao_vendas')
    if request.method == 'POST':
        form, erro_formulario_msg = _salvar_indicacao_e_ligacoes(
            request, campo_permissao='prod_vendas_endosso',
            model_indicacao=IndicacaoEndosso, model_ligacao=LigacaoEndosso,
            form_class=IndicacaoEndossoForm,
        )
        if form is None:
            return redirect('vendas_novo_endosso')
    else:
        form = IndicacaoEndossoForm()
        erro_formulario_msg = ''

    ultima_ligacao = LigacaoEndosso.objects.filter(indicacao=OuterRef('pk')).order_by('-id')
    indicacoes = IndicacaoEndosso.objects.annotate(
        ultima_central=Subquery(ultima_ligacao.values('venda_central')[:1]),
        ultima_agn=Subquery(ultima_ligacao.values('agn')[:1]),
        ultima_motivo=Subquery(ultima_ligacao.values('motivo_nao_venda')[:1]),
    ).filter(
        Q(ultima_central__isnull=True)
        | Q(ultima_central=False, ultima_agn=False, ultima_motivo__isnull=True)
    ).order_by('-id').select_related('ramo', 'responsavel_demanda', 'seguradora', 'tipo_documento').prefetch_related(Prefetch('ligacoes', queryset=LigacaoEndosso.objects.select_related('seguradora')))

    indicacoes = list(indicacoes)
    cids = {(i.cid_agencia or '').strip() for i in indicacoes if i.cid_agencia}
    mapa_agencia = {u.cid_unidade: u.unidade for u in Unidade.objects.filter(cid_unidade__in=cids)} if cids else {}
    limite_atend = timezone.now() - timedelta(seconds=ATENDIMENTO_TIMEOUT_SEG)
    for ind in indicacoes:
        ligacoes = list(ind.ligacoes.all())
        ultima = ligacoes[0] if ligacoes else None
        ind.responsavel = ultima.cadastrado_por if ultima else ''
        ind.proxima_ligacao = ultima.proximo_contato if ultima else None
        ind.nome_agencia = mapa_agencia.get((ind.cid_agencia or '').strip(), '')
        ind.atendimento_ativo = bool(ind.atendimento_por and ind.atendimento_em and ind.atendimento_em >= limite_atend)
        ind.status_fechamento = _status_fechamento_indicacao(ind)
        ind.responsavel_ultima_ligacao = _responsavel_ultima_ligacao(ind)

    return render(request, 'core/producao/vendas/endosso.html', {
        'indicacoes': indicacoes,
        'form_indicacao': form,
        'erro_formulario_msg': erro_formulario_msg,
        'motivos_nao_venda': LigacaoEndosso.MOTIVO_NAO_VENDA,
        'seguradoras': Seguradora.objects.all().order_by('seguradora'),
        'apenas_pendentes': True,
        'usuario_gestor': _usuario_e_gestor(request.user, 'prod_vendas_endosso'),
        'usuario_pode_editar': _usuario_pode_editar_dados(request.user, 'prod_vendas_endosso'),
        'usuario_pode_excluir': _usuario_pode_excluir(request.user, 'prod_vendas_endosso'),
        'colaboradores_demanda': Colaborador.objects.filter(inativo=False).order_by('colaborador'),
        'unidades_agencia': Unidade.objects.filter(inativada=False).order_by('cid_unidade'),
    })

@login_required
def gerar_protocolo_ligacao(request):
    return JsonResponse({'protocolo': LigacaoIndicacao.gerar_proximo_protocolo()})

@login_required
def buscar_cliente_por_cpf(request):
    """Ficha de Vendas (Novo/Renovação/Endosso): valida o CPF/CNPJ na hora
    (de acordo com o tipo escolhido na caixinha CPF/CNPJ da ficha) e, se for
    válido e já tiver cadastro em Base > Formulários > Clientes, puxa os
    dados pra preencher Nome/Telefone/E-mail sozinho. Sem CPF/CNPJ cadastrado,
    o usuário preenche na mão e um cliente novo é criado ao salvar a ficha."""
    # validador cpf alex (tempo real): mesma validação do salvar, só que na
    # hora, sem precisar enviar o formulário.
    valido, documento, mensagem = verificar_documento_por_tipo(
        request.GET.get('cpf', ''), request.GET.get('tipo', 'CPF')
    )

    resposta = {'valido': valido, 'mensagem': mensagem, 'encontrado': False}

    if valido and documento:
        cliente = buscar_cliente(documento)
        if cliente:
            resposta.update({
                'encontrado': True,
                'id': cliente.id,
                'nome': cliente.nome or '',
                'telefone': cliente.celular or cliente.telefone or '',
                'email': cliente.email or '',
            })

    return JsonResponse(resposta)

@login_required
def gerar_protocolo_ligacao_renovacao(request):
    return JsonResponse({'protocolo': LigacaoRenovacao.gerar_proximo_protocolo()})

@login_required
def gerar_protocolo_ligacao_endosso(request):
    return JsonResponse({'protocolo': LigacaoEndosso.gerar_proximo_protocolo()})

@login_required
def agora_servidor_ligacao(request):
    # horário vem sempre do servidor, nunca do relógio do navegador: o relógio do
    agora = timezone.localtime(timezone.now())
    return JsonResponse({'datahora': agora.strftime('%Y-%m-%dT%H:%M:%S')})

# a linha vermelha trabando quem ja esta em ligacao , 
ATENDIMENTO_TIMEOUT_SEG = 45

def _nome_usuario_atendimento(user):
    """mostra o nome na coluna quem esta usando uso por:"""
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.colaborador:
        col = perfil.colaborador
        return col.nome_social or col.colaborador
    return user.get_full_name() or user.username

def _marcar_atendimento(request, id, model_indicacao):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    ind = get_object_or_404(model_indicacao, id=id)
    ind.atendimento_por = _nome_usuario_atendimento(request.user)
    ind.atendimento_em = timezone.now()
    ind.save(update_fields=['atendimento_por', 'atendimento_em'])
    return JsonResponse({'ok': True})

def _encerrar_atendimento(request, id, model_indicacao):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    ind = get_object_or_404(model_indicacao, id=id)
    ind.atendimento_por = None
    ind.atendimento_em = None
    ind.save(update_fields=['atendimento_por', 'atendimento_em'])
    return JsonResponse({'ok': True})

def _atendimentos_ativos(model_indicacao):
    limite = timezone.now() - timedelta(seconds=ATENDIMENTO_TIMEOUT_SEG)
    qs = (model_indicacao.objects
          .filter(atendimento_em__gte=limite)
          .exclude(atendimento_por__isnull=True)
          .exclude(atendimento_por__exact='')
          .values('id', 'atendimento_por'))
    return JsonResponse({'atendimentos': {str(r['id']): r['atendimento_por'] for r in qs}})

@login_required
def marcar_atendimento(request, id):
    return _marcar_atendimento(request, id, Indicacao)

@login_required
def marcar_atendimento_renovacao(request, id):
    return _marcar_atendimento(request, id, IndicacaoRenovacao)

@login_required
def marcar_atendimento_endosso(request, id):
    return _marcar_atendimento(request, id, IndicacaoEndosso)

@login_required
def encerrar_atendimento(request, id):
    return _encerrar_atendimento(request, id, Indicacao)

@login_required
def encerrar_atendimento_renovacao(request, id):
    return _encerrar_atendimento(request, id, IndicacaoRenovacao)

@login_required
def encerrar_atendimento_endosso(request, id):
    return _encerrar_atendimento(request, id, IndicacaoEndosso)

@login_required
def atendimentos_ativos(request):
    return _atendimentos_ativos(Indicacao)

@login_required
def atendimentos_ativos_renovacao(request):
    return _atendimentos_ativos(IndicacaoRenovacao)

@login_required
def atendimentos_ativos_endosso(request):
    return _atendimentos_ativos(IndicacaoEndosso)

# indicar o responsavel da demandar pelo ao nivei do usuario
def _nivel_vendas(user, campo='prod_vendas_novo'):
    """Nível (0-3) do usuário para UM card de Vendas específico"""
    if user.is_superuser:
        return 3
    perfil = getattr(user, 'perfil', None)
    if not perfil:
        return 0
    try:
        return int(getattr(perfil, campo, 0) or 0)
    except (TypeError, ValueError):
        return 0

def _usuario_e_gestor(user, campo='prod_vendas_novo'):
    """Gestor (nível 3) no card indicado."""
    return _nivel_vendas(user, campo) == 3

def _usuario_pode_editar_dados(user, campo='prod_vendas_novo'):
    """Editor (2) ou Gestor (3) podem editar os dados da ficha no card indicado"""
    return _nivel_vendas(user, campo) >= 2

def _usuario_pode_excluir(user, campo='prod_vendas_novo'):
    """Apenas Gestor (nível 3) pode EXCLUIR no card indicado"""
    return _nivel_vendas(user, campo) == 3

def _status_fechamento_indicacao(ind):
    """Status de fechamento do registro, com base na ÚLTIMA ligação"""
    ligs = list(ind.ligacoes.all())
    if not ligs:
        return 'Em aberto'
    ult = max(ligs, key=lambda l: l.id or 0)
    if ult.venda_central:
        return 'Venda Central'
    if ult.agn:
        return 'Venda Agência'
    if ult.motivo_nao_venda:
        return 'Não venda: ' + ult.motivo_nao_venda
    return 'Em aberto'

def _responsavel_ultima_ligacao(ind):
    """Quem registrou a ligação MAIS RECENTE (cadastrado_por da última ligação), como "matrícula - nome"."""
    ligs = list(ind.ligacoes.all())
    if not ligs:
        return ''
    ult = max(ligs, key=lambda l: l.id or 0)
    return formatar_atendente(ult.cadastrado_por)

def _definir_responsavel_demanda(request, id, model_indicacao, campos_permissao):
    """somente o usuario pode tirar ou indicar o responsavel pela demanda '."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    if not any(_usuario_e_gestor(request.user, campo) for campo in campos_permissao):
        return JsonResponse({'ok': False, 'erro': 'Apenas usuários Gestor podem indicar o responsável.'}, status=403)
    ind = get_object_or_404(model_indicacao, id=id)
    col_id = request.POST.get('colaborador') or None
    ind.responsavel_demanda_id = col_id
    ind.save(update_fields=['responsavel_demanda'])
    ind.refresh_from_db()
    nome = ind.responsavel_demanda.matricula_nome if ind.responsavel_demanda_id else ''
    return JsonResponse({'ok': True, 'nome': nome, 'id': ind.responsavel_demanda_id or ''})

def _definir_responsavel_massa(request, model_indicacao, campos_permissao):
    """Indica o MESMO responsável para vários registros de uma vez (seleção por caixinha
    no card Novo/Renovação). Só Gestor. POST: ids[] + colaborador."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    if not any(_usuario_e_gestor(request.user, campo) for campo in campos_permissao):
        return JsonResponse({'ok': False, 'erro': 'Apenas usuários Gestor podem indicar o responsável.'}, status=403)
    ids = request.POST.getlist('ids')
    if not ids:
        return JsonResponse({'ok': False, 'erro': 'Selecione ao menos um registro.'}, status=400)
    col_id = request.POST.get('colaborador') or None
    model_indicacao.objects.filter(id__in=ids).update(responsavel_demanda_id=col_id)
    nome = ''
    if col_id:
        col = Colaborador.objects.filter(id=col_id).first()
        nome = col.matricula_nome if col else ''
    return JsonResponse({'ok': True, 'nome': nome, 'id': col_id or '', 'total': len(ids)})

@login_required
def definir_responsavel_demanda(request, id):
    # O botão aparece na ficha do Novo e do Base Novo: aceita Gestor em qualquer um dos dois.
    return _definir_responsavel_demanda(request, id, Indicacao, ('prod_vendas_novo', 'prod_vendas_basenovo'))

@login_required
def definir_responsavel_demanda_renovacao(request, id):
    return _definir_responsavel_demanda(request, id, IndicacaoRenovacao, ('prod_vendas_renovacao', 'prod_vendas_baserenovacao'))

@login_required
def definir_responsavel_demanda_endosso(request, id):
    return _definir_responsavel_demanda(request, id, IndicacaoEndosso, ('prod_vendas_endosso', 'prod_vendas_baseendosso'))

@login_required
def definir_responsavel_massa(request):
    return _definir_responsavel_massa(request, Indicacao, ('prod_vendas_novo', 'prod_vendas_basenovo'))

@login_required
def definir_responsavel_massa_renovacao(request):
    return _definir_responsavel_massa(request, IndicacaoRenovacao, ('prod_vendas_renovacao', 'prod_vendas_baserenovacao'))

@login_required
def definir_responsavel_massa_endosso(request):
    return _definir_responsavel_massa(request, IndicacaoEndosso, ('prod_vendas_endosso', 'prod_vendas_baseendosso'))

def _parse_valor_moeda_brl(valor_str):
    if not valor_str: return None
    limpo = str(valor_str).strip().replace('R$', '').replace(' ', '')
    if not limpo: return None
    if '.' in limpo and ',' in limpo:
        limpo = limpo.replace('.', '').replace(',', '.')
    elif ',' in limpo:
        limpo = limpo.replace(',', '.')
    try: return Decimal(limpo)
    except (InvalidOperation, ValueError): return None

def _parse_float(valor_str):
    if not valor_str: return None
    val = str(valor_str).replace('R$', '').replace('%', '').strip()
    if not val or val.lower() == 'nan': return None
    if '.' in val and ',' in val:
        val = val.replace('.', '').replace(',', '.')
    elif ',' in val:
        val = val.replace(',', '.')
    try: 
        f = float(val)
        if f != f or f == float('inf') or f == float('-inf'): return None
        return f
    except ValueError: return None

def _parse_int(valor_str):
    if not valor_str: return None
    val = str(valor_str).strip()
    if not val or val.lower() == 'nan': return None
    try: return int(float(val))
    except ValueError: return None

def _parse_date(valor_str):
    val = str(valor_str).strip() if valor_str else ''
    if not val or val.lower() == 'nan': return None
    try:
        dt = datetime.strptime(val, '%Y-%m-%d')
        if dt.year > 9999 or dt.year < 1900: return None
        return val
    except ValueError: return None


def _falta_premio_total_venda_central(request):
    """True se alguma ligação marcada como 'Vendas Central' ou 'Vendas Agência' ficou
    sem 'Prêmio Total'. O checkbox só aparece no POST quando marcado"""
    for prefixo in ('ligacao_venda_central', 'ligacao_agn'):
        for chave, valor in request.POST.items():
            if chave.startswith(prefixo) and valor == 'on':
                sufixo = chave[len(prefixo):]
                premio = (request.POST.get(f'ligacao_premio_total{sufixo}') or '').strip()
                if not premio:
                    return True
    return False


def _cadastro_repetido(request, form, model_indicacao):
    """Evita registro duplicado quando o mesmo cadastro novo é enviado mais de uma vez em
    sequência (vários cliques no Salvar). Duas proteções:
    1) trava de 30 s por usuário + CPF + nome (pega envios simultâneos);
    2) já existe registro com o mesmo CPF, nome e "Data/hora do cadastro" do formulário
       (a data/hora vem preenchida na abertura da ficha, então os reenvios trazem a mesma)."""
    dados = form.cleaned_data
    cpf = (dados.get('cpf_cliente') or '').strip()
    nome = (dados.get('nome_cliente') or '').strip()
    if not (cpf or nome):
        return False
    texto_chave = f'{model_indicacao._meta.label}|{request.user.pk}|{cpf}|{nome.lower()}'
    chave = 'novo_registro:' + hashlib.md5(texto_chave.encode(), usedforsecurity=False).hexdigest()
    if not cache.add(chave, 1, timeout=30):
        return True
    carimbo = dados.get('carimbo_data_hora')
    if carimbo and model_indicacao.objects.filter(cpf_cliente=cpf, nome_cliente=nome, carimbo_data_hora=carimbo).exists():
        return True
    return False

def _salvar_indicacao_e_ligacoes(request, processar_ligacoes=True, travar_dados=None,
                                 campo_permissao='prod_vendas_novo',
                                 model_indicacao=Indicacao, model_ligacao=LigacaoIndicacao,
                                 form_class=IndicacaoForm):
    """Processa o POST de cadastro/edição da ficha de Indicação (Base Novo e o card
    'Novo', que sao a mesma fincha; e também a Renovação/Base Renovação, na sua
    própria tabela). campo_permissao = campo do card (Novo/Base Novo/Emissão/
    Renovação/Base Renovação) usado para checar se o usuário pode editar."""
    if travar_dados is None:
        travar_dados = processar_ligacoes

    pode_editar = _usuario_pode_editar_dados(request.user, campo_permissao)
    # Leitor (nível 1) não pode gravar nada em Vendas: nem dados, nem ligações.
    # (o "somente_leitura" abaixo já trava os dados; aqui travamos também as ligações.)
    if not pode_editar:
        processar_ligacoes = False
    item_id = request.POST.get('item_id')
    instancia = get_object_or_404(model_indicacao, id=item_id) if item_id else None

    # A ficha da Base Novo envia o Indicador e a Agência em campos ÚNICOS.
    dados_post = request.POST
    if 'indicador_combo' in request.POST or 'agencia_combo' in request.POST:
        dados_post = request.POST.copy()
        if 'indicador_combo' in dados_post:
            mat, _, nome = (dados_post.get('indicador_combo') or '').strip().partition(' - ')
            dados_post['matricula_indicador'] = mat.strip()
            dados_post['nome_indicador'] = nome.strip()
        if 'agencia_combo' in dados_post:
            dados_post['cid_agencia'] = (dados_post.get('agencia_combo') or '').strip().partition(' - ')[0].strip()

    # No Novo e no Base Novo, os dados do registro só são gravados quando o salvamento vem do pop-up de edição
    # e apenas para quem pode editar (Editor ou Gestor).
    somente_leitura = travar_dados and (
        request.POST.get('editar_dados') != '1' or not pode_editar
    )
    form = form_class(dados_post, instance=instancia, ficha_somente_leitura=somente_leitura)

    # os campos "Vendas Central" obriga o preenchimento do "Prêmio Total".  se nao da erro
    if _falta_premio_total_venda_central(request):
        form.add_error(None, 'Informe o "Prêmio Total" nas ligações marcadas como "Vendas Central" ou "Vendas Agência".')

    if not form.is_valid():
        erro_formulario_msg = '; '.join(
            ', '.join(erros) if campo == '__all__' else f"{form.fields[campo].label if campo in form.fields else campo}: {', '.join(erros)}"
            for campo, erros in form.errors.items()
        )
        return form, erro_formulario_msg

    era_novo = instancia is None
    if era_novo and _cadastro_repetido(request, form, model_indicacao):
        # O mesmo cadastro chegou de novo (duplo/triplo clique no Salvar ou internet lenta):
        # não cria outro registro igual.
        return None, ''
    indicacao = form.save()

    # O card Clientes e a base: o CPF informado na ficha acha (ou cadastra) o
    # cliente em Base > Formulários > Clientes, e o registro guarda o ID dele.
    # Sem CPF nao da pra identificar a pessoa, entao fica sem vinculo mesmo.
    cliente_obj = sincronizar_cliente(
        cpf_cnpj=indicacao.cpf_cliente,
        nome=indicacao.nome_cliente,
        celular=indicacao.telefone_cliente,
        email=indicacao.email_cliente,
    )
    cliente_novo_id = cliente_obj.id if cliente_obj else None
    if indicacao.cliente_cadastro_id != cliente_novo_id:
        indicacao.cliente_cadastro = cliente_obj
        indicacao.save(update_fields=['cliente_cadastro'])

    # alex: quem CRIA o registro (Novo ou Base Novo) já entra como responsável pela
    # demanda. O Gestor continua podendo indicar/alterar depois (definir_responsavel_demanda).
    if era_novo and not indicacao.responsavel_demanda_id:
        perfil_criador = getattr(request.user, 'perfil', None)
        if perfil_criador and perfil_criador.colaborador_id:
            indicacao.responsavel_demanda_id = perfil_criador.colaborador_id
            indicacao.save(update_fields=['responsavel_demanda'])

    # alex: "Data/hora do cadastro" é gerado automatica
    if indicacao.carimbo_data_hora is None:
        indicacao.carimbo_data_hora = timezone.now()
        indicacao.save(update_fields=['carimbo_data_hora'])

    # Ao salvar, libera a trava de "uso" do registro (quem salvou terminou de mexer).
    if indicacao.atendimento_por or indicacao.atendimento_em:
        indicacao.atendimento_por = None
        indicacao.atendimento_em = None
        indicacao.save(update_fields=['atendimento_por', 'atendimento_em'])

    # Base Novo não mexe em ligação: preserva o histórico já registado no card "Novo".
    if not processar_ligacoes:
        return None, ''

    # salva quem ABRIU cada ligação (cadastrado_por), por protocolo
    cadastrado_por_original = {
        prot: cad
        for prot, cad in indicacao.ligacoes.values_list('protocolo', 'cadastrado_por')
        if prot
    }

    indicacao.ligacoes.all().delete()

    def salvar_ligacao(sufixo=''):
        data_val = request.POST.get(f'ligacao_data{sufixo}')
        status_val = request.POST.get(f'ligacao_status{sufixo}')
        proximo_val = request.POST.get(f'ligacao_proximo{sufixo}')
        obs_val = request.POST.get(f'ligacao_obs{sufixo}')
        ramal_val = request.POST.get(f'ligacao_ramal{sufixo}')
        venda_central_val = request.POST.get(f'ligacao_venda_central{sufixo}') == 'on'
        agn_val = request.POST.get(f'ligacao_agn{sufixo}') == 'on'
        motivo_val = request.POST.get(f'ligacao_motivo_nao_venda{sufixo}')
        seguradora_val = request.POST.get(f'ligacao_seguradora{sufixo}')

        # Comissão em %: aceita o formato milhar/decimal do pt-BR e é limitada a 0-65.
        comissao_val = _parse_valor_moeda_brl(request.POST.get(f'ligacao_comissao{sufixo}'))
        if comissao_val is not None:
            if comissao_val < 0:
                comissao_val = 0
            elif comissao_val > 65:
                comissao_val = 65

        # o "Prêmio Total" só vem no POST quando "Vendas Central" ou "Vendas Agência" está marcado
        premio_total_val = _parse_valor_moeda_brl(request.POST.get(f'ligacao_premio_total{sufixo}')) if (venda_central_val or agn_val) else None
        if not any([data_val, status_val, proximo_val, obs_val, ramal_val,
                    venda_central_val, agn_val, motivo_val, seguradora_val, comissao_val]):
            return

        # o protocolo já vem gerado do html (ao criar a ligação), mas se
        protocolo_val = request.POST.get(f'ligacao_protocolo{sufixo}')
        protocolo_existente = bool(protocolo_val) and protocolo_val in cadastrado_por_original
        if not protocolo_val or model_ligacao.objects.filter(protocolo=protocolo_val).exists():
            protocolo_val = model_ligacao.gerar_proximo_protocolo()
            protocolo_existente = False

        # Mantém quem abriu a ligação: se o protocolo já existia, preserva o responsável
        cadastrado_por_val = (
            cadastrado_por_original.get(protocolo_val)
            if protocolo_existente else None
        ) or (request.user.get_full_name() or request.user.username)

        model_ligacao.objects.create(
            indicacao=indicacao,
            protocolo=protocolo_val,
            data_ligacao=data_val or None,
            status=status_val or None,
            proximo_contato=proximo_val or None,
            observacoes=obs_val or None,
            ramal=ramal_val or None,
            venda_central=venda_central_val,
            premio_total=premio_total_val,
            agn=agn_val,
            motivo_nao_venda=motivo_val or None,
            seguradora_id=seguradora_val or None,
            comissao=comissao_val,
            cadastrado_por=cadastrado_por_val,
        )

    salvar_ligacao()
    contador = 2
    while True:
        sufixo = f'_{contador}'
        if request.POST.get(f'ligacao_data{sufixo}') is None \
           and request.POST.get(f'ligacao_status{sufixo}') is None \
           and request.POST.get(f'ligacao_proximo{sufixo}') is None \
           and request.POST.get(f'ligacao_obs{sufixo}') is None \
           and request.POST.get(f'ligacao_ramal{sufixo}') is None \
           and request.POST.get(f'ligacao_motivo_nao_venda{sufixo}') is None:
            break
        salvar_ligacao(sufixo)
        contador += 1

    return None, ''


@login_required
@cache_navegador_vendas(TABELAS_NOVO)
def lista_base_novo(request):
    # validador cpf alex: nega acesso a quem o Usuários deixou sem permissão neste card
    if _nivel_vendas(request.user, 'prod_vendas_basenovo') == 0:
        messages.error(request, 'Acesso Negado.')
        return redirect('producao_vendas')
    if request.method == 'POST':
        # trava os dados (só salvam via "Editar dados"), mas PROCESSA as ligações
        form, erro_formulario_msg = _salvar_indicacao_e_ligacoes(request, processar_ligacoes=True, travar_dados=True, campo_permissao='prod_vendas_basenovo')
        if form is None:
            return redirect('lista_base_novo')
    else:
        form = IndicacaoForm()
        erro_formulario_msg = ''

    indicacoes = list(
        Indicacao.objects.all().order_by('-id')
        #.select_related('seguradora', 'ramo', 'tipo_documento', 'responsavel_demanda')
        .select_related('ramo', 'responsavel_demanda', 'seguradora', 'tipo_documento')
        .prefetch_related(Prefetch('ligacoes', queryset=LigacaoIndicacao.objects.select_related('seguradora')))
    )
    # Nome da agência (tabela Unidade) para concatenar "CID - Nome" na lista, igual ao Novo
    cids = {(i.cid_agencia or '').strip() for i in indicacoes if i.cid_agencia}
    mapa_agencia = {u.cid_unidade: u.unidade for u in Unidade.objects.filter(cid_unidade__in=cids)} if cids else {}
    limite_atend = timezone.now() - timedelta(seconds=ATENDIMENTO_TIMEOUT_SEG)
    for ind in indicacoes:
        ind.nome_agencia = mapa_agencia.get((ind.cid_agencia or '').strip(), '')
        ind.atendimento_ativo = bool(ind.atendimento_por and ind.atendimento_em and ind.atendimento_em >= limite_atend)
        ind.status_fechamento = _status_fechamento_indicacao(ind)
        ind.responsavel_ultima_ligacao = _responsavel_ultima_ligacao(ind)

    return render(request, 'core/producao/vendas/base_novo.html', {
        'indicacoes': indicacoes,
        'form_indicacao': form,
        'erro_formulario_msg': erro_formulario_msg,
        'motivos_nao_venda': LigacaoIndicacao.MOTIVO_NAO_VENDA,
        # alex: seguradoras para o dropdown da LIGAÇÃO (relacionamento só na ligação)
        'seguradoras': Seguradora.objects.all().order_by('seguradora'),
        # Permissões deste card usam o campo do "Base Novo" (prod_vendas_basenovo).
        'usuario_gestor': _usuario_e_gestor(request.user, 'prod_vendas_basenovo'),
        'usuario_pode_editar': _usuario_pode_editar_dados(request.user, 'prod_vendas_basenovo'),
        'usuario_pode_excluir': _usuario_pode_excluir(request.user, 'prod_vendas_basenovo'),
        'colaboradores_demanda': Colaborador.objects.filter(inativo=False).order_by('colaborador'),
        # alex: autocomplete do campo Agência (Unidade: "CID - nome")
        'unidades_agencia': Unidade.objects.filter(inativada=False).order_by('cid_unidade'),
    })

# alex: as 3 "origens" de venda que alimentam a Emissão quando a venda é fechada
# (Central/Agência). Cada uma tem tabela própria (Indicacao/IndicacaoRenovacao/
# IndicacaoEndosso) - a Emissão só LÊ e edita os dados de apólice, sem duplicar nada.
ORIGENS_EMISSAO = {
    'novo': (Indicacao, LigacaoIndicacao, IndicacaoForm),
    'renovacao': (IndicacaoRenovacao, LigacaoRenovacao, IndicacaoRenovacaoForm),
    'endosso': (IndicacaoEndosso, LigacaoEndosso, IndicacaoEndossoForm),
}

# alex: status que "finalizam" a venda (regras emitida/recusada/cancelado do cadastro Base > Formulários
# > Status das emissões) - ela sai da Emissão (continua na Base Emissão) assim que, além do status,
# o cliente também já foi avisado (ver status_emissao_cliente_ciente).
REGRAS_EMISSAO_FINALIZADAS = StatusEmissao.REGRAS_FINALIZADAS

def _anexar_acompanhamentos(registros, origem):
    """Pendura em cada registro a lista 'acompanhamentos' (mais recente primeiro), o
    'status_emissao' atual (nome do status do último acompanhamento; 'Aguardando emissão' se não
    houver), a 'status_emissao_regra' (chave interna do status, que manda nas regras) e o
    'status_emissao_cliente_ciente' (o retorno do último acompanhamento avisou o cliente? - gravado
    no campo 'apolice_enviada')."""
    ids = [r.id for r in registros]
    por_registro = defaultdict(list)
    if ids:
        consulta = AcompanhamentoEmissao.objects.filter(origem=origem, registro_id__in=ids).select_related('status_ref', 'retorno_ref')
        for a in consulta:
            por_registro[a.registro_id].append(a)
    for r in registros:
        lista = sorted(por_registro.get(r.id, []), key=lambda a: (a.data_registro, a.id), reverse=True)
        r.acompanhamentos = lista
        r.status_emissao = lista[0].status_exibicao if lista else AcompanhamentoEmissao.STATUS_AGUARDANDO
        r.status_emissao_regra = lista[0].regra if lista else StatusEmissao.REGRA_AGUARDANDO
        r.status_emissao_cliente_ciente = bool(lista[0].apolice_enviada) if lista else False

def _nome_parece_banseg(seguradora):
    """Regra pelo nome, usada só enquanto ninguém escolheu a seguradora no botão do
    Banseg: 'BANESTES', 'Banestes Seguros' (com ou sem acento/maiúscula, com 'S.A.'
    no fim etc.) e 'Banseg'. Outras empresas do grupo (ex.: Banestes Capitalização)
    NÃO entram."""
    nome = _texto_comparavel(getattr(seguradora, 'seguradora', '') or '')
    return nome == 'BANESTES' or 'BANESTES SEGUROS' in nome or 'BANSEG' in nome

def _gestor_banseg(user):
    """Quem pode relacionar as seguradoras ao Banseg: superusuário (acesso total) ou quem
    tem o perfil Gestor (nível 3) na Emissão ou na Base Emissão."""
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfil', None)
    if not perfil:
        return False
    return any(int(getattr(perfil, campo, 0) or 0) == 3 for campo in ('prod_vendas_emissao', 'prod_vendas_baseemissao'))

def _eh_seguradora_banseg(seguradora):
    """A seguradora vai pro Banseg? Vale o que foi escolhido no botão do Banseg (campo
    'banseg' da seguradora); se ainda não foi escolhido, vale a regra pelo nome."""
    if seguradora is None:
        return False
    if seguradora.banseg is not None:
        return seguradora.banseg
    return _nome_parece_banseg(seguradora)

def _seguradora_da_venda(ind):
    """Seguradora que vale para a venda na Emissão. Ela pode estar em dois lugares: no
    Bloco Apólice da ficha e na última ligação (onde a venda foi fechada). Se qualquer
    um dos dois for Banestes, vale ele (a venda vai pro card Banseg); senão vale o da
    ficha e, na falta dele, o da última ligação."""
    ligacoes = list(ind.ligacoes.all())
    ultima = max(ligacoes, key=lambda l: l.id) if ligacoes else None
    candidatas = [sg for sg in (ind.seguradora, ultima.seguradora if ultima else None) if sg]
    for sg in candidatas:
        if _eh_seguradora_banseg(sg):
            return sg
    return candidatas[0] if candidatas else None

def _vendas_fechadas(model_indicacao, model_ligacao, origem):
    """Registros com venda fechada (última ligação Central/Agência) de UMA origem,
    já com os campos auxiliares (nome_agencia, status_fechamento etc.) calculados."""
    ultima_ligacao = model_ligacao.objects.filter(indicacao=OuterRef('pk')).order_by('-id')
    registros = list(
        model_indicacao.objects.annotate(
            ultima_central=Subquery(ultima_ligacao.values('venda_central')[:1]),
            ultima_agn=Subquery(ultima_ligacao.values('agn')[:1]),
        ).filter(
            Q(ultima_central=True) | Q(ultima_agn=True)
        ).select_related('ramo', 'responsavel_demanda', 'seguradora', 'tipo_documento').prefetch_related(Prefetch('ligacoes', queryset=model_ligacao.objects.select_related('seguradora')))
    )
    cids = {(i.cid_agencia or '').strip() for i in registros if i.cid_agencia}
    mapa_agencia = {u.cid_unidade: u.unidade for u in Unidade.objects.filter(cid_unidade__in=cids)} if cids else {}
    limite_atend = timezone.now() - timedelta(seconds=ATENDIMENTO_TIMEOUT_SEG)
    for ind in registros:
        ind.origem = origem
        ind.nome_agencia = mapa_agencia.get((ind.cid_agencia or '').strip(), '')
        ind.atendimento_ativo = bool(ind.atendimento_por and ind.atendimento_em and ind.atendimento_em >= limite_atend)
        ind.status_fechamento = _status_fechamento_indicacao(ind)
        ind.responsavel_ultima_ligacao = _responsavel_ultima_ligacao(ind)
        ind.seguradora_efetiva = _seguradora_da_venda(ind)
    _anexar_acompanhamentos(registros, origem)
    return registros

def _pode_alterar_status_emissao(user):
    """Alterar o status de um acompanhamento já registrado: só Gestor (nível 3) da Emissão ou da
    Base Emissão, ou superusuário. Editor e Leitor só registram acompanhamentos novos."""
    return _usuario_e_gestor(user, 'prod_vendas_emissao') or _usuario_e_gestor(user, 'prod_vendas_baseemissao')

def _opcoes_status_emissao():
    """Status ativos (com os retornos ativos de cada um) pro pop-up de acompanhamento. Se as
    tabelas ainda estão vazias (primeira vez depois do migrate), cria o cadastro padrão."""
    if not StatusEmissao.objects.exists():
        garantir_padroes_emissao()
    retornos_por_status = defaultdict(list)
    for r in RetornoClienteEmissao.objects.filter(inativo=False).order_by('id'):
        retornos_por_status[r.status_id].append({'id': r.id, 'texto': r.retorno, 'avisado': r.avisado})
    return [
        {'id': st.id, 'nome': st.status, 'regra': st.regra, 'bloqueio': st.bloqueio, 'retornos': retornos_por_status.get(st.id, [])}
        for st in StatusEmissao.objects.filter(inativo=False).order_by('id')
    ]

# Início do período da Emissão (Banseg / Outras cias): o que foi cadastrado antes não aparece lá.
EMISSAO_A_PARTIR_DE = date(2026, 9, 1)

def _render_emissao(request, base):
    """Monta a tela da Emissão (base=False) ou da Base Emissão (base=True). As duas mostram as
    vendas fechadas; a Base Emissão registra TUDO, a Emissão só as que ainda não foram finalizadas
    (último status diferente de Emitida/Recusada/Cancelado)."""
    campo = 'prod_vendas_baseemissao' if base else 'prod_vendas_emissao'
    rota = 'vendas_base_emissao' if base else 'vendas_emissao'
    # validador cpf alex: nega acesso a quem o Usuários deixou sem permissão neste card
    if _nivel_vendas(request.user, campo) == 0:
        messages.error(request, 'Acesso Negado.')
        return redirect('producao_vendas')
    if request.method == 'POST':
        origem = request.POST.get('origem') or 'novo'
        model_indicacao, model_ligacao, form_class = ORIGENS_EMISSAO.get(origem, ORIGENS_EMISSAO['novo'])
        form, erro_formulario_msg = _salvar_indicacao_e_ligacoes(
            request, processar_ligacoes=False, campo_permissao=campo,
            model_indicacao=model_indicacao, model_ligacao=model_ligacao, form_class=form_class,
        )
        if form is None:
            return redirect(rota)
    else:
        form = IndicacaoForm()
        erro_formulario_msg = ''

    indicacoes = (
        _vendas_fechadas(Indicacao, LigacaoIndicacao, 'novo')
        + _vendas_fechadas(IndicacaoRenovacao, LigacaoRenovacao, 'renovacao')
        + _vendas_fechadas(IndicacaoEndosso, LigacaoEndosso, 'endosso')
    )
    if not base:
        # Só sai da Emissão quando o status final foi registrado E o cliente já foi avisado
        # (campo "Apólice/endosso enviada" na Emitida, "Cliente ciente..." na Recusada/Cancelado).
        indicacoes = [
            i for i in indicacoes
            if not (i.status_emissao_regra in REGRAS_EMISSAO_FINALIZADAS and i.status_emissao_cliente_ciente)
        ]
        # A Emissão (Banseg e Outras cias) só mostra registros cadastrados a partir de setembro/2026
        # (coluna "Cadastrado em"). Os mais antigos continuam na Base Emissão.
        indicacoes = [
            i for i in indicacoes
            if not i.carimbo_data_hora or timezone.localtime(i.carimbo_data_hora).date() >= EMISSAO_A_PARTIR_DE
        ]

    # alex: card "Emissão" vira 2 botões (Banseg / Outras cias) de acordo com a
    # Seguradora de cada venda - Banseg é Banestes Seguros, o resto cai em Outras cias.
    # A seguradora pode estar no Bloco Apólice da ficha ou na última ligação (ver
    # _seguradora_da_venda): se qualquer um dos dois for Banestes, vai pro Banseg.
    cia = (request.GET.get('cia') or '').strip().lower()
    if cia == 'banseg':
        indicacoes = [i for i in indicacoes if _eh_seguradora_banseg(i.seguradora_efetiva)]
    elif cia == 'outras':
        indicacoes = [i for i in indicacoes if not _eh_seguradora_banseg(i.seguradora_efetiva)]

    indicacoes.sort(key=lambda i: i.carimbo_data_hora or timezone.now(), reverse=True)

    template = 'core/producao/vendas/base_emissao.html' if base else 'core/producao/vendas/emissao.html'
    return render(request, template, {
        'indicacoes': indicacoes,
        'cia_filtro': cia if cia in ('banseg', 'outras') else '',
        # Botão do Banseg (ao lado da lixeira): só Gestor. A lista traz todas as seguradoras,
        # já marcadas as que vão pro Banseg.
        'usuario_gestor_banseg': _gestor_banseg(request.user),
        # Selo do status no histórico de acompanhamentos vira botão de editar (só Gestor/superusuário).
        'usuario_pode_alterar_status': _pode_alterar_status_emissao(request.user),
        'seguradoras_banseg': [
            {'id': sg.id, 'nome': sg.seguradora or sg.cod_seguradora or f'Seguradora {sg.id}', 'marcada': _eh_seguradora_banseg(sg)}
            for sg in Seguradora.objects.all().order_by('seguradora')
        ] if _gestor_banseg(request.user) else [],
        'form_indicacao': form,
        'erro_formulario_msg': erro_formulario_msg,
        'motivos_nao_venda': LigacaoIndicacao.MOTIVO_NAO_VENDA,
        # alex: seguradoras para o dropdown da LIGAÇÃO (relacionamento só na ligação)
        'seguradoras': Seguradora.objects.all().order_by('seguradora'),
        'modo_emissao': True,
        'modo_base_emissao': base,
        # Opções do pop-up "Registrar acompanhamento da Emissão" (só os ATIVOS), vindas de
        # Base > Formulários > Status das emissões e Retorno ao cliente das emissões.
        'status_emissao_opcoes': _opcoes_status_emissao(),
        # Permissões de cada card usam o próprio campo (Emissão x Base Emissão).
        'usuario_gestor': _usuario_e_gestor(request.user, campo),
        'usuario_pode_editar': _usuario_pode_editar_dados(request.user, campo),
        'usuario_pode_excluir': _usuario_pode_excluir(request.user, campo),
        'colaboradores_demanda': Colaborador.objects.filter(inativo=False).order_by('colaborador'),
        # alex: autocomplete do campo Agência (Unidade: "CID - nome")
        'unidades_agencia': Unidade.objects.filter(inativada=False).order_by('cid_unidade'),
    })

@login_required
@cache_navegador_vendas(TABELAS_EMISSAO)
def vendas_emissao(request):
    """Card 'Emissão': só as vendas fechadas que ainda NÃO foram finalizadas (último
    acompanhamento diferente de Emitida/Recusada/Cancelado). Junta as 3 origens (Novo, Renovação,
    Endosso) - nada é duplicado no banco, cada linha mantém a sua origem."""
    return _render_emissao(request, base=False)

@login_required
@cache_navegador_vendas(TABELAS_EMISSAO)
def vendas_base_emissao(request):
    """Card 'Base Emissão': TODAS as vendas fechadas (inclusive as já emitidas/recusadas)."""
    return _render_emissao(request, base=True)

@login_required
def salvar_banseg_emissao(request):
    """Grava quais seguradoras vão pro card Banseg da Emissão (as outras ficam em Outras cias).
    Só superusuário ou quem tem o perfil Gestor da Emissão/Base Emissão."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    user = request.user
    if not _gestor_banseg(user):
        return JsonResponse({'ok': False, 'erro': 'Apenas usuários Gestor podem escolher as seguradoras do Banseg.'}, status=403)

    ids = [i for i in request.POST.getlist('seguradoras') if i.isdigit()]
    with transaction.atomic():
        Seguradora.objects.filter(id__in=ids).update(banseg=True)
        Seguradora.objects.exclude(id__in=ids).update(banseg=False)
    nomes = list(Seguradora.objects.filter(id__in=ids).order_by('seguradora').values_list('seguradora', flat=True))
    registrar_auditoria_backend(usuario=user, acao='Alterou', detalhe='Seguradoras do Banseg (Emissão): ' + (', '.join(n or '-' for n in nomes) or 'nenhuma'))
    return JsonResponse({'ok': True})

@login_required
def salvar_acompanhamento_emissao(request):
    """Registra um novo acompanhamento da emissão (data e atendente são automáticos). Com
    'acompanhamento_id' no POST, ALTERA um acompanhamento já registrado (status, retorno, datas,
    observação, anexo) - isso só Gestor/superusuário pode, e fica na Auditoria."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    user = request.user
    if not (_usuario_pode_editar_dados(user, 'prod_vendas_emissao') or _usuario_pode_editar_dados(user, 'prod_vendas_baseemissao')):
        return JsonResponse({'ok': False, 'erro': 'Você não tem permissão para registrar o acompanhamento.'}, status=403)

    origem = request.POST.get('origem') or ''
    registro_id = request.POST.get('registro_id') or ''
    if origem not in ORIGENS_EMISSAO or not registro_id.isdigit():
        return JsonResponse({'ok': False, 'erro': 'Registro inválido.'}, status=400)
    if not ORIGENS_EMISSAO[origem][0].objects.filter(id=registro_id).exists():
        return JsonResponse({'ok': False, 'erro': 'Registro não encontrado.'}, status=404)

    # Alterar um acompanhamento que já existe (em vez de registrar um novo): só Gestor/superusuário.
    editando = None
    acompanhamento_id = request.POST.get('acompanhamento_id') or ''
    if acompanhamento_id:
        if not _pode_alterar_status_emissao(user):
            return JsonResponse({'ok': False, 'erro': 'Apenas Gestor ou superusuário podem alterar o status de um acompanhamento.'}, status=403)
        if acompanhamento_id.isdigit():
            editando = AcompanhamentoEmissao.objects.select_related('status_ref', 'retorno_ref').filter(
                id=acompanhamento_id, origem=origem, registro_id=int(registro_id)).first()
        if not editando:
            return JsonResponse({'ok': False, 'erro': 'Acompanhamento não encontrado.'}, status=404)

    # Status e Retorno vêm dos cadastros de Base > Formulários (só os ATIVOS valem).
    status_id = request.POST.get('status_id') or ''
    status = StatusEmissao.objects.filter(id=status_id, inativo=False).first() if status_id.isdigit() else None
    # Status com Bloqueio só fica de fora ao alterar um acompanhamento que NÃO é o último (o
    # próprio status dele continua valendo). Novo acompanhamento e o último veem a lista completa.
    if status and status.bloqueio and editando and editando.status_ref_id != status.id:
        ultimo = AcompanhamentoEmissao.objects.filter(origem=origem, registro_id=int(registro_id)).order_by('-data_registro', '-id').first()
        if ultimo and ultimo.id != editando.id:
            status = None
    if not status:
        return JsonResponse({'ok': False, 'erro': 'Selecione o status.'}, status=400)

    retornos_ativos = list(status.retornos.filter(inativo=False))
    retorno = None
    if retornos_ativos:
        retorno_id = request.POST.get('retorno_id') or ''
        retorno = next((r for r in retornos_ativos if str(r.id) == retorno_id), None)
        if not retorno:
            return JsonResponse({'ok': False, 'erro': 'Selecione o retorno ao cliente.'}, status=400)
    cliente_avisado = bool(retorno and retorno.avisado)

    def _data(nome):
        valor = (request.POST.get(nome) or '').strip()
        if not valor:
            return None
        try:
            return datetime.strptime(valor, '%Y-%m-%d').date()
        except ValueError:
            return None

    data_envio = _data('data_envio_cliente') if cliente_avisado else None
    if cliente_avisado and not data_envio:
        return JsonResponse({'ok': False, 'erro': 'Informe a data de envio ao cliente.'}, status=400)

    data_emissao, numero_apolice = None, ''
    if status.regra == StatusEmissao.REGRA_EMITIDA:
        data_emissao = _data('data_emissao')
        numero_apolice = (request.POST.get('numero_apolice') or '').strip()
        if not data_emissao:
            return JsonResponse({'ok': False, 'erro': 'Informe a data de emissão.'}, status=400)
        if not numero_apolice:
            return JsonResponse({'ok': False, 'erro': 'Informe o número da apólice.'}, status=400)

    # Número do endosso: só quando a venda vem do Endosso e o cliente foi avisado ("Sim"/"enviada").
    # Obrigatório na Emitida; nas outras regras é opcional.
    numero_endosso = ''
    if origem == 'endosso' and cliente_avisado:
        numero_endosso = (request.POST.get('numero_endosso') or '').strip()[:50]
        if status.regra == StatusEmissao.REGRA_EMITIDA and not numero_endosso:
            return JsonResponse({'ok': False, 'erro': 'Informe o número do endosso.'}, status=400)

    # Anexo (PDF ou imagem): so vale para as regras recusada/cancelado e e opcional.
    anexo = request.FILES.get('anexo') if status.regra in StatusEmissao.REGRAS_COM_ANEXO else None
    # Só ao alterar um acompanhamento (Gestor): apagar o anexo que já existe, sem trocar por outro.
    remover_anexo = bool(editando and request.POST.get('remover_anexo') == '1'
                         and status.regra in StatusEmissao.REGRAS_COM_ANEXO)
    if anexo:
        erro_anexo = _validar_anexo_emissao(anexo)
        if erro_anexo:
            return JsonResponse({'ok': False, 'erro': erro_anexo}, status=400)

    if editando:
        antes = f'{editando.status_exibicao} / {editando.retorno_cliente_texto or "-"}'
        editando.observacao = (request.POST.get('observacao') or '').strip()
        editando.status = status.status
        editando.status_ref = status
        editando.retorno_ref = retorno
        editando.apolice_enviada = cliente_avisado
        editando.data_envio_cliente = data_envio
        editando.data_emissao = data_emissao
        editando.numero_apolice = numero_apolice
        editando.numero_endosso = numero_endosso
        # Anexo: arquivo novo SUBSTITUI o atual (o antigo é apagado da pasta, qualquer que seja o
        # tipo: imagem -> PDF também vale); "apagar" remove o arquivo da pasta e limpa o campo.
        if anexo or remover_anexo:
            if editando.anexo:
                editando.anexo.delete(save=False)
            editando.anexo = None
            editando.anexo_nome = ''
        if anexo:
            editando.anexo.save(anexo.name, anexo, save=False)  # grava como ANX-<id>.<ext>
            editando.anexo_nome = os.path.basename(editando.anexo.name)
        editando.save()
        registrar_auditoria_backend(
            usuario=user, acao='Alterou',
            detalhe=f'Acompanhamento da Emissão #{editando.id} ({origem}:{registro_id}): {antes} -> {status.status} / {retorno.retorno if retorno else "-"}',
        )
        return JsonResponse({'ok': True})

    acompanhamento = AcompanhamentoEmissao(
        origem=origem,
        registro_id=int(registro_id),
        atendente=atendente_do_usuario(user),
        observacao=(request.POST.get('observacao') or '').strip(),
        status=status.status,
        status_ref=status,
        retorno_ref=retorno,
        apolice_enviada=cliente_avisado,
        data_envio_cliente=data_envio,
        data_emissao=data_emissao,
        numero_apolice=numero_apolice,
        numero_endosso=numero_endosso,
    )
    acompanhamento.save()
    if anexo:
        # Só agora existe o ID do acompanhamento, que dá o nome do arquivo (ANX-<id>.<ext>).
        acompanhamento.anexo.save(anexo.name, anexo, save=False)
        acompanhamento.anexo_nome = os.path.basename(acompanhamento.anexo.name)
        acompanhamento.save(update_fields=['anexo', 'anexo_nome'])
    return JsonResponse({'ok': True})


# --- Anexos do acompanhamento da Emissão (PDF ou imagem) ---
ANEXO_EMISSAO_TAMANHO_MAX = 10 * 1024 * 1024  # 10 MB
# extensao -> (tipo do arquivo, inicios validos do conteudo). O conteudo e conferido
# de verdade (nao so o nome) pra ninguem enviar outro tipo de arquivo renomeado.
ANEXO_EMISSAO_TIPOS = {
    '.pdf': ('application/pdf', (b'%PDF-',)),
    '.jpg': ('image/jpeg', (b'\xff\xd8\xff',)),
    '.jpeg': ('image/jpeg', (b'\xff\xd8\xff',)),
    '.png': ('image/png', (b'\x89PNG\r\n\x1a\n',)),
    '.gif': ('image/gif', (b'GIF87a', b'GIF89a')),
    '.webp': ('image/webp', (b'RIFF',)),
}

def _validar_anexo_emissao(arquivo):
    """Devolve o texto do erro, ou '' se o anexo pode ser gravado."""
    extensao = os.path.splitext(arquivo.name)[1].lower()
    if extensao not in ANEXO_EMISSAO_TIPOS:
        return 'O anexo precisa ser um PDF ou uma imagem (JPG, PNG, GIF ou WEBP).'
    if arquivo.size > ANEXO_EMISSAO_TAMANHO_MAX:
        return 'O anexo é maior que 10 MB. Envie um arquivo menor.'
    if arquivo.size == 0:
        return 'O anexo está vazio.'
    inicio = arquivo.read(16)
    arquivo.seek(0)
    if not inicio.startswith(ANEXO_EMISSAO_TIPOS[extensao][1]):
        return 'O conteúdo do arquivo não bate com o tipo informado. Envie um PDF ou uma imagem de verdade.'
    if extensao == '.webp' and inicio[8:12] != b'WEBP':
        return 'O conteúdo do arquivo não bate com o tipo informado. Envie um PDF ou uma imagem de verdade.'
    return ''

@login_required
def anexo_acompanhamento_emissao(request, id):
    """Abre o anexo de um acompanhamento (so quem tem acesso a Emissao/Base Emissao)."""
    user = request.user
    if _nivel_vendas(user, 'prod_vendas_emissao') == 0 and _nivel_vendas(user, 'prod_vendas_baseemissao') == 0:
        return HttpResponse('Acesso negado.', status=403)
    acompanhamento = get_object_or_404(AcompanhamentoEmissao, id=id)
    if not acompanhamento.anexo:
        return HttpResponse('Este acompanhamento não tem anexo.', status=404)
    try:
        arquivo = acompanhamento.anexo.open('rb')
    except FileNotFoundError:
        return HttpResponse('O arquivo do anexo não foi encontrado no servidor.', status=404)
    extensao = os.path.splitext(acompanhamento.anexo.name)[1].lower()
    tipo = ANEXO_EMISSAO_TIPOS.get(extensao, ('application/octet-stream',))[0]
    resposta = FileResponse(arquivo, content_type=tipo)
    nome = acompanhamento.anexo_nome or os.path.basename(acompanhamento.anexo.name)
    resposta['Content-Disposition'] = "inline; filename*=UTF-8''" + quote(nome)
    resposta['X-Content-Type-Options'] = 'nosniff'
    resposta['Cache-Control'] = 'private, no-store'
    return resposta

@login_required
@cache_navegador_vendas(TABELAS_RENOVACAO)
def vendas_renovacao(request):
    """Card 'Base Renovação'. Mesma lógica do Base Novo, mas na tabela própria
    IndicacaoRenovacao/LigacaoRenovacao (não mistura os dados com o Base Novo)."""
    # validador cpf alex: nega acesso a quem o Usuários deixou sem permissão neste card
    if _nivel_vendas(request.user, 'prod_vendas_baserenovacao') == 0:
        messages.error(request, 'Acesso Negado.')
        return redirect('producao_vendas')
    if request.method == 'POST':
        form, erro_formulario_msg = _salvar_indicacao_e_ligacoes(
            request, processar_ligacoes=True, travar_dados=True,
            campo_permissao='prod_vendas_baserenovacao',
            model_indicacao=IndicacaoRenovacao, model_ligacao=LigacaoRenovacao,
            form_class=IndicacaoRenovacaoForm,
        )
        if form is None:
            return redirect('vendas_renovacao')
    else:
        form = IndicacaoRenovacaoForm()
        erro_formulario_msg = ''

    indicacoes = list(
        IndicacaoRenovacao.objects.all().order_by('-id')
        .select_related('ramo', 'responsavel_demanda', 'seguradora', 'tipo_documento')
        .prefetch_related(Prefetch('ligacoes', queryset=LigacaoRenovacao.objects.select_related('seguradora')))
    )
    cids = {(i.cid_agencia or '').strip() for i in indicacoes if i.cid_agencia}
    mapa_agencia = {u.cid_unidade: u.unidade for u in Unidade.objects.filter(cid_unidade__in=cids)} if cids else {}
    limite_atend = timezone.now() - timedelta(seconds=ATENDIMENTO_TIMEOUT_SEG)
    for ind in indicacoes:
        ind.nome_agencia = mapa_agencia.get((ind.cid_agencia or '').strip(), '')
        ind.atendimento_ativo = bool(ind.atendimento_por and ind.atendimento_em and ind.atendimento_em >= limite_atend)
        ind.status_fechamento = _status_fechamento_indicacao(ind)
        ind.responsavel_ultima_ligacao = _responsavel_ultima_ligacao(ind)

    return render(request, 'core/producao/vendas/base_renovacao.html', {
        'indicacoes': indicacoes,
        'form_indicacao': form,
        'erro_formulario_msg': erro_formulario_msg,
        'motivos_nao_venda': LigacaoRenovacao.MOTIVO_NAO_VENDA,
        'seguradoras': Seguradora.objects.all().order_by('seguradora'),
        'usuario_gestor': _usuario_e_gestor(request.user, 'prod_vendas_baserenovacao'),
        'usuario_pode_editar': _usuario_pode_editar_dados(request.user, 'prod_vendas_baserenovacao'),
        'usuario_pode_excluir': _usuario_pode_excluir(request.user, 'prod_vendas_baserenovacao'),
        'colaboradores_demanda': Colaborador.objects.filter(inativo=False).order_by('colaborador'),
        'unidades_agencia': Unidade.objects.filter(inativada=False).order_by('cid_unidade'),
    })
