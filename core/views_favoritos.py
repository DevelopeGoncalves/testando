from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .favoritos import POR_CHAVE, cards_permitidos
from .models import FavoritoUsuario


@login_required
@require_POST
def alternar_favorito(request):
    """Liga/desliga a estrela de um card pro usuário logado. Cada usuário tem os seus favoritos."""
    chave = (request.POST.get('chave') or '').strip()
    if chave not in POR_CHAVE or chave not in {c['chave'] for c in cards_permitidos(request.user)}:
        return JsonResponse({'ok': False, 'erro': 'Card inválido.'}, status=400)
    atual = FavoritoUsuario.objects.filter(usuario=request.user, chave=chave)
    if atual.exists():
        atual.delete()
        return JsonResponse({'ok': True, 'favorito': False})
    FavoritoUsuario.objects.get_or_create(usuario=request.user, chave=chave)
    return JsonResponse({'ok': True, 'favorito': True})
