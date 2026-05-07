import os
import time
import signal
import threading
import urllib.parse
try:
    import osw_incline
    _OSW_INCLINE_VERSION = osw_incline.__version__
except ModuleNotFoundError:
    _OSW_INCLINE_VERSION = 'unknown'
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
        # Keep lifecycle same as osw-validation; only force callback worker mode to
        # thread by default to avoid subprocess worker exits in this runtime.
        os.environ.setdefault('TOPIC_CALLBACK_EXECUTION_MODE', 'thread')

        self.core = Core()
        self._subscription_name = self._config.event_bus.request_subscription
        self.request_topic = self.core.get_topic(
            topic_name=self._config.event_bus.request_topic,
            max_concurrent_messages=self._config.max_concurrent_messages
        )
        self.storage_client = self.core.get_storage_client()
        self.container_name = self._config.event_bus.container_name
        self._shutdown_triggered = threading.Event()
        self.listening_thread = threading.Thread(target=self.subscribe, daemon=True)
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

        self.request_topic.subscribe(
            subscription=self._subscription_name,
            callback=process,
            max_receivable_messages=self._config.max_receivable_messages
        )
        if self._config.max_receivable_messages > 0:
            Logger.info('Listener finished processing available messages; stopping server/container.')
            self._stop_server_and_container(delay_seconds=2)

    def process_message(self, request_msg: RequestMessage) -> None:
        prefix = request_msg.data.jobId if request_msg.data.jobId else get_unique_id()
        file_path = request_msg.data.dataset_url
        status_sent = False
        try:
            tdei_record_id = request_msg.messageId
            Logger.info(
                f'Received message for: {tdei_record_id}. '
                f'Message received for OSW Incline! Core version: {Core.__version__}'
            )
            if file_path is None:
                error_msg = 'Request does not have valid file path specified.'
                Logger.error(f'{tdei_record_id}, {error_msg} !')
                raise Exception(error_msg)

            file_upload_path = urllib.parse.unquote(request_msg.data.dataset_url)
            if file_upload_path:
                inclination = Inclination(
                    file_path=file_upload_path,
                    storage_client=self.storage_client,
                    prefix=prefix
                )
                file_path = inclination.calculate()
                Logger.info(f' Calculated inclination for file: {file_path}')
                if file_path:
                    uploaded_file_path = self.upload_to_azure(
                        file_path=file_path,
                        job_id=prefix
                    )
                    if uploaded_file_path:
                        file_path = uploaded_file_path
                    else:
                        raise Exception('Failed to upload processed file to storage')
                else:
                    raise Exception('Failed to generate processed file')
            else:
                raise Exception('File entity not found')

            self.send_status(valid=True, request_message=request_msg, file_path=file_path)
            status_sent = True
        except Exception as e:
            Logger.error(f' Error: {e}')
            self.send_status(
                valid=False,
                request_message=request_msg,
                file_path=file_path,
                upload_message=f'Error: {e}'
            )
            status_sent = True
        finally:
            if status_sent:
                Logger.info(f'Validation status sent for {prefix}.')
            else:
                Logger.warning(f'Validation status was not sent for {prefix}.')
            Logger.info(f' Cleaning up files with prefix: {prefix}')
            clean_up(path=f'{self._config.get_download_directory()}/{prefix}')

    def send_status(
        self,
        valid: bool,
        request_message: RequestMessage,
        file_path: str,
        upload_message: str = None
    ) -> None:
        response_message = {
            'message': (
                upload_message
                if upload_message
                else 'Successfully added inclination to the dataset.'
            ),
            'success': valid,
            'file_upload_path': file_path,
            'package': {
                'python-ms-core': Core.__version__,
                'osw-incline': _OSW_INCLINE_VERSION
            }
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
        self._stop_server_and_container()
        if hasattr(self, 'listening_thread'):
            self.listening_thread.join(timeout=0)

    def upload_to_azure(self, job_id: str, file_path=None):
        Logger.info(f' Uploading file to Azure: {file_path}')
        try:
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                raise ValueError(f'File is empty, cannot upload: {file_path}')

            target_directory = f'jobs/{job_id}'
            target_file_remote_path = f'{target_directory}/{os.path.basename(file_path)}'

            container = self.storage_client.get_container(
                container_name=self.container_name
            )
            file = container.create_file(name=target_file_remote_path)
            with open(file_path, 'rb') as data:
                data.seek(0)
                file.upload(data)
            uploaded_path = file.get_remote_url()
            Logger.info(f' File uploaded to Azure: {uploaded_path}')
            return uploaded_path
        except Exception as e:
            Logger.error(f' Error: {e}')
            return None

    def _stop_server_and_container(self, delay_seconds: float = 0.0):
        """
        Attempt to gracefully stop the current process (stopping FastAPI/uvicorn and the Docker container).
        """
        Logger.info('Gracefully stopping FastAPI/uvicorn and Docker container')
        if self._shutdown_triggered.is_set():
            Logger.info('Server stop already in progress; skipping duplicate trigger.')
            return
        self._shutdown_triggered.set()
        Logger.info('Server stop triggered; scheduling shutdown.')

        def _terminate():
            if delay_seconds:
                time.sleep(delay_seconds)
            try:
                Logger.info('Sending SIGTERM to stop server/container.')
                os.kill(os.getpid(), signal.SIGTERM)
            except Exception as err:
                Logger.warning(f'Error occurred while sending SIGTERM: {err}')
            finally:
                Logger.info('Forcing process exit to stop server/container.')
                os._exit(0)

        threading.Thread(target=_terminate, daemon=True).start()
