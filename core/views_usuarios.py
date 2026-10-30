import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .auditoria import registrar_auditoria_backend
from .forms import NovoUsuarioForm
from .models import Colaborador, PerfilUsuario

def preencher_nome_pelo_colaborador(usuario, colaborador):
    """Como o login agora é a matrícula, guarda o nome do colaborador no usuário (só se ainda
    estiver vazio) - assim "Cadastrado por"/"Atendente" mostram o nome e não o número."""
    if colaborador and colaborador.colaborador and not (usuario.first_name or usuario.last_name):
        usuario.first_name = colaborador.colaborador[:150]


# Aba Administração > Usuários: lista, cadastro/edição, exclusão, "online" e desconectar.
# (As views de Vendas ficam em views_vendas.py; esta aba segue a mesma organização.)


# permisao henrique 
PERMISSOES_CAMPOS = [
    # BASE
    'base_form_unidade', 'base_form_colaboradores', 'base_form_contratados',
    'base_form_seguradoras', 'base_form_tiposdocumento', 'base_form_ramos',
    'base_form_produtos', 'base_form_agrupamentos', 'base_form_metas',
    'base_form_tipopessoa', 'base_form_clientes', 'base_form_estados_anbima',
    'base_form_fundos_anbima', 'base_form_status_emissao', 'base_form_retorno_emissao', 'base_proc_unidade',
    'base_proc_colaboradores', 'base_proc_ramos', 'base_rel',
    
    # PRODUÇÃO
    'prod_vendas_novo', 'prod_vendas_renovacao', 'prod_vendas_endosso', 'prod_vendas_emissao',
    'prod_vendas_basenovo', 'prod_vendas_baserenovacao', 'prod_vendas_baseendosso', 'prod_vendas_baseemissao',
    'prod_form_vida', 'prod_form_bap', 'prod_form_prestamista',
    'prod_form_patrimonialedemais', 'prod_form_consorcio', 'prod_form_odonto',
    'prod_form_previdencia', 'prod_form_banescap', 'prod_form_saude',
    'prod_form_habitacional', 'prod_proc_vida', 'prod_proc_bap',
    'prod_proc_prestamista', 'prod_proc_patrimonialedemais', 'prod_proc_consorcio',
    'prod_proc_odonto', 'prod_proc_previdencia', 'prod_proc_banescap',
    'prod_proc_saude', 'prod_proc_habitacional', 'prod_proc_basenovo', 'prod_proc_anbima', 'prod_rel',
    
    # FINANCEIRO
    'fin_form', 'fin_proc_habitacional', 'fin_rel',
    
    # ADMINISTRAÇÃO E AUDITORIA
    'admin_usuario', 'admin_listaestagiarios', 'admin_feriasestagiarios', 'aud'
]

@login_required
def listar_usuarios(request):

    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.admin_usuario > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')

    query = request.GET.get('q', '') 
    if query:
        usuarios = list(User.objects.filter(
            Q(username__icontains=query) |
            Q(perfil__colaborador__matricula__icontains=query) |
            Q(first_name__icontains=query)
        ).order_by('first_name'))
    else:
        usuarios = list(User.objects.all().order_by('first_name'))

    for u in usuarios:
        cache_key = f'online_user_{u.id}'
        u.is_online = bool(cache.get(cache_key))

    return render(request, 'core/administracao/usuarios/listar_usuarios.html', {
        'usuarios': usuarios,
        'query': query,
    })


