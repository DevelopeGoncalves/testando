# ---------------------------------------------------------------------------
# Sincronizacao do card Clientes com os registos de producao (Odonto/Habitacional)
# ---------------------------------------------------------------------------
# Regras combinadas com o Alex:
#
# 1) O CPF/CNPJ e a chave que identifica a pessoa (isso nunca muda). Toda
#    importacao procura o cliente por esse numero antes de qualquer coisa.
# 2) O registo de producao guarda o ID do cadastro em `cliente_cadastro`
#    (Base > Formularios > Clientes) e apenas espelha nome, e-mail, telefones.
# 3) Se a planilha nova trouxer dados diferentes (mudou o e-mail, o sobrenome,
#    o celular...), o cadastro do cliente e ATUALIZADO - nao se cria um cliente
#    repetido para o mesmo CPF/CNPJ.
# 4) O card Clientes e a base: quando o cadastro muda ali, a alteracao desce na
#    hora para todos os registos de producao ligados aquele cliente (ver o
#    signal em core/signals.py).

from django.db import IntegrityError, transaction

from .models import Cliente, RegistroProducao, TipoPessoa
from .odonto import _sem_acento


def somente_digitos(valor):
    """Deixa so os numeros (tira ponto, traco, barra e espaco do CPF/CNPJ)."""
    if valor is None:
        return ''
    return ''.join(c for c in str(valor) if c.isdigit())


def cortar(valor, tamanho):
    """Corta o texto no limite do campo do card Clientes."""
    return str(valor or '').strip()[:tamanho]


def variantes_documento(cpf_cnpj):
    """Formas em que o mesmo CPF/CNPJ pode ter sido gravado no banco.

    Cadastros antigos guardaram o documento formatado (000.000.000-00), por
    isso a busca testa o numero limpo e tambem a mascara.
    """
    documento = somente_digitos(cpf_cnpj)[:14]
    if not documento:
        return []

    variantes = [documento]
    if len(documento) == 11:
        variantes.append(
            f'{documento[:3]}.{documento[3:6]}.{documento[6:9]}-{documento[9:]}'
        )
    elif len(documento) == 14:
        variantes.append(
            f'{documento[:2]}.{documento[2:5]}.{documento[5:8]}/'
            f'{documento[8:12]}-{documento[12:]}'
        )
    return variantes


def buscar_cliente(cpf_cnpj):
    """Devolve o cliente ja cadastrado com aquele CPF/CNPJ (ou None)."""
    variantes = variantes_documento(cpf_cnpj)
    if not variantes:
        return None
    return Cliente.objects.filter(cpf_cnpj__in=variantes).first()


def tipo_pessoa_cliente(cpf_cnpj_digitos, tipo_pessoa_texto=''):
    """Acha o TipoPessoa cadastrado (Fisica / Juridica) para vincular ao cliente."""
    texto = _sem_acento(tipo_pessoa_texto)
    if texto:
        juridica = texto.startswith('PJ') or 'JURID' in texto
    else:
        juridica = len(cpf_cnpj_digitos) > 11
    procura = 'JURID' if juridica else 'FIS'
    for tp in TipoPessoa.objects.all():
        if procura in _sem_acento(tp.tipo_pessoa):
            return tp
    return None


def sincronizar_cliente(cpf_cnpj, nome, nome_social='', celular='', telefone='',
                        email='', tipo_pessoa=''):
    """Acha o cliente pelo CPF/CNPJ, atualiza o que mudou e devolve o cadastro.

    - Sem CPF/CNPJ na linha da planilha nao ha como identificar a pessoa: None.
    - Cliente novo: cadastra e devolve o registo recem-criado.
    - Cliente que ja existe: sobrescreve com os dados da planilha os campos que
      vieram preenchidos e estao diferentes (nome, nome social, celular,
      telefone, e-mail). Campo que veio vazio na planilha nao apaga o que ja
      estava no cadastro.
    """
    documento = somente_digitos(cpf_cnpj)[:14]
    if not documento:
        return None

    novos = {
        'nome': cortar(nome, 60),
        'nome_social': cortar(nome_social, 60),
        'celular': somente_digitos(celular)[:11],
        'telefone': somente_digitos(telefone)[:10],
        'email': cortar(email, 80),
    }

    cliente = buscar_cliente(documento)

    if cliente is None:
        try:
            with transaction.atomic():
                return Cliente.objects.create(
                    cpf_cnpj=documento,
                    tipo_pessoa=tipo_pessoa_cliente(documento, tipo_pessoa),
                    **{**novos, 'nome': novos['nome'] or documento},
                )
        except IntegrityError:
            # Outra linha da mesma planilha acabou de cadastrar esse CPF/CNPJ
            cliente = buscar_cliente(documento)
            if cliente is None:
                return None

    # Ja existia: atualiza so o que veio preenchido e esta diferente
    alterados = []
    for campo, valor in novos.items():
        if valor and valor != (getattr(cliente, campo) or ''):
            setattr(cliente, campo, valor)
            alterados.append(campo)

    # Cadastro antigo com o documento formatado: normaliza para so numeros
    if cliente.cpf_cnpj != documento and not Cliente.objects.filter(
        cpf_cnpj=documento
    ).exclude(id=cliente.id).exists():
        cliente.cpf_cnpj = documento
        alterados.append('cpf_cnpj')

    if cliente.tipo_pessoa_id is None:
        tp = tipo_pessoa_cliente(documento, tipo_pessoa)
        if tp:
            cliente.tipo_pessoa = tp
            alterados.append('tipo_pessoa')

    if alterados:
        # O save dispara o signal que espelha a mudanca nos registos de producao
        cliente.save(update_fields=alterados)

    return cliente


def dados_do_cliente(cliente):
    """Como os campos do registo de producao ficam segundo o cadastro (a base)."""
    dados = {
        'cpf_cnpj': (cliente.cpf_cnpj or '')[:50],
        'cliente': (cliente.nome or '')[:200],
        'nome_social': (cliente.nome_social or '')[:200],
        'celular': (cliente.celular or '')[:50],
        'telefone': (cliente.telefone or '')[:50],
        'email': (cliente.email or '')[:150],
    }
    if cliente.tipo_pessoa_id:
        dados['tipo_pessoa'] = (cliente.tipo_pessoa.tipo_pessoa or '')[:50]
    return dados


def propagar_para_registros(cliente):
    """Desce os dados do cadastro para os registos de producao ligados a ele.

    Tambem adota os registos antigos que foram importados antes do vinculo
    existir: quem tem o mesmo CPF/CNPJ e ainda esta sem `cliente_cadastro`
    passa a apontar para este cadastro.
    """
    if cliente is None or cliente.pk is None:
        return 0

    dados = dados_do_cliente(cliente)
    total = RegistroProducao.objects.filter(cliente_cadastro=cliente).update(**dados)

    variantes = variantes_documento(cliente.cpf_cnpj)
    if variantes:
        total += RegistroProducao.objects.filter(
            cliente_cadastro__isnull=True, cpf_cnpj__in=variantes
        ).update(cliente_cadastro=cliente, **dados)

    return total
