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
            self.my_sem.acquire(blocking=True, timeout=None)
            try:
                func(*args, **kwargs)
            # except Exception as e:
            #     print("Exception in coroutine! %s" % e)
            finally:
                self.dead = True
                self.caller_sem.release()  # Relinquish control back to caller.
                for i in range(len(self.ALL)):
                    if self.ALL[i].id == self.id:
                        del self.ALL[i]
                        break

        t = true_spawn(go)
        started.wait()

    @classmethod
    def get_current(cls):
        return cls.get_by_id(eventlet.corolocal.get_ident())

    @classmethod
    def get_by_id(cls, id):
        for cr in cls.ALL:
            if cr.id == id:
                return cr
        raise RuntimeError("Coroutine with id %s not found!" % id)

    def sleep(self):
        # Only call this from it's own thread.
        assert eventlet.corolocal.get_ident() == self.id
        self.caller_sem.release()  # Relinquish control back to caller.
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


def other_threads_are_active():
    """Returns True if concurrent activity is being simulated.

    Specifically, this means there is a fake thread in action other than the
    "pulse" thread and the main test thread.
    """
    return len(fake_threads) >= 2


def fake_sleep(time_to_sleep):
    # Do NOT let code call sleep if there's not an actual reason!
    # if not any_napping_threads():
    #     raise RuntimeError("Trying to sleep but there is nothing to wait for!")
    global sleep_allowance
    sleep_allowance -= 1
    if not other_threads_are_active():  # The main "pulse" thread, plus this thread = 2
        if sleep_allowance < -1:
            raise RuntimeError("Sleeping for no reason.")
        else:
            return  # Forgive the thread for calling this for one time.
    sleep_allowance = allowable_empty_sleeps

    cr = Coroutine.get_current()
    for ft in fake_threads:
        if ft['greenlet'].id == cr.id:
            ft['next_sleep_time'] = time_to_sleep

    cr.sleep()


def fake_poll_until(retriever, condition=lambda value: value,
                    sleep_time=1, time_out=None):
    from trove.common import exception
    slept_time = 0
    while True:
        resource = retriever()
        if condition(resource):
            return resource
        fake_sleep(sleep_time)
        slept_time += sleep_time
        if time_out and slept_time >= time_out:
                raise exception.PollTimeOut()


def run_main(func):
    global main_greenlet
    main_greenlet = Coroutine(main_loop)
    fake_spawn(0, func)
    main_greenlet.run()


def main_loop():
    while len(fake_threads) > 0:
        pulse(0.1)


def fake_spawn_n(func, *args, **kw):
    fake_spawn(0, func, *args, **kw)


def fake_spawn(time_from_now_in_seconds, func, *args, **kw):
    """Fakes events without doing any actual waiting."""
    def thread_start():
        #fake_sleep(time_from_now_in_seconds)
        return func(*args, **kw)

    cr = Coroutine(thread_start)
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
                t['sleep'] = 0
                t['next_sleep_time'] = None
                t['greenlet'].run()
                sleep_time = t['next_sleep_time']
                if sleep_time is None or isinstance(sleep_time, tuple):
                    del fake_threads[index]
                    index -= 1
                else:
                    t['sleep'] = sleep_time
            index += 1


def wait_until_all_activity_stops():
    """In fake mode, wait for all simulated events to chill out.

    This can be useful in situations where you need simulated activity (such
    as calls running in TaskManager) to "bleed out" and finish before running
    another test.

    """
    if main_greenlet is None:
        return
    while other_threads_are_active():
        fake_sleep(1)


def monkey_patch():
    import time
    time.sleep = fake_sleep
    import eventlet
    from eventlet import greenthread
    eventlet.sleep = fake_sleep
    greenthread.sleep = fake_sleep
    eventlet.spawn_after = fake_spawn
    def raise_error():
        raise RuntimeError("Illegal operation!")
    eventlet.spawn_n = fake_spawn_n
    eventlet.spawn = raise_error
    from trove.common import utils
    utils.poll_until = fake_poll_until
    from eventlet.hubs import kqueue


import sys

def _trace(frame, event, arg):
    print("""%s MARIO %s %s """ % (eventlet.corolocal.get_ident(), frame.f_code.co_filename, frame.f_lineno))

#sys.settrace(_trace)