@login_required
def form_usuario(request, id=None):


    # ---- Parte de negar acesso quem não pode ----
    user = request.user

    if not (user.is_superuser or (hasattr(user, 'perfil') and user.perfil.admin_usuario > 0)):
        messages.error(request, 'Acesso Negado.')
        return redirect('home')
    #-----

    if id:
        usuario_edit = get_object_or_404(User, id=id)
        perfil = getattr(usuario_edit, 'perfil', None)
    else:
        usuario_edit = None
        perfil = None

    colaboradores = Colaborador.objects.filter(inativo=False).order_by('colaborador')

    if request.method == 'POST':
        form = NovoUsuarioForm(request.POST)
        if form.is_valid():
            matricula = form.cleaned_data['matricula']
            senha = form.cleaned_data['password']
            # O login do usuário É a matrícula (só números).
            login = matricula

            # Só cadastra usuário quem está cadastrado em Base > Formulários > Colaboradores.
            colaborador_obj = Colaborador.objects.filter(matricula=matricula).first()
            if not colaborador_obj:
                messages.error(request, f'Erro: A matrícula {matricula} não está cadastrada em Colaboradores.')
                return render(request, 'core/administracao/usuarios/form_usuario.html', {'form': form, 'usuario_edit': usuario_edit, 'colaboradores': colaboradores})

            # Um colaborador só pode ter um usuário.
            outro_perfil = PerfilUsuario.objects.filter(colaborador=colaborador_obj).select_related('usuario')
            if usuario_edit:
                outro_perfil = outro_perfil.exclude(usuario=usuario_edit)
            outro_perfil = outro_perfil.first()
            if outro_perfil:
                messages.error(request, f'A matrícula {matricula} já tem usuário cadastrado ({outro_perfil.usuario.username}).')
                return render(request, 'core/administracao/usuarios/form_usuario.html', {'form': form, 'usuario_edit': usuario_edit, 'colaboradores': colaboradores})

            if usuario_edit:
                # Superusuário não tem matrícula: o login dele não é trocado por aqui.
                if not usuario_edit.is_superuser:
                    if User.objects.filter(username=login).exclude(id=usuario_edit.id).exists():
                        messages.error(request, 'Este login já está em uso no sistema.')
                        return render(request, 'core/administracao/usuarios/form_usuario.html', {'form': form, 'usuario_edit': usuario_edit, 'colaboradores': colaboradores})
                    usuario_edit.username = login
                    preencher_nome_pelo_colaborador(usuario_edit, colaborador_obj)
                if senha:
                    usuario_edit.set_password(senha)
                
                usuario_edit.is_active = form.cleaned_data.get('is_active', False)
                usuario_edit.save()

                if perfil:
                    perfil.colaborador = colaborador_obj

                    for campo in PERMISSOES_CAMPOS:
                        setattr(perfil, campo, form.cleaned_data[campo])

                    perfil.save()
                
                messages.success(request, 'Usuário atualizado com sucesso!')
            else:
                if User.objects.filter(username=login).exists():
                    messages.error(request, 'Este login já está em uso no sistema.')
                    return render(request, 'core/administracao/usuarios/form_usuario.html', {'form': form, 'usuario_edit': usuario_edit, 'colaboradores': colaboradores})
                
                if not senha:
                    messages.error(request, 'A senha é obrigatória para a criação de um novo usuário.')
                    return render(request, 'core/administracao/usuarios/form_usuario.html', {'form': form, 'usuario_edit': usuario_edit, 'colaboradores': colaboradores})

                user = User.objects.create_user(username=login, password=senha)
                preencher_nome_pelo_colaborador(user, colaborador_obj)
                user.save()
                
                permissoes_dit = {campo: form.cleaned_data[campo] for campo in PERMISSOES_CAMPOS}
                
                PerfilUsuario.objects.create(
                    usuario=user,
                    colaborador=colaborador_obj,
                    **permissoes_dit
                )
                
                messages.success(request, f'Sucesso! Usuário "{login}" foi criado.')
                registrar_auditoria_backend(usuario=request.user, acao="Criou usuário", detalhe=login)

            return redirect('listar_usuarios')
    else:
        if usuario_edit:
            dados_iniciais = {
                'matricula': perfil.colaborador.matricula if perfil and perfil.colaborador else '',
                'is_active': usuario_edit.is_active,
            }

            if perfil:
                for campo in PERMISSOES_CAMPOS:
                    dados_iniciais[campo] = getattr(perfil, campo, 0)
                    
            form = NovoUsuarioForm(initial=dados_iniciais)
        else:
            form = NovoUsuarioForm(initial={'is_active': True})

    todos_perfis = PerfilUsuario.objects.select_related('usuario', 'colaborador').exclude(usuario__is_superuser=True)
    
    perfis_espelho_data = []
    for p in todos_perfis:
        perms = {f"id_{campo}": getattr(p, campo, 0) for campo in PERMISSOES_CAMPOS}
        label = f"{p.usuario.username} - {p.colaborador.matricula}" if p.colaborador else p.usuario.username
        
        perfis_espelho_data.append({
            "id": p.usuario.id,
            "label": label,
            "perms": perms
        })

    return render(request, 'core/administracao/usuarios/form_usuario.html', {
        'form': form,
        'usuario_edit': usuario_edit,
        'colaboradores': colaboradores,
        'perfis_espelho_json': json.dumps(perfis_espelho_data) # Enviamos pronto pro JS
    })

