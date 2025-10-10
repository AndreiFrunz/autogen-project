from autogen_core import MessageContext, RoutedAgent, message_handler, type_subscription, TopicId
from tools.topisc import testing_code_writer_type, user_topic_type
from autogen_core.models import SystemMessage, ChatCompletionClient, UserMessage
from tools.dataType import Message

@type_subscription(topic_type=testing_code_writer_type)
class TestingCodeWriterAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("A expert in playwright testing code")
        self._system_message = SystemMessage(
            content=(
                "You are an expert in writing playwright testing code\n"
                "Your job is write a playwright javascript file\n"
                "Each scenario has to be inside a test case\n"
                "Respect the json file from the scraper agent\n"
                "Do not invent code or locators, stick to the json file\n"
            )
        )
        self._model_client = model_client

    @message_handler
    async def handle_intermediate_instruction(self, message: Message, ctx: MessageContext) -> None:
        prompt = f"Json instruction to create playwright testing code: {message.content}"
        llm_result = await self._model_client.create(
            messages=[self._system_message, UserMessage(content=prompt, source=self.id.key)],
            cancellation_token=ctx.cancellation_token,
        )
        response = llm_result.content
        assert isinstance(response, str)
        print(f"{'-'*80}\n{self.id.type}:\n{response}")

        await self.publish_message(Message(response), topic_id=TopicId(user_topic_type, source=self.id.key))
