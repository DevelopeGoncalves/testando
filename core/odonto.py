import re
import unicodedata

import pandas as pd

# Status considerado "produção válida" conforme a aba Orientações da planilha.
STATUS_CONCLUIDO = 'PROPOSTA CONCLUIDA COM SUCESSO'

# Valores de produção por tipo de plano PF replica a fórmula da planilha:

VALOR_MENSAL_PF = 54.99
VALOR_ANUAL_PF = 659.88

# Nomes de coluna do export da Odontoprev que não mudam de arquivo pra arquivo

COLUNA_STATUS = {'PF': 'STATUS_PROPOSTA', 'PJ': 'STATUS'}
COLUNA_CPF_VENDEDOR = {'PF': 'CPF_FORCA', 'PJ': 'CPF'}
COLUNA_NOME_VENDEDOR = {'PF': 'NOME_FORCA', 'PJ': 'VENDEDOR'}
COLUNA_TIPO_PLANO_PF = 'TIPO_PLANO'

# as duas colunas PF e PJ. usando para a chave para somar a quantidade de vida.

COLUNA_NUM_PROPOSTA = 'NUM_PROPOSTA'

# Valor padrão do Tipo documento quando a parametrização não mapeia nada fica proposta como padrao

TIPO_DOCUMENTO_PADRAO = 'Proposta'
TIPO_PESSOA = {'PF': 'Pessoa Física', 'PJ': 'Pessoa Jurídica'}
# Normalizações
def _sem_acento(texto):
    if texto is None:
        return ''
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode()
    return ' '.join(texto.upper().split())


def _so_digitos(valor):
    if valor is None:
        return ''
    return re.sub(r'\D', '', str(valor))


def _cpf_normalizado(valor):
    """CPF apenas com dígitos e completado com zeros à esquerda (11 posições)."""
    digitos = _so_digitos(valor)
    if not digitos:
        return ''
    # A exportação da Odontoprev às vezes perde o zero inicial do CPF.
    return digitos.zfill(11) if len(digitos) <= 11 else digitos


def _para_numero(valor):
    """Converte o valor da venda vindo como texto ('659.88', '1.234,56') em float."""
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)

    texto = str(valor).strip().replace('R$', '').replace(' ', '')
    if not texto:
        return 0.0

    if ',' in texto and '.' in texto:
        texto = texto.replace('.', '').replace(',', '.')
    elif ',' in texto:
        texto = texto.replace(',', '.')

    try:
        return float(texto)
    except ValueError:
        return 0.0
# Leitura dos relatórios da Odontoprev
def ler_relatorio_odonto(arquivo):
    bruto = None
    for engine in ('xlrd', 'openpyxl'):
        try:
            arquivo.seek(0)
            bruto = pd.read_excel(arquivo, engine=engine, header=None, dtype=str)
            break
        except ImportError:
            continue
        except Exception:
            continue

    if bruto is None:
        raise ValueError(
            'Não foi possível ler o arquivo enviado. Verifique se é o relatório '
            'da Odontoprev em formato Excel (.xls ou .xlsx) e exporte novamente.'
        )

    linha_cabecalho = None
    for indice, linha in bruto.iterrows():
        valores = {_sem_acento(v) for v in linha.tolist()}
        if 'NUM_PROPOSTA' in valores and 'DT_VENDA' in valores:
            linha_cabecalho = indice
            break

    if linha_cabecalho is None:
        raise ValueError(
            'Cabeçalho não localizado na planilha (não foi encontrada a coluna '
            'NUM_PROPOSTA). Envie o relatório exportado pelo site da Odontoprev.'
        )

    colunas = [_sem_acento(c) for c in bruto.iloc[linha_cabecalho].tolist()]
    df = bruto.iloc[linha_cabecalho + 1:].copy()
    df.columns = colunas
    df = df.loc[:, [c for c in df.columns if c]]
    df = df.dropna(how='all').reset_index(drop=True)
    return df


# Cruzamento com a base (Colaboradores + Agência CID)
class BaseColaboradores:

    def __init__(self, colaboradores):
        self.por_cpf = {}
        self.por_nome = {}
        self.nomes = []

        for colaborador in colaboradores:
            cpf = _cpf_normalizado(colaborador.cpf)
            if cpf:
                self._registrar(self.por_cpf, cpf, colaborador)

            for nome in (colaborador.colaborador, colaborador.nome_social):
                nome_chave = _sem_acento(nome)
                if nome_chave:
                    self._registrar(self.por_nome, nome_chave, colaborador)
                    self.nomes.append((nome_chave, colaborador))

    @staticmethod
    def _registrar(indice, chave, colaborador):
        atual = indice.get(chave)
        # Havendo repetição, mantém o colaborador ativo (o inativo é o histórico).
        if atual is None or (atual.inativo and not colaborador.inativo):
            indice[chave] = colaborador

    def buscar(self, cpf, nome):
        colaborador = self.por_cpf.get(_cpf_normalizado(cpf))
        if colaborador:
            return colaborador

        nome_chave = _sem_acento(nome)
        if not nome_chave:
            return None

        colaborador = self.por_nome.get(nome_chave)
        if colaborador:
            return colaborador

        # O relatório PF corta o nome em 30 caracteres ("Miguel Rogerio Souza
        # Strecht J"), então tenta casar por prefixo quando não há ambiguidade.
        if len(nome_chave) >= 15:
            candidatos = {c.pk: c for chave, c in self.nomes if chave.startswith(nome_chave)}
            if len(candidatos) == 1:
                return next(iter(candidatos.values()))

        return None
