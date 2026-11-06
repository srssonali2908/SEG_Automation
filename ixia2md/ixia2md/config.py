"""Configuration, read from environment variables so no secret is ever stored in code or files."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(v: str | None, default: bool) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # --- CCMS connection ---------------------------------------------------------------
    ccms_url: str = ""                      # e.g. https://ccms.example.com (the /rest/1.0 part is added)
    ccms_user: str = ""                     # service account
    ccms_password: str = ""
    ccms_auth_cookie: str = ""              # alternative: an existing IxiaAuth cookie value
    verify_tls: bool = True
    timeout: int = 60

    # ASSUMPTIONS about the sign-in call. The 7.5 documentation names /sessions/authorize but does
    # not show the verb or body fields on the pages we could read. Confirm with IXIASOFT.
    login_method: str = "POST"
    login_user_field: str = "userName"
    login_password_field: str = "password"

    # ASSUMPTIONS about snapshot properties (not documented in the pages we could read).
    published_statuses: tuple[str, ...] = ("published",)   # values of currentStatus that mean "published"
    version_field: str = "version"
    origin_field: str = "originIdentifier"

    # --- Conversion ----------------------------------------------------------------------
    dita_ot_home: str = ""                  # folder that contains bin/dita
    default_flavor: str = "markdown_github"
    keep_dita_source: bool = False          # copy the downloaded DITA into the output folder

    # --- Output --------------------------------------------------------------------------
    output_root: str = "./runs"
    fail_on_quality_fail: bool = False      # if True, a failed quality check makes the run fail
    qa_baseline: str = ""                   # optional baseline.json (e.g. built from a reference PDF); default: built from the DITA source

    @classmethod
    def from_env(cls) -> "Config":
        e = os.environ.get
        cfg = cls(
            ccms_url=e("CCMS_URL", ""),
            ccms_user=e("CCMS_USER", ""),
            ccms_password=e("CCMS_PASSWORD", ""),
            ccms_auth_cookie=e("CCMS_AUTH_COOKIE", ""),
            verify_tls=_bool(e("CCMS_VERIFY_TLS"), True),
            timeout=int(e("CCMS_TIMEOUT", "60")),
            login_method=e("CCMS_LOGIN_METHOD", "POST").upper(),
            login_user_field=e("CCMS_LOGIN_USER_FIELD", "userName"),
            login_password_field=e("CCMS_LOGIN_PASSWORD_FIELD", "password"),
            published_statuses=tuple(s.strip().lower() for s in e("CCMS_PUBLISHED_STATUSES", "published").split(",") if s.strip()),
            version_field=e("CCMS_VERSION_FIELD", "version"),
            origin_field=e("CCMS_ORIGIN_FIELD", "originIdentifier"),
            dita_ot_home=e("DITA_OT_HOME", ""),
            default_flavor=e("MD_FLAVOR", "markdown_github"),
            keep_dita_source=_bool(e("KEEP_DITA_SOURCE"), False),
            output_root=e("OUTPUT_ROOT", "./runs"),
            fail_on_quality_fail=_bool(e("FAIL_ON_QUALITY_FAIL"), False),
            qa_baseline=e("QA_BASELINE", ""),
        )
        return cfg

    def dita_executable(self) -> Path:
        home = self.dita_ot_home or os.environ.get("DITA_HOME", "")
        if not home:
            raise RuntimeError("DITA_OT_HOME is not set. Point it at the DITA-OT folder (the one containing bin/dita).")
        exe = Path(home) / "bin" / ("dita.bat" if os.name == "nt" else "dita")
        if not exe.exists():
            raise RuntimeError(f"DITA-OT launcher not found at {exe}")
        return exe


FLAVORS = {
    "markdown": "Original Markdown",
    "markdown_github": "GitHub-flavored Markdown",
    "markdown_gitbook": "GitBook (with SUMMARY.md)",
}
