# alex: volta o "Motivo Não Venda" a ser um campo de texto com lista fixa no
# Python (igual "Origem da informação"), em vez de depender de uma tabela
# separada (MotivoNaoVenda) que precisava de seed via migration.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0056_seed_motivos_nao_venda'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ligacaoindicacao',
            name='motivo_nao_venda',
            field=models.CharField(
                blank=True,
                choices=[
                    ('Condições comerciais (preço)', 'Condições comerciais (preço)'),
                    ('Condições financeiras', 'Condições financeiras'),
                    ('Condições técnicas', 'Condições técnicas'),
                    ('Desistiu', 'Desistiu'),
                    ('Efetivou com o corretor atual', 'Efetivou com o corretor atual'),
                    ('Falta de retorno do cliente/indicador', 'Falta de retorno do cliente/indicador'),
                    ('Mal atendimento Seguradora', 'Mal atendimento Seguradora'),
                    ('Operação Empréstimo', 'Operação Empréstimo'),
                    ('Venda do bem', 'Venda do bem'),
                ],
                max_length=50,
                null=True,
                verbose_name='Motivo Não Venda',
            ),
        ),
    ]
