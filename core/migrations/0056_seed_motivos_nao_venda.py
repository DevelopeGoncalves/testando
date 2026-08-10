# alex: popula os "Motivo Não Venda" padrão no banco. A lista aparecia só no
# local porque o db.sqlite3 não vai para o Git; assim, ao rodar "migrate" no
# servidor, a tabela é preenchida e a lista passa a aparecer também lá.
from django.db import migrations


MOTIVOS = [
    'Condições comerciais (preço)',
    'Condições financeiras',
    'Condições técnicas',
    'Desistiu',
    'Efetivou com o corretor atual',
    'Falta de retorno do cliente/indicador',
    'Mal atendimento Seguradora',
    'Operação Empréstimo',
    'Venda do bem',
]


def criar_motivos(apps, schema_editor):
    MotivoNaoVenda = apps.get_model('core', 'MotivoNaoVenda')
    for motivo in MOTIVOS:
        MotivoNaoVenda.objects.get_or_create(motivo=motivo)


def remover_motivos(apps, schema_editor):
    MotivoNaoVenda = apps.get_model('core', 'MotivoNaoVenda')
    MotivoNaoVenda.objects.filter(motivo__in=MOTIVOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0055_indicacao_responsavel_demanda'),
    ]

    operations = [
        migrations.RunPython(criar_motivos, remover_motivos),
    ]
