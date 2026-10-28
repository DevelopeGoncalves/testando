import unicodedata
from collections import defaultdict

from django.core.management.base import BaseCommand

from core.models import (
    AcompanhamentoEmissao, LigacaoEndosso, LigacaoIndicacao, LigacaoRenovacao, PerfilUsuario,
)

PARTICULAS = {'de', 'da', 'do', 'dos', 'das', 'e'}

# (modelo, campo) onde o sistema guardou, em texto, o login de quem fez o registro.
CAMPOS_COM_LOGIN = [
    (LigacaoIndicacao, 'cadastrado_por'),
    (LigacaoRenovacao, 'cadastrado_por'),
    (LigacaoEndosso, 'cadastrado_por'),
    (AcompanhamentoEmissao, 'atendente'),
]


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', texto or '')
    return ''.join(c for c in texto if not unicodedata.combining(c)).lower().strip()


class Command(BaseCommand):
    help = (
        'Registros antigos guardaram o LOGIN de quem atendeu (ex.: "thiagodias"), que agora é a matrícula. '
        'Este comando troca esse texto pelo nome completo do colaborador (como os registros novos) quando '
        'consegue identificar a pessoa com segurança (login igual ao nome, ou primeiro+segundo nome, '
        'primeiro+último nome, ou só o primeiro nome, desde que só um colaborador combine). '
        'O que for duvidoso ou não encontrado é só listado. Use --simular para ver antes de alterar.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true', help='Só mostra o que seria alterado.')

    def handle(self, *args, **opcoes):
        simular = opcoes['simular']

        # chave de comparação -> conjunto de nomes completos de colaboradores com usuário
        candidatos = defaultdict(set)
        conhecidos = set()
        for p in PerfilUsuario.objects.select_related('usuario', 'colaborador').filter(colaborador__isnull=False):
            nome = (p.colaborador.colaborador or '').strip()
            if not nome:
                continue
            conhecidos.add(_normalizar(nome))
            conhecidos.add(_normalizar(p.usuario.username))
            tokens = [t for t in _normalizar(nome).split() if t not in PARTICULAS]
            if not tokens:
                continue
            chaves = {''.join(tokens), tokens[0]}
            if len(tokens) > 1:
                chaves |= {tokens[0] + tokens[1], tokens[0] + tokens[-1]}
            for chave in chaves:
                candidatos[chave].add(nome)

        total = 0
        nao_resolvidos = defaultdict(int)
        for modelo, campo in CAMPOS_COM_LOGIN:
            valores = (modelo.objects.exclude(**{campo: ''}).exclude(**{campo + '__isnull': True})
                       .values_list(campo, flat=True).distinct())
            for valor in valores:
                texto = valor.strip()
                chave = _normalizar(texto)
                if chave in conhecidos or ' ' in chave:
                    continue  # já é nome completo/matrícula de um usuário (ou texto livre com espaços)
                nomes = candidatos.get(chave, set())
                if len(nomes) != 1:
                    nao_resolvidos[texto] += 1
                    continue
                novo = next(iter(nomes))
                qtd = modelo.objects.filter(**{campo: valor}).count()
                self.stdout.write(f'{modelo.__name__}.{campo}: "{valor}" -> "{novo}" ({qtd} registro(s))')
                total += qtd
                if not simular:
                    modelo.objects.filter(**{campo: valor}).update(**{campo: novo})

        for texto in sorted(nao_resolvidos):
            self.stdout.write(f'[não identificado] "{texto}" - fica como está')
        self.stdout.write(f'Registros corrigidos: {total}' + (' (simulação)' if simular else ''))
