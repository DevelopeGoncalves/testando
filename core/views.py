from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
import csv
import openpyxl
from .models import (
    Unidade, Produto, MetaMensal, Agrupamento, Ramo, Colaborador, Contratado,
    Seguradora, TipoDocumento, Cliente, Apolice, PerfilUsuario,
    CompatibilidadeSeguradora, TipoPessoa, RegistroProducao, EndossoAdicional,
    ParametrizacaoHabitacional, Indicacao, LigacaoIndicacao, MotivoNaoVenda,
    IndicacaoExcluida,
)
from .forms import UnidadeForm, NovoUsuarioForm, ProdutoForm, MetaMensalForm, AgrupamentoForm, RamoForm, ColaboradorForm, ContratadoForm, SeguradoraForm, TipoDocumentoForm, ClienteForm, ApoliceForm, IndicacaoForm
import pandas as pd
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, OuterRef, Subquery
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.utils import timezone


def ler_excel_robusto(arquivo, dtype=None):
    """
    Lê um arquivo Excel enviado por upload tentando várias estratégias.
    Necessário porque alguns sistemas bancários (ex: Banestes) exportam
    arquivos ".xls"/".xlsx" que na verdade são tabelas em HTML, e o pandas
    não consegue identificar automaticamente o formato real do arquivo.
    """
    kwargs = {'dtype': dtype} if dtype is not None else {}

    for engine in ('openpyxl', 'xlrd'):
        try:
            arquivo.seek(0)
            return pd.read_excel(arquivo, engine=engine, **kwargs)
        except ImportError:
            continue
        except Exception:
            continue

    # Fallback: o arquivo não é um Excel de verdade, e sim uma tabela HTML
    # (comum em exportações bancárias). Lê célula a célula como texto puro,
    # sem deixar o pandas converter para número e comer zeros à esquerda
    # de códigos como CID/matrícula.
    try:
        arquivo.seek(0)
        from lxml import html as lxml_html
        tabela = lxml_html.parse(arquivo).getroot().find('.//table')
        if tabela is not None:
            todas_linhas = []
            for tr in tabela.findall('.//tr'):
                celulas = tr.findall('./td') or tr.findall('./th')
                if celulas:
                    todas_linhas.append([(cel.text_content() or '').strip() for cel in celulas])

            if len(todas_linhas) >= 2:
                cabecalho = todas_linhas[0]
                dados = [linha for linha in todas_linhas[1:] if len(linha) == len(cabecalho)]
                if dados:
                    return pd.DataFrame(dados, columns=cabecalho, dtype=str)
    except Exception:
        pass

    raise ValueError(
        'Não foi possível ler o arquivo enviado. Verifique se é uma planilha Excel '
        '(.xlsx ou .xls) válida e tente exportá-la novamente.'
    )


# 1. TELAS INICIAIS
@login_required    
def home(request):
    return render(request, 'core/home.html')

@login_required  
def base_formularios(request):
    return render(request, 'core/base/formularios/base_formularios.html')

# 2. LISTAGENS E CADASTROS

# --- AGRUPAMENTOS ---
@login_required
def lista_agrupamentos(request):
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

# 3. FUNÇÕES DE EXCLUSÃO

@login_required
def excluir_em_massa(request):
    if request.method == 'POST':
        tipo = request.POST.get('tipo_massa')
        ids = request.POST.getlist('ids_excluir')
        rota_destino = 'base_formularios' 

        if ids:
            if tipo == 'unidade':
                Unidade.objects.filter(id__in=ids).delete()
                rota_destino = 'lista_unidades'
            elif tipo == 'produto':
                Produto.objects.filter(id__in=ids).delete()
                rota_destino = 'lista_produtos'
            elif tipo == 'agrupamento': 
                Agrupamento.objects.filter(id__in=ids).delete()
                rota_destino = 'lista_agrupamentos'
            elif tipo == 'ramo': 
                Ramo.objects.filter(id__in=ids).delete()
                rota_destino = 'lista_ramos'
            elif tipo == 'colaborador': 
                Colaborador.objects.filter(id__in=ids).delete()
                rota_destino = 'lista_colaboradores'
            elif tipo == 'contratado': 
                Contratado.objects.filter(id__in=ids).delete()
                rota_destino = 'lista_contratados'
            elif tipo == 'seguradora': 
                Seguradora.objects.filter(id__in=ids).delete()
                rota_destino = 'lista_seguradoras'
            elif tipo == 'tipodoc': 
                TipoDocumento.objects.filter(id__in=ids).delete()
                rota_destino = 'lista_tiposdoc'
            elif tipo == 'cliente': 
                Cliente.objects.filter(id__in=ids).delete()
                rota_destino = 'lista_clientes'
                
            elif tipo == 'apolice_renovacao':
                Apolice.objects.filter(id__in=ids).delete()
                rota_destino = 'vendas_renovacao'
            elif tipo == 'indicacao':
                nome_usuario = request.user.get_full_name() or request.user.username
                for carimbo, email in Indicacao.objects.filter(id__in=ids).values_list('carimbo_data_hora', 'email'):
                    if carimbo is None:
                        continue
                    IndicacaoExcluida.objects.get_or_create(
                        carimbo_data_hora=carimbo,
                        email=email or '',
                        defaults={'excluido_por': nome_usuario},
                    )
                Indicacao.objects.filter(id__in=ids).delete()
                rota_destino = 'lista_base_novo'

        return redirect(rota_destino)
    return redirect('base_formularios')

@login_required
def deletar_tudo(request, tipo):
    eh_admin = request.user.is_superuser or (hasattr(request.user, 'perfil') and request.user.perfil.nivel_acesso == 'ADMIN')
    if not eh_admin:
        messages.error(request, 'Acesso negado. Apenas administradores podem apagar todos os registos.')
        return redirect('base_formularios')

    if request.method != 'POST':
        return redirect('base_formularios')

    rota_destino = 'base_formularios'

    try:
        if tipo == 'unidade':
            Unidade.objects.all().delete()
            rota_destino = 'lista_unidades'
            messages.success(request, 'Todas as unidades foram apagadas com sucesso!')
            
        elif tipo == 'colaborador':
            Colaborador.objects.all().delete()
            rota_destino = 'lista_colaboradores'
            messages.success(request, 'Todos os colaboradores foram apagados com sucesso!')
            
        
    except Exception as e:
        messages.error(request, f'Erro ao tentar limpar a tabela: {str(e)}')

    return redirect(rota_destino)

@login_required
def base_processamentos(request):
    return render(request, 'core/base/processamentos/importacao.html')

@login_required
def base_relatorios(request):
    return render(request, 'core/base/relatorios/index.html')


@login_required
def lista_colaboradores(request):
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

@login_required
def lista_tiposdoc(request):
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

@login_required
def lista_clientes(request):
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

    

# 4. MÓDULO DE PRODUÇÃO

@login_required
def producao_formularios(request):
    agrupamentos = Agrupamento.objects.filter(inativo=False).order_by('ordem_apresentacao')
    return render(request, 'core/producao/formularios/index.html', {'agrupamentos': agrupamentos})

@login_required
def producao_formularios_painel(request, agrupamento_id):
    # Pega o agrupamento exato que o usuário clicou na tela
    agrupamento = get_object_or_404(Agrupamento, id=agrupamento_id)
    
    # Prepara as consultas (QuerySets) por fase
    qs_importados = RegistroProducao.objects.filter(agrupamento=agrupamento, fase__iexact='IMPORTADOS')
    qs_pendentes = RegistroProducao.objects.filter(agrupamento=agrupamento, fase__iexact='PENDENTES')
    qs_emitidos = RegistroProducao.objects.filter(agrupamento=agrupamento, fase__iexact='EMITIDOS')

    # Contadores de quantidade
    qtd_importados = qs_importados.count()
    qtd_pendentes = qs_pendentes.count()
    qtd_emitidos = qs_emitidos.count()

    # Totalizadores financeiros: soma do Prêmio Bruto de cada registro, incluindo os endossos adicionais
    def _soma_premio_bruto(queryset):
        total_principal = queryset.aggregate(total=Sum('premio_bruto'))['total'] or 0
        total_endossos = EndossoAdicional.objects.filter(registro_pai__in=queryset).aggregate(total=Sum('premio_bruto'))['total'] or 0
        return float(total_principal) + float(total_endossos)

    valor_importados = _soma_premio_bruto(qs_importados)
    valor_pendentes = _soma_premio_bruto(qs_pendentes)
    valor_emitidos = _soma_premio_bruto(qs_emitidos)
    
    # Envia tudo pronto para o HTML
    return render(request, 'core/producao/formularios/painel.html', {
        'agrupamento': agrupamento,
        'qtd_importados': qtd_importados,
        'qtd_pendentes': qtd_pendentes,
        'qtd_emitidos': qtd_emitidos,
        'valor_importados': valor_importados,
        'valor_pendentes': valor_pendentes,
        'valor_emitidos': valor_emitidos
    })

@login_required
def producao_processamentos(request):
    if request.method == 'POST':
        agrupamento_id = request.POST.get('agrupamento_id')
        arquivo = request.FILES.get('arquivo_importacao')
        
        if arquivo:
            extensao = arquivo.name.split('.')[-1].lower()
            try:
                # 1. Leitura do arquivo
                if extensao in ['xls', 'xlsx', 'xlsm']:
                    df = ler_excel_robusto(arquivo)
                else:
                    df = pd.read_csv(arquivo, sep=';', encoding='latin-1')

                # 2. Padronização: Deixa os nomes das colunas em MAIÚSCULO para não errar o mapa como diz adriel 
                df.columns = df.columns.str.strip().str.upper()

                contador = 0
                with transaction.atomic(): # Garante que ou salva tudo ou nada
                    for index, row in df.iterrows():
                        
                        # --- MAPA DE COLUNAS ---
                        
                        # 1. CPF_CNPJ -> CPF / CNPJ
                        val_cpf_cnpj = str(row.get('CPF_CNPJ', '')).strip()
                        
                        # 2. CID -> Agência
                        val_agencia = str(row.get('CID', '')).strip()
                        
                        # 3. CONTRATO -> Contrato
                        val_contrato = str(row.get('CONTRATO', '')).strip()
                        
                        # 4. SEGURADORA -> Segurado (Como adriel pediu)
                        val_segurado = str(row.get('SEGURADORA', '')).strip()
                        
                        # 5. VLR_SEGURO -> Vlr Seguro
                        val_vlr_seguro = row.get('VLR_SEGURO', 0)
                        # Limpeza básica de valor monetário se for texto
                        if isinstance(val_vlr_seguro, str):
                            val_vlr_seguro = val_vlr_seguro.replace('R$', '').replace('.', '').replace(',', '.').strip()

                        # Gravação na nova tabela RegistroProducao
                        RegistroProducao.objects.create(
                            agrupamento_id=agrupamento_id,
                            fase='IMPORTADOS', # smp entra como importado primeiro
                            cpf_cnpj=val_cpf_cnpj[:30],
                            agencia=val_agencia[:100],
                            contrato=val_contrato[:100],
                            segurado=val_segurado[:200],
                            vlr_seguro=float(val_vlr_seguro) if val_vlr_seguro else 0,
                        )
                        contador += 1

                messages.success(request, f'Sucesso! {contador} registros importados para o card.')
                return redirect('producao_processamentos')

            except Exception as e:
                messages.error(request, f'Erro ao processar: {str(e)}')
                return redirect('producao_processamentos')

    agrupamentos = Agrupamento.objects.filter(inativo=False).order_by('ordem_apresentacao')
    return render(request, 'core/producao/processamentos/importacao.html', {'agrupamentos': agrupamentos})



