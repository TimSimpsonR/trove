"""
Simulates time itself to make the fake mode tests run even faster.
"""
import eventlet
from eventlet import spawn as true_spawn
from eventlet.event import Event
from eventlet.semaphore import Semaphore
#from greenlet import greenlet as greenlet_thread


class Coroutine(object):
    """
    This class simulates a coroutine, which is ironic, as greenlet actually
    *is* a coroutine. But trying to use greenlet here gives nasty results
    since eventlet thoroughly monkey-patches things, making it difficult
    to run greenlet on its own.
    """

    ALL = []

    def __init__(self, func, *args, **kwargs):
        self.my_sem = Semaphore(0)   # This is held by the thread as it runs.
        self.caller_sem = None
        self.dead = False
        started = Event()
        self.id = 5
        self.ALL.append(self)
        def go():
            self.id = eventlet.corolocal.get_ident()
            started.send(True)
            print("MARIO\t\t\t\t\t\t\t\tBIRTH %s" % self.id)
            self.my_sem.acquire(blocking=True, timeout=None)
            try:
                print("MARIO\t\t\t\t\t\t\t\tSTART! %s" % self.id)
                print("Running func %s" % func)
                func(*args, **kwargs)
            # except Exception as e:
            #     print("Exception in coroutine! %s" % e)
            finally:
                print("MARIO\t\t\t\t\t\t\t\tI AM DEAD! %s" % self.id)
                self.dead = True
                self.caller_sem.release()  # Relinquish control back to caller.
                for i in range(len(self.ALL)):
                    if self.ALL[i].id == self.id:
                        del self.ALL[i]
                        break

        t = true_spawn(go)
        started.wait()
        print("LOCAL id=%s" % self.id)

    @classmethod
    def get_current(cls):
        return cls.get_by_id(eventlet.corolocal.get_ident())

    @classmethod
    def get_by_id(cls, id):
        for cr in cls.ALL:
            print("MARIO searching for id, could it be %s?" % cr.id)
            if cr.id == id:
                return cr
        raise RuntimeError("Coroutine with id %s not found!" % id)

    def sleep(self):
        # Only call this from it's own thread.
        assert eventlet.corolocal.get_ident() == self.id
        print("MARIO\t\t\t\t\t\t\t\tNAP %s!" % self.id)
        self.caller_sem.release()  # Relinquish control back to caller.
        print("MARIO\t\t\t\t\t\t\t\tAWAKE %s!" % self.id)
        self.my_sem.acquire(blocking=True, timeout=None)

    def run(self):
        # Don't call this from the thread which it represents.
        assert eventlet.corolocal.get_ident() != self.id
        self.caller_sem = Semaphore(0)
        self.my_sem.release()
        self.caller_sem.acquire()  # Wait for it to finish.



pending_events = []
sleep_entrance_count = 0

main_greenlet = None


fake_threads = []


allowable_empty_sleeps = 1
sleep_allowance = allowable_empty_sleeps


def fake_sleep(time_to_sleep):
    # Do NOT let code call sleep if there's not an actual reason!
    # if not any_napping_threads():
    #     raise RuntimeError("Trying to sleep but there is nothing to wait for!")
    global sleep_allowance
    sleep_allowance -= 1
    if len(fake_threads) < 2:  # The main "pulse" thread, plus this thread = 2
        if sleep_allowance < -1:
            raise RuntimeError("Sleeping for no reason.")
        else:
            return  # Forgive the thread for calling this for one time.
    sleep_allowance = allowable_empty_sleeps

    cr = Coroutine.get_current()
    print("MARIO I SLEEP!")
    print("      zzzz < %s" % cr.id)
    for ft in fake_threads:
        if ft['greenlet'].id == cr.id:
            ft['next_sleep_time'] = time_to_sleep

    cr.sleep()
    print("MARIO I doth awaken")


