"""Como mostrar quem atendeu/cadastrou algo: "matrícula - nome" (igual à coluna Responsável)."""
from django.utils import timezone

from .models import PerfilUsuario

_MAPA = {'quando': 0, 'dados': {}}

def _mapa_atendentes():
    """texto -> "matrícula - nome" dos usuários (pelo login/matrícula ou pelo nome completo).
    Guardado por 30 s pra não consultar o banco a cada linha da lista."""
    agora = timezone.now().timestamp()
    if agora - _MAPA['quando'] > 30:
        dados = {}
        perfis = PerfilUsuario.objects.select_related('usuario', 'colaborador').filter(colaborador__isnull=False)
        for p in perfis:
            colab = p.colaborador
            texto = f'{colab.matricula} - {colab.colaborador}' if colab.matricula else colab.colaborador
            for nome in ((p.usuario.get_full_name() or '').strip(), (colab.colaborador or '').strip()):
                if nome:
                    dados.setdefault(nome.lower(), texto)
        for p in perfis:  # login/matrícula tem prioridade sobre o nome
            colab = p.colaborador
            texto = f'{colab.matricula} - {colab.colaborador}' if colab.matricula else colab.colaborador
            dados[p.usuario.username.lower()] = texto
        _MAPA.update(quando=agora, dados=dados)
    return _MAPA['dados']

def formatar_atendente(texto):
    """Mostra quem atendeu como "matrícula - nome" (igual à coluna Responsável). Se não achar o
    usuário (ex.: registro antigo com login que não existe mais), devolve o texto como está."""
    texto = (texto or '').strip()
    if not texto:
        return ''
    return _mapa_atendentes().get(texto.lower(), texto)


def atendente_do_usuario(user):
    """"matrícula - nome" de um usuário logado (é o que passa a ser gravado como "cadastrado por" /
    "atendente"). Sem colaborador vinculado (ex.: superusuário), usa o nome completo ou o login."""
    perfil = getattr(user, 'perfil', None)
    colab = getattr(perfil, 'colaborador', None) if perfil else None
    if colab and colab.colaborador:
        return f'{colab.matricula} - {colab.colaborador}' if colab.matricula else colab.colaborador
    return user.get_full_name() or user.username
