from aiogram import Router

from .private import private_routers

router = Router()
router.include_routers(*private_routers)