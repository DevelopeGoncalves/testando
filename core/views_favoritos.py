from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .favoritos import LIMITE_FAVORITOS, cards_permitidos
from .models import FavoritoUsuario


@login_required
@require_POST
def alternar_favorito(request):
    """Liga/desliga a estrela de um card pro usuário logado. Cada usuário tem os seus favoritos."""
    chave = (request.POST.get('chave') or '').strip()
    if chave not in {c['chave'] for c in cards_permitidos(request.user)}:
        return JsonResponse({'ok': False, 'erro': 'Card inválido.'}, status=400)
    atual = FavoritoUsuario.objects.filter(usuario=request.user, chave=chave)
    if atual.exists():
        atual.delete()
        return JsonResponse({'ok': True, 'favorito': False})
    if FavoritoUsuario.objects.filter(usuario=request.user).count() >= LIMITE_FAVORITOS:
        return JsonResponse({'ok': False, 'limite': True,
                             'erro': f'Você já tem {LIMITE_FAVORITOS} favoritos (o máximo). Remova algum para favoritar este.'}, status=400)
    ultima = FavoritoUsuario.objects.filter(usuario=request.user).aggregate(m=Max('ordem'))['m']
    FavoritoUsuario.objects.get_or_create(usuario=request.user, chave=chave, defaults={'ordem': (ultima or 0) + 1})
    return JsonResponse({'ok': True, 'favorito': True})


@login_required
@require_POST
def ordenar_favoritos(request):
    """Guarda a nova ordem dos favoritos do usuário (ele arrasta os cards na página inicial)."""
    chaves = request.POST.getlist('chaves')
    meus = {f.chave: f for f in FavoritoUsuario.objects.filter(usuario=request.user)}
    for posicao, chave in enumerate(chaves, start=1):
        fav = meus.get(chave)
        if fav and fav.ordem != posicao:
            fav.ordem = posicao
            fav.save(update_fields=['ordem'])
    return JsonResponse({'ok': True})
