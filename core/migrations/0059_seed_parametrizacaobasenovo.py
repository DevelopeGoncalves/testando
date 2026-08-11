# alex: popula a parametrização padrão da Base Novo com os mesmos nomes de coluna que o
# importador antigo usava fixo no código, pra continuar funcionando sem precisar configurar
# nada. Pode ser editado na tela "Parametrizar a importação" a qualquer momento.
from django.db import migrations

MAPEAMENTO_PADRAO = {
    'carimbo_data_hora': 'Carimbo de data/hora',
    'email': 'Endereço de e-mail',
    'email_indicador_outro': 'E-mail do indicador caso não seja você mesmo',
    'matricula_indicador': 'Matrícula do indicador',
    'nome_indicador': 'Nome completo do indicador',
    'cid_agencia': 'CID da agência',
    'telefone_indicador': 'Telefone ou celular do indicador',
    'enviar_orcamento_para': 'Enviar orçamento para',
    'nome_cliente': 'Nome completo do cliente',
    'telefone_cliente': 'Telefone ou celular do cliente',
    'cpf_cliente': 'CPF do cliente',
    'email_cliente': 'E-mail do cliente',
    'produto': 'Produto',
    'dados_veiculo': 'Se Automóvel, informe os dados do veículo (modelo, ano e placa)',
    'possui_seguro': 'Cliente já possui seguro?',
    'observacoes': 'Observações',
}


def seed(apps, schema_editor):
    ParametrizacaoBaseNovo = apps.get_model('core', 'ParametrizacaoBaseNovo')
    for campo, coluna in MAPEAMENTO_PADRAO.items():
        ParametrizacaoBaseNovo.objects.get_or_create(
            campo_sistema=campo,
            defaults={'coluna_excel': coluna, 'valor_fixo': ''},
        )


def remover_seed(apps, schema_editor):
    ParametrizacaoBaseNovo = apps.get_model('core', 'ParametrizacaoBaseNovo')
    ParametrizacaoBaseNovo.objects.filter(campo_sistema__in=MAPEAMENTO_PADRAO.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0058_parametrizacaobasenovo_recriada'),
    ]

    operations = [
        migrations.RunPython(seed, remover_seed),
    ]
