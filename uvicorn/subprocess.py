"""
Some light wrappers around Python's multiprocessing, to deal with cleanly
starting child processes.
"""
import multiprocessing
import os
import platform
import sys

spawn = multiprocessing.get_context("spawn")


def get_subprocess(config, target, sockets):
    """
    Called in the parent process, to instantiate a new child process instance.
    The child is not yet started at this point.

    * config - The Uvicorn configuration instance.
    * target - A callable that accepts a list of sockets. In practice this will
               be the `Server.run()` method.
    * sockets - A list of sockets to pass to the server. Sockets are bound once
                by the parent process, and then passed to the child processes.
    """
    # We pass across the stdin fileno, and reopen it in the child process.
    # This is required for some debugging environments.
    try:
        stdin_fileno = sys.stdin.fileno()
    except OSError:
        stdin_fileno = None

    # Under Windows we cannot pass sockets directly, but must marshall
    # them into share instances.
    if platform.system() == "Windows":
        from multiprocessing.resource_sharer import DupSocket

        sockets = [DupSocket(s) for s in sockets]

    kwargs = {
        "config": config,
        "target": target,
        "sockets": sockets,
        "stdin_fileno": stdin_fileno,
    }

    return spawn.Process(target=subprocess_started, kwargs=kwargs)


def subprocess_started(config, target, sockets, stdin_fileno):
    """
    Called when the child process starts.

    * config - The Uvicorn configuration instance.
    * target - A callable that accepts a list of sockets. In practice this will
               be the `Server.run()` method.
    * sockets - A list of sockets to pass to the server. Sockets are bound once
                by the parent process, and then passed to the child processes.
    * stdin_fileno - The file number of sys.stdin, so that it can be reattached
                     to the child process.
    """
    # Re-open stdin.
    if stdin_fileno is not None:
        sys.stdin = os.fdopen(stdin_fileno)

    # On Windows we need to marshall sockets back from their share instances.
    if platform.system() == "Windows":
        sockets = [s.detach() for s in sockets]

    # Logging needs to be setup again for each child.
    config.configure_logging()

    # Now we can call into `Server.run(sockets=sockets)`
    target(sockets=sockets)
