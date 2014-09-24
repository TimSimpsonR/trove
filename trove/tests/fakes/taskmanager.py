import eventlet
from trove.taskmanager import api
from trove.taskmanager.manager import Manager


class FakeApi(api.API):

    def __init__(self, context):
        self.context = context

    def make_msg(self, method_name, *args, **kwargs):
        return {"name": method_name, "args":args, "kwargs":kwargs}

    def call(self, context, msg):
        manager, method = self.get_tm_method(msg['name'])
        return method(manager, context, *msg['args'], **msg['kwargs'])

    def cast(self, context, msg):
        manager, method = self.get_tm_method(msg['name'])
        def func():
            method(manager, context, *msg['args'], **msg['kwargs'])

        eventlet.spawn_after(0.1, func)

    def get_tm_method(self, method_name):
        manager = Manager()
        method = getattr(Manager, method_name)
        return manager, method


def monkey_patch():
    # def fake_get_client(self, *args, **kwargs):
    #     return FakeRpcClient()
    api.API = FakeApi
    def fake_load(context, manager=None):
        return FakeApi(context)
    api.load = fake_load
