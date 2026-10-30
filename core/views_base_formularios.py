from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import (
    UnidadeForm, ProdutoForm, MetaMensalForm, AgrupamentoForm, RamoForm, ColaboradorForm,
    ContratadoForm, SeguradoraForm, TipoDocumentoForm, ClienteForm, EstadoAnbimaForm,
    FundoAnbimaForm, StatusEmissaoForm, RetornoClienteEmissaoForm,
)
from .models import (
    Unidade, Produto, MetaMensal, Agrupamento, Ramo, Colaborador, Contratado, Seguradora,
    TipoDocumento, Cliente, TipoPessoa, EstadoAnbima, FundoAnbima, StatusEmissao,
    RetornoClienteEmissao,
)

# Aba Base > Formulários: a tela com os cards e a lista/cadastro de cada card (Unidades,
# Colaboradores, Contratados, Seguradoras, Tipos documento, Ramos, Produtos, Agrupamentos, Metas,
# Tipos de pessoa, Clientes, Regiões e Fundos ANBIMA, Status e Retorno ao cliente das emissões).
# (Mesma organização de views_vendas.py e views_usuarios.py. A exclusão em massa e o "apagar
# tudo" continuam em views.py porque também atendem outras telas.)


@login_required  
def base_formularios(request):

    # negar acesos aos perfil usuario
    user = request.user
    tem_permissao_base = False

    if not user.is_superuser and hasattr(user, 'perfil'):
        tem_permissao_base = any(
            valor > 0 
            for campo, valor in user.perfil.__dict__.items() 
            if campo.startswith('base_form_') and isinstance(valor, int)
        )

    if not (user.is_superuser or tem_permissao_base):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')


    return render(request, 'core/base/formularios/base_formularios.html')


# 2. LISTAGENS E CADASTROS

# --- AGRUPAMENTOS ---
@login_required
def lista_agrupamentos(request):

    # ---- Parte de negar acesso quem não pode ----
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_agrupamentos > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    #----

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(Agrupamento, id=item_id) if item_id else None
        form = AgrupamentoForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_agrupamentos')
    else:
        form = AgrupamentoForm()

    agrupamentos = Agrupamento.objects.all().order_by('id')
    return render(request, 'core/base/formularios/agrupamentos.html', {'agrupamentos': agrupamentos, 'form_agrupamento': form})


# --- AGÊNCIAS (Antiga Unidades) ---
@login_required
def lista_unidades(request):


    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_unidade > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')



    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(Unidade, id=item_id) if item_id else None
        form = UnidadeForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_unidades')
    else:
        form = UnidadeForm()

    unidades = Unidade.objects.all().order_by('-id')
    
    return render(request, 'core/base/formularios/unidades.html', {'unidades': unidades, 'form_unidade': form})


# --- PRODUTOS ---
@login_required
def lista_produtos(request):


    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_produtos > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    #-----

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(Produto, id=item_id) if item_id else None
        form = ProdutoForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_produtos')
    else:
        form = ProdutoForm()
        
    items = Produto.objects.select_related('agrupamento').all().order_by('produto')
    
    return render(request, 'core/base/formularios/produtos.html', {'produtos': items, 'form_produto': form})


# --- RAMOS ---
@login_required
def lista_ramos(request):

    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_ramos > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(Ramo, id=item_id) if item_id else None
        form = RamoForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_ramos')
    else:
        form = RamoForm()
        
 
    items = Ramo.objects.select_related('produto').all().order_by('grupo_e_ramo')
    
    return render(request, 'core/base/formularios/ramos.html', {'ramos': items, 'form_ramo': form})


# --- METAS ---
@login_required
def lista_metas(request):

    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_metas > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    # ----

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(MetaMensal, id=item_id) if item_id else None
        form = MetaMensalForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_metas')
    else:
        form = MetaMensalForm()

    metas = MetaMensal.objects.select_related('unidade', 'produto').all().order_by('-id')
    return render(request, 'core/base/formularios/metas.html', {'metas': metas, 'form_meta': form})


@login_required
def lista_colaboradores(request):

    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_colaboradores > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    # ----

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(Colaborador, id=item_id) if item_id else None
        form = ColaboradorForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_colaboradores')
    else:
        form = ColaboradorForm()
        
    items = Colaborador.objects.select_related('unidade').all().order_by('colaborador')
    
    return render(request, 'core/base/formularios/colaboradores.html', {'colaboradores': items, 'form_colaborador': form})


@login_required
def lista_contratados(request):

    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_contratados > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    # ----

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(Contratado, id=item_id) if item_id else None
        form = ContratadoForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_contratados')
    else:
        form = ContratadoForm()
    items = Contratado.objects.all().order_by('contratado')
    return render(request, 'core/base/formularios/contratados.html', {'contratados': items, 'form_contratado': form})


@login_required
def lista_seguradoras(request):

    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_seguradoras > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    # ----


    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(Seguradora, id=item_id) if item_id else None
        form = SeguradoraForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_seguradoras')
    else:
        form = SeguradoraForm()
    items = Seguradora.objects.all().order_by('seguradora')
    return render(request, 'core/base/formularios/seguradoras.html', {'seguradoras': items, 'form_seguradora': form})


def _nivel_base_form(user, campo):
    """Nível (0-3) do usuário num card de Base > Formulários. Superusuário = 3."""
    if user.is_superuser:
        return 3
    perfil = getattr(user, 'perfil', None)
    return int(getattr(perfil, campo, 0) or 0) if perfil else 0


