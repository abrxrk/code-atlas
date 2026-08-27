from fastapi import FastAPI

from code_atlas.server.routes import health_routes, index_routes


def create_app() -> FastAPI:
    app = FastAPI(title="code-atlas")

    app.include_router(health_routes.router)
    app.include_router(index_routes.router)

    return app
