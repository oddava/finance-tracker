import sentry_sdk
from sentry_sdk.integrations.loguru import LoguruIntegration, LoggingLevels
from loguru import logger

from bot.core.config import settings


def setup_sentry():
    if settings.SENTRY_DSN:
        sentry_loguru = LoguruIntegration(
            level=LoggingLevels.INFO,
            event_level=LoggingLevels.ERROR,
        )
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            enable_tracing=True,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
            integrations=[sentry_loguru],
            environment=settings.ENVIRONMENT,
            enable_logs=settings.ENABLE_LOGS,
        )
        logger.info("✅ Sentry initialized with DSN")
    else:
        logger.warning("⚠️ Sentry DSN not set, skipping Sentry initialization")
