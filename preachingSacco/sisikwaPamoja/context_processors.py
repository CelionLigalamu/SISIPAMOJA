from .views import _build_admin_dashboard_data


def admin_dashboard_context(request):
    resolver_match = getattr(request, 'resolver_match', None)
    is_admin_index = bool(
        resolver_match
        and resolver_match.app_name == 'admin'
        and resolver_match.url_name == 'index'
    )

    if not is_admin_index:
        return {}

    return {
        'dashboard_data': _build_admin_dashboard_data(),
    }