"""Errors raised by the DEMO client."""


class CTraderDemoError(Exception):
    """Base error for this package."""


class DemoGuardError(CTraderDemoError):
    """Host, port, or account is outside the DEMO-only binding.

    Callers must treat this as fatal and must not send a trading request.
    """


class ConfigError(CTraderDemoError):
    """Required configuration is missing or unusable."""


class UsageError(CTraderDemoError):
    """The command line is missing a required flag or subcommand."""


class ApiError(CTraderDemoError):
    """The proxy returned an error, or the response could not be used."""

    def __init__(self, error_code: str, description: str, payload_type: int):
        self.error_code = error_code
        self.description = description
        self.payload_type = payload_type
        text = description.strip()
        if text:
            message = f"cTrader API error {error_code}: {text} (payloadType={payload_type})"
        else:
            message = f"cTrader API error {error_code} (payloadType={payload_type})"
        super().__init__(message)
