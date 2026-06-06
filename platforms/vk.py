import asyncio
import json
import random
import threading
import tempfile
import os
import requests
import time
from typing import Any, Optional, List, Dict

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from ..context import Platform, EventType, Context, Message, Chat, User, CallbackQuery, Attachment
from .abstract import PlatformAdapter
from ..log import setup_logger


class VKAdapter(PlatformAdapter):
    def __init__(self, token: str, group_id: int, bot, user_token: Optional[str] = None,
                 admin_ids: Optional[List[int]] = None, log_level: str = None,
                 log_dir: str = None):
        super().__init__(Platform.VK, token, bot)
        self.group_id = group_id
        self.user_token = user_token
        self.admin_ids = admin_ids or []
        self.logger = setup_logger('VKAdapter', log_level, log_dir)

        self.vk_session = vk_api.VkApi(token=token)
        self.longpoll = VkBotLongPoll(self.vk_session, group_id)
        self.vk = self.vk_session.get_api()

        if user_token:
            self.user_vk_session = vk_api.VkApi(token=user_token)
            self.user_vk = self.user_vk_session.get_api()
        else:
            self.user_vk = self.vk

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_storage_key(self, ctx: Context) -> str:
        platform = self.platform.value
        if ctx.user and ctx.chat and ctx.chat.type != 'private':
            return f"{platform}:group:{ctx.chat.id}:user:{ctx.user.id}"
        if ctx.user:
            return f"{platform}:user:{ctx.user.id}"
        if ctx.chat:
            return f"{platform}:chat:{ctx.chat.id}"
        return f"{platform}:unknown"

    async def initialize(self):
        try:
            group_info = await asyncio.to_thread(self.vk.groups.getById, group_id=self.group_id)
            self.logger.info(f"VK adapter initialized for group: {group_info[0]['name']} (ID: {self.group_id})")
        except Exception as e:
            self.logger.error(f"Failed to initialize VK adapter: {e}", exc_info=True)
            raise

    async def cleanup(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    async def run(self):
        self.logger.info("Starting VK LongPoll worker")
        self._running = True
        self._loop = asyncio.get_running_loop()
        self._thread = threading.Thread(target=self._poll_worker, daemon=True)
        self._thread.start()
        asyncio.create_task(self._process_queue())

        while self._running:
            await asyncio.sleep(0.5)

    async def stop(self):
        self._running = False

    async def answer_inline_query(self, inline_query_id: str, results: List[Any], **kwargs) -> Any:
        raise NotImplementedError("Inline queries are not supported in VK")

    def _poll_worker(self):
        self.logger.info("VK LongPoll worker started")
        for event in self.longpoll.listen():
            if not self._running:
                break
            self.logger.debug(f"LongPoll event: {event.type}")
            asyncio.run_coroutine_threadsafe(self._event_queue.put(event), self._loop)

    async def _process_queue(self):
        while self._running:
            event = await self._event_queue.get()
            if event.type == VkBotEventType.MESSAGE_NEW:
                await self._dispatch_event(event, EventType.MESSAGE)
            elif event.type == VkBotEventType.MESSAGE_EVENT:
                await self._dispatch_event(event, EventType.CALLBACK_QUERY)


    async def send_message(self, chat_id: int, text: str, **kwargs) -> Any:
        self.logger.debug(f"Sending message to {chat_id}: {text[:50]}...")
        params = {
            'peer_id': chat_id,
            'message': text,
            'random_id': random.randint(1, 2**31),
        }
        if 'keyboard' in kwargs:
            params['keyboard'] = kwargs['keyboard']
        if 'reply_to' in kwargs:
            params['reply_to'] = kwargs['reply_to']
        if 'attachment' in kwargs:
            params['attachment'] = kwargs['attachment']
        return await asyncio.to_thread(self.vk.messages.send, **params)

    async def edit_message(self, chat_id: int, message_id: int, text: str, **kwargs) -> Any:
        params = {
            'peer_id': chat_id,
            'message': text,
            'message_id': message_id,
        }
        return await asyncio.to_thread(self.vk.messages.edit, **params)

    async def answer_callback_query(self, callback_query_id: str, **kwargs) -> Any:
        return await asyncio.to_thread(self.vk.messages.sendMessageEventAnswer, **kwargs)

    async def delete_message(self, chat_id: int, message_id: int, **kwargs) -> Any:
        params = {
            'peer_id': chat_id,
            'message_ids': [message_id],
            'delete_for_all': kwargs.get('delete_for_all', True)
        }
        return await asyncio.to_thread(self.vk.messages.delete, **params)

    async def get_me(self) -> Any:
        return await asyncio.to_thread(self.vk.groups.getById, group_id=self.group_id)[0]

    async def get_chat(self, chat_id: int) -> Any:
        return await asyncio.to_thread(self.vk.messages.getConversationsById, peer_ids=chat_id)

    async def get_user(self, user_id: int) -> Any:
        return await asyncio.to_thread(self._get_user_info, user_id)

    def _get_user_info(self, user_id: int) -> dict:
        try:
            users = self.vk.users.get(user_ids=user_id, fields='screen_name')
            return users[0] if users else {}
        except Exception:
            return {}

    @property
    def raw_client(self):
        return self.vk

    async def create_post_on_wall(self, message: str, attachments: Optional[List[str]] = None) -> Optional[Dict]:
        vk_to_use = self.user_vk if (attachments and self.user_token) else self.vk
        params = {
            'owner_id': -self.group_id,
            'from_group': 1,
            'message': message,
            'random_id': random.randint(1, 2**31)
        }
        if attachments:
            params['attachments'] = ','.join(attachments)
        return await asyncio.to_thread(vk_to_use.wall.post, **params)

    async def edit_post_on_wall(self, post_id: int, message: Optional[str] = None,
                                attachments: Optional[List[str]] = None) -> bool:
        vk_to_use = self.user_vk if (attachments and self.user_token) else self.vk
        params = {
            'owner_id': -self.group_id,
            'post_id': post_id,
            'from_group': 1
        }
        if message is not None:
            params['message'] = message
        if attachments is not None:
            params['attachments'] = ','.join(attachments) if attachments else ''
        try:
            await asyncio.to_thread(vk_to_use.wall.edit, **params)
            return True
        except Exception:
            return False

    async def get_wall_posts(self, count: int = 10, offset: int = 0) -> List[Dict]:
        vk_to_use = self.user_vk if self.user_token else self.vk
        response = await asyncio.to_thread(
            vk_to_use.wall.get, owner_id=-self.group_id, count=count, offset=offset
        )
        return response['items']

    async def get_post_by_id(self, post_id: int) -> Optional[Dict]:
        vk_to_use = self.user_vk if self.user_token else self.vk
        try:
            response = await asyncio.to_thread(
                vk_to_use.wall.getById, posts=[f"-{self.group_id}_{post_id}"]
            )
            return response[0] if response else None
        except Exception:
            return None

    async def upload_photo_for_wall(self, photo_url: str) -> Optional[str]:
        return await asyncio.to_thread(self._sync_upload_photo_for_wall, photo_url)

    def _sync_upload_photo_for_wall(self, photo_url: str) -> Optional[str]:
        self.logger.info(f"Uploading photo from {photo_url}")
        if not self.user_token:
            return None
        try:
            upload_server = self.user_vk.photos.getWallUploadServer(group_id=self.group_id)
            upload_url = upload_server['upload_url']
            response = requests.get(photo_url, stream=True, timeout=30)
            response.raise_for_status()

            content_type = response.headers.get('content-type', '')
            ext = '.jpg'
            if 'png' in content_type:
                ext = '.png'
            elif 'gif' in content_type:
                ext = '.gif'
            elif 'webp' in content_type:
                ext = '.webp'

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                for chunk in response.iter_content(8192):
                    tmp.write(chunk)
                tmp_path = tmp.name

            with open(tmp_path, 'rb') as f:
                files = {'photo': f}
                upload_resp = requests.post(upload_url, files=files, timeout=30).json()
            os.unlink(tmp_path)

            save_resp = self.user_vk.photos.saveWallPhoto(
                group_id=self.group_id,
                photo=upload_resp['photo'],
                server=upload_resp['server'],
                hash=upload_resp['hash']
            )
            photo = save_resp[0]
            return f"photo{photo['owner_id']}_{photo['id']}"
        except Exception as e:
            self.logger.error(f"Photo upload failed: {e}", exc_info=True)
            return None

    async def upload_document_for_wall(self, doc_url: str, filename: str) -> Optional[str]:
        return await asyncio.to_thread(self._sync_upload_document_for_wall, doc_url, filename)

    def _sync_upload_document_for_wall(self, doc_url: str, filename: str) -> Optional[str]:
        if not self.user_token:
            return None
        try:
            upload_server = self.user_vk.docs.getWallUploadServer(group_id=self.group_id)
            upload_url = upload_server['upload_url']

            response = requests.get(doc_url, stream=True, timeout=60)
            response.raise_for_status()

            ext = os.path.splitext(filename)[1] or '.dat'
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                for chunk in response.iter_content(8192):
                    tmp.write(chunk)
                tmp_path = tmp.name

            with open(tmp_path, 'rb') as f:
                files = {'file': f}
                upload_resp = requests.post(upload_url, files=files, timeout=60).json()
            os.unlink(tmp_path)

            save_resp = self.user_vk.docs.save(
                file=upload_resp['file'],
                title=filename[:100]
            )
            doc = save_resp['doc']
            return f"doc{doc['owner_id']}_{doc['id']}"
        except Exception as e:
            self.logger.error(f"Document upload failed: {e}", exc_info=True)
            return None

    async def upload_video_for_wall(self, video_url: str, title: str) -> Optional[str]:
        return await asyncio.to_thread(self._sync_upload_video_for_wall, video_url, title)

    def _sync_upload_video_for_wall(self, video_url: str, title: str) -> Optional[str]:
        if not self.user_token:
            return None
        try:
            upload_server = self.user_vk.video.save(
                name=title[:100],
                description=f"Uploaded via bot",
                wallpost=1,
                group_id=self.group_id
            )
            upload_url = upload_server['upload_url']

            response = requests.get(video_url, stream=True, timeout=120)
            response.raise_for_status()

            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                for chunk in response.iter_content(8192):
                    tmp.write(chunk)
                tmp_path = tmp.name

            with open(tmp_path, 'rb') as f:
                files = {'video_file': f}
                requests.post(upload_url, files=files, timeout=120)
            os.unlink(tmp_path)

            return f"video{upload_server['owner_id']}_{upload_server['video_id']}"
        except Exception as e:
            self.logger.error(f"Video upload failed: {e}", exc_info=True)
            return None

    async def create_poll(self, question: str, answers: List[str]) -> Optional[str]:
        return await asyncio.to_thread(self._sync_create_poll, question, answers)

    def _sync_create_poll(self, question: str, answers: List[str]) -> Optional[str]:
        if not self.user_token:
            return None
        try:
            poll = self.user_vk.polls.create(
                question=question,
                add_answers=answers,
                owner_id=-self.group_id,
                is_anonymous=0,
                is_multiple=0
            )
            return f"poll{poll['owner_id']}_{poll['id']}"
        except Exception as e:
            self.logger.error(f"Poll creation failed: {e}", exc_info=True)
            return None

    def _create_context(self, raw_event: Any, event_type: EventType) -> Context:
        ctx = Context(self.platform, event_type, raw_event, self.bot, adapter=self)

        if event_type == EventType.MESSAGE:
            msg = raw_event.object.message
            from_id = msg['from_id']
            user_info = self._get_user_info(from_id)

            attachments = []
            for att in msg.get('attachments', []):
                att_type = att['type']
                attachments.append(Attachment(type=att_type, raw=att))

            ctx.message = Message(
                id=msg['id'],
                text=msg.get('text', ''),
                date=msg.get('date'),
                chat=Chat(
                    id=msg['peer_id'],
                    type='private' if msg['peer_id'] > 2e9 else 'group',
                ),
                user=User(
                    id=from_id,
                    username=user_info.get('screen_name'),
                    first_name=user_info.get('first_name'),
                    last_name=user_info.get('last_name'),
                    is_bot=False
                ),
                attachments=attachments
            )
            ctx.chat = ctx.message.chat
            ctx.user = ctx.message.user

            if msg.get('text', '').startswith('/'):
                parts = msg['text'][1:].split()
                if parts:
                    ctx.command = parts[0]
                    ctx.args = parts[1:]

        elif event_type == EventType.CALLBACK_QUERY:
            ev = raw_event.object
            ctx.callback_query = CallbackQuery(
                id=ev.get('event_id'),
                data=json.dumps(ev.get('payload', {})),
                user=User(id=ev['user_id']),
                message=Message(id=ev.get('conversation_message_id'))
            )
            ctx.user = ctx.callback_query.user

        return ctx


VKBot = VKAdapter