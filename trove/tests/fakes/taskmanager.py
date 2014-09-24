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

    # def call(self, context, method_name, *args, **kwargs):
    #     self.context = context
    #     manager, method = self.get_tm_method(method_name)
    #     return method(manager, context, *args, **kwargs)

    def cast(self, context, msg):
        manager, method = self.get_tm_method(msg['name'])
        def func():
            print("MARIO I am casting like a fool!")
            method(manager, context, *msg['args'], **msg['kwargs'])

        print("MARIO going to cast the hell out of this!")
        eventlet.spawn_after(0.1, func)

    # def cast(self, context, method_name, *args, **kwargs):
    #     manager, method = self.get_tm_method(method_name)
    #     def func():
    #         print("MARIO I am casting like a fool!")
    #         method(manager, context, *args, **kwargs)

    #     print("MARIO going to cast the hell out of this!")
    #     eventlet.spawn_after(0.1, func)

    def get_tm_method(self, method_name):
        print("MARIO hiiiiii \t\t\%s\n%s" % (self, method_name))
        manager = Manager()
        method = getattr(Manager, method_name)
        return manager, method

    # def prepare(self, *args, **kwargs):
    #     return self


def monkey_patch():
    # def fake_get_client(self, *args, **kwargs):
    #     return FakeRpcClient()
    api.API = FakeApi
    def fake_load(context, manager=None):
        return FakeApi(context)
    api.load = fake_load
