from fastapi import FastAPI
from runtime_service.custom_routes.models import router as model_capabilities_router
from runtime_service.custom_routes.tools import router as capabilities_router

app = FastAPI(title="runtime_service custom routes")
app.include_router(capabilities_router)
app.include_router(model_capabilities_router)
