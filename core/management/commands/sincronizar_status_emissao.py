# Comando de manutenção (roda uma vez, depois que as tabelas novas forem criadas com o migrate):
#
#   python manage.py sincronizar_status_emissao
#
# 1) Cria o cadastro padrão de Base > Formulários > "Status das emissões" e
#    "Retorno ao cliente das emissões" (o que antes era fixo no código). Se já existir, não
#    duplica nem mexe no que você mudou.
# 2) Liga os acompanhamentos de emissão que já existem a esses cadastros (eles só tinham o
#    nome do status e o sim/não). Nada é apagado nem alterado além do vínculo.
#
# Use --simular para só ver o relatório, sem gravar nada.
# (Se você não rodar, o cadastro padrão é criado sozinho na primeira vez que abrir a Emissão, e
# os acompanhamentos antigos continuam aparecendo certinho; este comando só deixa tudo ligado.)
from django.core.management.base import BaseCommand
from django.db import transaction

from core.emissao_padroes import garantir_padroes_emissao, vincular_acompanhamentos_antigos
from core.models import AcompanhamentoEmissao, RetornoClienteEmissao, StatusEmissao


class Command(BaseCommand):
    help = 'Cria o cadastro padrão de status/retorno da Emissão e liga os acompanhamentos antigos.'

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true', help='Só mostra o que seria feito, sem gravar.')

    def handle(self, *args, **opcoes):
        simular = opcoes['simular']
        if simular:
            criados = 0
            vinculados, sem_correspondencia = self._simular()
        else:
            with transaction.atomic():
                criados = garantir_padroes_emissao()
                vinculados, sem_correspondencia = vincular_acompanhamentos_antigos()
        self.stdout.write(self.style.SUCCESS(
            f'Cadastros criados: {criados}\n'
            f'Acompanhamentos ligados aos cadastros: {vinculados}\n'
            f'Acompanhamentos sem status conhecido (ficam como estão): {sem_correspondencia}\n'
            f'Status cadastrados: {StatusEmissao.objects.count()} | Retornos cadastrados: {RetornoClienteEmissao.objects.count()}'
        ))
        if simular:
            self.stdout.write(self.style.WARNING('Modo simulação: nada foi gravado.'))

    def _simular(self):
        nomes = set(AcompanhamentoEmissao.REGRA_POR_NOME_ANTIGO)
        pendentes = AcompanhamentoEmissao.objects.filter(status_ref__isnull=True)
        ligaveis = pendentes.filter(status__in=nomes).count()
        return ligaveis, pendentes.count() - ligaveis