def fake_poll_until(retriever, condition=lambda value: value,
                    sleep_time=1, time_out=None):
    from trove.common import exception
    slept_time = 0
    while True:
        print("MARIO poll")
        resource = retriever()
        if condition(resource):
            return resource
        fake_sleep(sleep_time)
        slept_time += sleep_time
        if time_out and slept_time >= time_out:
                raise exception.PollTimeOut()


def run_main(func):
    global main_greenlet
    print("MARIO HI")
    main_greenlet = Coroutine(main_loop)
    print("MARIO HI 2")
    fake_spawn(0, func)
    print("MARIO HI 3")
    main_greenlet.run()
    print("HA HA")


def main_loop():
    while len(fake_threads) > 0:
        pulse(0.1)


def fake_spawn_n(func, *args, **kw):
    fake_spawn(0, func, *args, **kw)


def fake_spawn(time_from_now_in_seconds, func, *args, **kw):
    """Fakes events without doing any actual waiting."""
    def thread_start():
        #fake_sleep(time_from_now_in_seconds)
        print("MARIO Running %s" % func)
        return func(*args, **kw)

    cr = Coroutine(thread_start)
    print("MARIO, spawn, with sleep %d with func=%s" % (time_from_now_in_seconds, func))
    fake_threads.append({'sleep': time_from_now_in_seconds,
                         'greenlet': cr,
                         'name': str(func)})


def any_napping_threads():
    for t in fake_threads:
        if t['sleep'] > 0:
            return True
    return False


def pulse(seconds):
    if True: # try:
        index = 0
        while index < len(fake_threads):
            t = fake_threads[index]
            t['sleep'] -= seconds
            if t['sleep'] <= 0:
                print("MARIO x?")
                t['sleep'] = 0
                print("SWITCH %s" % t['name'])
                t['next_sleep_time'] = None
                t['greenlet'].run()
                sleep_time = t['next_sleep_time']
                print("MARIO will sleep of %s" % sleep_time)
                if sleep_time is None or isinstance(sleep_time, tuple):
                    print("MARIO DIE!!")
                    del fake_threads[index]
                    index -= 1
                else:
                    print("MARIO adding sleep to %s of %s" % (t['name'], t['sleep']))
                    t['sleep'] = sleep_time
            index += 1
    # except Exception as e:
    #     print("HOLY HELL!")
    #     print(e)
    #     import sys
    #     sys.abort()




def monkey_patch():
    print("HELL!")
    import time
    time.sleep = fake_sleep
    import eventlet
    from eventlet import greenthread
    eventlet.sleep = fake_sleep
    greenthread.sleep = fake_sleep
    eventlet.spawn_after = fake_spawn
    def b():
        raise RuntimeError("fgfdf")
    eventlet.spawn_n = fake_spawn_n
    eventlet.spawn = b
    print("HELL!")
    from trove.common import utils
    utils.poll_until = fake_poll_until
    from eventlet.hubs import kqueue
    class Err(object):
        def __init__(self, *args, **kw):
            raise RuntimeError("Fdg")
    #kqueue.Hub = Err()
    # from trove.openstack.common.rpc import impl_fake
    # def new_call(self, context, version, method, namespace, args, timeout):
    #     ctxt = impl_fake.RpcContext.from_dict(context.to_dict())
    #     rval = self.proxy.dispatch(context, version, method,
    #                                namespace, **args)
    #     res = []
    #     # Caller might have called ctxt.reply() manually
    #     for (reply, failure) in ctxt._response:
    #         if failure:
    #             raise failure[0], failure[1], failure[2]
    #         res.append(reply)
    #     # if ending not 'sent'...we might have more data to
    #     # return from the function itself
    #     if not ctxt._done:
    #         if inspect.isgenerator(rval):
    #             for val in rval:
    #                 res.append(val)
    #         else:
    #             res.append(rval)
    #     return res


    # impl_fake.call = new_call

import sys

def _trace(frame, event, arg):
    print("""%s MARIO %s %s """ % (eventlet.corolocal.get_ident(), frame.f_code.co_filename, frame.f_lineno))

#sys.settrace(_trace)