@login_required
def producao_habitacional_import(request):
    campos_destino = [
        {'nome': 'mes_producao', 'label': 'Mês da produção'},
        {'nome': 'seguradora', 'label': 'Seguradora'},
        {'nome': 'grupo_ramo', 'label': 'Grupo/Ramo'},
        {'nome': 'tipo_documento', 'label': 'Tipo documento'},
        {'nome': 'documento', 'label': 'Documento'},
        {'nome': 'endosso', 'label': 'Endosso'},
        {'nome': 'qtd_parcelas', 'label': 'Qtd. parcelas'},
        {'nome': 'inicio_vigencia', 'label': 'Início de vigência'},
        {'nome': 'fim_vigencia', 'label': 'Fim de vigência'},
        {'nome': 'tipo_pessoa', 'label': 'Tipo de pessoa'},
        {'nome': 'cpf_cnpj', 'label': 'CPF / CNPJ'},
        {'nome': 'cliente', 'label': 'Cliente'},
        {'nome': 'nome_social', 'label': 'Nome social'},
        {'nome': 'celular', 'label': 'Celular'},
        {'nome': 'telefone', 'label': 'Telefone'},
        {'nome': 'email', 'label': 'E-mail'},
        {'nome': 'unidade', 'label': 'Unidade'},
        {'nome': 'superintendencia', 'label': 'Superintendência'},
        {'nome': 'gerente_agencia', 'label': 'Gerente da agência'},
        {'nome': 'grupo', 'label': 'Grupo'}, 
        {'nome': 'colaborador', 'label': 'Colaborador'},
        {'nome': 'superintendente', 'label': 'Superintendente'},
        {'nome': 'premio_bruto', 'label': 'Prêmio bruto'},
        {'nome': 'premio_liquido', 'label': 'Prêmio Líquido'}, 
        {'nome': 'perc_comissao', 'label': '% de comissão'},
        {'nome': 'realizado', 'label': 'Realizado'},
        {'nome': 'renovacao_propria', 'label': 'Renovação Própria'}, 
        {'nome': 'observacoes', 'label': 'Observações'},
    ]

    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        # --- AÇÕES DE SALVAR REGRAS ---
        if acao == 'salvar_compatibilidade':
            list_seg_planilha = request.POST.getlist('seg_planilha[]')
            list_seg_base_ids = request.POST.getlist('seg_base[]')
            with transaction.atomic():
                CompatibilidadeSeguradora.objects.all().delete()
                for de_txt, para_id in zip(list_seg_planilha, list_seg_base_ids):
                    de_txt_clean = de_txt.strip().upper()
                    if de_txt_clean and para_id:
                        CompatibilidadeSeguradora.objects.create(
                            nome_planilha=de_txt_clean,
                            seguradora_base_id=para_id
                        )
            messages.success(request, 'Regras de compatibilidade salvas com sucesso!')
            return redirect('producao_habitacional_import')

        elif acao == 'salvar_parametrizacao':
            with transaction.atomic():
                for campo in campos_destino:
                    nome = campo['nome']
                    col_excel = request.POST.get(f'map_{nome}', '').strip()
                    val_fixo = request.POST.get(f'fixo_{nome}', '').strip()
                    ParametrizacaoHabitacional.objects.update_or_create(
                        campo_sistema=nome,
                        defaults={'coluna_excel': col_excel, 'valor_fixo': val_fixo}
                    )
            messages.success(request, 'Parametrização padrão salva com sucesso!')
            return redirect('producao_habitacional_import')

        # --- FLUXO DE IMPORTAÇÃO ---
        arquivo = request.FILES.get('arquivo_excel')
        agrupamento_id = request.POST.get('agrupamento_id')

        if arquivo:
            ja_tem_dados = RegistroProducao.objects.filter(agrupamento_id=agrupamento_id, fase='IMPORTADOS').exists()
            if ja_tem_dados:
                messages.error(request, 'A aba "IMPORTADOS" já possui registros ativos para este produto.')
                return redirect('producao_habitacional_import')

            try:
                # Limpeza de espaços em branco invisíveis no Excel
                if arquivo.name.endswith('.csv'):
                    df = pd.read_csv(arquivo, sep=';', encoding='latin-1', dtype=str)
                else:
                    df = ler_excel_robusto(arquivo, dtype=str)
                
                df = df.fillna('') 
                df.columns = df.columns.astype(str).str.strip() # Remove espaços dos títulos das colunas

                parametros_query = ParametrizacaoHabitacional.objects.all()
                parametros_salvos_db = {p.campo_sistema: {'col': p.coluna_excel, 'fixo': p.valor_fixo} for p in parametros_query}

                mapeamento = {}
                for campo in campos_destino:
                    nome_campo = campo['nome']
                    salvo_db = parametros_salvos_db.get(nome_campo, {'col': '', 'fixo': ''})
                    
                    # Remove espaços também dos parâmetros salvos
                    col_excel = (salvo_db['col'] if salvo_db['col'] else request.POST.get(f'map_{nome_campo}', '')).strip()
                    val_fixo = (salvo_db['fixo'] if salvo_db['fixo'] else request.POST.get(f'fixo_{nome_campo}', '')).strip()
                    
                    mapeamento[nome_campo] = {'col_excel': col_excel, 'val_fixo': val_fixo}

                depara_seguradoras = {
                    regra.nome_planilha: regra.seguradora_base 
                    for regra in CompatibilidadeSeguradora.objects.select_related('seguradora_base').all()
                }

                contador = 0
                valid_fields = [f.name for f in RegistroProducao._meta.get_fields()]

                # Prepara o nome correto da coluna CID na sua tabela de Unidades (cid ou cid_unidade)
                campos_unidade = [f.name for f in Unidade._meta.get_fields()]
                campo_busca_cid = 'cid_unidade' if 'cid_unidade' in campos_unidade else 'cid'
                
                with transaction.atomic():
                    for index, row in df.iterrows():
                        if row.astype(str).str.strip().eq('').all():
                            continue

                        dados_salvar = {
                            'agrupamento_id': agrupamento_id,
                            'fase': 'IMPORTADOS',
                            'usuario_cadastro': request.user.username
                        }

                        for campo_banco, origem in mapeamento.items():
                            if campo_banco not in valid_fields:
                                continue
                                
                            if origem['col_excel'] and origem['col_excel'] in df.columns:
                                valor = str(row[origem['col_excel']]).strip()
                            elif origem['val_fixo']:
                                valor = origem['val_fixo']
                            else:
                                valor = ''
                            
                            # 1. Tratamento da Seguradora
                            if campo_banco == 'seguradora':
                                if valor:
                                    valor_upper = valor.upper()
                                    if valor_upper in depara_seguradoras:
                                        dados_salvar['seguradora'] = depara_seguradoras[valor_upper]
                                    else:
                                        dados_salvar['seguradora'] = Seguradora.objects.filter(seguradora__iexact=valor).first()
                                else:
                                    dados_salvar['seguradora'] = None
                                continue

                            # 2. Tratamento do Grupo/Ramo (busca o objeto na base pelo texto da planilha)
                            if campo_banco == 'grupo_ramo':
                                dados_salvar['grupo_ramo'] = Ramo.objects.filter(grupo_e_ramo__iexact=valor).first() if valor else None
                                continue

                            # 3. Tratamento do Tipo de Documento (idem)
                            if campo_banco == 'tipo_documento':
                                dados_salvar['tipo_documento'] = TipoDocumento.objects.filter(tipo_documento__iexact=valor).first() if valor else None
                                continue

                            # 4. Restante dos campos em texto/número/data
                            if not valor: 
                                if campo_banco in ['inicio_vigencia', 'fim_vigencia', 'qtd_parcelas', 'premio_bruto', 'premio_liquido', 'perc_comissao']:
                                    dados_salvar[campo_banco] = None
                                else:
                                    dados_salvar[campo_banco] = ''
                            else:
                                if campo_banco in ['premio_bruto', 'premio_liquido', 'perc_comissao']:
                                    dados_salvar[campo_banco] = _parse_float(valor)
                                elif campo_banco == 'qtd_parcelas':
                                    try: dados_salvar[campo_banco] = int(float(valor))
                                    except: dados_salvar[campo_banco] = None
                                elif campo_banco in ['inicio_vigencia', 'fim_vigencia']:
                                    try:
                                        dt_val = pd.to_datetime(valor, dayfirst=True)
                                        dados_salvar[campo_banco] = dt_val.date()
                                    except: dados_salvar[campo_banco] = None
                                else:
                                    dados_salvar[campo_banco] = valor[:150]

                        #  CRUZAMENTO COM A BASE DE UNIDADES 
                        valor_unidade_planilha = dados_salvar.get('unidade')
                        
                        if valor_unidade_planilha:
                            unidade_raw = str(valor_unidade_planilha).strip()
                            if '.' in unidade_raw:
                                unidade_raw = unidade_raw.split('.')[0].strip()
                            unidade_sem_zero = unidade_raw.lstrip('0')
                            cid_com_zero = unidade_raw.zfill(4) if unidade_raw else ''
                            
                            # Busca o objeto da Agência
                            filtro = Q(**{campo_busca_cid: cid_com_zero}) | Q(**{campo_busca_cid: unidade_raw}) | Q(**{campo_busca_cid: unidade_sem_zero})
                            unid_db = Unidade.objects.filter(filtro).first()
                            
                            if unid_db:
                                # 1. Se "unidade" no model for ForeignKey, vincula o objeto. Se não, salva só o texto.
                                is_fk = RegistroProducao._meta.get_field('unidade').get_internal_type() == 'ForeignKey'
                                if is_fk:
                                    dados_salvar['unidade'] = unid_db
                                else:
                                    dados_salvar['unidade'] = getattr(unid_db, 'unidade', unidade_raw)
                                
                                # 2. Puxa todos os relacionamentos preenchendo automaticamente
                                dados_salvar['grupo'] = getattr(unid_db, 'grupo', '') or ''
                                dados_salvar['superintendencia'] = getattr(unid_db, 'superintendencia', '') or ''
                                dados_salvar['nome_unidade'] = getattr(unid_db, 'unidade', '') or ''

                                # Tenta pegar o gerente (seja qual for o nome da coluna no seu banco: gerente_agencia ou matricula_gg)
                                dados_salvar['gerente_agencia'] = getattr(unid_db, 'gerente_agencia', getattr(unid_db, 'matricula_gg', '')) or ''
                                # Tenta pegar o super (superintendente ou matricula_superintendente)
                                dados_salvar['superintendente'] = getattr(unid_db, 'superintendente', getattr(unid_db, 'matricula_superintendente', '')) or ''
                            else:
                                if RegistroProducao._meta.get_field('unidade').get_internal_type() == 'ForeignKey':
                                    dados_salvar['unidade'] = None

                        # CRUZAMENTO COM A BASE DE COLABORADORES (busca o nome pela matrícula)
                        matricula_colaborador = str(dados_salvar.get('colaborador') or '').strip()
                        if matricula_colaborador:
                            colaborador_db = Colaborador.objects.filter(matricula=matricula_colaborador).first()
                            dados_salvar['nome_colaborador'] = colaborador_db.colaborador if colaborador_db else ''

                        # A duplicidade não é mais bloqueada aqui: todos entram em Importados
                        RegistroProducao.objects.create(**dados_salvar)
                        contador += 1

                messages.success(request, f'Sucesso! {contador} registos foram importados.')
                return redirect('producao_formularios_painel', agrupamento_id=agrupamento_id)

            except Exception as e:
                messages.error(request, f'A importação falhou: [{str(e)}]')
                return redirect('producao_habitacional_import')

    # --- MÉTODO GET INTACTO --- 
    agrupamento = Agrupamento.objects.filter(agrupamento__icontains='Habitacional').first()
    produto_hab = Produto.objects.filter(agrupamento=agrupamento).first() if agrupamento else None
    mes_padrao = produto_hab.mes_producao_em_aberto if produto_hab and hasattr(produto_hab, 'mes_producao_em_aberto') else ''
    ramos_hab = Ramo.objects.filter(produto=produto_hab).values_list('grupo_e_ramo', flat=True) if produto_hab else []
    tipos_doc = TipoDocumento.objects.all()
    unidades = Unidade.objects.all()
    seguradoras_base = Seguradora.objects.all().order_by('seguradora')
    regras_salvas = CompatibilidadeSeguradora.objects.all().order_by('id')

    parametros_query = ParametrizacaoHabitacional.objects.all()
    parametros_salvos = {p.campo_sistema: {'col': p.coluna_excel, 'fixo': p.valor_fixo} for p in parametros_query}

    aba_importados_cheia = False
    if agrupamento:
        aba_importados_cheia = RegistroProducao.objects.filter(agrupamento=agrupamento, fase='IMPORTADOS').exists()

    return render(request, 'core/producao/processamentos/importacao_habitacional.html', {
        'agrupamento': agrupamento,
        'mes_padrao': mes_padrao or '',
        'ramos_hab': ramos_hab,
        'tipos_doc': tipos_doc,
        'unidades': unidades,
        'seguradoras_base': seguradoras_base,
        'regras_salvas': regras_salvas, 
        'tipos_pessoa': TipoPessoa.objects.all(),
        'parametros_salvos': parametros_salvos,
        'aba_importados_cheia': aba_importados_cheia,
    })


