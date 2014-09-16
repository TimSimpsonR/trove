"""
Simulates time itself to make the fake mode tests run even faster.
"""
from greenlet import greenlet as greenlet_thread



pending_events = []
sleep_entrance_count = 0

main_greenlet = None


fake_threads = []

def fake_sleep(time_to_sleep):
    # Do NOT let code call sleep if there's not an actual reason!
    # if not any_napping_threads():
    #     raise RuntimeError("Trying to sleep but there is nothing to wait for!")
    global main_greenlet
    print("MARIO I SLEEP!")
    print("      zzzz < %s" % greenlet_thread.getcurrent())

    main_greenlet.switch(time_to_sleep)
    print("MARIO I doth awaken")


def run_main(func):
    global main_greenlet
    print("MARIO HI")
    main_greenlet = greenlet_thread(main_loop)
    print("MARIO HI 2")
    fake_spawn(0, func)
    print("MARIO HI 3")
    main_greenlet.switch()
    print("HA HA")


def main_loop():
    while True:
        if len(fake_threads) > 0:
            pulse(0.1)
        else:
            return

def fake_spawn(time_from_now_in_seconds, func, *args, **kw):
    """Fakes events without doing any actual waiting."""
    def thread_start():
        #fake_sleep(time_from_now_in_seconds)
        func(*args, **kw)

    print("MARIO, spawn, with sleep %d with func=%s" % (time_from_now_in_seconds, func))
    fake_threads.append({'sleep': time_from_now_in_seconds,
                         'greenlet': greenlet_thread(thread_start),
                         'name': str(func)})


def any_napping_threads():
    for t in fake_threads:
        if t['sleep'] > 0:
            return True
    return False


def pulse(seconds):
    try:
        for index in range(len(fake_threads)):
            print("LOOOPIN' %s" % seconds)
            t = fake_threads[index]
            t['sleep'] -= seconds
            if t['sleep'] <= 0:
                print("MARIO no sleep?")
                t['sleep'] = 0
                print("SWITCH %s" % t['name'])
                sleep_time = t['greenlet'].switch()
                print("MARIO will sleep of %s" % sleep_time)
                if sleep_time is None or isinstance(sleep_time, tuple):
                    print("MARIO DIE!!")
                    del fake_threads[index]
                    index -= 1
                else:
                    print("MARIO adding sleep to %s of %s" % (t['name'], t['sleep']))
                    t['sleep'] = sleep_time
    except Exception as e:
        print("HOLY HELL!")
        print(e)
        import sys
        sys.abort()




def monkey_patch():
    print("HELL!")
    import time
    time.sleep = fake_sleep
    import eventlet
    from eventlet import greenthread
    eventlet.sleep = fake_sleep
    greenthread.sleep = fake_sleep
    eventlet.spawn_after = fake_spawn
    #eventlet.spawn_n = event_simulator_spawn
    eventlet.spawn = RuntimeError
    print("HELL!")

