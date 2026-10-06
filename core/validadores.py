# validador cpf alex
# ---------------------------------------------------------------------------
# Validador de CPF/CNPJ (biblioteca validate-docbr: pip install validate-docbr).
# Usado em qualquer formulário que tenha um campo de CPF/CNPJ (Cliente,
# Indicação/Renovação/Endosso) - ver `clean_cpf_cnpj`/`clean_cpf_cliente` em
# core/forms.py, que só chamam a função `documento_cpf_cnpj_valido` daqui.
#
# Regras combinadas com o Alex:
# - No banco guarda SÓ NÚMERO (sem ponto, traço, barra ou espaço).
# - A pessoa pode informar o CPF/CNPJ sem os zeros à esquerda (comum quando o
#   número veio de uma planilha/Excel, que trata como número e perde o zero
#   do início). O validador completa o número sozinho antes de validar:
#       até 11 dígitos  -> completa com zero à esquerda até 11 e valida como CPF
#       de 12 a 14 dígitos -> completa com zero à esquerda até 14 e valida como CNPJ
#   e guarda o número JÁ COMPLETO no banco.
# - A máscara (com ponto e traço, ao digitar no formulário) é só visual, feita
#   em JavaScript - ver "mascara cpf cnpj alex" em core/templates/core/layout.html.
#   Aqui (Python/backend) só valida e devolve o número limpo pra gravar.
# ---------------------------------------------------------------------------
from django import forms
from validate_docbr import CNPJ, CPF


def somente_digitos(valor):
    """Tira ponto, traço, barra e espaço do CPF/CNPJ - fica só o número."""
    if valor is None:
        return ''
    return ''.join(c for c in str(valor) if c.isdigit())


def documento_cpf_cnpj_valido(valor):
    """Valida CPF ou CNPJ e devolve o número completo (com os zeros à esquerda
    que a pessoa não tiver digitado), pronto pra gravar no banco.

    Levanta `django.forms.ValidationError` quando o número não é um CPF nem
    um CNPJ válido. Campo vazio devolve vazio (cada formulário decide se o
    campo é obrigatório ou não - isso aqui só valida o formato/dígito
    verificador de quem preencheu alguma coisa).
    """
    digitos = somente_digitos(valor)
    if not digitos:
        return ''

    if len(digitos) > 14:
        raise forms.ValidationError('CPF/CNPJ inválido: têm dígitos demais. Confira o número.')

    if len(digitos) <= 11:
        documento = digitos.zfill(11)
        if not CPF().validate(documento):
            raise forms.ValidationError('CPF inválido. Confira o número digitado.')
    else:
        documento = digitos.zfill(14)
        if not CNPJ().validate(documento):
            raise forms.ValidationError('CNPJ inválido. Confira o número digitado.')

    return documento


def verificar_documento_por_tipo(valor, tipo):
    """Confere o CPF/CNPJ de acordo com o TIPO escolhido na caixinha da ficha
    (CPF ou CNPJ) - ao contrário de `documento_cpf_cnpj_valido`, que adivinha
    o tipo pelo tamanho do número, aqui quem manda é a escolha da pessoa.

    Usado na validação em tempo real (ver "validador cpf alex (tempo real)"
    no JavaScript do formulário e em `buscar_cliente_por_cpf` no views.py):
    ao sair do campo ou apertar Enter, confirma na hora se é válido, sem
    precisar salvar a ficha.

    Devolve (valido, documento_completo, mensagem) - nunca levanta exceção
    (diferente de `documento_cpf_cnpj_valido`), pra ficar fácil de transformar
    em JSON na view.
    """
    digitos = somente_digitos(valor)
    if not digitos:
        return True, '', ''  # campo vazio: cada formulário decide se é obrigatório

    if (tipo or '').strip().upper() == 'CNPJ':
        if len(digitos) > 14:
            return False, digitos, 'CNPJ inválido: tem dígitos demais.'
        documento = digitos.zfill(14)
        if not CNPJ().validate(documento):
            return False, documento, 'CNPJ inválido. Confira o número digitado.'
        return True, documento, 'CNPJ válido.'

    # CPF (padrão)
    if len(digitos) > 11:
        return False, digitos, 'CPF inválido: tem dígitos demais.'
    documento = digitos.zfill(11)
    if not CPF().validate(documento):
        return False, documento, 'CPF inválido. Confira o número digitado.'
    return True, documento, 'CPF válido.'
