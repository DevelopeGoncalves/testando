import os

from django.core.management.base import BaseCommand

from core.models import AcompanhamentoEmissao, caminho_anexo_emissao


class Command(BaseCommand):
    help = (
        'Renomeia os anexos antigos da Emissão (nome aleatório) para o padrão do sistema '
        '<origem>/<ano>/<mês>/ANX-<id do acompanhamento>.<extensão> (e também move para as pastas '
        'os anexos que ficaram soltos), atualizando o nome mostrado no card. '
        'Use --simular para só ver o que seria feito.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true', help='Só mostra o que seria renomeado.')

    def handle(self, *args, **opcoes):
        simular = opcoes['simular']
        feitos = ausentes = 0
        for a in AcompanhamentoEmissao.objects.exclude(anexo='').exclude(anexo__isnull=True).order_by('id'):
            novo = caminho_anexo_emissao(a, a.anexo.name)
            nome_card = os.path.basename(novo)
            if a.anexo.name == novo and a.anexo_nome == nome_card:
                continue
            origem = a.anexo.storage.path(a.anexo.name)
            if not os.path.exists(origem):
                ausentes += 1
                self.stdout.write(f'#{a.id}: arquivo não encontrado ({a.anexo.name}) - ignorado')
                continue
            destino = a.anexo.storage.path(novo)
            self.stdout.write(f'#{a.id}: {a.anexo.name} -> {novo}')
            if simular:
                continue
            if os.path.exists(destino) and os.path.abspath(destino) != os.path.abspath(origem):
                self.stdout.write(f'#{a.id}: já existe {novo} - ignorado')
                continue
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            os.replace(origem, destino)
            a.anexo.name = novo
            a.anexo_nome = nome_card
            a.save(update_fields=['anexo', 'anexo_nome'])
            feitos += 1
        self.stdout.write(f'Renomeados: {feitos} | Arquivos ausentes: {ausentes}' + (' (simulação)' if simular else ''))