@login_required
def producao_vendas(request):
    return render(request, 'core/producao/vendas/index.html')

@login_required
def vendas_banseg(request):
    return render(request, 'core/producao/vendas/banseg.html')

@login_required
def vendas_endosso(request):
    return render(request, 'core/producao/vendas/base_endosso.html')

@login_required
def vendas_novo_negocio(request):
    if request.method == 'POST':
        form, erro_formulario_msg = _salvar_indicacao_e_ligacoes(request)
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
        ultima_motivo=Subquery(ultima_ligacao.values('motivo_nao_venda_id')[:1]),
    ).filter(
        Q(ultima_central__isnull=True)
        | Q(ultima_central=False, ultima_agn=False, ultima_motivo__isnull=True)
    ).order_by('-id').select_related('seguradora', 'ramo', 'tipo_documento').prefetch_related('ligacoes__motivo_nao_venda')

    indicacoes = list(indicacoes)
    # Mapa CID -> nome da agência (tabela Unidade), para exibir "CID - Nome" concatenado
    # na lista do Novo (facilita a busca/filtro). Se o CID não existir em Unidade, fica só o CID.
    cids = {(i.cid_agencia or '').strip() for i in indicacoes if i.cid_agencia}
    mapa_agencia = {u.cid_unidade: u.unidade for u in Unidade.objects.filter(cid_unidade__in=cids)} if cids else {}
    limite_atend = timezone.now() - timedelta(minutes=ATENDIMENTO_TIMEOUT_MIN)
    for ind in indicacoes:
        ligacoes = list(ind.ligacoes.all())
        ultima = ligacoes[0] if ligacoes else None
        ind.responsavel = ultima.cadastrado_por if ultima else ''
        ind.proxima_ligacao = ultima.proximo_contato if ultima else None
        ind.nome_agencia = mapa_agencia.get((ind.cid_agencia or '').strip(), '')
        ind.atendimento_ativo = bool(ind.atendimento_por and ind.atendimento_em and ind.atendimento_em >= limite_atend)

    return render(request, 'core/base/formularios/base_novo.html', {
        'indicacoes': indicacoes,
        'form_indicacao': form,
        'erro_formulario_msg': erro_formulario_msg,
        'motivos_nao_venda': MotivoNaoVenda.objects.all(),
        'apenas_pendentes': True,
    })

@login_required
def vendas_nova_renovacao(request):
    return render(request, 'core/producao/vendas/em_construcao.html', {
        'titulo_pagina': 'Renovação',
        'icone_pagina': 'fa-redo',
    })

@login_required
def vendas_novo_endosso(request):
    return render(request, 'core/producao/vendas/em_construcao.html', {
        'titulo_pagina': 'Endosso',
        'icone_pagina': 'fa-file-medical',
    })

@login_required
def gerar_protocolo_ligacao(request):
    return JsonResponse({'protocolo': LigacaoIndicacao.gerar_proximo_protocolo()})

@login_required
def agora_servidor_ligacao(request):
    # horário vem sempre do servidor, nunca do relógio do navegador: o relógio do
    agora = timezone.localtime(timezone.now())
    return JsonResponse({'datahora': agora.strftime('%Y-%m-%dT%H:%M:%S')})


# --- Trava de atendimento ("em ligação") --------------------------------------------------
# Quando alguém abre um registro para registrar uma ligação, ele fica "em atendimento" e
# aparece em vermelho na lista para TODOS os usuários (evita duas pessoas no mesmo lead).
# Some ao salvar/cancelar. A trava expira sozinha após ATENDIMENTO_TIMEOUT_MIN minutos, para
# não travar para sempre caso o usuário feche o navegador sem encerrar.
ATENDIMENTO_TIMEOUT_MIN = 15

def _nome_usuario_atendimento(user):
    """Nome mostrado na coluna 'Uso por': pega pelo perfil (colaborador vinculado).
    Se não houver perfil/colaborador, cai para o nome completo ou o login."""
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.colaborador:
        col = perfil.colaborador
        return col.nome_social or col.colaborador
    return user.get_full_name() or user.username

@login_required
def marcar_atendimento(request, id):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    ind = get_object_or_404(Indicacao, id=id)
    ind.atendimento_por = _nome_usuario_atendimento(request.user)
    ind.atendimento_em = timezone.now()
    ind.save(update_fields=['atendimento_por', 'atendimento_em'])
    return JsonResponse({'ok': True})

@login_required
def encerrar_atendimento(request, id):
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    ind = get_object_or_404(Indicacao, id=id)
    ind.atendimento_por = None
    ind.atendimento_em = None
    ind.save(update_fields=['atendimento_por', 'atendimento_em'])
    return JsonResponse({'ok': True})