# Montagem das linhas para RegistroProducao
def preparar_linhas_odonto(df, origem, mapeamento, colaboradores):
    col_status = COLUNA_STATUS[origem]
    col_cpf_vend = COLUNA_CPF_VENDEDOR[origem]
    col_num_proposta = COLUNA_NUM_PROPOSTA

    colunas_faltantes = [c for c in (col_status, col_cpf_vend, col_num_proposta) if c not in df.columns]
    if colunas_faltantes:
        return {'ok': False, 'colunas_faltantes': colunas_faltantes}

    col_nome_vend = COLUNA_NOME_VENDEDOR[origem]
    col_nome_vend = col_nome_vend if col_nome_vend in df.columns else ''
    col_tipo_plano = COLUNA_TIPO_PLANO_PF if origem == 'PF' and COLUNA_TIPO_PLANO_PF in df.columns else ''

    base = BaseColaboradores(colaboradores)

    def coluna(campo):
        col = (mapeamento.get(campo) or {}).get('col_excel')
        col = _sem_acento(col) if col else ''
        return col if col in df.columns else ''

    def valor(row, campo):
        col = coluna(campo)
        if col:
            bruto = row[col]
            return str(bruto).strip() if bruto is not None and str(bruto).strip().lower() != 'nan' else ''
        fixo = (mapeamento.get(campo) or {}).get('val_fixo')
        return (fixo or '').strip()

    # 1ª passada: filtra por status e agrupa por NUM_PROPOSTA, contando quantas
    # vezes cada proposta se repete (= quantidade de vidas daquela proposta).
    propostas = {}
    ordem_propostas = []
    total_ignorados_status = 0

    for _, row in df.iterrows():
        if _sem_acento(row[col_status]) != STATUS_CONCLUIDO:
            total_ignorados_status += 1
            continue

        num_proposta = str(row[col_num_proposta]).strip()
        if num_proposta not in propostas:
            propostas[num_proposta] = {'row': row, 'quantidade_vidas': 0}
            ordem_propostas.append(num_proposta)
        propostas[num_proposta]['quantidade_vidas'] += 1

    linhas = []
    nao_encontrados = []
    vistos_nao_encontrados = set()

    # 2ª passada: monta uma linha por proposta (não por linha da planilha).
    for num_proposta in ordem_propostas:
        row = propostas[num_proposta]['row']
        quantidade_vidas = propostas[num_proposta]['quantidade_vidas']

        cpf_vendedor = row[col_cpf_vend]
        nome_vendedor = row[col_nome_vend] if col_nome_vend else None
        colaborador = base.buscar(cpf_vendedor, nome_vendedor)

        dados = {
            'seguradora_valor': valor(row, 'seguradora'),
            'tipo_documento_valor': valor(row, 'tipo_documento') or TIPO_DOCUMENTO_PADRAO,
            'documento': valor(row, 'documento'),
            'tipo_pessoa': TIPO_PESSOA[origem],
            'cpf_cnpj': _so_digitos(valor(row, 'cpf_cnpj')),
            'cliente': valor(row, 'cliente'),
            'nome_social': valor(row, 'nome_social'),
            'celular': _so_digitos(valor(row, 'celular')),
            'telefone': _so_digitos(valor(row, 'telefone')),
            'email': valor(row, 'email'),
            'grupo_ramo_valor': valor(row, 'grupo_ramo'),
            'inicio_vigencia_valor': valor(row, 'inicio_vigencia'),
            'fim_vigencia_valor': valor(row, 'fim_vigencia'),
            'premio_liquido': _para_numero(valor(row, 'premio_liquido')),
            'perc_comissao': _para_numero(valor(row, 'perc_comissao')),
            'realizado': valor(row, 'realizado'),
            'observacoes': valor(row, 'observacoes'),
            'quantidade_vidas': quantidade_vidas,
        }

        if col_tipo_plano:
            tipo = _sem_acento(row[col_tipo_plano])
            if tipo == 'MENSAL':
                dados['premio_bruto'] = VALOR_MENSAL_PF
            elif tipo == 'ANUAL':
                dados['premio_bruto'] = VALOR_ANUAL_PF
            else:
                dados['premio_bruto'] = _para_numero(valor(row, 'premio_bruto'))
        else:
            dados['premio_bruto'] = _para_numero(valor(row, 'premio_bruto'))

        if colaborador is None:
            cpf_chave = _cpf_normalizado(cpf_vendedor)
            nome_chave = str(nome_vendedor or '').strip()
            dados['colaborador'] = ''
            dados['nome_colaborador'] = ''
            dados['unidade'] = None
            if (cpf_chave, nome_chave) not in vistos_nao_encontrados:
                vistos_nao_encontrados.add((cpf_chave, nome_chave))
                nao_encontrados.append({'cpf': cpf_chave, 'nome': nome_chave, 'origem': origem})
        else:
            dados['colaborador'] = colaborador.matricula or ''
            dados['nome_colaborador'] = colaborador.nome_social or colaborador.colaborador
            dados['unidade'] = colaborador.unidade

        linhas.append(dados)

    return {
        'ok': True,
        'linhas': linhas,
        'nao_encontrados': nao_encontrados,
        'total_ignorados_status': total_ignorados_status,
    }
