# alex: ParametrizacaoBaseNovo não existe mais em models.py (removido antes desta
# migration existir). Isso só registra formalmente a remoção da tabela.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0054_alter_ligacaoindicacao_motivo_nao_venda'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ParametrizacaoBaseNovo',
        ),
    ]