@login_required
def atendimentos_ativos(request):
    limite = timezone.now() - timedelta(minutes=ATENDIMENTO_TIMEOUT_MIN)
    qs = (Indicacao.objects
          .filter(atendimento_em__gte=limite)
          .exclude(atendimento_por__isnull=True)
          .exclude(atendimento_por__exact='')
          .values('id', 'atendimento_por'))
    return JsonResponse({'atendimentos': {str(r['id']): r['atendimento_por'] for r in qs}})

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
    sem 'Prêmio Total'. O checkbox só aparece no POST quando marcado; o sufixo
    ('' ou '_2', '_3'...) identifica a ligação correspondente."""
    for prefixo in ('ligacao_venda_central', 'ligacao_agn'):
        for chave, valor in request.POST.items():
            if chave.startswith(prefixo) and valor == 'on':
                sufixo = chave[len(prefixo):]
                premio = (request.POST.get(f'ligacao_premio_total{sufixo}') or '').strip()
                if not premio:
                    return True
    return False


def _salvar_indicacao_e_ligacoes(request, processar_ligacoes=True):
    """Processa o POST de cadastro/edição da ficha de Indicação (Base Novo e o card
    'Novo', que reaproveitam a mesma ficha/tabela). Retorna None quando salvo com
    sucesso; caso contrário retorna (form, erro_formulario_msg) para reabrir a
    ficha com os erros.

    processar_ligacoes=False é usado pela Base Novo, onde a ficha é só de
    cadastro/consulta e não traz os campos de ligação. Sem essa trava, o
    delete/recreate abaixo apagaria todo o histórico de ligações da indicação a
    cada gravação feita por lá (o POST chega sem os campos e nada é recriado)."""
    item_id = request.POST.get('item_id')
    instancia = get_object_or_404(Indicacao, id=item_id) if item_id else None

    # A ficha da Base Novo envia o Indicador e a Agência em campos ÚNICOS concatenados
    # ("matrícula - nome" / "CID - nome"). Aqui separamos de volta para os campos que o
    # formulário espera: matrícula/CID = parte antes do primeiro " - "; nome = o resto.
    dados_post = request.POST
    if 'indicador_combo' in request.POST or 'agencia_combo' in request.POST:
        dados_post = request.POST.copy()
        if 'indicador_combo' in dados_post:
            mat, _, nome = (dados_post.get('indicador_combo') or '').strip().partition(' - ')
            dados_post['matricula_indicador'] = mat.strip()
            dados_post['nome_indicador'] = nome.strip()
        if 'agencia_combo' in dados_post:
            dados_post['cid_agencia'] = (dados_post.get('agencia_combo') or '').strip().partition(' - ')[0].strip()

    # No Novo, os dados do registro só são gravados quando o salvamento vem do pop-up de
    # edição (flag 'editar_dados'). Ao só registrar uma ligação, a ficha continua só leitura
    # (não sobrescreve os dados). Na Base Novo/Emissão a ficha é sempre editável.
    somente_leitura = processar_ligacoes and request.POST.get('editar_dados') != '1'
    form = IndicacaoForm(dados_post, instance=instancia, ficha_somente_leitura=somente_leitura)

    # os campos "Vendas Central" obriga o preenchimento do "Prêmio Total".  se nao da erro
    if _falta_premio_total_venda_central(request):
        form.add_error(None, 'Informe o "Prêmio Total" nas ligações marcadas como "Vendas Central" ou "Vendas Agência".')

    if not form.is_valid():
        erro_formulario_msg = '; '.join(
            ', '.join(erros) if campo == '__all__' else f"{form.fields[campo].label if campo in form.fields else campo}: {', '.join(erros)}"
            for campo, erros in form.errors.items()
        )
        return form, erro_formulario_msg

    indicacao = form.save()

    # Ao salvar, libera a trava de "uso" do registro (quem salvou terminou de mexer).
    if indicacao.atendimento_por or indicacao.atendimento_em:
        indicacao.atendimento_por = None
        indicacao.atendimento_em = None
        indicacao.save(update_fields=['atendimento_por', 'atendimento_em'])

    # Base Novo não mexe em ligação: preserva o histórico já registado no card "Novo".
    if not processar_ligacoes:
        return None, ''

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
        if not protocolo_val or LigacaoIndicacao.objects.filter(protocolo=protocolo_val).exists():
            protocolo_val = LigacaoIndicacao.gerar_proximo_protocolo()

        LigacaoIndicacao.objects.create(
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
            motivo_nao_venda_id=motivo_val or None,
            seguradora_id=seguradora_val or None,
            comissao=comissao_val,
            # sempre gravado com o usuário logado no momento do salvamento,
            # nunca aceito vindo do POST (campo é readonly na ficha)
            cadastrado_por=request.user.get_full_name() or request.user.username,
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
def lista_base_novo(request):
    if request.method == 'POST':
        form, erro_formulario_msg = _salvar_indicacao_e_ligacoes(request, processar_ligacoes=False)
        if form is None:
            return redirect('lista_base_novo')
    else:
        form = IndicacaoForm()
        erro_formulario_msg = ''

    indicacoes = list(
        Indicacao.objects.all().order_by('-id')
        .select_related('seguradora', 'ramo', 'tipo_documento')
        .prefetch_related('ligacoes__motivo_nao_venda')
    )
    # Nome da agência (tabela Unidade) para concatenar "CID - Nome" na lista, igual ao Novo.
    # Necessário aqui também porque, ao encerrar a ligação, o registro sai do Novo e passa a
    # aparecer só na Base Novo - que deve manter a mesma visão concatenada.
    cids = {(i.cid_agencia or '').strip() for i in indicacoes if i.cid_agencia}
    mapa_agencia = {u.cid_unidade: u.unidade for u in Unidade.objects.filter(cid_unidade__in=cids)} if cids else {}
    limite_atend = timezone.now() - timedelta(minutes=ATENDIMENTO_TIMEOUT_MIN)
    for ind in indicacoes:
        ind.nome_agencia = mapa_agencia.get((ind.cid_agencia or '').strip(), '')
        ind.atendimento_ativo = bool(ind.atendimento_por and ind.atendimento_em and ind.atendimento_em >= limite_atend)

    return render(request, 'core/base/formularios/base_novo.html', {
        'indicacoes': indicacoes,
        'form_indicacao': form,
        'erro_formulario_msg': erro_formulario_msg,
        'motivos_nao_venda': MotivoNaoVenda.objects.all(),
    })

@login_required
def vendas_emissao(request):
    """Card 'Emissão': mostra SOMENTE os registros cuja venda foi fechada (a última
    ligação está marcada como 'Vendas Central' ou 'Vendas Agência'). É uma visão
    filtrada dos mesmos dados da Base Novo - nada é duplicado no banco. Reaproveita a
    mesma tela (base_novo.html) no modo de consulta/edição, igual à Base Novo."""
    if request.method == 'POST':
        form, erro_formulario_msg = _salvar_indicacao_e_ligacoes(request, processar_ligacoes=False)
        if form is None:
            return redirect('vendas_emissao')
    else:
        form = IndicacaoForm()
        erro_formulario_msg = ''

    ultima_ligacao = LigacaoIndicacao.objects.filter(indicacao=OuterRef('pk')).order_by('-id')
    indicacoes = list(
        Indicacao.objects.annotate(
            ultima_central=Subquery(ultima_ligacao.values('venda_central')[:1]),
            ultima_agn=Subquery(ultima_ligacao.values('agn')[:1]),
        ).filter(
            Q(ultima_central=True) | Q(ultima_agn=True)
        ).order_by('-id')
        .select_related('seguradora', 'ramo', 'tipo_documento')
        .prefetch_related('ligacoes__motivo_nao_venda')
    )
    cids = {(i.cid_agencia or '').strip() for i in indicacoes if i.cid_agencia}
    mapa_agencia = {u.cid_unidade: u.unidade for u in Unidade.objects.filter(cid_unidade__in=cids)} if cids else {}
    limite_atend = timezone.now() - timedelta(minutes=ATENDIMENTO_TIMEOUT_MIN)
    for ind in indicacoes:
        ind.nome_agencia = mapa_agencia.get((ind.cid_agencia or '').strip(), '')
        ind.atendimento_ativo = bool(ind.atendimento_por and ind.atendimento_em and ind.atendimento_em >= limite_atend)

    return render(request, 'core/base/formularios/base_novo.html', {
        'indicacoes': indicacoes,
        'form_indicacao': form,
        'erro_formulario_msg': erro_formulario_msg,
        'motivos_nao_venda': MotivoNaoVenda.objects.all(),
        'modo_emissao': True,
    })

@login_required
def vendas_renovacao(request):
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        instancia = get_object_or_404(Apolice, id=item_id) if item_id else None
        form = ApoliceForm(request.POST, instance=instancia)
        if form.is_valid():
            nova_apolice = form.save(commit=False)
            nova_apolice.tipo_negocio = 'RENOVACAO' 
            nova_apolice.save()
            return redirect('vendas_renovacao')
    else:
        form = ApoliceForm()

    items = Apolice.objects.filter(tipo_negocio='RENOVACAO').order_by('-id')
    return render(request, 'core/producao/vendas/base_renovacao.html', {
        'apolices': items, 
        'form_apolice': form
    })

@login_required
def vendas_outras_cias(request):
    return render(request, 'core/producao/vendas/outras_cias.html')


@login_required
def producao_relatorios(request):
    return render(request, 'core/producao/relatorios/home.html')

@login_required
def importar_unidades(request):
    if request.method == 'POST' and request.FILES.get('arquivo_planilha'):
        arquivo = request.FILES['arquivo_planilha']
        
        try:
            if arquivo.name.endswith('.csv'):
                df = pd.read_csv(arquivo, dtype=str)
            else:
                df = ler_excel_robusto(arquivo, dtype=str)

            # Limpa os nomes das colunas
            df.columns = df.columns.str.strip()
            df = df.fillna('')
            
            contador_novos = 0
            contador_atualizados = 0
            
            for index, row in df.iterrows():
                # Tenta pegar a coluna 'CID' bruta
                cid_bruto = str(row.get('CID', '')).strip()
                
                # Pula a linha se o CID for vazio, ou se for apenas um tracinho '-'
                if not cid_bruto or cid_bruto == '-':
                    continue
                
                # Preenche com zeros à esquerda até ter 4 dígitos!
                cid = cid_bruto.zfill(4)
                
                # Mapeamento EXATO respeitando os nomes da planilha
                defaults_data = {
                    'superintendencia': str(row.get('SUPERINTENDÊNCIA', '')).strip(),
                    'unidade_original': str(row.get('Agência (no GOT)', '')).strip(),
                    'unidade': str(row.get('AGÊNCIA', '')).strip(),
                    'grupo': str(row.get('GRUPO', '')).strip(),
                }

                # Tenta pegar observações se existir na planilha
                if 'Observações' in df.columns:
                    defaults_data['observacoes'] = str(row.get('Observações', '')).strip()

                # Atualiza ou Cria usando o CID já formatado com zeros
                unidade, criada = Unidade.objects.update_or_create(
                    cid_unidade=cid,
                    defaults=defaults_data
                )
                
                if criada:
                    contador_novos += 1
                else:
                    contador_atualizados += 1

            messages.success(request, f'Importação concluída! {contador_novos} novas unidades criadas e {contador_atualizados} atualizadas.')

            registrar_auditoria_backend(usuario=request.user,acao="Importou", detalhe="Unidade")
        except Exception as e:
            messages.error(request, f'Erro ao processar a planilha: {str(e)}. Verifique os cabeçalhos.')

    return redirect('base_processamentos')

@login_required
def importar_base_novo(request):
    if request.method == 'POST' and request.FILES.get('arquivo_planilha'):
        arquivo = request.FILES['arquivo_planilha']

        try:
            if arquivo.name.endswith('.csv'):
                df = pd.read_csv(arquivo, dtype=str)
            else:
                df = ler_excel_robusto(arquivo, dtype=str)

            # Limpa os nomes das colunas
            df.columns = df.columns.str.strip()
            df = df.fillna('')

            contador_novos = 0
            contador_atualizados = 0
            contador_ignorados = 0
            contador_excluidos_pulados = 0

            for index, row in df.iterrows():
                # Mapeamento EXATO respeitando os cabeçalhos da planilha "Indicação Seguridade (base novo)"
                carimbo_bruto = str(row.get('Carimbo de data/hora', '')).strip()

                # Pula a linha se não tiver carimbo de data/hora (linha vazia/inválida)
                if not carimbo_bruto:
                    contador_ignorados += 1
                    continue

                carimbo = pd.to_datetime(carimbo_bruto, dayfirst=True, errors='coerce')
                if pd.isna(carimbo):
                    contador_ignorados += 1
                    continue

                email = str(row.get('Endereço de e-mail', '')).strip()

                if IndicacaoExcluida.objects.filter(carimbo_data_hora=carimbo, email=email).exists():
                    contador_excluidos_pulados += 1
                    continue

                defaults_data = {
                    'email_indicador_outro': str(row.get('E-mail do indicador caso não seja você mesmo', '')).strip(),
                    'matricula_indicador': str(row.get('Matrícula do indicador', '')).strip(),
                    'nome_indicador': str(row.get('Nome completo do indicador', '')).strip(),
                    'cid_agencia': str(row.get('CID da agência', '')).strip(),
                    'telefone_indicador': str(row.get('Telefone ou celular do indicador', '')).strip(),
                    'enviar_orcamento_para': str(row.get('Enviar orçamento para', '')).strip(),
                    'nome_cliente': str(row.get('Nome completo do cliente', '')).strip(),
                    'telefone_cliente': str(row.get('Telefone ou celular do cliente', '')).strip(),
                    'cpf_cliente': str(row.get('CPF do cliente', '')).strip(),
                    'email_cliente': str(row.get('E-mail do cliente', '')).strip(),
                    'produto': str(row.get('Produto', '')).strip(),
                    'dados_veiculo': str(row.get('Se Automóvel, informe os dados do veículo (modelo, ano e placa)', '')).strip(),
                    'possui_seguro': str(row.get('Cliente já possui seguro?', '')).strip(),
                    'observacoes': str(row.get('Observações', '')).strip(),
                }

                # Considera duplicada a mesma resposta
                indicacao, criada = Indicacao.objects.update_or_create(
                    carimbo_data_hora=carimbo,
                    email=email,
                    defaults=defaults_data
                )

                if criada:
                    contador_novos += 1
                else:
                    contador_atualizados += 1

            msg = f'Importação concluída! {contador_novos} novas indicações criadas e {contador_atualizados} atualizadas.'
            if contador_ignorados:
                msg += f' {contador_ignorados} linha(s) ignorada(s) por falta de carimbo de data/hora válido.'
            if contador_excluidos_pulados:
                msg += f' {contador_excluidos_pulados} linha(s) ignorada(s) por já terem sido excluídas manualmente antes.'
            messages.success(request, msg)

            registrar_auditoria_backend(usuario=request.user, acao="Importou", detalhe="Base Novo (Indicação)")
        except Exception as e:
            messages.error(request, f'Erro ao processar a planilha: {str(e)}. Verifique os cabeçalhos.')

    return redirect('base_processamentos')

@login_required
def importar_colaboradores(request):
    if request.method == 'POST' and request.FILES.get('arquivo_planilha'):
        arquivo = request.FILES['arquivo_planilha']
        try:
            df = pd.read_csv(arquivo, dtype=str) if arquivo.name.endswith('.csv') else ler_excel_robusto(arquivo, dtype=str)
            df.columns = df.columns.str.strip()
            df = df.fillna('')
            contador_novos, contador_atualizados = 0, 0
            with transaction.atomic():
                for index, row in df.iterrows():
                    # busca pela coluna MATRICULA 
                    matricula_bruta = str(row.get('MATRICULA', '')).strip()
                    if not matricula_bruta or matricula_bruta == '-': 
                        continue

                    # Mapeia o nome e deixa o colaborador ativo por padrão
                    defaults_data = {
                        'colaborador': str(row.get('NOME', '')).strip(),
                        'inativo': False,
                    }
                    
                    # Vincula a agência usando a coluna CID_COORDENADORIA
                    cid_lotacao = str(row.get('CID_COORDENADORIA', '')).strip()
                    if cid_lotacao and cid_lotacao != '-':
                        unidade_vinculo = Unidade.objects.filter(cid_unidade=cid_lotacao.zfill(4)).first()
                        if unidade_vinculo: 
                            defaults_data['unidade'] = unidade_vinculo

                    # Salva ou atualiza utilizando a MATRÍCULA como chave única
                    colab, criada = Colaborador.objects.update_or_create(
                        matricula=matricula_bruta, 
                        defaults=defaults_data
                    )
                    if criada: 
                        contador_novos += 1
                    else: 
                        contador_atualizados += 1
                        
            messages.success(request, f'Sucesso! {contador_novos} criados e {contador_atualizados} atualizados.')
            registrar_auditoria_backend(usuario=request.user,acao="Importou", detalhe="Colaboradores")
        except Exception as e:
            messages.error(request, f'Erro: {str(e)}')
    return redirect('base_processamentos')

@login_required
def importar_ramos(request):
    if request.method == 'POST' and request.FILES.get('arquivo_planilha'):
        arquivo = request.FILES['arquivo_planilha']
        
        try:
            if arquivo.name.endswith('.csv'):
                df = pd.read_csv(arquivo, dtype=str)
            else:
                df = ler_excel_robusto(arquivo, dtype=str)

            df.columns = df.columns.str.strip()
            df = df.fillna('')
            
            contador_novos = 0
            contador_atualizados = 0
            
            # Abre uma transação única (blindagem contra travamentos)
            with transaction.atomic():
                for index, row in df.iterrows():
                    # 1. Pega o Cód. do Ramo (Chave principal)
                    cod_ramo_bruto = str(row.get('Cód. do Ramo', '')).strip()
                    
                    # Se não tiver código do ramo, pula a linha
                    if not cod_ramo_bruto or cod_ramo_bruto == '-':
                        continue
                    
                    # 2. Regra do Inativo Blindada
                    inativo_planilha = str(row.get('inativo', '')).strip().upper()
                    
                    # Se vier 'VERDADEIRO' (texto) ou 'TRUE', marca a caixinha!
                    inativo_bool = True if inativo_planilha in ['VERDADEIRO', 'TRUE', '1'] else False

                    # 3. Mapeia os dados das colunas para o Banco de Dados
                    defaults_data = {
                        'cod_grupo': str(row.get('Cód. do Grupo', '')).strip(),
                        'grupo': str(row.get('Grupo', '')).strip(),
                        'ramo': str(row.get('Ramo', '')).strip(),
                        'inativo': inativo_bool,
                        'observacoes': str(row.get('Observações', '')).strip(),
                    }

                    # 4. Salva ou Atualiza usando o cod_ramo como busca!
                    ramo_obj, criada = Ramo.objects.update_or_create(
                        cod_ramo=cod_ramo_bruto,
                        defaults=defaults_data
                    )
                    
                    if criada:
                        contador_novos += 1
                    else:
                        contador_atualizados += 1

            messages.success(request, f'Sucesso! {contador_novos} ramos criados e {contador_atualizados} atualizados.')
            registrar_auditoria_backend(usuario=request.user,acao="Importou", detalhe="Ramos")
        except Exception as e:
            messages.error(request, f'Erro na planilha: {str(e)}')

    return redirect('base_processamentos')


@login_required
def importar_usuarios(request):
    # TRAVA BLINDADA (Só Admin)
    eh_admin = request.user.is_superuser or (hasattr(request.user, 'perfil') and request.user.perfil.nivel_acesso == 'ADMIN')
    if not eh_admin:
        messages.error(request, 'Acesso Negado. Apenas Administradores podem importar usuários.')
        return redirect('home')

    if request.method == 'POST' and request.FILES.get('arquivo'):
        arquivo = request.FILES['arquivo']
        cadastrados = 0
        ignorados = 0
        nao_encontrados = 0 # Contador para matrículas que não existem em Colaborador
        
        try:
            linhas_dados = [] 

            # --- SE FOR EXCEL (.xlsx) ---
            if arquivo.name.endswith('.xlsx'):
                wb = openpyxl.load_workbook(arquivo, data_only=True)
                planilha = wb.active
                cabecalhos = [str(celula.value).strip() if celula.value else '' for celula in planilha[1]]
                for linha in planilha.iter_rows(min_row=2, values_only=True):
                    dados = dict(zip(cabecalhos, [str(v).strip() if v is not None else '' for v in linha]))
                    linhas_dados.append(dados)

            # --- SE FOR CSV (.csv) ---
            elif arquivo.name.endswith('.csv'):
                arquivo_decodificado = arquivo.read().decode('utf-8-sig').splitlines()
                leitor = csv.DictReader(arquivo_decodificado, delimiter=';')
                for linha in leitor:
                    linhas_dados.append(linha)
                    
            else:
                messages.error(request, 'Formato inválido! Envie um arquivo .xlsx ou .csv')
                return redirect('importar_usuarios')

            # --- AGORA CADASTRA TODO MUNDO ---
            for dados in linhas_dados:
                matricula = dados.get('MATRICULA', '').strip()
                nome = dados.get('NOME', '').strip()
                email = dados.get('EMAIL', '').strip()
                cid = dados.get('CID_COORDENADORIA', '').strip()
                
                if matricula:
                    # 1ª VALIDAÇÃO: Matrícula existe em Colaborador?
                    if not Colaborador.objects.filter(matricula=matricula).exists():
                        nao_encontrados += 1
                        continue # Pula para a próxima linha da planilha
                        
                    # 2ª VALIDAÇÃO: Usuário já existe?
                    if not User.objects.filter(username=matricula).exists():
                        # Cria a Conta
                        user = User.objects.create_user(
                            username=matricula, 
                            email=email, 
                            password='mudar@123',
                            first_name=nome[:150]
                        )
                        # Cria o Perfil
                        PerfilUsuario.objects.create(
                            usuario=user,
                            nivel_acesso='COMUM',
                            cid_coordenadoria=cid
                        )
                        cadastrados += 1
                    else:
                        ignorados += 1
                        
            messages.success(request, f'Importação concluída! {cadastrados} criados. {ignorados} já existiam. {nao_encontrados} ignorados por não existirem em Colaborador.')

            registrar_auditoria_backend(usuario=request.user,acao="Importou", detalhe="Usuario")
        except Exception as e:
            messages.error(request, f'Erro ao ler a planilha. Verifique se o formato e as colunas estão corretos. Erro: {str(e)}')
            
        return redirect('importar_usuarios')
        
    return render(request, 'core/administracao/importar_usuarios.html')

    
# SAIR DO SISTEMA (LOGOUT CUSTOMIZADO)
def sair_do_sistema(request):
    logout(request) # Apaga a sessão do usuário
    return redirect('login') 


# --- NOVO CARD DE TIPOS DE PESSOA ---


def _ids_duplicados_no_lote(fase_origem, agrupamento):
    """
    Verifica, dentro dos registos de `fase_origem` (Importados ou Pendentes) de um
    agrupamento, quais resultariam em chave_unica repetida caso avançassem de fase.

    Considera repetido tanto quando dois registos do próprio lote batem entre si
    quanto quando a chave já existe na fase seguinte (checagem em cascata: Importados
    só olha para o que já está em Pendentes; Pendentes só olha para o que já está em
    Emitidos - nunca pula fase).

    Retorna um set com os ids dos RegistroProducao (da fase_origem) que precisam
    ser apagados ou editados antes de liberar a passagem de fase.
    """
    registros = RegistroProducao.objects.filter(
        agrupamento=agrupamento, fase__iexact=fase_origem
    ).prefetch_related('endossos_extras')

    fase_seguinte = 'PENDENTES' if fase_origem.upper() == 'IMPORTADOS' else 'EMITIDOS'
    chaves_ja_existentes = set(
        RegistroProducao.objects.filter(agrupamento=agrupamento, fase__iexact=fase_seguinte)
        .exclude(chave_unica__isnull=True).exclude(chave_unica='')
        .values_list('chave_unica', flat=True)
    )

    contagem = {}
    dono_da_chave = {}

    for reg in registros:
        chaves_deste_registro = [reg.chave_unica]

        # Ao emitir, cada endosso adicional vira um registo próprio
        if fase_origem.upper() == 'PENDENTES':
            for extra in reg.endossos_extras.all():
                chaves_deste_registro.append(RegistroProducao.montar_chave_unica(
                    reg.seguradora_id, reg.grupo_ramo_id, reg.tipo_documento_id, reg.documento, extra.endosso
                ))

        for chave in chaves_deste_registro:
            contagem[chave] = contagem.get(chave, 0) + 1
            dono_da_chave.setdefault(chave, set()).add(reg.id)

    ids_duplicados = set()
    for chave, qtd in contagem.items():
        if qtd > 1 or chave in chaves_ja_existentes:
            ids_duplicados.update(dono_da_chave[chave])

    return ids_duplicados


@login_required
def producao_lista_fase(request, agrupamento_id, fase):
    agrupamento = get_object_or_404(Agrupamento, id=agrupamento_id)
    fase_banco = fase.upper()

    if request.method == 'POST':
        acao = request.POST.get('acao')
        if acao == 'editar':
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            registro_id = request.POST.get('registro_id')
            if registro_id:
                reg = get_object_or_404(RegistroProducao, id=registro_id)

                if reg.fase.upper() == 'EMITIDOS':
                    erro = 'Registos na fase Emitidos não podem mais ser editados.'
                    if is_ajax:
                        return JsonResponse({'sucesso': False, 'erro': erro}, status=400)
                    messages.error(request, erro)
                    return redirect('producao_lista_fase', agrupamento_id=agrupamento.id, fase=fase)

                reg.cliente = request.POST.get('cliente')
                reg.cpf_cnpj = request.POST.get('cpf_cnpj')
                
                seg_input = request.POST.get('seguradora')
                reg.seguradora = Seguradora.objects.filter(id=seg_input).first() if seg_input else None

                unidade_input = request.POST.get('unidade')
                reg.unidade = Unidade.objects.filter(id=unidade_input).first() if unidade_input else None

                tipodoc_input = request.POST.get('tipo_documento')
                reg.tipo_documento = TipoDocumento.objects.filter(id=tipodoc_input).first() if tipodoc_input else None

                ramo_input = request.POST.get('grupo_ramo')
                reg.grupo_ramo = Ramo.objects.filter(id=ramo_input).first() if ramo_input else None

                reg.tipo_pessoa = request.POST.get('tipo_pessoa') 
                reg.documento = request.POST.get('documento')
                
                endosso_principal_input = request.POST.get('endosso')
                if not endosso_principal_input or not endosso_principal_input.strip():
                    msg_erro = "O número do endosso principal não pode ficar vazio."
                    if is_ajax: return JsonResponse({'sucesso': False, 'erro': msg_erro}, status=400)
                    messages.error(request, msg_erro)
                    return redirect('producao_lista_fase', agrupamento_id=agrupamento.id, fase=fase)
                
                reg.endosso = endosso_principal_input.strip()

                if reg.fase.upper() == 'PENDENTES':
                    nova_chave = RegistroProducao.montar_chave_unica(
                        reg.seguradora_id, reg.grupo_ramo_id, reg.tipo_documento_id, reg.documento, reg.endosso
                    )
                    ja_existe = RegistroProducao.objects.filter(
                        agrupamento=agrupamento, fase__iexact='PENDENTES', chave_unica=nova_chave
                    ).exclude(id=reg.id).exists()
                    if ja_existe:
                        erro = ('Já existe um registo em Pendentes com a mesma Seguradora, Grupo/Ramo, '
                                'Tipo de Documento, Documento e Endosso. Altere um desses campos antes de guardar.')
                        if is_ajax:
                            return JsonResponse({
                                'sucesso': False,
                                'erro': erro,
                                'campos_duplicados': ['seguradora', 'grupo_ramo', 'tipo_documento', 'documento', 'endosso'],
                            }, status=409)
                        messages.error(request, erro)
                        return redirect('producao_lista_fase', agrupamento_id=agrupamento.id, fase=fase)

                reg.mes_producao = request.POST.get('mes_producao')
                reg.nome_social = request.POST.get('nome_social')
                reg.celular = request.POST.get('celular')
                reg.telefone = request.POST.get('telefone')
                reg.email = request.POST.get('email')
                reg.superintendencia = request.POST.get('superintendencia')
                reg.nome_unidade = request.POST.get('nome_unidade')
                reg.colaborador = request.POST.get('colaborador')
                reg.nome_colaborador = request.POST.get('nome_colaborador')
                reg.gerente_agencia = request.POST.get('gerente_agencia')
                reg.superintendente = request.POST.get('superintendente')
                reg.realizado = request.POST.get('realizado')
                reg.observacoes = request.POST.get('observacoes')
                reg.motivo_endosso = request.POST.get('motivo_endosso')
                reg.renovacao_propria = request.POST.get('renovacao_propria')
                reg.grupo = request.POST.get('grupo')   

                def valida_limites(p_com, p_bruto, p_liq):
                    if p_com and (p_com > 999.99 or p_com < -999.99): 
                        return "O campo '% de comissão' não pode exceder 999,99%."
                    if p_bruto and (p_bruto > 9999999999999.99 or p_bruto < -9999999999999.99): 
                        return "O valor do 'Prêmio Bruto' excedeu o limite permitido."
                    if p_liq and (p_liq > 9999999999999.99 or p_liq < -9999999999999.99): 
                        return "O valor do 'Prêmio Líquido' excedeu o limite permitido."
                    return None

                p_bruto_val = _parse_float(request.POST.get('premio_bruto'))
                p_liq_val = _parse_float(request.POST.get('premio_liquido'))
                p_com_val = _parse_float(request.POST.get('perc_comissao'))
                
                erro_limite = valida_limites(p_com_val, p_bruto_val, p_liq_val)
                if erro_limite:
                    if is_ajax: return JsonResponse({'sucesso': False, 'erro': erro_limite}, status=400)
                    messages.error(request, erro_limite)
                    return redirect('producao_lista_fase', agrupamento_id=agrupamento.id, fase=fase)

                endossos_enviados = [reg.endosso] # Já inicia com o endosso principal para checar conflitos
                
                contador_check = 2
                while True:
                    mes_check = request.POST.get(f'mes_producao_{contador_check}')
                    endosso_ext = request.POST.get(f'endosso_{contador_check}')
                    
                    # Se o formulário não enviou essas chaves no POST, acabou a lista
                    if mes_check is None and endosso_ext is None: 
                        break
                    
                    # Se o card foi adicionado no HTML, mas deixaram o número do endosso em branco
                    if not endosso_ext or not endosso_ext.strip():
                        msg_erro = f"O número do {contador_check}º endosso está vazio. Preencha-o ou clique em 'Remover'."
                        if is_ajax: return JsonResponse({'sucesso': False, 'erro': msg_erro}, status=400)
                        messages.error(request, msg_erro)
                        return redirect('producao_lista_fase', agrupamento_id=agrupamento.id, fase=fase)

                    endosso_ext = endosso_ext.strip()
                    
                    # Checagem de Endossos Repetidos
                    if endosso_ext in endossos_enviados:
                        msg_erro = f"O endosso '{endosso_ext}' foi preenchido repetidamente no formulário. Corrija para salvar."
                        if is_ajax: return JsonResponse({'sucesso': False, 'erro': msg_erro}, status=400)
                        messages.error(request, msg_erro)
                        return redirect('producao_lista_fase', agrupamento_id=agrupamento.id, fase=fase)
                    
                    endossos_enviados.append(endosso_ext)

                    p_bruto_ext = _parse_float(request.POST.get(f'premio_bruto_{contador_check}'))
                    p_liq_ext = _parse_float(request.POST.get(f'premio_liquido_{contador_check}'))
                    p_com_ext = _parse_float(request.POST.get(f'perc_comissao_{contador_check}'))
                    
                    erro_limite_ext = valida_limites(p_com_ext, p_bruto_ext, p_liq_ext)
                    if erro_limite_ext:
                        msg_erro = f"Endosso {contador_check - 1}: {erro_limite_ext}"
                        if is_ajax: return JsonResponse({'sucesso': False, 'erro': msg_erro}, status=400)
                        messages.error(request, msg_erro)
                        return redirect('producao_lista_fase', agrupamento_id=agrupamento.id, fase=fase)
                    
                    contador_check += 1

                reg.premio_bruto = p_bruto_val
                reg.premio_liquido = p_liq_val
                reg.perc_comissao = p_com_val
                reg.qtd_parcelas = _parse_int(request.POST.get('qtd_parcelas'))

                reg.inicio_vigencia = _parse_date(request.POST.get('inicio_vigencia'))
                reg.fim_vigencia = _parse_date(request.POST.get('fim_vigencia'))
                reg.save() 
                
                reg.endossos_extras.all().delete()
                contador = 2
                while True:
                    mes_extra = request.POST.get(f'mes_producao_{contador}')
                    endosso_extra = request.POST.get(f'endosso_{contador}')
                    if mes_extra is None and endosso_extra is None: break
                    
                    unidade_extra_input = request.POST.get(f'unidade_{contador}')
                    unidade_extra_inst = Unidade.objects.filter(id=unidade_extra_input).first() if unidade_extra_input else None

                    EndossoAdicional.objects.create(
                        registro_pai=reg, mes_producao=mes_extra, endosso=endosso_extra.strip(),
                        motivo_endosso=request.POST.get(f'motivo_endosso_{contador}'),
                        inicio_vigencia=_parse_date(request.POST.get(f'inicio_vigencia_{contador}')),
                        fim_vigencia=_parse_date(request.POST.get(f'fim_vigencia_{contador}')),
                        qtd_parcelas=_parse_int(request.POST.get(f'qtd_parcelas_{contador}')),
                        renovacao_propria=request.POST.get(f'renovacao_propria_{contador}'),
                        premio_bruto=_parse_float(request.POST.get(f'premio_bruto_{contador}')),
                        premio_liquido=_parse_float(request.POST.get(f'premio_liquido_{contador}')),
                        perc_comissao=_parse_float(request.POST.get(f'perc_comissao_{contador}')),
                        realizado=request.POST.get(f'realizado_{contador}'),
                        unidade=unidade_extra_inst.cid_unidade if unidade_extra_inst else None,
                        nome_unidade=request.POST.get(f'nome_unidade_{contador}') or (unidade_extra_inst.unidade if unidade_extra_inst else None),
                        superintendencia=request.POST.get(f'superintendencia_{contador}'), grupo=request.POST.get(f'grupo_{contador}'),
                        colaborador=request.POST.get(f'colaborador_{contador}'), nome_colaborador=request.POST.get(f'nome_colaborador_{contador}'),
                        gerente_agencia=request.POST.get(f'gerente_agencia_{contador}'),
                        superintendente=request.POST.get(f'superintendente_{contador}')
                    )
                    contador += 1
                messages.success(request, 'Registo atualizado com sucesso!')
                if is_ajax:
                    return JsonResponse({'sucesso': True, 'mensagem': 'Registo atualizado com sucesso!'})
                return redirect('producao_lista_fase', agrupamento_id=agrupamento.id, fase=fase)
            else:
                if is_ajax:
                    return JsonResponse({'sucesso': False, 'erro': 'Registo não encontrado.'}, status=400)
                messages.error(request, 'Registo não encontrado.')
                return redirect('producao_lista_fase', agrupamento_id=agrupamento.id, fase=fase)

        elif acao == 'validar':
            ids_duplicados = _ids_duplicados_no_lote('IMPORTADOS', agrupamento)
            if ids_duplicados:
                ids_str = ','.join(str(i) for i in ids_duplicados)
                return redirect(f"{reverse('producao_lista_fase', args=[agrupamento.id, 'importados'])}?duplicados={ids_str}&bloqueio=validar")

            atualizados = RegistroProducao.objects.filter(
                agrupamento=agrupamento, fase__iexact='IMPORTADOS'
            ).update(fase='PENDENTES')
            if atualizados:
                messages.success(request, f'{atualizados} registo(s) validado(s) e enviado(s) para Pendentes!')
            else:
                messages.warning(request, 'Não há registos em Importados para validar.')
            return redirect('producao_formularios_painel', agrupamento_id=agrupamento.id)

        elif acao == 'emitir':
            ids_duplicados = _ids_duplicados_no_lote('PENDENTES', agrupamento)

            campos_identificacao = [
                'agrupamento', 'seguradora', 'tipo_documento', 'documento', 'tipo_pessoa',
                'cpf_cnpj', 'cliente', 'nome_social', 'celular', 'telefone', 'email',
                'agencia', 'contrato', 'segurado', 'vlr_seguro', 'grupo_ramo',
            ]
            registos_pendentes = RegistroProducao.objects.filter(
                agrupamento=agrupamento, fase__iexact='PENDENTES'
            ).exclude(id__in=ids_duplicados).prefetch_related('endossos_extras')

            total_emitidos = 0
            with transaction.atomic():
                for reg in registos_pendentes:
                    endossos = list(reg.endossos_extras.all())

                    for end in endossos:
                        novo = RegistroProducao(fase='EMITIDOS', usuario_cadastro=reg.usuario_cadastro)
                        for campo in campos_identificacao:
                            setattr(novo, campo, getattr(reg, campo))

                        novo.mes_producao = end.mes_producao
                        novo.endosso = end.endosso
                        novo.motivo_endosso = end.motivo_endosso
                        novo.inicio_vigencia = end.inicio_vigencia
                        novo.fim_vigencia = end.fim_vigencia
                        novo.qtd_parcelas = end.qtd_parcelas
                        novo.renovacao_propria = end.renovacao_propria
                        novo.premio_bruto = end.premio_bruto
                        novo.premio_liquido = end.premio_liquido
                        novo.perc_comissao = end.perc_comissao
                        novo.realizado = end.realizado
                        novo.superintendencia = end.superintendencia
                        novo.nome_unidade = end.nome_unidade
                        novo.grupo = end.grupo
                        novo.colaborador = end.colaborador
                        novo.nome_colaborador = end.nome_colaborador
                        novo.gerente_agencia = end.gerente_agencia
                        novo.superintendente = end.superintendente

                        novo.unidade = None
                        novo.save()
                        total_emitidos += 1

                    reg.endossos_extras.all().delete()
                    reg.unidade = None
                    reg.fase = 'EMITIDOS'
                    reg.save()
                    total_emitidos += 1

            if total_emitidos:
                messages.success(request, f'{total_emitidos} registo(s) enviado(s) para Emitidos!')
            elif not ids_duplicados:
                messages.warning(request, 'Não há registos em Pendentes para enviar para Emitidos.')

            if ids_duplicados:
                ids_str = ','.join(str(i) for i in ids_duplicados)
                return redirect(f"{reverse('producao_lista_fase', args=[agrupamento.id, 'pendentes'])}?duplicados={ids_str}&bloqueio=emitir")

            return redirect('producao_formularios_painel', agrupamento_id=agrupamento.id)

        else:
            ids_para_excluir = request.POST.getlist('ids_selecionados')
            if ids_para_excluir:
                RegistroProducao.objects.filter(id__in=ids_para_excluir).delete()
                messages.success(request, f'{len(ids_para_excluir)} registo(s) apagado(s) com sucesso!')
        return redirect('producao_lista_fase', agrupamento_id=agrupamento.id, fase=fase)

    registros = RegistroProducao.objects.filter(agrupamento=agrupamento, fase__iexact=fase_banco).order_by('-id')
    
    seguradoras_base = Seguradora.objects.all().order_by('seguradora')
    unidades = Unidade.objects.all().order_by('cid_unidade')
    tipos_doc = TipoDocumento.objects.all().order_by('tipo_documento')
    tipos_pessoa = TipoPessoa.objects.all().order_by('tipo_pessoa')
    colaboradores = Colaborador.objects.filter(inativo=False).order_by('colaborador')

    produto_hab = Produto.objects.filter(agrupamento=agrupamento).first()
    ramos_hab = Ramo.objects.filter(produto=produto_hab).order_by('cod_ramo') if produto_hab else Ramo.objects.none()

    if fase_banco in ('IMPORTADOS', 'PENDENTES'):
        ids_duplicados = _ids_duplicados_no_lote(fase_banco, agrupamento)
    else:
        ids_duplicados = set()

    ids_duplicados_str = request.GET.get('duplicados', '')
    if ids_duplicados_str:
        ids_duplicados |= {int(i) for i in ids_duplicados_str.split(',') if i.strip().isdigit()}

    context = {
        'agrupamento': agrupamento,
        'fase_nome': fase.capitalize(),
        'registros': registros,
        'seguradoras_base': seguradoras_base,
        'unidades': unidades,
        'tipos_doc': tipos_doc,
        'tipos_pessoa': tipos_pessoa,
        'colaboradores': colaboradores,
        'ramos_hab': ramos_hab,
        'ids_duplicados': ids_duplicados,
    }

    return render(request, 'core/producao/formularios/lista_fase.html', context)



@login_required
def tipo_pessoa_lista(request):
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


"""                             HENRIQUE                                                                    """
from .models import FeriasEstagiario, AuditoriaExportacao, FinanceiroHabitacional
from django.urls import reverse

from django.views.decorators.http import require_POST
from django.http import HttpResponse
import json
import logging
import calendar

@login_required
def estagiarios(request):
    return render(request, 'core/administracao/estagiarios/estagiarios.html')

@login_required
def lista_estagiarios(request):
    estagiarios_filtrados = Colaborador.objects.filter(
        Q(matricula__startswith='70') | Q(matricula__startswith='72')
    ).order_by('colaborador')

    contexto = {
        'estagiarios_filtrados': estagiarios_filtrados,
    }

    return render(request, 'core/administracao/estagiarios/lista_estagiarios.html', contexto)


@login_required
def ferias_estagiarios(request):

    if request.method == 'POST':
        matricula = request.POST.get('matricula_selecionada')
        acao = request.POST.get('acao') 
        
        try:
            estagiario = Colaborador.objects.get(matricula=matricula)

            if acao == 'salvar_inicio':
                inicio_emprego = request.POST.get('data_inicio_emprego')
                fim_emprego = request.POST.get('data_fim_emprego')
                
                estagiario.data_inicio_emprego = inicio_emprego or None
                estagiario.data_fim_emprego = fim_emprego or None
                estagiario.save()

            elif acao == 'salvar_ferias':
                inicio_ferias_str = request.POST.get('inicio_ferias')
                qtd_dias_str = request.POST.get('quantidade_dias')
                
                inicio_ferias = datetime.strptime(inicio_ferias_str, "%Y-%m-%d").date()
                qtd_dias = int(qtd_dias_str)
                
                FeriasEstagiario.objects.create(
                    colaborador=estagiario,
                    inicio_ferias=inicio_ferias,
                    quantidade_dias=qtd_dias
                )

            elif acao == 'deletar_ferias':
                ferias_ids_str = request.POST.get('ferias_ids', '')
                
                if ferias_ids_str:
                    ids_lista = [int(x) for x in ferias_ids_str.split(',') if x.isdigit()]
                    FeriasEstagiario.objects.filter(colaborador=estagiario, id__in=ids_lista).delete()

            url_redirecionamento = reverse('ferias_estagiarios') + f'?matricula={matricula}'
            return redirect(url_redirecionamento)

        except Colaborador.DoesNotExist:
            return redirect('ferias_estagiarios')
        except (ValueError, TypeError) as e:
            return redirect('ferias_estagiarios')

    # ------------------------------------------
    matricula_persistida = request.GET.get('matricula', None)

    estagiarios_filtrados = Colaborador.objects.filter(
        Q(matricula__startswith='70') | Q(matricula__startswith='72')
    ).order_by('colaborador')
    
    todas_ferias = FeriasEstagiario.objects.filter(colaborador__in=estagiarios_filtrados).order_by('-inicio_ferias')

    contexto = {
        'estagiarios_filtrados': estagiarios_filtrados,
        'todas_ferias': todas_ferias, 
        'matricula_persistida': matricula_persistida
    }
    
    return render(request, 'core/administracao/estagiarios/ferias_estagiarios.html', contexto)

@login_required
def lista_auditoria(request):
    lista_auditados = AuditoriaExportacao.objects.all().order_by('-data_hora')
    
    context = {
        'lista_auditados': lista_auditados
    }
    
    return render(request, 'core/auditoria/auditoria.html', context)


#As duas funções a baixo são pra registrar auditoria no front e outra no back
@login_required
@require_POST
def registrar_auditoria(request):
    try:
        data = json.loads(request.body)

        acao_recebida = data.get('acao')
        detalhe_recebido = data.get('detalhe')
        
        AuditoriaExportacao.objects.create(
            usuario=request.user,
            acao=acao_recebida,
            detalhe=detalhe_recebido
        )
        
        # Retorna sucesso HTTP 204 (Deu certo, sem conteúdo para responder)
        return HttpResponse(status=204)
        
    except Exception as e:
        # Se algo der errado (ex: banco fora do ar), retorna erro 500 (Erro Interno)
        return HttpResponse(status=500)

logger = logging.getLogger(__name__)
def registrar_auditoria_backend(usuario, acao, detalhe):    

    try:
        AuditoriaExportacao.objects.create(
            usuario=usuario,
            acao=acao,
            detalhe=detalhe
        )

    except Exception as e:
        # Tipo console.error()
        logger.error(f"Falha ao registrar auditoria no backend: {e}")


@login_required
def producao_relatorios(request):
    return render(request, 'core/producao/relatorios/index.html')

@login_required
def financeiro_processamentos(request):
    return render(request, 'core/financeiro/processamentos/index.html')

@login_required
def financeiro_formularios(request):
    return render(request, 'core/financeiro/formularios/index.html')

@login_required
def financeiro_relatorios(request):
    return render(request, 'core/financeiro/relatorios/index.html')



@login_required
def listar_usuarios(request):
    eh_admin = request.user.is_superuser or (hasattr(request.user, 'perfil') and request.user.perfil.nivel_acesso == 'ADMIN')
    if not eh_admin:
        messages.error(request, 'Acesso Negado. Apenas Administradores podem acessar.')
        return redirect('home')

    query = request.GET.get('q', '') 
    if query:
        usuarios = User.objects.filter(
            Q(username__icontains=query) |
            Q(perfil__colaborador__matricula__icontains=query) |
            Q(first_name__icontains=query)
        ).order_by('first_name')
    else:
        usuarios = User.objects.all().order_by('first_name')

    return render(request, 'core/administracao/usuarios/listar_usuarios.html', {
        'usuarios': usuarios,
        'query': query,
    })


@login_required
def form_usuario(request, id=None):
    eh_admin = request.user.is_superuser or (hasattr(request.user, 'perfil') and request.user.perfil.nivel_acesso == 'ADMIN')
    if not eh_admin:
        messages.error(request, 'Acesso Negado.')
        return redirect('home')

    # Se recebemos um ID, é edição. Senão, é criação.
    if id:
        usuario_edit = get_object_or_404(User, id=id)
        perfil = getattr(usuario_edit, 'perfil', None)
    else:
        usuario_edit = None
        perfil = None

    colaboradores = Colaborador.objects.filter(inativo=False).order_by('colaborador')

    if request.method == 'POST':
        form = NovoUsuarioForm(request.POST)
        if form.is_valid():
            login = form.cleaned_data['login']
            matricula = form.cleaned_data['matricula']
            senha = form.cleaned_data['password']


            colaborador_obj = Colaborador.objects.filter(matricula=matricula).first()
            if not colaborador_obj:
                messages.error(request, f'Erro: A matrícula {matricula} não existe na base.')
                return render(request, 'core/administracao/usuarios/form_usuario.html', {'form': form, 'usuario_edit': usuario_edit, 'colaboradores': colaboradores})

            if usuario_edit:

                usuario_edit.username = login
                if senha:
                    usuario_edit.set_password(senha)
                
                usuario_edit.is_active = form.cleaned_data.get('is_active', False)
                usuario_edit.save()

                if perfil:
                    perfil.colaborador = colaborador_obj
                    perfil.nivel_acesso = form.cleaned_data['nivel_acesso']

                    perfil.sub_base_formularios = form.cleaned_data['sub_base_formularios']
                    perfil.sub_base_processamentos = form.cleaned_data['sub_base_processamentos']
                    perfil.sub_base_relatorios = form.cleaned_data['sub_base_relatorios']

                    perfil.sub_prod_vendas = form.cleaned_data['sub_prod_vendas']
                    perfil.sub_prod_formularios = form.cleaned_data['sub_prod_formularios']
                    perfil.sub_prod_processamentos = form.cleaned_data['sub_prod_processamentos']
                    perfil.sub_prod_relatorios = form.cleaned_data['sub_prod_relatorios']

                    perfil.sub_fin_formularios = form.cleaned_data['sub_fin_formularios']
                    perfil.sub_fin_processamentos = form.cleaned_data['sub_fin_processamentos']
                    perfil.sub_fin_relatorios = form.cleaned_data['sub_fin_relatorios']

                    perfil.sub_admin_criar = form.cleaned_data['sub_admin_criar']
                    perfil.sub_admin_estagiarios = form.cleaned_data['sub_admin_estagiarios']

                    perfil.aba_auditoria = form.cleaned_data['aba_auditoria']

                    perfil.save()
                
                messages.success(request, 'Usuário atualizado com sucesso!')
            else:

                if User.objects.filter(username=login).exists():
                    messages.error(request, 'Este login já está em uso no sistema.')
                    return render(request, 'core/administracao/usuarios/form_usuario.html', {'form': form, 'usuario_edit': usuario_edit, 'colaboradores': colaboradores})
                
                if not senha:
                    messages.error(request, 'A senha é obrigatória para a criação de um novo usuário.')
                    return render(request, 'core/administracao/usuarios/form_usuario.html', {'form': form, 'usuario_edit': usuario_edit, 'colaboradores': colaboradores})

                user = User.objects.create_user(username=login, password=senha)
                PerfilUsuario.objects.create(
                    usuario=user,
                    colaborador=colaborador_obj,
                    nivel_acesso=form.cleaned_data['nivel_acesso'],
                    
                    sub_base_formularios=form.cleaned_data['sub_base_formularios'],
                    sub_base_processamentos=form.cleaned_data['sub_base_processamentos'],
                    sub_base_relatorios=form.cleaned_data['sub_base_relatorios'],

                    sub_prod_vendas=form.cleaned_data['sub_prod_vendas'],
                    sub_prod_formularios=form.cleaned_data['sub_prod_formularios'],
                    sub_prod_processamentos=form.cleaned_data['sub_prod_processamentos'],
                    sub_prod_relatorios=form.cleaned_data['sub_prod_relatorios'],

                    sub_fin_formularios=form.cleaned_data['sub_fin_formularios'],
                    sub_fin_processamentos=form.cleaned_data['sub_fin_processamentos'],
                    sub_fin_relatorios=form.cleaned_data['sub_fin_relatorios'],

                    sub_admin_criar=form.cleaned_data['sub_admin_criar'],
                    sub_admin_estagiarios=form.cleaned_data['sub_admin_estagiarios'],

                    aba_auditoria=form.cleaned_data['aba_auditoria']
                )
                messages.success(request, f'Sucesso! Usuário "{login}" foi criado.')
                registrar_auditoria_backend(usuario=request.user, acao="Criou usuário", detalhe=login)

            return redirect('listar_usuarios')
    else:

        if usuario_edit:
            dados_iniciais = {
                'login': usuario_edit.username,
                'matricula': perfil.colaborador.matricula if perfil and perfil.colaborador else '',
                'nivel_acesso': perfil.nivel_acesso if perfil else 'COMUM',
                'is_active': usuario_edit.is_active,

                'sub_base_formularios': perfil.sub_base_formularios if perfil else False,
                'sub_base_processamentos': perfil.sub_base_processamentos if perfil else False,
                'sub_base_relatorios': perfil.sub_base_relatorios if perfil else False,

                'sub_prod_vendas': perfil.sub_prod_vendas if perfil else False,
                'sub_prod_formularios': perfil.sub_prod_formularios if perfil else False,
                'sub_prod_processamentos': perfil.sub_prod_processamentos if perfil else False,
                'sub_prod_relatorios': perfil.sub_prod_relatorios if perfil else False,

                'sub_fin_formularios': perfil.sub_fin_formularios if perfil else False,
                'sub_fin_processamentos': perfil.sub_fin_processamentos if perfil else False,
                'sub_fin_relatorios': perfil.sub_fin_relatorios if perfil else False,

                'sub_admin_criar': perfil.sub_admin_criar if perfil else False,
                'sub_admin_estagiarios': perfil.sub_admin_estagiarios if perfil else False,

                'aba_auditoria': perfil.aba_auditoria if perfil else False,
            }
            form = NovoUsuarioForm(initial=dados_iniciais)
        else:
            form = NovoUsuarioForm(initial={'is_active': True})

    todos_perfis = PerfilUsuario.objects.select_related('usuario', 'colaborador').exclude(usuario__is_superuser=True)

    return render(request, 'core/administracao/usuarios/form_usuario.html', {
        'form': form,
        'usuario_edit': usuario_edit,
        'colaboradores': colaboradores,
        'todos_perfis': todos_perfis
    })

@login_required
def excluir_usuarios(request):
    if request.method == 'POST':
        ids_para_excluir = request.POST.getlist('usuarios_ids') 
        
        if ids_para_excluir:
            usuarios_a_excluir = User.objects.filter(id__in=ids_para_excluir).exclude(is_superuser=True)
            
            logins_excluidos = ", ".join([u.username for u in usuarios_a_excluir])
            
            quantidade_deletada, _ = usuarios_a_excluir.delete()
            
            if quantidade_deletada > 0:
                registrar_auditoria_backend(usuario=request.user, acao="Deletou usuário(s)", detalhe=logins_excluidos)
                
                messages.success(request, f'{quantidade_deletada} usuário(s) excluído(s) com sucesso!')
            else:
                messages.warning(request, 'Nenhum usuário foi excluído.')

    return redirect('listar_usuarios')

@login_required
def financeiro_habitacional(request):
    # Pega apenas os meses que JÁ FORAM PROCESSADOS (ignora os nulos/vazios) para popular o Modal
    meses_disponiveis = FinanceiroHabitacional.objects.exclude(
        Q(data_processamento__isnull=True) | Q(data_processamento__exact='')
    ).values_list('data_processamento', flat=True).distinct()
    
    # Ordena os meses para o Modal do mais recente para o mais antigo
    def sort_key(m):
        if m and '/' in m:
            mes, ano = m.split('/')
            return (int(ano), int(mes))
        return (0, 0)

    meses_disponiveis = sorted(list(meses_disponiveis), key=sort_key, reverse=True)

    return render(request, 'core/financeiro/processamentos/habitacional.html', {
        'meses_disponiveis': meses_disponiveis
    })


@login_required
def processar_mensal_habitacional(request):
    agora = timezone.localtime(timezone.now())
    mes_ano_atual = agora.strftime('%m/%Y')
    mes_str = agora.strftime('%m')
    ano_str = agora.strftime('%Y')

    aguardando = FinanceiroHabitacional.objects.filter(
        Q(data_processamento__isnull=True) | Q(data_processamento__exact='')
    )

    if not aguardando.exists():
        messages.warning(request, "Atenção: Não há registros aguardando processamento.")
        return redirect('financeiro_habitacional')
    
    aguardando.update(data_processamento=mes_ano_atual)

    produto_hab = Produto.objects.filter(agrupamento__agrupamento__icontains='Habitacional').first()
    
    if produto_hab and produto_hab.mes_folha_pagamento_em_aberto:
        data_atual = produto_hab.mes_folha_pagamento_em_aberto
        novo_mes = data_atual.month + 1
        novo_ano = data_atual.year
        
        if novo_mes > 12:
            novo_mes = 1
            novo_ano += 1
            
        ultimo_dia_novo_mes = calendar.monthrange(novo_ano, novo_mes)[1]
        novo_dia = min(data_atual.day, ultimo_dia_novo_mes)
        
        produto_hab.mes_folha_pagamento_em_aberto = data_atual.replace(year=novo_ano, month=novo_mes, day=novo_dia)
        produto_hab.save()

    agrupados = FinanceiroHabitacional.objects.filter(
        data_processamento=mes_ano_atual
    ).exclude(
        Q(registro_producao__premio_bruto=0) | Q(registro_producao__premio_bruto__isnull=True)
    ).values('matricula_colaborador').annotate(total_valor=Sum('valor'))

    linhas_txt = []
    for item in agrupados:
        matricula = (item['matricula_colaborador'] or "").strip()
        if not matricula:
            continue

        m = str(matricula).zfill(9) 
        mat_formatada = f"{m[:2]} {m[2:-1]} {m[-1]}" if len(m) >= 3 else m
        
        valor_centavos = int(item['total_valor'] * 100)
        valor_formatado = str(valor_centavos).zfill(11)
        
        linha = f"{mat_formatada} {mes_str} {ano_str} 000087 {valor_formatado} 001      "
        linhas_txt.append(linha)

    conteudo = "\n".join(linhas_txt) + "\n"

    nome_arquivo = f"processamento_habitacional_{mes_str}-{ano_str}.txt"
    response = HttpResponse(conteudo, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return response


@login_required 
def exportar_txt_habitacional(request):
    mes_escolhido = request.GET.get('mes')

    if not mes_escolhido:
        messages.error(request, "Selecione um mês para exportar.")
        return redirect('financeiro_habitacional')

    registros = FinanceiroHabitacional.objects.filter(
        data_processamento=mes_escolhido
    ).exclude(
        Q(registro_producao__premio_bruto=0) | Q(registro_producao__premio_bruto__isnull=True)
    )

    if not registros.exists():
        messages.warning(request, f"Nenhum registro válido para exportação no mês {mes_escolhido}.")
        return redirect('financeiro_habitacional')

    mes_str, ano_str = mes_escolhido.split('/')

    agrupados = registros.values('matricula_colaborador').annotate(total_valor=Sum('valor'))

    linhas_txt = []
    for item in agrupados:
        matricula = (item['matricula_colaborador'] or "").strip()
        if not matricula:
            continue

        m = str(matricula).zfill(9) 
        mat_formatada = f"{m[:2]} {m[2:-1]} {m[-1]}" if len(m) >= 3 else m
        
        valor_centavos = int(item['total_valor'] * 100)
        valor_formatado = str(valor_centavos).zfill(11)
        
        linha = f"{mat_formatada} {mes_str} {ano_str} 000087 {valor_formatado} 001      "
        linhas_txt.append(linha)

    conteudo = "\n".join(linhas_txt) + "\n"
    
    nome_arquivo = f"exportacao_habitacional_{mes_str}-{ano_str}.txt"
    response = HttpResponse(conteudo, content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return response