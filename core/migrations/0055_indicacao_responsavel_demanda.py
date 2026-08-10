# alex: adiciona o "Responsável pela demanda" (Colaborador) na Indicacao.
# Migração escrita à mão de propósito, só com este campo, para NÃO mexer em outras
# pendências do modelo (ex.: ParametrizacaoBaseNovo), que ficam a seu critério.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0054_merge_20260810_1006'),
    ]

    operations = [
        migrations.AddField(
            model_name='indicacao',
            name='responsavel_demanda',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='demandas_responsavel',
                to='core.colaborador',
                verbose_name='Responsável pela demanda',
            ),
        ),
    ]
