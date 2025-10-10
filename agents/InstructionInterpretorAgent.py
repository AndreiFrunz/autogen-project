import asyncio, inspect, json
from typing import Callable, Awaitable, Union, Dict, Any
from autogen_core import MessageContext, RoutedAgent, message_handler, type_subscription, TopicId
from tools.topisc import instruction_interpretor_type, scrapper_topic_type
from autogen_core.models import SystemMessage, ChatCompletionClient, UserMessage
from tools.dataType import Message


DomFetcher = Union[Callable[[str], str], Callable[[str], Awaitable[str]]]

@type_subscription(topic_type=instruction_interpretor_type)
class InstructionInterpretorAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient, dom_fetcher: DomFetcher) -> None:
        super().__init__("A intereptor of instruction agent.")
        self._dom_fetcher = dom_fetcher
        self._system_message = SystemMessage(
            content=(
                "You are the Intake Parser\n"
                "Your job is to read a single free-text message from the user that always includes a URL plus instructions for creating tests.\n"
                "Then separate the URL from the scenario instructions and return a clean, structured JSON payload for downstream agents.\n"
                "Return an json with a format like this:\n"
                "{\n"
                "'url':'user-provided-url,\n'"
                "'raw_instruction':'user-provided-instruction,'\n"
                "'scenarios' : [\n"
                "   {\n"
                "      'name': 'scenario-name',\n"
                "      'steps': ['step-1-scenario', 'step-2-scenario'], \n  "
                "   }\n"
                "  ]\n"
                "}\n"
            ),
        )
        self._model_client = model_client

    async def _fetch_html(self, url: str) -> str:
        if inspect.iscoroutinefunction(self._dom_fetcher):
            return await self._dom_fetcher(url)  # async helper
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._dom_fetcher, url)

    def _parse_llm_json(self, text: str) -> Dict[str, Any]:
        t = text.strip()
        if t.startswith("```"):
            lines = t.splitlines()
            if lines and lines[-1].startswith("```"):
                t = "\n".join(lines[1:-1]).strip()
        return json.loads(t)

    @message_handler
    async def handle_user_instruction(self, message: Message, ctx: MessageContext) -> None:
        prompt = f"User instruction to create playwright testing code: {message.content}"
        llm_result = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt, source=self.id.key)],
            cancellation_token=ctx.cancellation_token,
        )
        payload = self._parse_llm_json(llm_result.content)
        url = payload.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("Missing 'url' in parsed payload.")
        html = await self._fetch_html(url.strip())
        payload["html"] = html 
        assert isinstance(payload, str)
        print(f"{'-'*80}\n{self.id.type}:\n{payload}")

        await self.publish_message(Message(payload), topic_id=TopicId(scrapper_topic_type, source=self.id.key))
