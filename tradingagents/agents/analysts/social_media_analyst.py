from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.utils.agent_utils import (
    build_instrument_context,
    get_language_instruction,
)
from tradingagents.agents.utils.social_data_tools import (
    get_social_messages,
    get_social_sentiment,
)


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [get_social_sentiment, get_social_messages]

        system_message = (
            "You are a social media and news sentiment analyst. Use these tools:\n"
            "- get_social_sentiment(ticker, start_date, end_date): a daily-grouped "
            "digest of the latest company-news headlines and summaries from Finnhub. "
            "Use it as the primary source to infer sentiment direction, momentum "
            "shifts, and notable narratives across the date range.\n"
            "- get_social_messages(ticker, limit): recent retail-investor messages "
            "from StockTwits, each tagged Bullish/Bearish/None. Use it for the "
            "retail-tone counterpart to the news flow.\n"
            "Always pass the bare ticker symbol (e.g. 'AAPL'). Never pass free-form "
            "queries. Synthesize sentiment direction, momentum shifts, notable "
            "narratives, and any divergence between the news flow and retail messages. "
            "Append a Markdown summary table at the end of the report."
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""
        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    return social_media_analyst_node
