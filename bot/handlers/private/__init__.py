from .start import start_router
from .expenses import expense_router
from .admin import admin_router

private_routers = [start_router, expense_router, admin_router]