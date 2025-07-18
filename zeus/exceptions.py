from pydantic import ValidationError


def extract_first_validation_error(exc: ValidationError):
    err = exc.errors()[0]
    field = ' -> '.join(str(f) for f in err['loc'])

    # if root validator raised error, do not include field value
    if "__root__" in field:
        return err["msg"]

    return f"Field '{field}': {err['msg']}"


class ZeusCmdError(Exception):
    def __init__(self, message, severity="danger"):
        self.message = message
        self.severity = severity
        super().__init__(message)


class ZeusMailSendError(Exception):
    def __init__(self, sender, recipient, subject, user=None):
        self.sender = sender
        self.recipient = recipient
        self.subject = subject
        self.user = user
        message = f"Email from: '{sender}' to: '{recipient}' subj: '{subject}' could not be sent"
        super().__init__(message)


class ZeusCmdFormValidationError(ZeusCmdError):
    pass


class ZeusFileNotFoundError(ZeusCmdError):
    pass


class ZeusBulkOpFailed(ZeusCmdError):
    pass


class ZeusConversionError(ZeusCmdError):
    def __init__(self, error):
        self.error = error
        message = error
        super().__init__(message=message)


class ZeusWorkbookError(ZeusCmdError):
    pass


class TokenMgrError(ZeusCmdError):
    pass


class TokenMgrStoreError(TokenMgrError):
    pass
