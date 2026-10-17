from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class DoctrinesMenuItem(MenuItemHook):
    """Side-menu entry in auth; only for members with the permission."""

    def __init__(self):
        super().__init__("Doctrines", "fas fa-jet-fighter fa-fw", "doctrines:index", navactive=["doctrines:"])

    def render(self, request):
        if request.user.has_perm("doctrines.basic_access"):
            return super().render(request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return DoctrinesMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "doctrines", r"^doctrines/")
