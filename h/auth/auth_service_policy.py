import base64
import os

from pyramid.interfaces import IAuthenticationPolicy, ISessionFactory
from pyramid.security import Authenticated, Everyone
from pyramid_authsanity.interfaces import IAuthSourceService
from zope.interface import Interface, implementer


class IAuthService(Interface):
    """Represents an authentication service. This service verifies that the
    users authentication ticket is valid and returns groups the user is a
    member of."""

    def userid():
        """Return the current user id, None, or raise an error. Raising an
        error is used when no attempt to verify a ticket has been made yet and
        signifies that the authentication policy should attempt to call
        ``verify_ticket``"""

    def groups():
        """Returns the groups for the current user, as a list. Including the
        current userid in this list is not required, as it will be implicitly
        added by the authentication policy."""

    def verify_ticket(principal, ticket):
        """Verify that the principal matches the ticket given."""

    def add_ticket(principal, ticket):
        """Add a new ticket for the principal. If there is a failure, due to a
        missing/non-existent principal, or failure to add ticket for principal,
        should raise an error"""

    def remove_ticket(ticket):
        """Remove a ticket for the current user. Upon success return True"""


UNSET = object()


@implementer(IAuthenticationPolicy)
class AuthServicePolicy(object):
    _have_session = UNSET

    def unauthenticated_userid(self, request):
        """We do not allow the unauthenticated userid to be used."""

    def authenticated_userid(self, request):
        """Returns the authenticated userid for this request."""

        source_svc, auth_svc = self._find_services(request)
        self._add_vary_callback(request, source_svc.vary)

        try:
            userid = auth_svc.userid()

        except Exception:
            principal, ticket = source_svc.get_value()

            # Verify the principal and the ticket, even if None
            auth_svc.verify_ticket(principal, ticket)

            try:
                # This should now return None or the userid
                userid = auth_svc.userid()
            except Exception:
                userid = None

        return userid

    def effective_principals(self, request):
        """A list of effective principals derived from request."""

        effective_principals = [Everyone]

        userid = self.authenticated_userid(request)
        _, auth_svc = self._find_services(request)

        if userid is None:
            return effective_principals

        if userid in (Authenticated, Everyone):
            return effective_principals

        effective_principals.append(Authenticated)
        effective_principals.append(userid)
        effective_principals.extend(auth_svc.groups())

        return effective_principals

    def remember(self, request, principal, **kw):
        """Returns a list of headers that are to be set from the source service."""
        if self._have_session is UNSET:
            self._have_session = self._session_registered(request)

        prev_userid = self.authenticated_userid(request)

        source_svc, auth_svc = self._find_services(request)
        self._add_vary_callback(request, source_svc.vary)

        ticket = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")

        auth_svc.add_ticket(principal, ticket)

        # Clear the previous session
        if self._have_session:
            if prev_userid != principal:
                request.session.invalidate()
            else:
                # We are logging in the same user that is already logged in, we
                # still want to generate a new session, but we can keep the
                # existing data
                data = dict(request.session.items())
                request.session.invalidate()
                request.session.update(data)
                request.session.new_csrf_token()

        return source_svc.headers_remember([principal, ticket])

    def forget(self, request):
        """A list of headers which will delete appropriate cookies."""

        if self._have_session is UNSET:
            self._have_session = self._session_registered(request)

        source_svc, auth_svc = self._find_services(request)
        self._add_vary_callback(request, source_svc.vary)

        _, ticket = source_svc.get_value()
        auth_svc.remove_ticket(ticket)

        # Clear the session by invalidating it
        if self._have_session:
            request.session.invalidate()

        return source_svc.headers_forget()

    @staticmethod
    def _add_vary_callback(request, vary_by):
        def vary_add(request, response):
            vary = set(response.vary if response.vary is not None else [])
            vary |= set(vary_by)
            response.vary = list(vary)

        request.add_response_callback(vary_add)

    @staticmethod
    def _find_services(request):
        source_svc = request.find_service(IAuthSourceService)
        auth_svc = request.find_service(IAuthService)

        return source_svc, auth_svc

    @staticmethod
    def _session_registered(request):
        factory = request.registry.queryUtility(ISessionFactory)

        return False if factory is None else True
