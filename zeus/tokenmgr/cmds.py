import logging
from flask import request, flash
from .mgr_base import TokenMgrBase
from zeus.exceptions import ZeusCmdError

log = logging.getLogger(__name__)


class TokenMgrCmd:
    def __init__(self, org_type, mgr):
        self.messages = []
        self.org_type = org_type
        self.mgr: TokenMgrBase = mgr
        self.is_htmx_request = "HX-Request" in request.headers

    def process(self):
        pass

    def flash_messages(self):
        if not self.is_htmx_request:
            for msg, cat in self.messages:
                flash(msg, cat)

    def to_dict(self):
        return self.__dict__


class TokenMgrAuthorizeCmd(TokenMgrCmd):

    def process(self):
        auth_code, state = self.mgr.parse_auth_response(request.args)

        org = self.mgr.get(state=state)
        if not org:
            raise ZeusCmdError("No Org found with provided state value")

        token_resp = self.mgr.send_token_request(auth_code, org)
        self.mgr.save_token_response(org, token_resp)

        self.messages.append(("Authorization Successful", "info"))
        self.flash_messages()


class TokenMgrRefreshCmd(TokenMgrCmd):

    def process(self):
        org_id = request.args.get("id", type=int)
        org = self.mgr.get(id=org_id)
        if not org:
            raise ZeusCmdError("No Org found with provided state value")

        token_resp = self.mgr.send_refresh_request(org=org)
        self.mgr.save_token_response(org, token_resp)

        self.messages.append(("Token Refresh Successful", "info"))
        self.flash_messages()


class TokenMgrConsentCmd(TokenMgrCmd):

    def process(self):
        admin_consent = request.args.get("admin_consent", type=bool, default=False)
        error = request.args.get("error")
        error_description = request.args.get("error_description")
        if admin_consent and error is None:
            self.messages.append(
                (
                    (
                        "Microsoft Admin consent granted. You can now authorize your "
                        "organization by signing in with a Teams Admin account.",
                        "info"
                    )
                )
            )
            self.flash_messages()
        else:
            self.messages.append((f"{error_description}", "warning"))
            self.flash_messages()
