from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class ShipyardMenuItem(MenuItemHook):
    """Side-menu entry; only rendered for users with basic access."""

    def __init__(self):
        super().__init__(
            "Shipyard",
            "fas fa-industry fa-fw",
            "shipyard:index",
            navactive=["shipyard:"],
        )

    def render(self, request):
        if request.user.has_perm("shipyard.basic_access"):
            return super().render(request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return ShipyardMenuItem()


@hooks.register("url_hook")
def register_urls():
    return UrlHook(urls, "shipyard", r"^shipyard/")
