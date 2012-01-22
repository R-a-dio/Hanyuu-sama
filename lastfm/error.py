#!/usr/bin/env python
"""Mdoule containing the exceptions for this package"""

__author__ = "Abhinav Sarkar <abhinav@abhinavsarkar.net>"
__version__ = "0.2"
__license__ = "GNU Lesser General Public License"
__package__ = "lastfm"

class LastfmError(Exception):
    """Base class for Lastfm web service API errors"""
    def __init__(self, message = None, code = None):
        """
        Initialize the error object.
        
        @param message: the error message
        @type message:  L{str}
        @param code:    the error code
        @type code:     L{int}
        """
        super(LastfmError, self).__init__()
        self._code = code
        self._message = message

    @property
    def code(self):
        """
        The error code as returned by last.fm web service API.
        @rtype: L{int}
        """
        return self._code

    @property
    def message(self):
        """
        The error message as returned by last.fm web service API.
        @rtype: L{str}
        """
        return self._message

    def __str__(self):
        return "%s" % self.message

class InvalidServiceError(LastfmError):#2
    """Invalid service - This service does not exist."""
    pass

class InvalidMethodError(LastfmError):#3
    """Invalid method - No method with that name in this package."""
    pass

class AuthenticationFailedError(LastfmError):#4
    """Authentication failed - You do not have permissions to access the service"""
    pass

class InvalidFormatError(LastfmError):#5
    """Invalid format - This service doesn't exist in that format"""
    pass

class InvalidParametersError(LastfmError):#6
    """Invalid parameters - Your request is missing a required parameter"""
    pass

class InvalidResourceError(LastfmError):#7
    """Invalid resource - Invalid resource specified"""
    pass

class OperationFailedError(LastfmError):#8
    """
    Operation failed - There was an error during the requested operation.
    lease try again later.
    """
    pass

class InvalidSessionKeyError(LastfmError):#9
    """Invalid session key - Please re-authenticate"""
    pass

class InvalidApiKeyError(LastfmError):#10
    """Invalid API key - You must be granted a valid key by last.fm"""
    pass

class ServiceOfflineError(LastfmError):#11
    """Service offline - This service is temporarily offline. Try again later."""
    pass

class SubscribersOnlyError(LastfmError):#12
    """Subscribers only - This service is only available to paid last.fm subscribers"""
    pass

class InvalidMethodSignatureError(LastfmError):#13
    """Invalid method signature - the method signature provided is invalid"""
    pass

class TokenNotAuthorizedError(LastfmError):#14
    """Token not authorized - This token has not been authorized"""
    pass

class TokenExpiredError(LastfmError):#15
    """Token expired - This token has expired"""
    pass

error_map = {
            1: LastfmError,
            2: InvalidServiceError,
            3: InvalidMethodError,
            4: AuthenticationFailedError,
            5: InvalidFormatError,
            6: InvalidParametersError,
            7: InvalidResourceError,
            8: OperationFailedError,
            9: InvalidSessionKeyError,
            10: InvalidApiKeyError,
            11: ServiceOfflineError,
            12: SubscribersOnlyError,
            13: InvalidMethodSignatureError,
            14: TokenNotAuthorizedError,
            15: TokenExpiredError,
}
"""Map of error codes to the error types"""
