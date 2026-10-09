# Cache das telas de Vendas no navegador.
#
# O navegador guarda a pagina do card e, a cada abertura, so pergunta ao
# servidor "mudou alguma coisa?". O servidor calcula uma assinatura dos dados
# que aparecem na tela (registros, ligacoes, tabelas de apoio, permissoes do
# usuario e versao dos arquivos do sistema); se for a mesma da copia guardada,
# responde 304 na hora e o navegador reaproveita a copia, sem montar a lista
# de novo. Qualquer inclusao, alteracao ou exclusao - feita por qualquer
# usuario - muda a assinatura e a pagina e montada de novo automaticamente.
#
# "Em uso por" fica de fora da assinatura de proposito: muda a todo instante
# enquanto alguem atende, e a propria tela ja atualiza isso sozinha a cada
# 5 segundos (atualizarAtendimentos).
import hashlib
import os
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseNotModified
from django.utils.http import parse_etags, quote_etag

from .models import (
    AcompanhamentoEmissao, Colaborador, Indicacao, IndicacaoEndosso, IndicacaoRenovacao,
    LigacaoEndosso, LigacaoIndicacao, LigacaoRenovacao, MotivoNaoVenda, Produto, Ramo,
    Seguradora, TipoDocumento, TipoPessoa, Unidade,
)

CAMPOS_FORA_DA_ASSINATURA = {'atendimento_por', 'atendimento_em'}

TABELAS_DE_APOIO = [
    Seguradora, Ramo, TipoDocumento, TipoPessoa, Colaborador, Unidade, Produto,
    MotivoNaoVenda, AcompanhamentoEmissao,
]

TABELAS_NOVO = [Indicacao, LigacaoIndicacao]
TABELAS_RENOVACAO = [IndicacaoRenovacao, LigacaoRenovacao]
TABELAS_ENDOSSO = [IndicacaoEndosso, LigacaoEndosso]
TABELAS_EMISSAO = TABELAS_NOVO + TABELAS_RENOVACAO + TABELAS_ENDOSSO

_PASTA_CORE = os.path.dirname(os.path.abspath(__file__))
_ARQUIVOS_DO_SISTEMA = [
    os.path.join(_PASTA_CORE, 'templates', 'core', 'layout.html'),
    os.path.join(_PASTA_CORE, 'templates', 'core', 'producao', 'vendas'),
    _PASTA_CORE,
]


def _versao_dos_arquivos():
    """Muda quando algum arquivo do sistema (templates de Vendas, layout, .py do
    core) e atualizado - assim uma copia antiga nunca e reaproveitada depois
    de uma atualizacao do sistema."""
    partes = []
    for caminho in _ARQUIVOS_DO_SISTEMA:
        if os.path.isdir(caminho):
            for nome in sorted(os.listdir(caminho)):
                if nome.endswith(('.html', '.py')):
                    arquivo = os.path.join(caminho, nome)
                    partes.append(f'{nome}:{os.path.getmtime(arquivo)}')
        elif os.path.exists(caminho):
            partes.append(f'{caminho}:{os.path.getmtime(caminho)}')
    return '|'.join(partes)


def _assinatura_tabela(model, hash_total):
    campos = [
        f.attname for f in model._meta.concrete_fields
        if f.attname not in CAMPOS_FORA_DA_ASSINATURA
    ]
    hash_total.update(model._meta.label.encode())
    for linha in model.objects.order_by('pk').values_list(*campos).iterator(chunk_size=2000):
        hash_total.update(repr(linha).encode())


def _assinatura_usuario(request):
    user = request.user
    partes = [
        str(user.pk), user.username, str(user.is_superuser),
        request.session.session_key or '',
        request.COOKIES.get(settings.CSRF_COOKIE_NAME, ''),
        request.get_full_path(),
    ]
    perfil = getattr(user, 'perfil', None)
    if perfil is not None:
        partes.append(repr(sorted(
            (f.attname, getattr(perfil, f.attname)) for f in perfil._meta.concrete_fields
        )))
    return '|'.join(partes)


def _calcular_etag(request, tabelas):
    hash_total = hashlib.md5(usedforsecurity=False)
    hash_total.update(_assinatura_usuario(request).encode())
    hash_total.update(_versao_dos_arquivos().encode())
    for model in tabelas + TABELAS_DE_APOIO:
        _assinatura_tabela(model, hash_total)
    return hash_total.hexdigest()


def _tem_mensagem_pendente(request):
    # len() nao consome as mensagens - elas continuam la pra pagina mostrar.
    return len(messages.get_messages(request)) > 0


def cache_navegador_vendas(tabelas):
    """Guarda a tela no navegador e so remonta quando algum dado dela mudou."""
    def decorador(view):
        @wraps(view)
        def view_com_cache(request, *args, **kwargs):
            if request.method != 'GET' or _tem_mensagem_pendente(request):
                return view(request, *args, **kwargs)

            etag = quote_etag(_calcular_etag(request, tabelas))
            if etag in parse_etags(request.headers.get('If-None-Match', '')):
                resposta = HttpResponseNotModified()
            else:
                resposta = view(request, *args, **kwargs)
                if resposta.status_code != 200:
                    return resposta

            resposta['ETag'] = etag
            # private: so o navegador do proprio usuario guarda; no-cache: sempre
            # confere com o servidor antes de reaproveitar a copia.
            resposta['Cache-Control'] = 'private, no-cache'
            return resposta
        return view_com_cache
    return decorador
