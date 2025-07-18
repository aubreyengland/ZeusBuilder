import logging
from . import tokenmgr, cmds
from .wxcc import WxccTokenMgr
from .wbxc import WbxcTokenMgr
from .zoom import ZoomTokenMgr
from .msteams import MsTeamsTokenMgr
from flask import redirect, url_for
from zeus.exceptions import ZeusCmdError
from zeus.shared.helpers import redirect_on_cmd_err

log = logging.getLogger(__name__)


@tokenmgr.get("/wbxc/redir")
def wbxc_redir():
    """Accept Redirect URI requests"""
    mgr = WbxcTokenMgr()
    cmd = cmds.TokenMgrAuthorizeCmd("wbxc", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("wbxc.orgs", exc)

    return redirect(url_for("wbxc.orgs"))


@tokenmgr.get("/wbxc/refresh")
def wbxc_refresh():
    """Send refresh requests"""
    mgr = WbxcTokenMgr()
    cmd = cmds.TokenMgrRefreshCmd("wbxc", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("wbxc.orgs", exc)

    return redirect(url_for("wbxc.orgs"))


@tokenmgr.get("/wxcc/redir")
def wxcc_redir():
    """Accept Redirect URI requests"""
    mgr = WxccTokenMgr()
    cmd = cmds.TokenMgrAuthorizeCmd("wxcc", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("wxcc.orgs", exc)

    return redirect(url_for("wxcc.orgs"))


@tokenmgr.get("/wxcc/refresh")
def wxcc_refresh():
    """Send refresh requests"""
    mgr = WxccTokenMgr()
    cmd = cmds.TokenMgrRefreshCmd("wxcc", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("wxcc.orgs", exc)

    return redirect(url_for("wxcc.orgs"))


@tokenmgr.get("/zoom/redir")
def zoom_redir():
    """Accept Redirect URI requests"""
    mgr = ZoomTokenMgr()
    cmd = cmds.TokenMgrAuthorizeCmd("zoom", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("zoom.orgs", exc)

    return redirect(url_for("zoom.orgs"))


@tokenmgr.get("/zoom/refresh")
def zoom_refresh():
    """Send refresh requests"""
    mgr = ZoomTokenMgr()
    cmd = cmds.TokenMgrRefreshCmd("zoom", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("zoom.orgs", exc)

    return redirect(url_for("zoom.orgs"))


@tokenmgr.get("/zoomcc/redir")
def zoomcc_redir():
    """Accept Redirect URI requests"""
    mgr = ZoomTokenMgr()
    cmd = cmds.TokenMgrAuthorizeCmd("zoomcc", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("zoomcc.orgs", exc)

    return redirect(url_for("zoomcc.orgs"))


@tokenmgr.get("/zoomcc/refresh")
def zoomcc_refresh():
    """Send refresh requests"""
    mgr = ZoomTokenMgr()
    cmd = cmds.TokenMgrRefreshCmd("zoomcc", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("zoomcc.orgs", exc)

    return redirect(url_for("zoomcc.orgs"))


@tokenmgr.get("/msteams/redir")
def msteams_redir():
    """Accept Redirect URI requests"""
    mgr = MsTeamsTokenMgr()
    cmd = cmds.TokenMgrAuthorizeCmd("msteams", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("msteams.orgs", exc)

    return redirect(url_for("msteams.orgs"))


@tokenmgr.get("/msteams/refresh")
def msteams_refresh():
    """Send refresh requests"""
    mgr = MsTeamsTokenMgr()
    cmd = cmds.TokenMgrRefreshCmd("msteams", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("msteams.orgs", exc)

    return redirect(url_for("msteams.orgs"))


@tokenmgr.get("/msteams/consent")
def msteams_consent():
    """
    Accept Redirect URI requests for MS Admin Consent

    Microsoft admin consent for the Skype and Teams Tenant Admin API can be a separate action from OAuth.
    This allows a Microsoft account with Application Admin privileges to grant consent for the tenant first.
    Then a Microsoft account with Teams Admin privileges can be used to authorize the organization.
    """
    mgr = MsTeamsTokenMgr()
    cmd = cmds.TokenMgrConsentCmd("msteams", mgr)
    try:
        cmd.process()
    except ZeusCmdError as exc:
        return redirect_on_cmd_err("msteams.orgs", exc)

    return redirect(url_for("msteams.orgs"))
