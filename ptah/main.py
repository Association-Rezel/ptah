from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
import yaml
from api.routes import router as api_router
from models.PtahConfig import PtahConfig

app = FastAPI(title="PTAH API")
app.include_router(api_router)