import multiprocessing.managers
import config


class BaseManager(multiprocessing.managers.BaseManager):

    """A simple modified BaseManager from multiprocessing

    This adds three classmethods.

    """
    authkey = getattr(config, 'authkey', "Not very random")
    socket = None

    @classmethod
    def connect_to(cls):
        """Connects to a remote already running manager and returns it."""
        manager = cls(address=cls.socket, authkey=cls.authkey)
        manager.connect()
        return manager

    @classmethod
    def start_server(cls):
        """Starts a manager server in the calling thread and blocks until
        shutdown from another thread in some way."""
        manager = cls(address=cls.socket, authkey=cls.authkey)
        server = manager.get_server()
        server.serve_forever()

    @classmethod
    def launch_process(cls):
        """Launches a process and returns the manager associated."""
        manager = cls(address=cls.socket, authkey=cls.authkey)
        manager.start()
        return manager
