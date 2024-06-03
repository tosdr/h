"""View for serving static assets under `/assets`."""

import os
import importlib_resources
from h_assets import Environment, assets_view
from pyramid.settings import asbool


def includeme(config):  # pragma: no cover
    auto_reload = asbool(config.registry.settings.get("h.reload_assets", False))
    h_files = importlib_resources.files("h")

    asset_path = "/hypothesis/assets"
    if "ASSET_PATH" in os.environ:
        asset_path = os.environ["ASSET_PATH"]

    assets_env = Environment(
        assets_base_url=asset_path,
        bundle_config_path=h_files / "assets.ini",
        manifest_path=h_files / "../build/manifest.json",
        auto_reload=auto_reload,
    )

    # Store asset environment in registry for use in registering `asset_urls`
    # Jinja2 helper in `app.py`.
    config.registry["assets_env"] = assets_env

    config.add_view(route_name="assets", view=assets_view(assets_env))
