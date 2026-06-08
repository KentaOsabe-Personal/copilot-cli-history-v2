from django.http import JsonResponse


def up(request: object) -> JsonResponse:
    return JsonResponse({"status": "ok"})
