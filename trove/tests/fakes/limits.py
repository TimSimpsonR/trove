import webob.dec


from trove.common import wsgi as base_wsgi
from trove.openstack.common import wsgi
from trove.common import limits


ENABLED = False


class FakeRateLimitingMiddleware(limits.RateLimitingMiddleware):

    def enabled(self):
        return ENABLED

