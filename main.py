from contextlib import asynccontextmanager
from fastapi import FastAPI

from ptah.api.routes import router as api_router
from ptah.contexts import AppContext


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _app.state.ctx = AppContext()
    yield


app = FastAPI(title="PTAH API", lifespan=lifespan)
app.include_router(api_router)