@login_required
def excluir_usuarios(request):  


    if request.method == 'POST':
        ids_para_excluir = request.POST.getlist('usuarios_ids') 
        
        if ids_para_excluir:
            usuarios_a_excluir = User.objects.filter(id__in=ids_para_excluir).exclude(is_superuser=True)
            
            logins_excluidos = ", ".join([u.username for u in usuarios_a_excluir])
            
            quantidade_deletada, _ = usuarios_a_excluir.delete()
            
            if quantidade_deletada > 0:
                registrar_auditoria_backend(usuario=request.user, acao="Deletou usuário(s)", detalhe=logins_excluidos)
                
                messages.success(request, f'{quantidade_deletada} usuário(s) excluído(s) com sucesso!')
            else:
                messages.warning(request, 'Nenhum usuário foi excluído.')

    return redirect('listar_usuarios')


@login_required
def ping_online(request):
    # Salva no cache que este usuário está online. Expira em 40 segundos.
    cache_key = f'online_user_{request.user.id}'
    cache.set(cache_key, True, timeout=40)
    return JsonResponse({'status': 'ok'})

@login_required
def desconectar_usuarios(request):
    if request.method == 'POST':
        ids_para_desconectar = request.POST.getlist('usuarios_ids')
        
        if ids_para_desconectar:
            # 1. Varre as sessões ativas e apaga as dos usuários selecionados
            sessions = Session.objects.filter(expire_date__gte=timezone.now())
            for session in sessions:
                data = session.get_decoded()
                if str(data.get('_auth_user_id')) in ids_para_desconectar:
                    session.delete()
            
            # 2. Apaga o cache imediatamente para a "bolinha verde" virar vermelha na hora
            for uid in ids_para_desconectar:
                cache.delete(f'online_user_{uid}')
                
            messages.success(request, 'Sessão dos usuários selecionados foi encerrada.')
            
    return redirect('listar_usuarios')


from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

@login_required
def resetar_senha_usuario(request):
    if request.method == 'POST':
        nova_senha = request.POST.get('nova_senha', '').strip()
        confirmar_senha = request.POST.get('confirmar_senha', '').strip()

        if not nova_senha:
            messages.error(request, 'A nova senha não pode ser vazia.')
            return redirect(request.META.get('HTTP_REFERER', 'home'))

        if nova_senha != confirmar_senha:
            messages.error(request, 'As senhas informadas não coincidem.')
            return redirect(request.META.get('HTTP_REFERER', 'home'))

        user = request.user

        try:

            validate_password(nova_senha, user)
            
            user.set_password(nova_senha)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Sua senha foi alterada com sucesso!')

        except ValidationError as e:
            for erro in e.messages:
                messages.error(request, erro)

    return redirect(request.META.get('HTTP_REFERER', 'home'))
