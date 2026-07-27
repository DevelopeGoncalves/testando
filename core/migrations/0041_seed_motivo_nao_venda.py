# Popula a tabela MotivoNaoVenda com a lista usada no sistema antigo (tblMotivo).

from django.db import migrations

MOTIVOS = [
    "Condições comerciais (preço)",
    "Condições financeiras",
    "Condições técnicas",
    "Desistiu",
    "Efetivou com o corretor atual",
    "Falta de retorno do cliente/indicador",
    "Mal atendimento Seguradora",
    "Operação Empréstimo",
    "Venda do bem",
]


def seed(apps, schema_editor):
    MotivoNaoVenda = apps.get_model('core', 'MotivoNaoVenda')
    for texto in MOTIVOS:
        MotivoNaoVenda.objects.get_or_create(motivo=texto)


def remover_seed(apps, schema_editor):
    MotivoNaoVenda = apps.get_model('core', 'MotivoNaoVenda')
    MotivoNaoVenda.objects.filter(motivo__in=MOTIVOS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_motivonaovenda_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, remover_seed),
    ]
