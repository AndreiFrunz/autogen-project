from autogen_core import SingleThreadedAgentRuntime, TopicId, TypePrefixSubscription
from autogen_ext.models.openai import OpenAIChatCompletionClient, AzureOpenAIChatCompletionClient
from agents.InstructionInterpretorAgent import InstructionInterpretorAgent
from agents.ScraperDomAgent import ScraperDomAgent
from agents.TestingCodeWriterAgent import TestingCodeWriterAgent
from agents.UserAgent import UserAgent
from tools.topisc import user_topic_type, scrapper_topic_type, instruction_interpretor_type, testing_code_writer_type;
from tools.dataType import Message
from helper import clean_html_with_playwright

async def pipelineTry(task: str)-> str:
  model_client = OpenAIChatCompletionClient(
      model="gpt-4o-mini",
      api_key=""
  )

  runtime = SingleThreadedAgentRuntime()

  await InstructionInterpretorAgent.register(
    runtime, type=instruction_interpretor_type, factory=lambda: InstructionInterpretorAgent(model_client=model_client, dom_fetcher=clean_html_with_playwright)
  )
  await ScraperDomAgent.register(
    runtime, type=scrapper_topic_type, factory=lambda: ScraperDomAgent(model_client=model_client)
  )
  await TestingCodeWriterAgent.register(
    runtime, type=testing_code_writer_type, factory=lambda: TestingCodeWriterAgent(model_client=model_client)
  )

  await UserAgent.register(runtime, type=user_topic_type, factory=lambda: UserAgent())

  runtime.start()

  await runtime.publish_message(
      Message(content="https://demo.testfire.net \n Scenario: Check if there is on the main page 'About Us' link or button."),
      topic_id=TopicId(instruction_interpretor_type, source="default"),
  )


  await runtime.stop_when_idle()
  await model_client.close()

