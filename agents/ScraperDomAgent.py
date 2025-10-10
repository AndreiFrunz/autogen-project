from autogen_core import MessageContext, RoutedAgent, message_handler, type_subscription, TopicId
from tools.topisc import scrapper_topic_type, testing_code_writer_type
from autogen_core.models import SystemMessage, ChatCompletionClient, UserMessage
from tools.dataType import Message

@type_subscription(topic_type=scrapper_topic_type)
class ScraperDomAgent(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("A expert in playwright testing planner for url/website.")
        self._system_message = SystemMessage(
            content=(
                "You are an expert in playwright testing planner\n"
                "Your job is to access that url and analyse html DOM based on test scenarios\n"
                "To access the link and retrive the html use dom_fetcher function"
                "Extract all data locators with id/class arguments (<locators arguments='argument-name' > content </locator>) which will be used in creating playwright tests\n"
                "Create a json with all testing scenario and data html locators\n"
                "Do not invent or create any locators or invent any other information stay strict to the information you recieved\n"
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

        await self.publish_message(Message(response), topic_id=TopicId(testing_code_writer_type, source=self.id.key))
