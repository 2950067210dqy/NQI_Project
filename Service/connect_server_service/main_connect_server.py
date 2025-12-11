import os
import sys

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QMessageBox
from loguru import logger

from Service.connect_server_service.api.api_client import UpperAPIClient
from Service.connect_server_service.index.Client_server import Client_server
from Service.connect_server_service.listener.notification_listener import NotificationListener
from public.config_class import global_load
from public.config_class.global_setting import global_setting
from public.entity.MyQThread import MyQThread
from public.entity.queue.ObjectQueueItem import ObjectQueueItem
service_name = "connect_server"
client_server:Client_server = None
class read_queue_data_Thread(MyQThread):
    def __init__(self, name):
        super().__init__(name)
        self.queue = None
        pass

    def stop(self):

        super().stop()
    def dosomething(self):
        if not self.queue.empty():
            # logger.error(f"{self.queue.qsize()}")
            try:
                message: ObjectQueueItem = self.queue.get()
            except Exception as e:
                logger.error(f"{self.name}发生错误{e}")
                return
            # logger.error(f"{self.name}_get_message:{message}|")
            if message is not None and message.is_Empty():
                return
            if message is not None and isinstance(message, ObjectQueueItem) and message.to == f'main_{service_name}':
                # logger.error(f"{self.name}_get_message:{message}")
                match message.title:

                    case _:
                        pass




            else:
                # 把消息放回去
                self.queue.put(message)

        pass




read_queue_data_thread = read_queue_data_Thread(name=f"main_{service_name}_read_queue_data_thread")

def main(q,send_message_q):
    logger.info(f"{'-' * 30}{service_name}_start{'-' * 30}")
    logger.info(f"{__name__} | {os.path.basename(__file__)}|{os.getpid()}|{os.getppid()}")
    app = QCoreApplication(sys.argv)
    # 设置全局变量
    global_load.load_global_setting_without_Qt()

    global read_queue_data_thread,client_server
    client_server = Client_server()
    read_queue_data_thread.queue = send_message_q

    read_queue_data_thread.start()
    start()
    # 系统退出
    return app.exec()
def start():
    logger.info(f"{'-' * 30}{service_name}_run{'-' * 30}")
    global client_server
    client_server.connect_to_server()



def restart(q,send_message_q):
    main(q,send_message_q)

def pause():
    logger.info(f"{'-' * 30}{service_name}_pause{'-' * 30}")
    pass

def stop():
    logger.info(f"{'-' * 30}{service_name}_stop{'-' * 30}")
    client_server.disconnect_from_server()
