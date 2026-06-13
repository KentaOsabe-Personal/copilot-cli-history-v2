import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REQUIRED_ENV_KEYS = (
    "BIGQUERY_PROJECT_ID",
    "BIGQUERY_DATASET_ID",
    "BIGQUERY_LOCATION",
)
GOOGLE_APPLICATION_CREDENTIALS = "GOOGLE_APPLICATION_CREDENTIALS"
CREDENTIALS_SOURCE_LABEL = "credentials source (GOOGLE_APPLICATION_CREDENTIALS or ADC)"
MAXIMUM_BYTES_BILLED_DEFAULT = "BIGQUERY_MAX_BYTES_BILLED_DEFAULT"
TABLE_PREFIX_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DATASET_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LOCATION_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class BigQueryReadModelSettings:
    project_id: str
    dataset_id: str
    location: str
    table_prefix: str
    credentials_path: str | None
    maximum_bytes_billed_default: int | None = None


class BigQuerySettingsError(Exception):
    def __init__(
        self,
        missing_settings: tuple[str, ...] = (),
        invalid_keys: tuple[str, ...] = (),
    ) -> None:
        self.missing_settings = missing_settings
        self.invalid_keys = invalid_keys
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        details: list[str] = []
        if self.missing_settings:
            details.append(f"missing settings: {', '.join(self.missing_settings)}")
        if self.invalid_keys:
            details.append(f"invalid keys: {', '.join(self.invalid_keys)}")
        return "Invalid BigQuery read model settings (" + "; ".join(details) + ")"


def load_bigquery_settings(require_credentials: bool) -> BigQueryReadModelSettings:
    environ = os.environ
    missing_settings = tuple(key for key in REQUIRED_ENV_KEYS if _env_value(environ, key) is None)
    invalid_keys = _invalid_env_keys(environ)
    credentials_path = _env_value(environ, GOOGLE_APPLICATION_CREDENTIALS)

    if require_credentials and credentials_path is None and not _adc_credentials_path().exists():
        missing_settings = (*missing_settings, CREDENTIALS_SOURCE_LABEL)

    if (
        require_credentials
        and credentials_path is not None
        and not Path(credentials_path).is_file()
    ):
        invalid_keys = (*invalid_keys, GOOGLE_APPLICATION_CREDENTIALS)

    if missing_settings or invalid_keys:
        raise BigQuerySettingsError(
            missing_settings=missing_settings,
            invalid_keys=invalid_keys,
        )

    return BigQueryReadModelSettings(
        project_id=_env_value(environ, "BIGQUERY_PROJECT_ID") or "",
        dataset_id=_env_value(environ, "BIGQUERY_DATASET_ID") or "",
        location=_env_value(environ, "BIGQUERY_LOCATION") or "",
        table_prefix=_env_value(environ, "BIGQUERY_TABLE_PREFIX") or "",
        credentials_path=credentials_path,
        maximum_bytes_billed_default=_maximum_bytes_billed_default(environ),
    )


def read_bigquery_integration_enabled() -> bool:
    raw_value = os.environ.get("BIGQUERY_READ_MODEL_INTEGRATION", "")
    return raw_value.strip().lower() in TRUTHY_ENV_VALUES


def _env_value(environ: Mapping[str, str], key: str) -> str | None:
    value = environ.get(key)
    if value is None:
        return None

    stripped_value = value.strip()
    if stripped_value == "":
        return None
    return stripped_value


def _invalid_env_keys(environ: Mapping[str, str]) -> tuple[str, ...]:
    invalid_keys: list[str] = []
    dataset_id = _env_value(environ, "BIGQUERY_DATASET_ID")
    location = _env_value(environ, "BIGQUERY_LOCATION")
    table_prefix = _env_value(environ, "BIGQUERY_TABLE_PREFIX")
    maximum_bytes_billed_default = _env_value(environ, MAXIMUM_BYTES_BILLED_DEFAULT)

    if dataset_id is not None and not DATASET_ID_PATTERN.fullmatch(dataset_id):
        invalid_keys.append("BIGQUERY_DATASET_ID")
    if location is not None and not LOCATION_PATTERN.fullmatch(location):
        invalid_keys.append("BIGQUERY_LOCATION")
    if table_prefix is not None and not TABLE_PREFIX_PATTERN.fullmatch(table_prefix):
        invalid_keys.append("BIGQUERY_TABLE_PREFIX")
    if maximum_bytes_billed_default is not None:
        try:
            parsed_maximum_bytes_billed = int(maximum_bytes_billed_default)
        except ValueError:
            invalid_keys.append(MAXIMUM_BYTES_BILLED_DEFAULT)
        else:
            if parsed_maximum_bytes_billed <= 0:
                invalid_keys.append(MAXIMUM_BYTES_BILLED_DEFAULT)

    return tuple(invalid_keys)


def _maximum_bytes_billed_default(environ: Mapping[str, str]) -> int | None:
    value = _env_value(environ, MAXIMUM_BYTES_BILLED_DEFAULT)
    if value is None:
        return None
    return int(value)


def _adc_credentials_path() -> Path:
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