def _lista_cadastro_emissao(request, campo, form_class, model, rota, template, contexto_form, itens):
    """Base comum dos cards "Status das emissões" e "Retorno ao cliente das emissões".
    Ver 1 = leitor, criar >= 2 (Editor), editar um existente >= 3 (Gestor)."""
    user = request.user
    nivel = _nivel_base_form(user, campo)
    if nivel == 0:
        messages.error(request, 'Acesso Negado.')
        return redirect('home')

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        if nivel < (3 if item_id else 2):
            messages.error(request, 'Acesso Negado.')
            return redirect(rota)
        instancia = get_object_or_404(model, id=item_id) if item_id else None
        form = form_class(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect(rota)
    else:
        form = form_class()
    return render(request, template, {contexto_form: form, 'itens': itens})


@login_required
def lista_status_emissao(request):
    """Base > Formulários > Status das emissões (opções do campo Status da Emissão)."""
    from .emissao_padroes import garantir_padroes_emissao
    if not StatusEmissao.objects.exists():
        garantir_padroes_emissao()
    return _lista_cadastro_emissao(
        request, 'base_form_status_emissao', StatusEmissaoForm, StatusEmissao, 'lista_status_emissao',
        'core/base/formularios/status_emissao.html', 'form_status',
        StatusEmissao.objects.all().order_by('id'),
    )


@login_required
def lista_retorno_emissao(request):
    """Base > Formulários > Retorno ao cliente das emissões (respostas de cada Status)."""
    from .emissao_padroes import garantir_padroes_emissao
    if not StatusEmissao.objects.exists():
        garantir_padroes_emissao()
    return _lista_cadastro_emissao(
        request, 'base_form_retorno_emissao', RetornoClienteEmissaoForm, RetornoClienteEmissao,
        'lista_retorno_emissao', 'core/base/formularios/retorno_emissao.html', 'form_retorno',
        RetornoClienteEmissao.objects.select_related('status').order_by('status_id', 'id'),
    )


@login_required
def lista_tiposdoc(request):

    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_tiposdocumento > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    # ----


    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(TipoDocumento, id=item_id) if item_id else None
        form = TipoDocumentoForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_tiposdoc')
    else:
        form = TipoDocumentoForm()
    items = TipoDocumento.objects.all().order_by('tipo_documento')
    return render(request, 'core/base/formularios/tiposdocumentos.html', {'tipos_documentos': items, 'form_tipodoc': form})


# --- ESTADOS ANBIMA ---
@login_required
def lista_estados_anbima(request):

    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_estados_anbima > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    # ----

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(EstadoAnbima, id=item_id) if item_id else None
        form = EstadoAnbimaForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_estados_anbima')
    else:
        form = EstadoAnbimaForm()
    items = EstadoAnbima.objects.all().order_by('ordem_apresentacao', 'uf')
    return render(request, 'core/base/formularios/estados_anbima.html', {'estados_anbima': items, 'form_estado_anbima': form})


# --- VALORES POR FUNDOS (ANBIMA) ---
@login_required
def lista_fundos_anbima(request):

    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_fundos_anbima > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    # ----

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(FundoAnbima, id=item_id) if item_id else None
        form = FundoAnbimaForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_fundos_anbima')
    else:
        form = FundoAnbimaForm()
    items = FundoAnbima.objects.all().order_by('ordem_apresentacao', 'nome_fundo')
    return render(request, 'core/base/formularios/fundos_anbima.html', {'fundos_anbima': items, 'form_fundo_anbima': form})


@login_required
def lista_clientes(request):

    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_clientes > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    # ----

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(Cliente, id=item_id) if item_id else None
        form = ClienteForm(request.POST, instance=instancia)
        if form.is_valid():
            form.save()
            return redirect('lista_clientes')
        
    else:
        form = ClienteForm()
    items = Cliente.objects.all().order_by('nome')
    return render(request, 'core/base/formularios/clientes.html', {'clientes': items, 'form_cliente': form})


@login_required
def tipo_pessoa_lista(request):


    # negar acesso ao usuario
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.base_form_tipopessoa > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    #-----

    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        if acao == 'novo':
            item_id = request.POST.get('item_id')
            nome = request.POST.get('tipo_pessoa', '').strip()
            obs = request.POST.get('observacoes', '').strip()
            
            if item_id:
                tipo = get_object_or_404(TipoPessoa, id=item_id)
                tipo.tipo_pessoa = nome
                tipo.observacoes = obs
                tipo.save()
                messages.success(request, 'Tipo de pessoa atualizado com sucesso!')
            elif nome:
                TipoPessoa.objects.create(tipo_pessoa=nome, observacoes=obs)
                messages.success(request, 'Novo tipo de pessoa cadastrado com sucesso!')
                
        elif acao == 'excluir': 
            ids_selecionados = request.POST.getlist('ids_selecionados')
            if ids_selecionados:
                TipoPessoa.objects.filter(id__in=ids_selecionados).delete()
                messages.success(request, 'Registo(s) excluído(s) com sucesso!')
                
        return redirect('tipo_pessoa_lista')

    tipos = TipoPessoa.objects.all().order_by('tipo_pessoa')
    return render(request, 'core/base/formularios/tipo_pessoa_lista.html', {'tipos': tipos})
