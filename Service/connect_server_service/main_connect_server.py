import os
import sys
from queue import Empty

from PyQt6.QtCore import QCoreApplication
from loguru import logger

from Service.connect_server_service.index.Client_server import Client_server
from public.config_class import global_load
from public.config_class.global_setting import global_setting
from public.entity.MyQThread import MyQThread
from public.entity.queue.ObjectQueueItem import ObjectQueueItem

service_name = 'connect_server'
client_server: Client_server = None


class read_queue_data_Thread(MyQThread):
    def __init__(self, name):
        super().__init__(name)
        self.queue = None

    def stop(self):
        super().stop()

    def dosomething(self):
        if self.queue is None:
            self.msleep(20)
            return
        try:
            message: ObjectQueueItem = self.queue.get(timeout=0.05)
        except Empty:
            return
        except Exception as e:
            logger.error(f'{self.name}发生错误{e}')
            return

        if message is not None and message.is_Empty():
            return

        if message is not None and isinstance(message, ObjectQueueItem) and message.to == f'main_{service_name}':
            match message.title:
                case 'reconnect':
                    logger.info('收到上位机重连服务器指令')
                    payload = message.data if isinstance(message.data, dict) else {}
                    client_server.disconnect_from_server(notify_ui=False)
                    client_server.connect_to_server(auto_connect=bool(payload.get('auto_connect', False)))
                case _:
                    pass
        else:
            self.queue.put(message)



read_queue_data_thread = read_queue_data_Thread(name=f'main_{service_name}_read_queue_data_thread')


def main(q, send_message_q):
    logger.info(f"{'-' * 30}{service_name}_start{'-' * 30}")
    logger.info(f'{__name__} | {os.path.basename(__file__)}|{os.getpid()}|{os.getppid()}')
    app = QCoreApplication(sys.argv)
    global_load.load_global_setting_without_Qt()
    global_setting.set_setting('queue', q)
    global_setting.set_setting('send_message_queue', send_message_q)

    global read_queue_data_thread, client_server
    client_server = Client_server()
    read_queue_data_thread.queue = send_message_q
    read_queue_data_thread.start()
    start()
    return app.exec()


def start():
    logger.info(f"{'-' * 30}{service_name}_run{'-' * 30}")
    global client_server
    # 进程启动时自动连接服务器，并通知主界面进入自动重连锁定状态。
    client_server.connect_to_server(auto_connect=True)


def restart(q, send_message_q):
    main(q, send_message_q)


def pause():
    logger.info(f"{'-' * 30}{service_name}_pause{'-' * 30}")


def stop():
    logger.info(f"{'-' * 30}{service_name}_stop{'-' * 30}")
    if client_server is not None:
        client_server.disconnect_from_server()

