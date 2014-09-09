import eventlet
from trove.taskmanager.api import API
from trove.taskmanager.manager import Manager


class FakeRpcClient(object):

    def call(self, context, method_name, *args, **kwargs):
        self.context = context
        manager, method = self.get_tm_method(method_name)
        return method(manager, context, *args, **kwargs)

    def cast(self, context, method_name, *args, **kwargs):
        manager, method = self.get_tm_method(method_name)
        def func():

            method(manager, context, *args, **kwargs)

        eventlet.spawn_after(0.1, func)

    def get_tm_method(self, method_name, *args, **kwargs):
        manager = Manager()
        method = getattr(Manager, method_name)
        return manager, method

    def prepare(self, *args, **kwargs):
        return self


def monkey_patch():
    def fake_get_client(self, *args, **kwargs):
        return FakeRpcClient()
    API.get_client = fake_get_client
