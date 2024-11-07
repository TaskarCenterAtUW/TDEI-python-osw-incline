import os
import gc
import threading
from src.logger import Logger
from python_ms_core import Core
from src.config import Settings
from src.inclination_helper.inclination import Inclination
from src.models.queue_message_content import RequestMessage
from src.inclination_helper.utils import get_unique_id, clean_up
from python_ms_core.core.queue.models.queue_message import QueueMessage


class InclinationService:
    _config = Settings()

    def __init__(self):
        self.core = Core()
        self._subscription_name = self._config.event_bus.request_subscription
        self.request_topic = self.core.get_topic(
            topic_name=self._config.event_bus.request_topic,
            max_concurrent_messages=self._config.max_concurrent_messages
        )
        self.storage_client = self.core.get_storage_client()
        self.container_name = self._config.event_bus.container_name
        self.listening_thread = threading.Thread(target=self.subscribe)
        self.listening_thread.start()

    def subscribe(self) -> None:
        # Process the incoming message
        def process(message) -> None:
            if message is not None:
                request_message = QueueMessage.to_dict(message)
                request_msg = RequestMessage.from_dict(request_message)
                self.process_message(request_msg)
            else:
                Logger.info(' No Message')

        self.request_topic.subscribe(subscription=self._subscription_name, callback=process)

    def process_message(self, request_msg: RequestMessage) -> None:
        prefix = request_msg.data.jobId if request_msg.data.jobId else get_unique_id()
        file_path = request_msg.data.dataset_url
        inclination = None
        try:
            Logger.info(f' Message ID: {request_msg.messageId}')
            is_valid = True
            if file_path is None:
                Logger.warning(' No file path found in the request!')
                is_valid = False
            else:
                inclination = Inclination(
                    file_path=file_path,
                    storage_client=self.storage_client,
                    prefix=prefix
                )
                file_path = inclination.calculate()
                Logger.info(f' Calculated inclination for file: {file_path}')
                if file_path:
                    file_path = self.upload_to_azure(
                        file_path=file_path,
                        job_id=prefix
                    )
                else:
                    is_valid = False
                    file_path = request_msg.data.dataset_url

            self.send_status(valid=is_valid, request_message=request_msg, file_path=file_path)
        except Exception as e:
            Logger.error(f' Error: {e}')
            self.send_status(valid=False, request_message=request_msg, file_path=file_path)
        finally:
            Logger.info(f' Cleaning up files with prefix: {prefix}')
            clean_up(path=f'{self._config.get_download_directory()}/{prefix}')
            del inclination
            gc.collect()

    def send_status(self, valid: bool, request_message: RequestMessage, file_path: str) -> None:
        response_message = {
            'message': 'Success' if valid else 'Failed',
            'success': valid,
            'file_upload_path': file_path
        }
        Logger.info(
            f' Publishing new message with ID: {request_message.messageId} with status: {valid}')
        data = QueueMessage.data_from({
            'messageId': request_message.messageId,
            'messageType': request_message.messageType,
            'data': response_message
        })
        response_topic = self.core.get_topic(topic_name=self._config.event_bus.response_topic)
        response_topic.publish(data=data)
        return

    def stop_listening(self):
        self.listening_thread.join(timeout=0)
        return

    def upload_to_azure(self, job_id: str, file_path=None):
        Logger.info(f' Uploading file to Azure: {file_path}')
        try:
            target_directory = f'jobs/{job_id}'
            target_file_remote_path = f'{target_directory}/{os.path.basename(file_path)}'

            container = self.storage_client.get_container(
                container_name=self.container_name
            )
            file = container.create_file(name=target_file_remote_path)
            with open(file_path, 'rb') as data:
                file.upload(data)
            uploaded_path = file.get_remote_url()
            Logger.info(f' File uploaded to Azure: {uploaded_path}')
            return uploaded_path
        except Exception as e:
            Logger.error(f' Error: {e}')
            return None
