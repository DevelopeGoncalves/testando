from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import PerfilUsuario


class Command(BaseCommand):
    help = (
        'Passa o login dos usuários já cadastrados para a MATRÍCULA do colaborador vinculado '
        '(Administração > Usuários). A senha, as permissões e as sessões não mudam; só o login '
        '(username). Também preenche o nome do usuário com o nome do colaborador quando estiver vazio. '
        'Superusuários (sem matrícula) não são alterados. Pode rodar mais de uma vez. '
        'Use --simular para só ver o que seria feito.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true', help='Só mostra o que seria alterado.')

    def handle(self, *args, **opcoes):
        simular = opcoes['simular']
        alterados = iguais = ignorados = 0
        usados = set()  # matrículas já distribuídas nesta execução

        perfis = (PerfilUsuario.objects.select_related('usuario', 'colaborador')
                  .filter(usuario__is_superuser=False).order_by('usuario_id'))
        for perfil in perfis:
            usuario, colab = perfil.usuario, perfil.colaborador
            if not colab or not (colab.matricula or '').strip():
                ignorados += 1
                self.stdout.write(f'[ignorado] {usuario.username}: sem colaborador/matrícula vinculado')
                continue
            matricula = colab.matricula.strip()
            if not matricula.isdigit():
                ignorados += 1
                self.stdout.write(f'[ignorado] {usuario.username}: matrícula "{matricula}" não é só número')
                continue
            if matricula in usados:
                ignorados += 1
                self.stdout.write(f'[ignorado] {usuario.username}: a matrícula {matricula} já foi dada a outro usuário')
                continue
            usados.add(matricula)

            campos = {}
            if usuario.username != matricula:
                if User.objects.filter(username=matricula).exclude(id=usuario.id).exists():
                    ignorados += 1
                    self.stdout.write(f'[ignorado] {usuario.username}: já existe outro usuário com o login {matricula}')
                    continue
                campos['username'] = matricula
            if colab.colaborador and not (usuario.first_name or usuario.last_name):
                campos['first_name'] = colab.colaborador[:150]
            if not campos:
                iguais += 1
                continue
            self.stdout.write(f'{usuario.username} -> {campos.get("username", usuario.username)}'
                              + (' (+ nome)' if 'first_name' in campos else ''))
            if not simular:
                # update(): troca só esses campos (a senha e o resto ficam exatamente como estão).
                User.objects.filter(id=usuario.id).update(**campos)
            alterados += 1
        self.stdout.write(f'Alterados: {alterados} | Já estavam certos: {iguais} | Ignorados: {ignorados}'
                          + (' (simulação)' if simular else ''))
