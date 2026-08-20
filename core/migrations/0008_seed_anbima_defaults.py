# Popula os cadastros "Por Estado" e "Valores por Fundos" com os mesmos
# dados hardcoded que hoje vivem em analise/anbima.py, para o processamento
# ANBIMA já funcionar assim que o sistema subir. Continuam 100% editáveis
# depois pela tela (Base > Formulários).

from django.db import migrations

ORDEM_ESTADOS = [
    'RO', 'AC', 'AM', 'RR', 'PA', 'AP', 'TO', 'MA', 'PI', 'CE', 'RN', 'PB', 'PE',
    'AL', 'SE', 'BA', 'MG', 'ES', 'RJ', 'SP', 'PR', 'SC', 'RS', 'MS', 'MT', 'GO', 'DF'
]

ESTADOS_FORMATADOS = {
    'RO': 'Rondônia', 'AC': 'Acre', 'AM': 'Amazonas',
    'RR': 'Roraima', 'PA': 'Pará', 'AP': 'Amapá',
    'TO': 'Tocantins', 'MA': 'Maranhão', 'PI': 'Piauí',
    'CE': 'Ceará', 'RN': 'Rio Grande do Norte', 'PB': 'Paraíba',
    'PE': 'Pernambuco', 'AL': 'Alagoas', 'SE': 'Sergipe',
    'BA': 'Bahia', 'MG': 'Minas Gerais', 'ES': 'Espírito Santo',
    'RJ': 'Rio de Janeiro', 'SP': 'São Paulo', 'PR': 'Paraná',
    'SC': 'Santa Catarina', 'RS': 'Rio Grande do Sul',
    'MS': 'Mato Grosso do Sul', 'MT': 'Mato Grosso',
    'GO': 'Goiás', 'DF': 'Distrito Federal'
}

ORDEM_FUNDOS = [
    'ICATU SEG COMPOSTO 20C FIC FI MULTIMERCADO',
    'ICATU SEG MODERADO C FIC FI RENDA FIXA',
    'ICATU SEG COMPOSTO 20E FIC FI MULTIMERCADO',
    'ICATU VANGUARDA FIC DE FIRF INFLAÇÃO LONGA PREV',
    'ICATU SEG DURATION FI RENDA FIXA',
    'ICATU SEG COMPOSTO 49E FIC FI MULTIMERCADO',
    'ICATU SEG CLASSIC FIC DE FI RENDA FIXA',
    'ICATU VANGUARDA MINHA APOSENTADORIA 2040 FIM PREV',
    'ICATU VANGUARDA MINHA APOSENTADORIA 2030 FIM PREV',
    'ICATU SEG PRIVILEGE RENDA FIXA FIC DE FI',
    'ICATU SEG BRASIL TOTAL FIC FI MULTIMERCADO',
    'ICATU VANGUARDA ABSOLUTO FI PREVIDENCIÁRIO RF CRÉDITO PRIV',
    'ATHENA ICATU PREV FUNDO DE INVESTIMENTO MULTIMERCADO 49',
    'CAPITÂNIA CREDPREVIDÊNCIA ICATU FIC DE FIF RF CP RESP LTDA',
    'ICATU VANGUARDA MINHA APOSENTADORIA 2050 FC FIM PREV',
    'JGP CRÉDITO PREV TIPO 1 ICATU FIC DE FIRF CP LONGO PRAZO',
    'ICATU VANGUARDA ABSOLUTO II FI RF CP PREV',
    'ICATU VANGUARDA CRÉDITO GLOBAL PREV FIC FIM CP',
    'INTEGRAL ICATU PREVIDENCIARIO FICRF CP',
    'ARX INCOME ICATU PREV FIF MULTIMERCADO RESP LTDA',
    'ARX INCOME ICATU PREV 100 FIC DE FIA',
    'ICATU SEG MINHA APOSENTADORIA 2030 FIC FI MULTIMERCADO',
    'ARX INCOME ICATU PREVIDÊNCIA FI MULTIMERCADO',
    'OCCAM ICATU PREVIDÊNCIA FIC DE FIM',
    'RIZA ICATU PREVIDÊNCIA LOW VOL FIF MULTIMERCADO RESP LTDA',
    'OCCAM ICATU PREV FIC DE FIF MULTIMERCADO - RESP LTDA',
    'ICATU VANGUARDA IGARATÉ FIM PREVIDENCIÁRIO',
    'ICATU VANGUARDA PRIVILEGE PLUS FIC DE FIM RF PREV',
]

CODIGOS_ANBIMA = [
    'C0000061522', 'C0000061484', 'C0000083739', 'C0000099481',
    'C0000100390', 'C0000101834', 'C0000114715', 'C0000153321',
    'C0000153338', 'C0000236403', 'C0000265225', 'C0000396389',
    'C0000440590', 'C0000441104', 'C0000567493', 'C0000623733',
    'C0000678228', 'C0000555789', 'C0000513792', 'C0000100676',
    '',            '',            '',            '',
    'C0000533629', 'C0000347264', 'C0000676195', 'BR0GBMCTF005',
]

CNPJ_FUNDOS = [
    '02.764.357/0001-71', '02.764.937/0001-69', '03.537.485/0001-45',
    '04.228.716/0001-00', '04.511.286/0001-20', '04.782.224/0001-53',
    '05.200.914/0001-10', '07.190.735/0001-74', '07.190.746/0001-54',
    '09.321.515/0001-68', '12.053.727/0001-16', '21.494.444/0001-09',
    '26.680.218/0001-28', '27.239.065/0001-40', '35.636.610/0001-60',
    '41.128.345/0001-02', '46.685.502/0001-02', '36.352.241/0001-47',
    '33.588.888/0001-84', '03.879.361/0001-48', '', '', '', '',
    '31.248.460/0001-67', '17.685.620/0001-04', '46.192.463/0001-01',
    '51.620.403/0001-74',
]


def semear_dados(apps, schema_editor):
    EstadoAnbima = apps.get_model('core', 'EstadoAnbima')
    FundoAnbima = apps.get_model('core', 'FundoAnbima')

    for ordem, uf in enumerate(ORDEM_ESTADOS):
        estado_nome = ESTADOS_FORMATADOS[uf]
        EstadoAnbima.objects.get_or_create(
            uf=uf,
            defaults={
                'estado': estado_nome,
                'uf_estado': f"{uf} - {estado_nome}",
                'ordem_apresentacao': ordem,
            },
        )

    for ordem, nome_fundo in enumerate(ORDEM_FUNDOS):
        FundoAnbima.objects.get_or_create(
            nome_fundo=nome_fundo,
            defaults={
                'codigo_anbima': CODIGOS_ANBIMA[ordem] or None,
                'cnpj_fundo': CNPJ_FUNDOS[ordem] or None,
                'ordem_apresentacao': ordem,
            },
        )


def remover_dados(apps, schema_editor):
    EstadoAnbima = apps.get_model('core', 'EstadoAnbima')
    FundoAnbima = apps.get_model('core', 'FundoAnbima')
    EstadoAnbima.objects.filter(uf__in=ORDEM_ESTADOS).delete()
    FundoAnbima.objects.filter(nome_fundo__in=ORDEM_FUNDOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_estadoanbima_fundoanbima_and_more'),
    ]

    operations = [
        migrations.RunPython(semear_dados, remover_dados),
    ]
