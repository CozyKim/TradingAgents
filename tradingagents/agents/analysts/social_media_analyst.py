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
            "- get_social_sentiment(ticker, start_date, end_date): news-based "
            "sentiment from Finnhub company-news (US tickers). Korean tickers "
            "(.KS/.KQ) are not covered here — use get_social_messages instead.\n"
            "- get_social_messages(ticker, limit, sort, days): recent retail-"
            "investor posts. US tickers → StockTwits, each tagged Bullish/Bearish/"
            "None. Korean tickers (e.g. '005930.KS', '035720.KQ') → Naver 종목토론방, "
            "each post with view + 추천 counts. For Korean names prefer "
            "sort='views', days=3 to surface the most-viewed posts of the last "
            "3 days (sort='latest' with no days = newest-first).\n"
            "Always pass the bare ticker symbol (e.g. 'AAPL' or '005930.KS' for "
            "Korean stocks). Never pass free-form queries. For US names lean on "
            "the news flow vs. StockTwits divergence; for Korean names rely on "
            "the 종목토론방 retail posts. Synthesize sentiment direction, momentum "
            "shifts, and notable narratives. "
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
