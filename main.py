from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from app.api.routes import auth, cashiers, shops, providers, super_agents, transactions, float_movement, settings
from app.utils.error_codes import HTTP_STATUS_TO_ERROR_CODE

app = FastAPI(
    title="Backend API",
    description="FastAPI backend for Mile",
    version="1.0.0"
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",                          # development
        "https://www.mile.sewmrtechnologies.com",         # production
        "https://mile.sewmrtechnologies.com",             # production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

# Root route
@app.get("/")
def root():
    return {"success": True, "message": "Welcome to the Mile backend API!", "data": None}

# Include routers
app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["Auth"])
app.include_router(cashiers.router, prefix=f"{API_PREFIX}/cashiers", tags=["Cashiers"])
app.include_router(shops.router, prefix=f"{API_PREFIX}/shops", tags=["Shops"])
app.include_router(providers.router, prefix=f"{API_PREFIX}/providers", tags=["Providers"])
app.include_router(super_agents.router, prefix=f"{API_PREFIX}/super-agents", tags=["Super Agents"])
app.include_router(transactions.router, prefix=f"{API_PREFIX}/transactions", tags=["Transactions"])
app.include_router(float_movement.router, prefix=f"{API_PREFIX}/float-movement", tags=["Float Movement"])
app.include_router(settings.router, prefix=f"{API_PREFIX}/settings", tags=["Settings"])

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    error_code = HTTP_STATUS_TO_ERROR_CODE.get(exc.status_code, "SERVER_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": error_code,
                "message": exc.detail,
                "details": None
            }
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": HTTP_STATUS_TO_ERROR_CODE.get(422, "VALIDATION_ERROR"),
                "message": "Invalid request: Please send the correct content type and required fields.",
                "details": exc.errors()
            }
        },
    )


