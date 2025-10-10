from autogen_core import  MessageContext, RoutedAgent, message_handler, type_subscription, TopicId
from tools.topisc import user_topic_type
from tools.dataType import Message

@type_subscription(topic_type=user_topic_type)
class UserAgent(RoutedAgent):
    def __init__(self) -> None:
        super().__init__("A user agent that outputs the final copy to the user.")

    @message_handler
    async def handle_final_copy(self, message: Message, ctx: MessageContext) -> None:
        print(f"\n{'-'*80}\n{self.id.type} received final copy:\n{message.content}")
