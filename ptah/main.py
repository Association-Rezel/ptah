from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
import yaml

from api.routes import router as api_router
from contexts import AppContext


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ctx = AppContext()
    yield


app = FastAPI(title="PTAH API", lifespan=lifespan)
app.include_router(api_router)
